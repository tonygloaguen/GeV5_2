#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
import time
from typing import Dict

from gev5.boot.loader import load_config

_cfg = load_config()


class InputWatcher(threading.Thread):
    """
    Watcher cellule 1 (S1).

    - En mode NORMAL (sim=0) : lit Svr_Unipi_rec.Inp_3[1]
    - En mode SIMULATION (sim=1) : lit simulateur.Application.variable1[0]
    """

    cellules: Dict[int, int] = {1: 0}
    running: bool = True
    sim_override: int | None = None

    def __init__(self) -> None:
        super().__init__(daemon=True)

    def run(self) -> None:
        while self.running:
            sim = int(self.sim_override) if self.sim_override is not None else int(_cfg.sim)
            if sim:
                # --- MODE SIMULATION ---
                try:
                    from gev5.core.simulation import simulateur
                    v = int(simulateur.Application.variable1.get(0, 0))
                except Exception:
                    v = 0
            else:
                # --- MODE NORMAL → lire Svr_Unipi_rec.Inp_3[1] ---
                try:
                    from gev5.hardware.Svr_Unipi import Svr_Unipi_rec
                    v = int(Svr_Unipi_rec.Inp_3[1])
                except Exception:
                    v = 0

            InputWatcher.cellules[1] = 1 if v else 0
            time.sleep(0.02)  # 50 Hz


# On démarre le watcher au import du module (comme avant)
watcher = InputWatcher()
watcher.start()
