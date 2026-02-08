#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag EVOK: WS + REST (Nginx et direct)
- Teste WS sur 80 (/ws, /ws/), sur 8080 (/ws, /ws/)
- Variantes d'entêtes (avec/ sans Origin)
- Vérifie REST: /rest/all via 80 et 8080
Affiche un résumé clair + suggestion de config.
"""

import json, time, socket
from datetime import datetime

# -- Dépendances : websocket-client, requests
#   pip3 install websocket-client requests
import requests
try:
    import websocket
except Exception:
    print("Le module 'websocket-client' est manquant. Installe-le :  pip3 install websocket-client")
    raise

TIMEOUT = 4

WS_TARGETS = [
    ("nginx_ws",              "ws://127.0.0.1/ws"),
    ("nginx_ws_slash",        "ws://127.0.0.1/ws/"),
    ("direct_8080_ws",        "ws://127.0.0.1:8080/ws"),
    ("direct_8080_ws_slash",  "ws://127.0.0.1:8080/ws/"),
]

WS_HEADERS = [
    ("no_origin",    []),
    ("with_origin",  ["Origin: http://127.0.0.1"]),
]

REST_TARGETS = [
    ("nginx_rest_all",   "http://127.0.0.1/rest/all"),
    ("direct_rest_all",  "http://127.0.0.1:8080/rest/all"),
    ("nginx_rest_relay", "http://127.0.0.1/rest/relay"),
    ("direct_rest_relay","http://127.0.0.1:8080/rest/relay"),
    ("nginx_input_1",    "http://127.0.0.1/rest/input/1"),
    ("direct_input_1",   "http://127.0.0.1:8080/rest/input/1"),
]

results = {"ws": [], "rest": []}

def ok(x):  return "OK" if x else "FAIL"
def trim(s, n=140):
    try:
        t = s if isinstance(s, str) else repr(s)
        return (t[:n] + "…") if len(t) > n else t
    except Exception:
        return "<repr_error>"

def test_ws(name, url, headers):
    label = f"{name} [{','.join(h.split(':')[0] for h in headers) or 'nohdr'}]"
    t0 = time.time()
    try:
        ws = websocket.create_connection(url, timeout=TIMEOUT, header=headers)
        # petit ping si supporté
        try:
            ws.ping()
        except Exception:
            pass
        ws.close()
        dt = time.time() - t0
        results["ws"].append({"target": label, "url": url, "headers": headers, "status": True, "latency_s": round(dt,3)})
        print(f"[WS] {label:<30} -> OK   ({dt:.2f}s)")
    except Exception as e:
        dt = time.time() - t0
        results["ws"].append({"target": label, "url": url, "headers": headers, "status": False, "error": trim(str(e)), "latency_s": round(dt,3)})
        print(f"[WS] {label:<30} -> FAIL ({dt:.2f}s)  {e}")

def test_rest(name, url):
    t0 = time.time()
    try:
        r = requests.get(url, timeout=TIMEOUT)
        ct = r.headers.get("Content-Type","")
        ok_json = r.status_code == 200 and ("json" in ct or r.text.strip().startswith("[") or r.text.strip().startswith("{"))
        info = ""
        if r.status_code == 200:
            info = "200"
        else:
            info = f"{r.status_code}"
        # léger parse si JSON probable
        sample = ""
        if ok_json:
            try:
                data = r.json()
                if isinstance(data, list) and data:
                    sample = trim(json.dumps(data[0], ensure_ascii=False))
                elif isinstance(data, dict):
                    sample = trim(json.dumps({k:data[k] for k in list(data)[:3]}, ensure_ascii=False))
            except Exception:
                sample = trim(r.text[:120])
        else:
            sample = trim(r.text[:120])
        dt = time.time() - t0
        results["rest"].append({"target": name, "url": url, "status": ok_json, "http": r.status_code, "latency_s": round(dt,3), "sample": sample})
        print(f"[REST] {name:<20} -> {ok(ok_json):<4} HTTP {info} ({dt:.2f}s)  {sample}")
    except Exception as e:
        dt = time.time() - t0
        results["rest"].append({"target": name, "url": url, "status": False, "http": None, "latency_s": round(dt,3), "error": trim(str(e))})
        print(f"[REST] {name:<20} -> FAIL ({dt:.2f}s)  {e}")

def port_open(host, port, timeout=1.5):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

def main():
    print("="*70)
    print("EVOK Diagnostic —", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70)

    # Info ports
    print("\n[PORTS] Présence des services :")
    for p in (80, 8080, 5002, 8888):
        print(f" - 127.0.0.1:{p} -> {'OPEN' if port_open('127.0.0.1', p) else 'closed'}")

    # REST d'abord (simple)
    print("\n--- TEST REST ---")
    for name, url in REST_TARGETS:
        test_rest(name, url)

    # WebSocket ensuite
    print("\n--- TEST WEBSOCKET ---")
    for ws_name, url in WS_TARGETS:
        for hdr_name, hdrs in WS_HEADERS:
            test_ws(f"{ws_name}/{hdr_name}", url, hdrs)

    # Résumé
    print("\n=== RÉSUMÉ ===")
    ok_rest = [r for r in results["rest"] if r["status"]]
    ok_ws   = [r for r in results["ws"]   if r["status"]]

    print(f"REST OK   : {len(ok_rest)}/{len(results['rest'])}")
    for r in ok_rest:
        print(f"  ✔ {r['target']}: {r['url']}  ({r.get('latency_s','?')}s)")

    print(f"WS OK     : {len(ok_ws)}/{len(results['ws'])}")
    for r in ok_ws:
        print(f"  ✔ {r['target']}: {r['url']}  ({r.get('latency_s','?')}s)")

    # Recommandations
    print("\n=== SUGGESTION DE CONFIG ===")
    if ok_ws:
        # priorité au proxy nginx (80) avec Origin
        choice = None
        for pref in ["nginx_ws/with_origin", "nginx_ws_slash/with_origin", "nginx_ws/no_origin"]:
            for r in ok_ws:
                if r["target"] == pref:
                    choice = r; break
            if choice: break
        if not choice:
            choice = ok_ws[0]
        print(f"- WebSocket : utilise {choice['url']}  (headers={choice['headers'] or 'none'})")
    else:
        print("- WebSocket : AUCUN endpoint n'a répondu. Vérifie EVOK (route /ws) ou Nginx (/ws).")

    good_rest = [r for r in ok_rest if r["target"].endswith("rest_all")]
    if good_rest:
        print(f"- REST : {good_rest[0]['url']} (préférer /rest/all puis filtrer dev=='relay').")
    else:
        print("- REST : AUCUN /rest/all OK. Vérifie EVOK et Nginx /rest/ → 8080.")

    print("\nFin du diag.")

if __name__ == "__main__":
    main()
