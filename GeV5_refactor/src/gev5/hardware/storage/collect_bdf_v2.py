# src/gev5/hardware/storage/collect_bdf_v2.py
from __future__ import annotations

import threading
import time
import sqlite3
from typing import Optional, Union
from pathlib import Path

from ...core.alarmes.alarmes import AlarmeThread
from ...utils.paths import BRUIT_FOND_DB_PATH, ensure_partage_structure


class BdfCollectorV2(threading.Thread):
    """
    Collecteur V2 du bruit de fond.

    - lit périodiquement AlarmeThread.fond[1..12]
    - écrit dans Bruit_de_fond.db, table bdf_history :
        timestamp | bdf1..bdf12
    """

    def __init__(
        self,
        interval: int = 30,
        db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.interval = interval
        self.db_path = str(db_path or BRUIT_FOND_DB_PATH)

    # ------------------------------------------------------------------ #
    # Boucle principale
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        ensure_partage_structure()
        self._init_db()

        while True:
            try:
                self._collect()
            except Exception as e:
                print(f"[BDF_V2] Erreur collecte : {e}")
            time.sleep(self.interval)

    # ------------------------------------------------------------------ #
    # DB
    # ------------------------------------------------------------------ #
    def _init_db(self) -> None:
        """Crée la table bdf_history si nécessaire."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bdf_history (
                    timestamp   TEXT,
                    bdf1        REAL,
                    bdf2        REAL,
                    bdf3        REAL,
                    bdf4        REAL,
                    bdf5        REAL,
                    bdf6        REAL,
                    bdf7        REAL,
                    bdf8        REAL,
                    bdf9        REAL,
                    bdf10       REAL,
                    bdf11       REAL,
                    bdf12       REAL
                )
                """
            )
            conn.commit()

    def _collect(self) -> None:
        """Lit les fonds et insère une ligne."""
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        row = [ts]

        for ch in range(1, 13):
            val = float(AlarmeThread.fond.get(ch, 0.0))
            row.append(val)

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO bdf_history (
                    timestamp,
                    bdf1, bdf2, bdf3, bdf4, bdf5, bdf6,
                    bdf7, bdf8, bdf9, bdf10, bdf11, bdf12
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            conn.commit()
