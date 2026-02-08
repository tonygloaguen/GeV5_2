# run_sim.py
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    ROOT = Path(__file__).resolve().parent
    SRC = ROOT / "src"
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    from src.gev5.boot.loader import load_config
    from src.gev5.boot.starter import Gev5System
    from src.gev5.core.simulation.simulateur import Application
    from src.gev5.hardware import etat_cellule_1, etat_cellule_2

    print("[run_sim] src ajouté au sys.path:", SRC)

    cfg = load_config()
    cfg.sim = 1  # IMPORTANT : force simulation
    etat_cellule_1.InputWatcher.sim_override = 1
    etat_cellule_2.InputWatcher.sim_override = 1

    system = Gev5System(cfg)
    system.start_all()

    print("[run_sim] moteur démarré, lancement UI simulateur...")

    app = Application()

    # mini check runtime: on doit pouvoir écrire dans les watchers cellules
    try:
        from src.gev5.hardware.etat_cellule_1 import InputWatcher as IW1
        from src.gev5.hardware.etat_cellule_2 import InputWatcher as IW2
        print("[run_sim] cellules init:", IW1.cellules.get(1), IW2.cellules.get(2))
    except Exception as e:
        print("[run_sim] WARN cellules watchers non accessibles:", e)

    app.mainloop()


if __name__ == "__main__":
    main()
