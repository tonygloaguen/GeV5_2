#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
import time
from logging import Logger

from gev5.boot.loader import load_config
from gev5.boot.starter import Gev5System
from gev5.utils.logging import get_logger

logger: Logger = get_logger("gev5.main")


def run_engine(cfg) -> None:
    """Lancement du moteur GeV5 V2 (tous les threads)."""
    system = Gev5System(cfg)
    system.start_all()


def main() -> None:
    cfg = load_config()

    if int(cfg.sim) == 1:
        logger.info("Mode SIMULATION actif -> lancement du moteur en arrière-plan")

        from gev5.core.simulation import simulateur

        app = simulateur.Application()  # 👉 maintenant Application est un tk.Tk

        def start_engine_later() -> None:
            t = threading.Thread(
                target=run_engine,
                args=(cfg,),
                name="GeV5Engine",
                daemon=True,
            )
            t.start()
            logger.info("Thread moteur GeV5 lancé (daemon)")

        # On démarre le moteur 200 ms après l’affichage de la fenêtre
        app.after(200, start_engine_later)
        app.mainloop()

        logger.info("Simulateur fermé, arrêt du programme.")

    else:
        # 🔹 MODE NORMAL (moteur seul, pas d'interface Tk)
        logger.info("Mode NORMAL : démarrage GeV5 sans simulateur Tkinter")
        run_engine(cfg)


if __name__ == "__main__":
    main()
