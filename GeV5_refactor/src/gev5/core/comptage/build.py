
from __future__ import annotations

from typing import Dict, List

from .comptage import ComptageConfig, ComptageThread


def build_all_comptages(
    sampling: float,
    pins: Dict[int, int],
    d_on_flags: Dict[int, int],
    sim: int,
) -> List[ComptageThread]:
    """Construit les 12 threads de comptage (1 par voie).

    - sampling   : fréquence d'échantillonnage logique
    - pins       : {1: pin_D1, 2: pin_D2, ...}
    - d_on_flags : {1: D1_ON, 2: D2_ON, ...}
    - sim        : 0/1
    """
    threads: List[ComptageThread] = []

    for channel_id in range(1, 13):
        raw_key = channel_id * 10
        cfg = ComptageConfig(
            channel_id=channel_id,
            raw_key=raw_key,
            sampling=sampling,
            pin=pins[channel_id],
            sim=sim,
        )
        t = ComptageThread(cfg, d_on_flag=d_on_flags.get(channel_id, 1))
        threads.append(t)

    return threads
