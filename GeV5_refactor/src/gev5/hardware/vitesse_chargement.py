from __future__ import annotations

import threading
import time
from typing import Dict

from .passage import PassageService
from ..core.alarmes.alarmes import AlarmeThread


class ListWatcher(threading.Thread):
    """
    V2 — Surveille les cellules S1/S2 via PassageService et estime la vitesse
    de passage + le sens de circulation.

    - distance_cellules : distance (en mètres) entre S1 et S2
    - mode_sans_cellules (mss) :
        1 -> pas de cellules, on ne calcule pas de vitesse
        0 -> mode normal, on utilise S1/S2

    Expose :
      - ListWatcher.vitesse[1]  : vitesse en km/h ou message ("Vitesse N.A.", "Pas de vitesse mesurée", "Defaut vitesse")
      - ListWatcher.vitesse[10] : sens détecté ("1 -> 2", "2 -> 1", "Pas de détection de sens")
    """

    vitesse: Dict[int, str | float] = {1: "Vitesse N.A.", 10: "Pas de détection de sens"}

    def __init__(self, distance_cellules: float, mode_sans_cellules: int, passage_service: PassageService) -> None:
        super().__init__(name="ListWatcher_Vitesse")
        self.distance_cellules = float(distance_cellules)
        self.mss = int(mode_sans_cellules)
        self.passage_service = passage_service

        self.time_cellule1: float | None = None
        self.time_cellule2: float | None = None
        self.last_cellule1: int = 0
        self.last_cellule2: int = 0
        self.derniere_mesure: float = 0.0

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def calculer_vitesse(self) -> str | float:
        t1 = self.time_cellule1
        t2 = self.time_cellule2
        if t1 is None or t2 is None:
            return "Vitesse N.A."

        diff_time = abs(t2 - t1)
        if diff_time == 0:
            return "Vitesse N.A."

        vitesse_m_s = self.distance_cellules / diff_time
        vitesse_kmh = vitesse_m_s * 3.6

        # Seuil historique : > 10 km/h → considéré comme défaut
        if vitesse_kmh > 10:
            return "Defaut vitesse"

        return round(vitesse_kmh, 1)

    def get_alarm_list(self) -> list[int]:
        """
        V2 : on utilise l'état d'alarme global AlarmeThread.alarme_resultat
        (0 = OK, 1 = N1, 2 = N2).
        """
        return list(AlarmeThread.alarme_resultat.values())

    # ------------------------------------------------------------------ #
    # Boucle principale
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        while True:
            # Mode sans cellules -> pas de calcul de vitesse, on sort
            if self.mss == 1:
                self.vitesse[1] = "Vitesse N.A."
                self.vitesse[10] = "Pas de détection de sens"
                break

            # Lecture des cellules via PassageService
            c1, c2 = self.passage_service.get_cells()
            now = time.perf_counter()

            # Détection front montant cellule 1
            if c1 == 1 and self.last_cellule1 == 0 and self.time_cellule1 is None:
                self.time_cellule1 = now

            # Détection front montant cellule 2
            if c2 == 1 and self.last_cellule2 == 0 and self.time_cellule2 is None:
                self.time_cellule2 = now

            # Mise à jour états précédents
            self.last_cellule1 = c1
            self.last_cellule2 = c2

            # Cas de mesure de passage (2 fronts captés)
            if self.time_cellule1 is not None and self.time_cellule2 is not None:
                delta = abs(self.time_cellule1 - self.time_cellule2)

                # Trop court = probablement rebond
                if delta < 0.03:
                    self.time_cellule1 = None
                    self.time_cellule2 = None
                    time.sleep(0.01)
                    continue

                # Si une alarme N2 est active, on ignore la mesure
                if any(val == 2 for val in self.get_alarm_list()):
                    self.time_cellule1 = None
                    self.time_cellule2 = None
                    time.sleep(0.01)
                    continue

                # Détection du sens
                if self.time_cellule1 < self.time_cellule2:
                    sens = "1 -> 2"
                else:
                    sens = "2 -> 1"

                self.vitesse[10] = sens
                self.vitesse[1] = self.calculer_vitesse()
                self.derniere_mesure = now

                # Reset pour prochaine mesure
                self.time_cellule1 = None
                self.time_cellule2 = None

            # Cellule 1 seule active trop longtemps
            elif self.time_cellule1 is not None and self.time_cellule2 is None:
                if now - self.time_cellule1 > 5 and self.time_cellule1 > self.derniere_mesure:
                    self.vitesse[1] = "Pas de vitesse mesurée"
                    self.vitesse[10] = "Pas de détection de sens"
                    self.time_cellule1 = None

            # Cellule 2 seule active trop longtemps
            elif self.time_cellule2 is not None and self.time_cellule1 is None:
                if now - self.time_cellule2 > 5 and self.time_cellule2 > self.derniere_mesure:
                    self.vitesse[1] = "Pas de vitesse mesurée"
                    self.vitesse[10] = "Pas de détection de sens"
                    self.time_cellule2 = None

            time.sleep(0.01)
