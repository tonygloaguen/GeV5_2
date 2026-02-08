from __future__ import annotations

from typing import Callable, Dict, List

from .defauts import DefautConfig, DefautThread


def build_all_defauts(
    limites_inf: Dict[int, float],
    limites_sup: Dict[int, float],
    get_raw_vals: Dict[int, Callable[[], float]],
    get_d_on_flags: Dict[int, Callable[[], int]],
    period_s: float = 0.5,
) -> List[DefautThread]:
    """
    Construit 1 DefautThread par voie (1..12).

    - limites_inf  : {1: val, 2: val, ...}
    - limites_sup  : {1: val, 2: val, ...}
    - get_raw_vals : {1: callable → brut de la voie (compteur[10], 20, ..., 120)}
    - get_d_on_flags : {1: callable → D1_ON, ...}
    """
    threads: List[DefautThread] = []

    for channel_id in range(1, 13):
        raw_key = channel_id * 10

        cfg = DefautConfig(
            channel_id=channel_id,
            raw_key=raw_key,
            limite_inferieure=limites_inf[channel_id],
            limite_superieure=limites_sup[channel_id],
            period_s=period_s,
        )

        t = DefautThread(
            cfg,
            get_val=get_raw_vals[channel_id],
            get_d_on=get_d_on_flags[channel_id],
        )
        threads.append(t)

    return threads
