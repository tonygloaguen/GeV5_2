
from __future__ import annotations

from typing import Callable, Dict, List

from .courbes import CourbeConfig, CourbeThread


def build_all_courbes(
    get_vals: Dict[int, Callable[[], float]],
    max_points: int = 3600,
    period_s: float = 1.0,
) -> List[CourbeThread]:
    threads: List[CourbeThread] = []

    for channel_id in range(1, 13):
        cfg = CourbeConfig(
            channel_id=channel_id,
            max_points=max_points,
            period_s=period_s,
        )
        t = CourbeThread(cfg, get_val=get_vals[channel_id])
        threads.append(t)

    return threads
