from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict


@dataclass
class DefautConfig:
    """Config d'un dÃ©faut voie.

    - channel_id : nÂ° de voie (1..12)
    - raw_key    : clÃ© "brute" utilisÃ©e dans les dicts (10, 20, ..., 120)
    - limite_inferieure / limite_superieure : bornes dÃ©faut bas / haut
    - period_s   : pÃ©riode de test
    """
    channel_id: int
    raw_key: int
    limite_inferieure: float
    limite_superieure: float
    period_s: float = 0.5


class DefautThread(threading.Thread):
    """
    Thread gÃ©nÃ©rique de dÃ©faut pour une voie.

    Reprend la logique Defaut_1 / Defaut_2 :
    - 0 = OK
    - 1 = dÃ©faut bas (perte comptage)
    - 2 = dÃ©faut haut (parasite)
    - email_send_defaut : flag â†’ 1 sur front montant de dÃ©faut
    """

    # Ã‰tats partagÃ©s (API V2)
    defaut_resultat: Dict[int, int] = {}     # 0 / 1 / 2
    defaut_valeur: Dict[int, float] = {}     # valeur brute associÃ©e
    email_send_defaut: Dict[int, int] = {}

    def __init__(
        self,
        cfg: DefautConfig,
        get_val: Callable[[], float],
        get_d_on: Callable[[], int],
    ) -> None:
        super().__init__(name=f"Defaut_{cfg.channel_id}")
        self.cfg = cfg
        self._get_val = get_val
        self._get_d_on = get_d_on
        self.valeur: float | None = None

        # init des dicts partagÃ©s
        self.defaut_resultat.setdefault(self.cfg.channel_id, 0)
        self.defaut_valeur.setdefault(self.cfg.channel_id, 0.0)
        self.email_send_defaut.setdefault(self.cfg.channel_id, 0)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Boucle principale
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def run(self) -> None:
        while True:
            # Si la voie est coupÃ©e â†’ on reset et on sort
            if self._get_d_on() == 0:
                self.defaut_resultat[self.cfg.channel_id] = 0
                self.defaut_valeur[self.cfg.raw_key] = 0
                self.email_send_defaut[self.cfg.channel_id] = 0
                time.sleep(self.cfg.period_s)
                continue

            # lecture valeur brute (comptage brut)
            val = float(self._get_val())
            self.valeur = val

            # calcul Ã©tat dÃ©faut
            if val < self.cfg.limite_inferieure:
                new_state = 1  # dÃ©faut bas
            elif val > self.cfg.limite_superieure:
                new_state = 2  # dÃ©faut haut
            else:
                new_state = 0  # OK

            old_state = self.defaut_resultat[self.cfg.channel_id]

            if new_state != 0:
                # on enregistre le dÃ©faut pour la voie + valeur brute
                self.defaut_resultat[self.cfg.channel_id] = new_state
                self.defaut_valeur[self.cfg.raw_key] = val

                # front montant â†’ lever le flag mail
                if old_state == 0 and self.email_send_defaut[self.cfg.channel_id] == 0:
                    self.email_send_defaut[self.cfg.channel_id] = 1

            else:
                # retour Ã  la normale pour CETTE voie
                self.defaut_resultat[self.cfg.channel_id] = 0
                self.defaut_valeur[self.cfg.raw_key] = 0
                self.email_send_defaut[self.cfg.channel_id] = 0

            time.sleep(self.cfg.period_s)
