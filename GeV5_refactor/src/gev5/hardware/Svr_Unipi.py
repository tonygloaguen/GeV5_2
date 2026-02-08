#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Svr_Unipi.py — Version simplifiée et stable
- Lecture DI 3/4/5 via REST EVOK (poll permanent)
- AI et WS optionnels (désactivés par défaut)
- Inversion logique possible via INVERT_DI
- Anti-rebond (STABLE_MS) + warmup au démarrage (WARMUP_S)
"""

import json
import time
import threading
import urllib.request
from typing import Optional

# -------------------- Config --------------------
REST_BASE       = "http://127.0.0.1:8080"
REST_DI_BULK    = (f"{REST_BASE}/rest/di", f"{REST_BASE}/rest/input", f"{REST_BASE}/rest/all")
REST_DI_ONE     = (f"{REST_BASE}/rest/di/{{c}}", f"{REST_BASE}/rest/input/{{c}}")

POLL_PERIOD_S   = 0.2   # 200 ms
TRACKED_DI      = (3, 4, 5)
DEBUG_BOOT_PRINTS = 8

# --- Options I/O ---
INVERT_DI = {3: True, 4: True, 5: False}  # inverse les circuits si besoin
WARMUP_S  = 5
STABLE_MS = 100

# -------------------- Utils --------------------
def _coerce01(v) -> int:
    """Normalise valeur EVOK en 0/1 (0 = libre, 1 = obstrué/panne)."""
    try:
        if isinstance(v, bool):
            return 0 if v else 1
        if isinstance(v, (int, float)):
            return 0 if int(v) != 0 else 1
        s = str(v).strip().lower()
        if s in ("1", "true", "on", "high"):
            return 0
        if s in ("0", "false", "off", "low"):
            return 1
    except Exception:
        pass
    return 1


def _rest_get_one_di(c: int, timeout=0.4) -> Optional[int]:
    """Lit /rest/di/{c} (ou /rest/input/{c}) et retourne 0/1 ou None si échec."""
    headers = {"Accept": "application/json"}
    for tpl in REST_DI_ONE:
        url = tpl.format(c=c)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
                return _coerce01(data.get("value", 0))
        except Exception:
            continue
    return None


def _rest_get_all_di(timeout=0.6):
    """Essaie /rest/di, /rest/input, /rest/all. Fallback par circuit si vide."""
    headers = {"Accept": "application/json"}
    for url in REST_DI_BULK:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                raw = r.read().decode("utf-8", errors="ignore")
                data = json.loads(raw)
                frames = data if isinstance(data, list) else [data]
                mp = {}
                for it in frames:
                    if not isinstance(it, dict):
                        continue
                    dev = str(it.get("dev", "")).lower()
                    if dev not in ("input", "di"):
                        continue
                    try:
                        c = int(str(it.get("circuit", "")).strip())
                    except Exception:
                        continue
                    mp[c] = _coerce01(it.get("value", 0))
                if mp:
                    return mp
        except Exception:
            continue
    # Fallback : un par un
    mp = {}
    for c in TRACKED_DI:
        v = _rest_get_one_di(c)
        if v is not None:
            mp[c] = v
    return mp


# -------------------- Classe principale --------------------
class Svr_Unipi_rec(threading.Thread):
    """Thread REST (DI + AI placeholder)"""
    Inp_3 = [0, 0]
    Inp_4 = [0, 0]
    Inp_5 = [0, 0]
    Ai_1  = [0.0, 0.0]
    Ai_2  = [0.0, 0.0]

    _instance_lock = threading.Lock()
    _instance = None

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__(name="Svr_Unipi_rec", daemon=True)
        self._initialized = True
        self._stop = threading.Event()

        # États
        self._boot_ts = time.time()
        self._di_last = {c: None for c in TRACKED_DI}
        self._di_last_change = {c: 0.0 for c in TRACKED_DI}
        self._di_stable = {c: None for c in TRACKED_DI}

    # --------- Thread principal (REST permanent) ---------
    def run(self):
        print("[Svr_Unipi] Thread REST démarré (poll permanent).")
        shown = 0
        while not self._stop.is_set():
            mp = _rest_get_all_di(timeout=0.5)
            if shown < DEBUG_BOOT_PRINTS:
                shown += 1

            now = time.time()
            for c in TRACKED_DI:
                v = mp.get(c)
                if v is None:
                    continue
                if INVERT_DI.get(c, False):
                    v = 1 - v

                # init
                if self._di_last[c] is None:
                    self._di_last[c] = v
                    self._di_last_change[c] = now
                    self._di_stable[c] = v
                    if c == 3: Svr_Unipi_rec.Inp_3[1] = v
                    elif c == 4: Svr_Unipi_rec.Inp_4[1] = v
                    elif c == 5: Svr_Unipi_rec.Inp_5[1] = v
                    continue

                # changement brut
                if self._di_last[c] != v:
                    self._di_last[c] = v
                    self._di_last_change[c] = now

                stable = (now - self._di_last_change[c]) * 1000.0 >= STABLE_MS
                warmed = (now - self._boot_ts) >= WARMUP_S

                if stable and warmed and self._di_stable[c] != v:
                    self._di_stable[c] = v
                    if c == 3: Svr_Unipi_rec.Inp_3[1] = v
                    elif c == 4: Svr_Unipi_rec.Inp_4[1] = v
                    elif c == 5: Svr_Unipi_rec.Inp_5[1] = v

            time.sleep(POLL_PERIOD_S)
        print("[Svr_Unipi] Thread arrêté.")

    def stop(self, wait: bool = True):
        self._stop.set()
        if wait and self.is_alive():
            self.join(timeout=2.0)
        print("[Svr_Unipi] Arrêt demandé.")


# --------- API module-level --------- #
_srv_thread: Optional[Svr_Unipi_rec] = None
_srv_lock = threading.Lock()

def demarrage_Srv_Unipi():
    """Démarre le listener REST si pas déjà lancé."""
    global _srv_thread
    with _srv_lock:
        if _srv_thread is None or not _srv_thread.is_alive():
            _srv_thread = Svr_Unipi_rec()
            _srv_thread.start()
            time.sleep(0.8)
        try:
            mp = getattr(Svr_Unipi_rec, "_instance")._di_stable
        except Exception as e:
            print(f"[DEBUG POLARITE] erreur lecture : {e}")
    return _srv_thread

def arret_Srv_Unipi():
    """Arrête proprement le listener REST si lancé."""
    global _srv_thread
    with _srv_lock:
        if _srv_thread is not None:
            _srv_thread.stop(wait=True)
            _srv_thread = None


# --------- TEST DIRECT --------- #
# if __name__ == "__main__":
#     demarrage_Srv_Unipi()
#     try:
#         while True:
#             print(
#                 f"DI3={Svr_Unipi_rec.Inp_3[1]}  DI4={Svr_Unipi_rec.Inp_4[1]}  DI5={Svr_Unipi_rec.Inp_5[1]}  "
#                 f"|  AI1={Svr_Unipi_rec.Ai_1[1]:.4f}  AI2={Svr_Unipi_rec.Ai_2[1]:.4f}"
#             )
#             time.sleep(0.5)
#     except KeyboardInterrupt:
#         arret_Srv_Unipi()
#         print("\\n🛑 Arrêt du listener.")
