"""
Core/unipi_core.py — Noyau du simulateur UniPi 1.1
═══════════════════════════════════════════════════
État interne thread-safe : DI1-14, RO1-8, compteurs, callbacks.
"""

import threading
from typing import Callable, Optional, Dict


class UniPiCore:

    NB_DI = 14
    NB_RO = 8

    def __init__(self):
        self._lock = threading.Lock()
        self._di: Dict[int, bool] = {i: False for i in range(1, self.NB_DI + 1)}
        self._ro: Dict[int, bool] = {i: False for i in range(1, self.NB_RO + 1)}
        self._di_counters: Dict[int, int] = {i: 0 for i in range(1, self.NB_DI + 1)}
        self._ro_counters: Dict[int, int] = {i: 0 for i in range(1, self.NB_RO + 1)}
        self._on_di_change: Optional[Callable[[int, bool], None]] = None
        self._on_ro_change: Optional[Callable[[int, bool], None]] = None

    # ── DI ──────────────────────────────────────────────

    def get_di(self, index: int) -> bool:
        self._validate_di(index)
        with self._lock:
            return self._di[index]

    def get_all_di(self) -> Dict[int, bool]:
        with self._lock:
            return dict(self._di)

    def set_di(self, index: int, state: bool):
        self._validate_di(index)
        with self._lock:
            old = self._di[index]
            self._di[index] = state
            if old != state:
                self._di_counters[index] += 1
        if old != state and self._on_di_change:
            self._on_di_change(index, state)

    def get_di_counter(self, index: int) -> int:
        self._validate_di(index)
        with self._lock:
            return self._di_counters[index]

    # ── RO ──────────────────────────────────────────────

    def get_ro(self, index: int) -> bool:
        self._validate_ro(index)
        with self._lock:
            return self._ro[index]

    def get_all_ro(self) -> Dict[int, bool]:
        with self._lock:
            return dict(self._ro)

    def set_ro(self, index: int, state: bool):
        self._validate_ro(index)
        with self._lock:
            old = self._ro[index]
            self._ro[index] = state
            if old != state:
                self._ro_counters[index] += 1
        if old != state and self._on_ro_change:
            self._on_ro_change(index, state)

    def get_ro_counter(self, index: int) -> int:
        self._validate_ro(index)
        with self._lock:
            return self._ro_counters[index]

    # ── Callbacks ───────────────────────────────────────

    def register_di_callback(self, cb: Callable[[int, bool], None]):
        self._on_di_change = cb

    def register_ro_callback(self, cb: Callable[[int, bool], None]):
        self._on_ro_change = cb

    # ── Reset ───────────────────────────────────────────

    def reset_all(self):
        with self._lock:
            for i in self._di:
                self._di[i] = False
            for i in self._ro:
                self._ro[i] = False
            self._di_counters = {i: 0 for i in range(1, self.NB_DI + 1)}
            self._ro_counters = {i: 0 for i in range(1, self.NB_RO + 1)}

    # ── Validation ──────────────────────────────────────

    def _validate_di(self, index: int):
        if not isinstance(index, int) or index < 1 or index > self.NB_DI:
            raise ValueError(f"DI invalide : {index} (1–{self.NB_DI})")

    def _validate_ro(self, index: int):
        if not isinstance(index, int) or index < 1 or index > self.NB_RO:
            raise ValueError(f"RO invalide : {index} (1–{self.NB_RO})")

    def __repr__(self) -> str:
        di_on = [i for i, v in self._di.items() if v]
        ro_on = [i for i, v in self._ro.items() if v]
        return f"UniPiCore(DI_ON={di_on}, RO_ON={ro_on})"
