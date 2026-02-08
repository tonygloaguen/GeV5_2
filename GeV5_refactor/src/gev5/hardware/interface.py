from __future__ import annotations

import threading
import time

from ..core.alarmes.alarmes import AlarmeThread
from ..core.comptage.comptage import ComptageThread
from ..core.defauts.defauts import DefautThread
from ..core.courbes.courbes import CourbeThread
from ..core.acquittement.acquittement import AcquittementThread
from . import etat_cellule_1, etat_cellule_2

try:
    from . import vitesse_chargement
except Exception:
    vitesse_chargement = None

try:
    from .prise_photo import PrisePhoto
except Exception:
    PrisePhoto = None


class Interface(threading.Thread):
    """
    Interface de supervision V2 (compat).

    Les anciennes structures V1 (suiv/val_max/recal/val_deb_mes)
    ne sont plus exposÃ©es en V2. Elles sont remplacÃ©es par des valeurs
    par dÃ©faut ou des estimations simples basÃ©es sur fond/mesure.
    """

    liste_comptage = {1: None}
    liste_variance = {1: None}
    liste_alarm = {1: None}
    liste_suiveur = {1: None}
    list_recal = {1: None}
    liste_val_max = {1: None}
    liste_defaut = {1: None}
    list_cell = {1: None}
    liste_photo = {1: None}
    liste_vitesse = {1: None}
    list_acq = {1: None}
    list_mesure = {1: None}
    list_courbe = {1: None}
    list_val_deb_mes = {1: None}

    def __init__(self) -> None:
        super().__init__(daemon=True)

    def run(self) -> None:
        while True:
            self.liste_comptage[1] = [
                float(ComptageThread.compteur.get(i, 0.0)) for i in range(1, 13)
            ]
            self.liste_variance[1] = [0.0 for _ in range(12)]
            self.liste_alarm[1] = [
                int(AlarmeThread.alarme_resultat.get(i, 0)) for i in range(1, 13)
            ]
            self.liste_suiveur[1] = [
                float(AlarmeThread.fond.get(i, 0.0)) for i in range(1, 13)
            ]
            self.liste_val_max[1] = [0.0 for _ in range(12)]
            self.liste_defaut[1] = [
                int(DefautThread.defaut_resultat.get(i, 0)) for i in range(1, 13)
            ]
            self.list_cell[1] = [
                int(etat_cellule_1.InputWatcher.cellules.get(1, 0)),
                int(etat_cellule_2.InputWatcher.cellules.get(2, 0)),
            ]

            if PrisePhoto is not None:
                self.liste_photo[1] = [
                    PrisePhoto.timestamp.get(1),
                    PrisePhoto.filename.get(1),
                    PrisePhoto.cam_dispo.get(1),
                ]
            else:
                self.liste_photo[1] = [None, None, None]

            if vitesse_chargement is not None:
                self.liste_vitesse[1] = [vitesse_chargement.ListWatcher.vitesse]
            else:
                self.liste_vitesse[1] = ["Vitesse N.A."]

            self.list_acq[1] = [AcquittementThread.eta_acq.get(1, 0)]
            self.list_mesure[1] = [
                float(AlarmeThread.alarme_mesure.get(i, 0.0)) for i in range(1, 13)
            ]
            self.list_recal[1] = [0.0 for _ in range(12)]
            self.list_courbe[1] = [
                CourbeThread.curves.get(i, []) for i in range(1, 13)
            ]
            self.list_val_deb_mes[1] = [
                float(AlarmeThread.fond.get(i, 0.0)) for i in range(1, 13)
            ]

            print("comptage = ", self.liste_comptage[1])
            print("Bdf au demarrage = ", self.list_val_deb_mes[1])
            print("variance = ", self.liste_variance[1])
            print("seuil 1 = ", self.liste_suiveur[1])
            print("seuil 1 recal = ", self.list_recal[1])
            print("valeur max = ", self.liste_val_max[1])
            print("alarme = ", self.liste_alarm[1])
            print("defaut = ", self.liste_defaut[1])
            print("cellules = ", self.list_cell[1])
            print("photo = ", self.liste_photo[1])
            print("vitesse = ", self.liste_vitesse[1])
            print("acquittement = ", self.list_acq[1])
            print("En mesure = ", self.list_mesure[1])
            print("Courbe = ", self.list_courbe[1])

            time.sleep(1)
