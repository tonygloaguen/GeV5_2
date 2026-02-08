from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ComptageConfig:
    """Configuration du comptage pour une voie."""
    channel_id: int
    raw_key: int
    sampling: float
    pin: int
    sim: int


class ComptageThread(threading.Thread):
    """
    Thread générique de comptage pour une voie.

    - calcule une fréquence filtrée (équivalent Frequence_X_Thread V1)
    - stocke le résultat dans compteur[channel_id]
    - gère les hooks :
        * is_pdf_running() → fige le comptage
        * is_defaut_active() → compteur=0 si défaut
    """

    # États partagés entre toutes les voies
    compteur: Dict[int, float] = {}
    compteur_brut: Dict[int, float] = {}        # brut non filtré (optionnel)
    cpt_impulsions: Dict[int, int] = {}  # impulsions accumulées dans sampling

    def __init__(self, cfg: ComptageConfig, d_on_flag: int = 1) -> None:
        super().__init__(name=f"Comptage_{cfg.channel_id}")
        self.cfg = cfg
        self.channel_id = cfg.channel_id
        self.raw_key = cfg.raw_key
        self.sampling = cfg.sampling
        self.pin = cfg.pin
        self.sim = cfg.sim
        self.d_on_flag = d_on_flag

        # init des dicts
        self.compteur.setdefault(self.channel_id, 0.0)
        self.compteur_brut.setdefault(self.raw_key, 0.0)
        self.cpt_impulsions.setdefault(self.channel_id, 0)

    # ------------------------------------------------------------------ #
    # Hooks intégrés
    # ------------------------------------------------------------------ #
    def is_pdf_running(self) -> bool:
        """
        Retourne True si un PDF d'alarme est en cours sur cette voie.
        Equivalent de la logique pdf_gen dans Alarme1 V1.
        """
        try:
            from ..alarmes.alarmes import AlarmeThread  # import local pour éviter circulaires
            return bool(AlarmeThread.pdf_gen.get(self.channel_id, 0))
        except Exception:
            return False

    def is_defaut_active(self) -> bool:
        """
        Retourne True si un défaut est actif sur cette voie.
        Equivalent de eta_defaut != 0 dans les Defaut_X V1.
        """
        try:
            from ..defauts.defauts import DefautThread
            state = DefautThread.defaut_resultat.get(self.channel_id, 0)
            return state != 0
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Lecture physique / simulation
    # ------------------------------------------------------------------ #
    def read_impulsion(self) -> int:
        """Lecture impulsion GPIO ou valeur simulée."""
        if self.sim == 1:
            return 1
        # GPIO réel (placeholder)
        return 1 if self.pin != 0 else 0

    # ------------------------------------------------------------------ #
    # Boucle principale
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        t0 = time.time()

        while True:
            time.sleep(0.01)  # haute résolution impulsions

            # voie désactivée ?
            if self.d_on_flag == 0:
                self.compteur[self.channel_id] = 0
                continue

            # comptage impulsions
            if self.read_impulsion():
                self.cpt_impulsions[self.channel_id] += 1

            # période atteinte ?
            if time.time() - t0 >= self.sampling:
                impulses = self.cpt_impulsions[self.channel_id]
                t0 = time.time()

                # brut → historique V1 : raw_key = 10,20,30...
                self.compteur_brut[self.raw_key] = impulses

                # PDF en cours → fige la valeur (ne touche pas compteur)
                if self.is_pdf_running():
                    self.cpt_impulsions[self.channel_id] = 0
                    continue

                # défaut actif → compteur = 0
                if self.is_defaut_active():
                    self.compteur[self.channel_id] = 0
                    self.cpt_impulsions[self.channel_id] = 0
                    continue

                # calcul fréquence (simple)
                freq = impulses / self.sampling

                self.compteur[self.channel_id] = freq
                self.cpt_impulsions[self.channel_id] = 0
