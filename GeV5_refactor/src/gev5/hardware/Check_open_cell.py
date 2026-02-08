import time
import threading

from . import etat_cellule_1, etat_cellule_2


# Etat central (lu par api_flsk.py)
class CellStatus:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = False
        self.started_at = None
        self.elapsed = 0
        self.last_triggered_at = None


state = CellStatus()

# Seuil en dur et hysteresis (secondes)
THRESHOLD_CELL_OPEN_SEC = 900   # 15 min
CLEAR_HYSTERESIS_SEC = 10       # fermeture continue requise pour effacer


class etat_cellule_check(threading.Thread):
    # Compat avec anciens modules
    t0 = {1: 0}
    defaut_cell = {1: 0}

    def __init__(self, Mode_sans_cellules: int) -> None:
        super().__init__(name="Check_Open_Cell_Thread", daemon=True)
        self.mss = Mode_sans_cellules
        self.ticks = 0

    def run(self) -> None:
        while True:
            if self.mss == 1:
                time.sleep(1)
                continue

            # Lire les deux cellules (1 et 2)
            try:
                c1 = int(etat_cellule_1.InputWatcher.cellules.get(1, 0))
            except Exception:
                c1 = 1
            try:
                c2 = int(etat_cellule_2.InputWatcher.cellules.get(2, 0))
            except Exception:
                c2 = 1

            # Securite positive: 0 = coupe/obstrue/panne, 1 = libre
            occupied = (c1 == 0 or c2 == 0)

            if occupied:
                self.ticks += 1
                etat_cellule_check.t0[1] = self.ticks
                if self.ticks >= THRESHOLD_CELL_OPEN_SEC:
                    etat_cellule_check.defaut_cell[1] = 1
                    with state.lock:
                        if not state.active:
                            state.active = True
                            state.started_at = time.time() - self.ticks
                            state.last_triggered_at = time.time()
            else:
                # fermeture continue -> clear si on n'a pas depasse le seuil - hysteresis
                if 0 < self.ticks <= max(0, THRESHOLD_CELL_OPEN_SEC - CLEAR_HYSTERESIS_SEC):
                    with state.lock:
                        state.active = False
                        state.started_at = None
                        state.elapsed = 0
                self.ticks = 0
                etat_cellule_check.t0[1] = 0
                etat_cellule_check.defaut_cell[1] = 0

            time.sleep(1)

    # Compat: force l'alarme via API si besoin
    def notify_open_cell(self) -> None:
        with state.lock:
            state.active = True
            if state.started_at is None:
                state.started_at = time.time()
