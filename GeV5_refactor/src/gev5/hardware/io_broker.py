# io_broker.py — broker I/O central pour DI UNIPI + SIM
import time, threading

class IOBroker:
    def __init__(self, read_fn_di3, read_fn_di4, sim_get=None, poll_ms=5):
        self._read_di3 = read_fn_di3
        self._read_di4 = read_fn_di4
        self._sim_get  = sim_get
        self._poll_s   = max(1, int(poll_ms))/1000.0
        self._stop     = threading.Event()
        self._lock     = threading.RLock()
        self._snap     = {"di3":0,"di4":0,"t_ms":0.0,"src":"unipi"}
        self._t = threading.Thread(target=self._run, name="IOBroker", daemon=True)

    def start(self): self._t.start(); return self
    def stop(self):  self._stop.set(); self._t.join(timeout=1.0)

    def snapshot(self):
        with self._lock: return dict(self._snap)

    def _run(self):
        last = {"di3":0,"di4":0}
        while not self._stop.is_set():
            try:
                src = "unipi"
                if self._sim_get:
                    v1, v2 = self._sim_get()
                    if v1 is not None and v2 is not None:
                        di3, di4 = int(bool(v1)), int(bool(v2))
                        src = "sim"
                    else:
                        di3, di4 = int(self._read_di3()), int(self._read_di4())
                else:
                    di3, di4 = int(self._read_di3()), int(self._read_di4())
                now = time.perf_counter()*1000.0
                if di3!=last["di3"] or di4!=last["di4"]:
                    with self._lock:
                        self._snap.update({"di3":di3,"di4":di4,"t_ms":now,"src":src})
                    last["di3"], last["di4"] = di3, di4
            except Exception:
                pass
            time.sleep(self._poll_s)
