from __future__ import annotations

"""
Abstraction matÃ©riel (DI/DO) pour GeV5.

Objectif :
- Ne plus accÃ©der directement Ã  Svr_Unipi ou au simulateur dans le cÅ“ur mÃ©tier.
- Fournir une interface unique HardwarePort avec :
    - read_di(index) -> 0/1
    - write_do(index, value) -> None

ImplÃ©mentations :
- UnipiHardware : lit/Ã©crit sur Svr_Unipi.Svr_Unipi_rec
- SimHardware   : lit les infos depuis simulateur.Application
                  (variable1, variable2, acqui)
"""

from abc import ABC, abstractmethod
from typing import Optional


# --------------------------------------------------------------------------- #
# Interface gÃ©nÃ©rique
# --------------------------------------------------------------------------- #
class HardwarePort(ABC):
    """Interface d'abstraction des entrÃ©es/sorties matÃ©rielles."""

    @abstractmethod
    def read_di(self, index: int) -> int:
        """
        Lecture d'une entrÃ©e digitale (DI).

        :param index: numÃ©ro logique de l'entrÃ©e (ex: 3, 4, 5)
        :return: 0 ou 1
        """
        raise NotImplementedError

    @abstractmethod
    def write_do(self, index: int, value: int) -> None:
        """
        Ã‰criture sur une sortie digitale (DO).

        :param index: numÃ©ro logique de la sortie
        :param value: 0 ou 1
        """
        raise NotImplementedError

    def read_cellule(self, idx: int) -> int:
        """
        Lecture logique des cellules passage.
        idx=1 â†’ DI3, idx=2 â†’ DI4 (mapping historique).
        """
        if idx == 1:
            return self.read_di(3)
        if idx == 2:
            return self.read_di(4)
        return 0


# --------------------------------------------------------------------------- #
# ImplÃ©mentation Unipi (prod)
# --------------------------------------------------------------------------- #
class UnipiHardware(HardwarePort):
    """
    Adaptateur vers Svr_Unipi.Svr_Unipi_rec.

    HypothÃ¨se basÃ©e sur la V1 (acquittement.py) :
    - lecture DI : Svr_Unipi.Svr_Unipi_rec.Inp_X[1] âˆˆ {0,1}
    - Ã©criture DO : Svr_Unipi.Svr_Unipi_rec.Out_X[1] = 0/1 (Ã  adapter si besoin)
    - index = DI/DO logique (3,4,5â€¦)
    - return = 0/1
    - value = 0/1
    """

    def __init__(self) -> None:
        try:
            import Svr_Unipi  # type: ignore
            self._svr_unipi = Svr_Unipi
        except Exception:
            self._svr_unipi = None

    def _safe_read_unipi_input(self, n: int, default: int = 0) -> int:
        if self._svr_unipi is None:
            return default
        try:
            rec = getattr(self._svr_unipi, "Svr_Unipi_rec")
            val = getattr(rec, f"Inp_{n}")[1]
            return int(val)
        except Exception:
            return default

    def _safe_write_unipi_output(self, n: int, value: int) -> None:
        if self._svr_unipi is None:
            return
        try:
            rec = getattr(self._svr_unipi, "Svr_Unipi_rec")
            out = list(getattr(rec, f"Out_{n}"))
            out[1] = 1 if value else 0
            setattr(rec, f"Out_{n}", tuple(out))
        except Exception:
            # On ne casse jamais la boucle temps rÃ©el pour un problÃ¨me IO
            return

    def read_di(self, index: int) -> int:
        return self._safe_read_unipi_input(index, default=0)

    def write_do(self, index: int, value: int) -> None:
        self._safe_write_unipi_output(index, value)


# --------------------------------------------------------------------------- #
# ImplÃ©mentation Simulation (simulateur Tkinter)
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
            # simulateur est dans src/gev5/core/simulation/simulateur.py
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
        """
        Lecture logique des cellules passage.
        idx=1 â†’ S1 (DI3)
        idx=2 â†’ S2 (DI4)
        """
        if idx == 1:
            return self.read_di(3)
        if idx == 2:
            return self.read_di(4)
        return 0

    def write_do(self, index: int, value: int) -> None:
        # No-op pour lâ€™instant en mode simu
        return


# --------------------------------------------------------------------------- #
# Factory pratique
# --------------------------------------------------------------------------- #
def create_hardware(sim: int) -> HardwarePort:
    """
    Factory simple :

    - sim == 1 â†’ SimHardware (simulateur Tkinter)
    - sim == 0 â†’ UnipiHardware (prod)

    Ã€ utiliser par Gev5System / starter pour injecter le bon backend.
    """
    if int(sim) == 1:
        return SimHardware()
    return UnipiHardware()
