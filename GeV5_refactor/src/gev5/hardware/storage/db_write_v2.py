# src/gev5/hardware/storage/db_write_v2.py
from __future__ import annotations

import threading
import time
import datetime
import sqlite3
from typing import Dict, Optional

from ...core.comptage.comptage import ComptageThread
from ...core.alarmes.alarmes import AlarmeThread
from ...core.defauts.defauts import DefautThread
from ...utils.paths import GEV5_DB_PATH, ensure_partage_structure

from ...hardware import etat_cellule_1, etat_cellule_2  # type: ignore

try:
    # si vitesse_chargement existe et fournit ListWatcher.vitesse[1]
    from ...hardware import vitesse_chargement  # type: ignore
except Exception:  # pragma: no cover - optionnel
    vitesse_chargement = None


def passage_actif() -> bool:
    """
    Détection de passage basée sur etat_cellule_1 / etat_cellule_2.

    Hypothèse : InputWatcher.cellules[1] / [2] == 1 quand faisceau coupé.
    """
    try:
        c1 = getattr(etat_cellule_1.InputWatcher, "cellules", {}).get(1, 0)
    except Exception:
        c1 = 0

    try:
        c2 = getattr(etat_cellule_2.InputWatcher, "cellules", {}).get(2, 0)
    except Exception:
        c2 = 0

    return (c1 == 1) or (c2 == 1)


class PassageRecorderV2(threading.Thread):
    """
    Writer V2 des passages :

    - Sur front montant de passage_actif():
        * snapshot des fonds AlarmeThread.fond[1..12]
        * reset des maxima de comptage
    - Pendant le passage :
        * max1..12 = max(max, ComptageThread.compteur[ch])
    - Sur front descendant (ou timeout) :
        * écrit une ligne dans Db_GeV5.db, table passages_v2
    """

    TICK_S = 0.1
    END_STABLE_S = 0.2     # durée sans passage avant de considérer la fin
    TIMEOUT_S = 10.0       # si passage trop long sans fin → on force

    def __init__(self, db_path: Optional[str] = None) -> None:
        super().__init__(daemon=True)
        ensure_partage_structure()
        self.db_path = db_path or str(GEV5_DB_PATH)

        self._active_prev = False
        self._inactive_since: Optional[float] = None
        self._start_ts: Optional[float] = None

        self._bdf_start: Dict[int, float] = {i: 0.0 for i in range(1, 13)}
        self._max_vals: Dict[int, float] = {i: 0.0 for i in range(1, 13)}

        self._init_db()

    # ------------------------------------------------------------------ #
    # DB
    # ------------------------------------------------------------------ #
    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS passages_v2 (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_start    TEXT,
                    ts_end      TEXT,
                    duration_s  REAL,
                    bdf1        REAL, bdf2 REAL, bdf3 REAL, bdf4 REAL,
                    bdf5        REAL, bdf6 REAL, bdf7 REAL, bdf8 REAL,
                    bdf9        REAL, bdf10 REAL, bdf11 REAL, bdf12 REAL,
                    max1        REAL, max2 REAL, max3 REAL, max4 REAL,
                    max5        REAL, max6 REAL, max7 REAL, max8 REAL,
                    max9        REAL, max10 REAL, max11 REAL, max12 REAL,
                    alarm1      INTEGER, alarm2 INTEGER, alarm3 INTEGER, alarm4 INTEGER,
                    alarm5      INTEGER, alarm6 INTEGER, alarm7 INTEGER, alarm8 INTEGER,
                    alarm9      INTEGER, alarm10 INTEGER, alarm11 INTEGER, alarm12 INTEGER,
                    defaut1     INTEGER, defaut2 INTEGER, defaut3 INTEGER, defaut4 INTEGER,
                    defaut5     INTEGER, defaut6 INTEGER, defaut7 INTEGER, defaut8 INTEGER,
                    defaut9     INTEGER, defaut10 INTEGER, defaut11 INTEGER, defaut12 INTEGER,
                    vitesse     REAL,
                    comment     TEXT
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _snapshot_bdf_start(self) -> None:
        for ch in range(1, 13):
            self._bdf_start[ch] = float(AlarmeThread.fond.get(ch, 0.0))

    def _reset_max_vals(self) -> None:
        for ch in range(1, 13):
            self._max_vals[ch] = 0.0

    def _update_max_vals(self) -> None:
        for ch in range(1, 13):
            val = float(ComptageThread.compteur.get(ch, 0.0))
            if val > self._max_vals[ch]:
                self._max_vals[ch] = val

    def _get_vitesse(self) -> float:
        if vitesse_chargement is None:
            return 0.0
        try:
            return float(vitesse_chargement.ListWatcher.vitesse.get(1, 0.0))
        except Exception:
            return 0.0

    def _write_passage(self, reason: str) -> None:
        if self._start_ts is None:
            return

        ts_start = datetime.datetime.fromtimestamp(self._start_ts)
        ts_end = datetime.datetime.now()
        duration_s = (ts_end - ts_start).total_seconds()

        # snapshot états alarmes/défauts au moment de la fin
        alarms = [int(AlarmeThread.alarme_resultat.get(ch, 0)) for ch in range(1, 13)]
        defauts = [int(DefautThread.defaut_resultat.get(ch, 0)) for ch in range(1, 13)]

        bdf = [self._bdf_start[ch] for ch in range(1, 13)]
        maxv = [self._max_vals[ch] for ch in range(1, 13)]

        vitesse = self._get_vitesse()
        comment = f"fin={reason}"

        row = [
            ts_start.strftime("%Y-%m-%d %H:%M:%S"),
            ts_end.strftime("%Y-%m-%d %H:%M:%S"),
            duration_s,
            *bdf,
            *maxv,
            *alarms,
            *defauts,
            vitesse,
            comment,
        ]

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO passages_v2 (
                    ts_start, ts_end, duration_s,
                    bdf1, bdf2, bdf3, bdf4, bdf5, bdf6, bdf7, bdf8, bdf9, bdf10, bdf11, bdf12,
                    max1, max2, max3, max4, max5, max6, max7, max8, max9, max10, max11, max12,
                    alarm1, alarm2, alarm3, alarm4, alarm5, alarm6, alarm7, alarm8, alarm9, alarm10, alarm11, alarm12,
                    defaut1, defaut2, defaut3, defaut4, defaut5, defaut6, defaut7, defaut8, defaut9, defaut10, defaut11, defaut12,
                    vitesse,
                    comment
                )
                VALUES (
                    ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?,
                    ?
                )
                """,
                row,
            )
            conn.commit()

        print(f"[DB_V2] Passage écrit ({reason}), durée={duration_s:.2f}s.")

    # ------------------------------------------------------------------ #
    # Boucle principale
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        print(f"[DB_V2] Writer démarré sur {self.db_path}")
        while True:
            now_active = passage_actif()
            now_ts = time.time()

            # Front montant = début de passage
            if now_active and not self._active_prev:
                self._start_ts = now_ts
                self._inactive_since = None
                self._snapshot_bdf_start()
                self._reset_max_vals()
                print("[DB_V2] Passage détecté (start).")

            # Pendant le passage → met à jour les maxima
            if now_active:
                self._update_max_vals()

            # Front descendant = fin potentielle
            if (not now_active) and self._active_prev:
                if self._inactive_since is None:
                    self._inactive_since = now_ts
                elif (now_ts - self._inactive_since) >= self.END_STABLE_S:
                    # fin confirmée
                    try:
                        self._write_passage("fin de passage")
                    except Exception as e:
                        print(f"[DB_V2][ERR] écriture fin: {e}")
                    finally:
                        self._start_ts = None
                        self._inactive_since = None

            # Timeout (passage trop long sans fin)
            if self._start_ts is not None and now_active:
                if (now_ts - self._start_ts) >= self.TIMEOUT_S:
                    try:
                        self._write_passage("timeout")
                    except Exception as e:
                        print(f"[DB_V2][ERR] écriture timeout: {e}")
                    finally:
                        self._start_ts = None
                        self._inactive_since = None

            self._active_prev = now_active
            time.sleep(self.TICK_S)
