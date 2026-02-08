#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import websocket, json, time, os, urllib.request

WS_URL = "ws://localhost:8080/ws"

def norm(c):
    try: return str(int(c))
    except: return str(c)

def recv_for(ws, dur=0.4):
    """Récupère tout ce qui arrive pendant dur secondes et renvoie la dernière valeur DI3 vue, sinon None."""
    end = time.time() + dur
    last = None
    while time.time() < end:
        try:
            msg = ws.recv()
        except Exception:
            break
        try:
            data = json.loads(msg)
        except Exception:
            continue

        frames = []
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                frames = [it for it in data["data"] if isinstance(it, dict)]
            else:
                frames = [data]
        elif isinstance(data, list):
            frames = [it for it in data if isinstance(it, dict)]

        for it in frames:
            dev = str(it.get("dev", "")).lower()
            cir = norm(it.get("circuit", ""))
            if dev in ("input", "di") and cir == "3":
                try:
                    last = 1 if int(it.get("value", 0)) else 0
                except Exception:
                    pass
    return last

def rest_get_di(circuit):
    """Fallback REST si EVOK WS ne renvoie rien."""
    try:
        with urllib.request.urlopen(f"http://localhost:8080/rest/di/{circuit}", timeout=0.5) as r:
            data = json.loads(r.read().decode())
            return int(data.get("value", 0))
    except Exception:
        return None

if __name__ == "__main__":
    ws = websocket.create_connection(WS_URL, timeout=3, ping_interval=20, ping_timeout=5)
    print("WS connecté")

    # Abonnements + snapshot au démarrage
    ws.send(json.dumps({"cmd":"subscribe","dev":"all"}))
    ws.send(json.dumps({"cmd":"subscribe","dev":"input"}))
    ws.send(json.dumps({"cmd":"subscribe","dev":"di"}))
    ws.send(json.dumps({"cmd":"all"}))
    recv_for(ws, 0.8)  # on vide la file et récupère un 1er état si dispo

    try:
        while True:
            # Interroge explicitement DI3 sous 'input' puis 'di'
            ws.send(json.dumps({"cmd":"get","dev":"input","circuit":3}))
            ws.send(json.dumps({"cmd":"get","dev":"di",   "circuit":3}))
            val = recv_for(ws, 0.4)

            # 🛑 Fallback REST si rien reçu en WS
            if val is None:
                val = rest_get_di(3)

            os.system("clear")
            print("📡 Test EVOK — Lecture DI3 (WebSocket + REST fallback)")
            print(f"DI3 = {val}")
            print("\nCTRL+C pour quitter")
            time.sleep(0.6)
    except KeyboardInterrupt:
        pass
    finally:
        try: ws.close()
        except Exception: pass
