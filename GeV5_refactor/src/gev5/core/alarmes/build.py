from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .alarmes import AlarmeConfig, AlarmeThread


def build_all_alarmes(
    seuils_haut: Dict[int, float],
    seuils_bas: Dict[int, float],
    get_vals: Dict[int, Callable[[], float]],
    enabled_flags: Dict[int, Callable[[], bool]] | None = None,
    period_s: float = 0.1,
    hysteresis: float = 0.0,
    tempo_s: float = 0.0,
    multiple: float = 1.0,
    mode_sans_cellules: int = 0,
    get_passage_flags: Dict[int, Callable[[], bool]] | None = None,
) -> List[AlarmeThread]:
    """Construit 1 thread d'alarme par voie.

    - seuils_haut      : {1: val, 2: val, ...}
    - seuils_bas       : {1: val, 2: val, ...}
    - get_vals         : {1: callable, 2: callable, ...} (lecture comptage)
    - enabled_flags    : optionnel {1: callable_bool, ...}
    - multiple         : coefficient du seuil suiveur (fond * multiple)
    - mode_sans_cellules : 1 = portique toujours en mesure
    - get_passage_flags  : {1: callable_bool, ...} → True si passage actif
    """
    threads: List[AlarmeThread] = []

    enabled_flags = enabled_flags or {}
    get_passage_flags = get_passage_flags or {}

    for channel_id in range(1, 13):
        cfg = AlarmeConfig(
            channel_id=channel_id,
            seuil_haut=seuils_haut[channel_id],
            seuil_bas=seuils_bas.get(channel_id, 0.0),
            hysteresis=hysteresis,
            tempo_s=tempo_s,
            multiple=multiple,
            mode_sans_cellules=mode_sans_cellules,
        )
        t = AlarmeThread(
            cfg,
            get_val=get_vals[channel_id],
            enabled_flag=enabled_flags.get(channel_id),
            get_passage=get_passage_flags.get(channel_id),
            period_s=period_s,
        )
        threads.append(t)

    return threads
