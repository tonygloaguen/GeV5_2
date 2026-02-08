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

    - En mode NORMAL : à terme on lira l'entrée physique (UNIPI I3, etc.)
    - En mode SIMULATION : on lit simulateur.Application.variable1[0]
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
                # --- MODE NORMAL → TODO: lire l'entrée réelle UNIPI I3 ---
                v = 0

            InputWatcher.cellules[1] = 1 if v else 0
            time.sleep(0.02)  # 50 Hz, largement suffisant


# On démarre le watcher au import du module (comme avant)
watcher = InputWatcher()
watcher.start()
