"""
API/unipi_api.py — Façade publique du simulateur UniPi 1.1
══════════════════════════════════════════════════════════
Seule couche accessible par Application et Web.
"""

from typing import Callable, Dict
from Core import UniPiCore


class UniPiAPI:

    def __init__(self):
        self._core = UniPiCore()

    @property
    def NB_DI(self) -> int:
        return self._core.NB_DI

    @property
    def NB_RO(self) -> int:
        return self._core.NB_RO

    # ── DI ──────────────────────────────────────────────

    def read_di(self, index: int) -> bool:
        return self._core.get_di(index)

    def read_all_di(self) -> Dict[int, bool]:
        return self._core.get_all_di()

    def set_di(self, index: int, state: bool):
        self._core.set_di(index, state)

    def toggle_di(self, index: int):
        self._core.set_di(index, not self._core.get_di(index))

    def get_di_counter(self, index: int) -> int:
        return self._core.get_di_counter(index)

    # ── RO ──────────────────────────────────────────────

    def read_ro(self, index: int) -> bool:
        return self._core.get_ro(index)

    def read_all_ro(self) -> Dict[int, bool]:
        return self._core.get_all_ro()

    def set_ro(self, index: int, state: bool):
        self._core.set_ro(index, state)

    def toggle_ro(self, index: int):
        self._core.set_ro(index, not self._core.get_ro(index))

    def get_ro_counter(self, index: int) -> int:
        return self._core.get_ro_counter(index)

    # ── Callbacks ───────────────────────────────────────

    def on_di_change(self, callback: Callable[[int, bool], None]):
        self._core.register_di_callback(callback)

    def on_ro_change(self, callback: Callable[[int, bool], None]):
        self._core.register_ro_callback(callback)

    # ── Utilitaires ─────────────────────────────────────

    def reset(self):
        self._core.reset_all()

    def status(self) -> str:
        lines = ["═══ UniPi 1.1 — État I/O ═══", ""]
        lines.append("Entrées digitales :")
        di = self._core.get_all_di()
        for i in range(1, self.NB_DI + 1):
            s = "ON " if di[i] else "OFF"
            c = self._core.get_di_counter(i)
            lines.append(f"  DI{i:02d} : {s}  (transitions: {c})")
        lines.append("")
        lines.append("Sorties relais :")
        ro = self._core.get_all_ro()
        for i in range(1, self.NB_RO + 1):
            s = "ON " if ro[i] else "OFF"
            c = self._core.get_ro_counter(i)
            lines.append(f"  RO{i:02d} : {s}  (commutations: {c})")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"UniPiAPI({self._core})"
