from __future__ import annotations

"""
Abstraction matériel (DI/DO) pour GeV5.

Objectif :
- Ne plus accéder directement à Svr_Unipi ou au simulateur dans le cœur métier.
- Fournir une interface unique HardwarePort avec :
    - read_di(index) -> 0/1
    - write_do(index, value) -> None

Implémentations :
- UnipiHardware : lit/écrit sur Svr_Unipi.Svr_Unipi_rec
- SimHardware   : lit les infos depuis simulateur.Application
                  (variable1, variable2, acqui)
"""

from abc import ABC, abstractmethod
from typing import Optional


# --------------------------------------------------------------------------- #
# Interface générique
# --------------------------------------------------------------------------- #
class HardwarePort(ABC):
    """Interface d'abstraction des entrées/sorties matérielles."""

    @abstractmethod
    def read_di(self, index: int) -> int:
        """
        Lecture d'une entrée digitale (DI).

        :param index: numéro logique de l'entrée (ex: 3, 4, 5)
        :return: 0 ou 1
        """
        raise NotImplementedError

    @abstractmethod
    def write_do(self, index: int, value: int) -> None:
        """
        Écriture sur une sortie digitale (DO).

        :param index: numéro logique de la sortie
        :param value: 0 ou 1
        """
        raise NotImplementedError

    def read_cellule(self, idx: int) -> int:
        """
        Lecture logique des cellules passage.
        idx=1 → DI3, idx=2 → DI4 (mapping historique).
        """
        if idx == 1:
            return self.read_di(3)
        if idx == 2:
            return self.read_di(4)
        return 0


# --------------------------------------------------------------------------- #
# Implémentation Unipi (prod)
# --------------------------------------------------------------------------- #
class UnipiHardware(HardwarePort):
    """
    Adaptateur vers Svr_Unipi.Svr_Unipi_rec.

    Lit les attributs de classe Inp_3, Inp_4, Inp_5 qui sont
    mis à jour en permanence par le thread REST de Svr_Unipi.

    Mapping :
    - DI3 → Svr_Unipi_rec.Inp_3[1]  (cellule S1)
    - DI4 → Svr_Unipi_rec.Inp_4[1]  (cellule S2)
    - DI5 → Svr_Unipi_rec.Inp_5[1]  (acquittement)
    """

    def __init__(self) -> None:
        self._rec_cls = None
        self._ensure_rec()

    def _ensure_rec(self) -> None:
        """Import paresseux de Svr_Unipi_rec (disponible après démarrage)."""
        if self._rec_cls is not None:
            return
        try:
            from .Svr_Unipi import Svr_Unipi_rec
            self._rec_cls = Svr_Unipi_rec
        except Exception:
            self._rec_cls = None

    def read_di(self, index: int) -> int:
        """Lit une entrée digitale via les attributs de classe Svr_Unipi_rec."""
        self._ensure_rec()
        if self._rec_cls is None:
            return 0
        try:
            attr = getattr(self._rec_cls, f"Inp_{index}", None)
            if attr is not None and isinstance(attr, (list, tuple)):
                return int(attr[1])
        except Exception:
            pass
        return 0

    def write_do(self, index: int, value: int) -> None:
        """Écriture DO — pas utilisé directement (relais.py gère via WS)."""
        # Les sorties relais sont gérées par relais.py via WebSocket
        # Ce hook est prévu pour une extension future si besoin
        pass


# --------------------------------------------------------------------------- #
# Implémentation Simulation (simulateur Tkinter)
# --------------------------------------------------------------------------- #
class SimHardware(HardwarePort):
    """
    Adaptateur vers le simulateur Tkinter.

    Mapping :
    - DI3 -> S1  (Application.variable1[0])
    - DI4 -> S2  (Application.variable2[0])
    - DI5 -> ACK (Application.acqui[0])
    """

    def __init__(self) -> None:
        self._sim_app_cls: Optional[type] = None
        self._ensure_app_cls()

    def _ensure_app_cls(self) -> None:
        if self._sim_app_cls is not None:
            return
        try:
            from ..core.simulation import simulateur  # type: ignore
            self._sim_app_cls = getattr(simulateur, "Application", None)
        except Exception:
            self._sim_app_cls = None

    def _read_sim_var(self, di_index: int) -> int:
        if self._sim_app_cls is None:
            return 0
        try:
            app = self._sim_app_cls
            if di_index == 3:
                return int(getattr(app, "variable1", {0: 0})[0])
            if di_index == 4:
                return int(getattr(app, "variable2", {0: 0})[0])
            if di_index == 5:
                return int(getattr(app, "acqui", {0: 0})[0])
        except Exception:
            return 0
        return 0

    def read_di(self, index: int) -> int:
        self._ensure_app_cls()
        return self._read_sim_var(index)

    def read_cellule(self, idx: int) -> int:
        if idx == 1:
            return self.read_di(3)
        if idx == 2:
            return self.read_di(4)
        return 0

    def write_do(self, index: int, value: int) -> None:
        return


# --------------------------------------------------------------------------- #
# Factory pratique
# --------------------------------------------------------------------------- #
def create_hardware(sim: int) -> HardwarePort:
    """
    Factory simple :

    - sim == 1 → SimHardware (simulateur Tkinter)
    - sim == 0 → UnipiHardware (prod / faux EVOK)
    """
    if int(sim) == 1:
        return SimHardware()
    return UnipiHardware()
