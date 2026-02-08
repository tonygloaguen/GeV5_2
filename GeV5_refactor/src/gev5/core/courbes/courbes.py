
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class CourbeConfig:
    channel_id: int
    max_points: int = 3600  # nombre max de points conservés
    period_s: float = 1.0   # période d'échantillonnage


class CourbeThread(threading.Thread):
    """Thread de courbe générique pour 1 voie.

    Il lit périodiquement une valeur (comptage) et la stocke
    dans une liste courbes[channel_id].
    """

    curves: Dict[int, List[float]] = {}

    def __init__(
        self,
        config: CourbeConfig,
        get_val: Callable[[], float],
    ) -> None:
        super().__init__(name=f"Courbe_{config.channel_id}")
        self.cfg = config
        self._get_val = get_val

        self.curves.setdefault(self.cfg.channel_id, [])

    def run(self) -> None:
        while True:
            time.sleep(self.cfg.period_s)
            val = float(self._get_val())
            lst = self.curves[self.cfg.channel_id]
            lst.append(val)
            if len(lst) > self.cfg.max_points:
                del lst[0: len(lst) - self.cfg.max_points]
