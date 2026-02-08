from __future__ import annotations

from typing import Dict, List

from .comptage.comptage import ComptageThread
from .alarmes.alarmes import AlarmeThread
from .defauts.defauts import DefautThread
from .courbes.courbes import CourbeThread


class SystemState:
    """
    Point d’accès UNIQUE à l’état global du système (lecture seule).
    Utilisé par :
      - API FastAPI
      - supervision
      - PDF
      - tests
    """

    # ───────────────────────────
    # Comptage
    # ───────────────────────────
    @staticmethod
    def get_counts() -> Dict[int, float]:
        return dict(ComptageThread.compteur)

    @staticmethod
    def get_raw_counts() -> Dict[int, float]:
        return dict(ComptageThread.compteur_brut)

    # ───────────────────────────
    # Alarmes
    # ───────────────────────────
    @staticmethod
    def get_alarm_states() -> Dict[int, int]:
        return dict(AlarmeThread.alarme_resultat)

    @staticmethod
    def get_alarm_measures() -> Dict[int, float]:
        return dict(AlarmeThread.alarme_mesure)

    @staticmethod
    def get_background() -> Dict[int, float]:
        return dict(AlarmeThread.fond)

    # ───────────────────────────
    # Défauts
    # ───────────────────────────
    @staticmethod
    def get_defauts() -> Dict[int, int]:
        return dict(DefautThread.defaut_resultat)

    # ───────────────────────────
    # Courbes
    # ───────────────────────────
    @staticmethod
    def get_curves() -> Dict[int, List[float]]:
        return dict(CourbeThread.curves)
