# src/gev5/hardware/passage.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


class HardwarePort(Protocol):
    """Interface minimale attendue par PassageService."""
    def read_cellule(self, idx: int) -> int: ...


@dataclass(frozen=True)
class PassageConfig:
    """
    Paramètres du service passage.

    - arm_delay_s : délai d’armement au boot (ignore tout passage pendant X s)
    - min_off_s   : durée minimale "au repos" avant d’accepter un nouveau start
                   (anti-spam si cellules flottent/rebondissent)
    """
    arm_delay_s: float = 2.0
    min_off_s: float = 0.2


class PassageService:
    """
    Service central de gestion de passage basé sur 2 cellules (S1/S2).

    Convention :
      - 0 = faisceau libre (repos)
      - 1 = faisceau coupé (objet détecté)
    """

    def __init__(self, hw: HardwarePort, cfg: PassageConfig | None = None) -> None:
        self.hw = hw
        self.cfg = cfg or PassageConfig()

        now = time.monotonic()
        self._armed_at = now + float(self.cfg.arm_delay_s)

        # états précédents pour détection de fronts
        self._last_s1 = 0
        self._last_s2 = 0

        # état passage "niveau"
        self._active = False

        # anti-spam / anti-rebond
        self._last_stop_t = now
        self._last_edge_t = now

    # ─────────────────────────────────────────────
    # API publique figée
    # ─────────────────────────────────────────────
    def get_cells(self) -> tuple[int, int]:
        """
        Retourne (S1, S2) en int.
        """
        # hardware peut renvoyer None/True/False selon implémentations → on force int 0/1
        s1 = 1 if int(self.hw.read_cellule(1) or 0) else 0
        s2 = 1 if int(self.hw.read_cellule(2) or 0) else 0
        return s1, s2

    def is_passage(self) -> bool:
        """
        True si passage actif (niveau), False sinon.
        ⚠️ Ne déclenche pas d’événement : c’est une vue instantanée.
        """
        # Pas armé → jamais de passage
        if time.monotonic() < self._armed_at:
            return False

        s1, s2 = self.get_cells()
        return (s1 == 1) or (s2 == 1)

    def passage_edges(self) -> tuple[bool, bool]:
        """
        Détection d’événements (fronts) :
          - start_edge = passage commence (front montant)
          - stop_edge  = passage se termine (front descendant)

        Avec :
          - arm_delay au boot
          - anti-spam : un start n’est accepté que si on est resté OFF >= min_off_s
        """
        now = time.monotonic()

        # armement boot : on initialise les derniers états sans générer d’événement
        if now < self._armed_at:
            s1, s2 = self.get_cells()
            self._last_s1, self._last_s2 = s1, s2
            self._active = False
            self._last_stop_t = now
            return False, False

        s1, s2 = self.get_cells()

        # fronts montants individuels
        s1_rise = (s1 == 1 and self._last_s1 == 0)
        s2_rise = (s2 == 1 and self._last_s2 == 0)

        # état niveau courant
        active_now = (s1 == 1) or (s2 == 1)

        start_edge = False
        stop_edge = False

        # START = on devient actif, via un front montant (pas juste un niveau)
        if (not self._active) and active_now and (s1_rise or s2_rise):
            # anti-spam : il faut être resté OFF au moins min_off_s
            if (now - self._last_stop_t) >= float(self.cfg.min_off_s):
                start_edge = True
                self._active = True
                self._last_edge_t = now
            else:
                # on ignore ce start (flottement/rebond), mais on laisse active_now sans activer
                pass

        # STOP = on repasse inactif (niveau)
        if self._active and (not active_now):
            stop_edge = True
            self._active = False
            self._last_stop_t = now
            self._last_edge_t = now

        # mise à jour des états précédents
        self._last_s1, self._last_s2 = s1, s2

        return start_edge, stop_edge

    def are_cells_free_and_stable(self, stable_s: float = 0.2) -> bool:
        """
        True si les cellules sont libres (S1=0 et S2=0) et stables
        depuis au moins stable_s secondes.
        """
        now = time.monotonic()
        s1, s2 = self.get_cells()
        if s1 != self._last_s1 or s2 != self._last_s2:
            self._last_s1, self._last_s2 = s1, s2
            self._last_edge_t = now
        return (s1 == 0 and s2 == 0) and ((now - self._last_edge_t) >= float(stable_s))
