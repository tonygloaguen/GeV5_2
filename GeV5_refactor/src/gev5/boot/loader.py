# gev5/boot/loader.py
"""
Chargement de la configuration systÃ¨me depuis la base Parametres.db.

Cette logique est extraite de legacy/GeV5_Moteur.py pour
avoir une API propre : load_config() -> SystemConfig
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.config import SystemConfig
from ..utils.paths import PARAM_DB_PATH


def _get_parametres(db_path: str) -> Dict[str, str]:
    """
    Lit la table Parametres (nom, valeur) et renvoie un dict {nom: valeur}.
    """
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("SELECT nom, valeur FROM Parametres")
        rows = c.fetchall()
    finally:
        conn.close()
    return {row[0]: row[1] for row in rows}


def _init_empty_db(db_path: str) -> None:
    """CrÃ©e la table Parametres si besoin (sans valeur par dÃ©faut)."""
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS Parametres (
                nom TEXT,
                valeur TEXT
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_db_initialized(db_path: str) -> Dict[str, str]:
    """
    Reprend la logique de GeV5_Moteur.py :
    - tente lecture
    - en cas d'erreur SQL, initialise la base et relit
    """
    try:
        return _get_parametres(db_path)
    except sqlite3.Error:
        # On tente d'initialiser la base via l'outil local si dispo
        try:
            from ..hardware.storage import reinit_params  # type: ignore

            if hasattr(reinit_params, "init_params"):
                reinit_params.init_params(db_path)  # type: ignore
            elif hasattr(reinit_params, "main"):
                reinit_params.main()  # type: ignore
        except Exception:
            _init_empty_db(db_path)

        return _get_parametres(db_path)


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_date(value: str | None, default: date | None = None) -> date:
    if default is None:
        default = datetime.now().date()
    if not value:
        return default
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except Exception:
        return default


def _split_list(value: str) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def load_config(db_path: Optional[str] = None) -> SystemConfig:
    """
    Charge la configuration systÃ¨me complÃ¨te depuis Parametres.db
    et retourne un objet SystemConfig prÃªt Ã  l'emploi.

    - Si db_path est None â†’ utilise le chemin centralisÃ© dans utils.paths.PARAM_DB_PATH
    - Si db_path est fourni â†’ surcharge (utile pour les tests / outils).
    """

    # Chemin par dÃ©faut basÃ© sur le rÃ©pertoire local `partage/Base_donnees`
    if db_path is None:
        db_path = str(PARAM_DB_PATH)

    # On permet une surcharge en dev si chemin relatif
    db_path = str(Path(db_path))

    raw: Dict[str, str] = _ensure_db_initialized(db_path)

    # ------------------------------------------------------------------
    # Conversions de base (sans muter raw: Dict[str,str])
    # ------------------------------------------------------------------
    p: Dict[str, Any] = dict(raw)

    p["sample_time"] = _safe_float(raw.get("sample_time", ""), default=0.1)
    p["distance_cellules"] = _safe_float(raw.get("distance_cellules", ""), default=0.0)
    p["Mode_sans_cellules"] = _safe_int(raw.get("Mode_sans_cellules", ""), default=0)
    p["multiple"] = _safe_float(raw.get("multiple", ""), default=1.0)
    p["seuil2"] = _safe_int(raw.get("seuil2", ""), default=0)
    p["low"] = _safe_int(raw.get("low", ""), default=0)
    p["high"] = _safe_int(raw.get("high", ""), default=0)
    p["camera"] = _safe_int(raw.get("camera", ""), default=0)
    p["modbus"] = _safe_int(raw.get("modbus", ""), default=0)
    p["eVx"] = _safe_int(raw.get("eVx", ""), default=0)
    p["mod_SMS"] = _safe_int(raw.get("mod_SMS", ""), default=0)

    # Activation dÃ©tecteurs D1..D12
    for i in range(1, 13):
        key = f"D{i}_ON"
        p[key] = _safe_int(raw.get(key, "0"), default=0)

    # Port SMTP (peut Ãªtre "--")
    if raw.get("port") and raw["port"] != "--":
        port: Optional[int] = _safe_int(raw["port"], default=25)
    else:
        port = None

    recipients = _split_list(raw.get("recipients", ""))
    SMS = _split_list(raw.get("SMS", ""))

    # ------------------------------------------------------------------
    # Calcul Ã©chÃ©ance (identique GeV5_Moteur.py)
    # ------------------------------------------------------------------
    date_prochaine_visite = _safe_date(raw.get("date_prochaine_visite"))
    today = datetime.now().date()
    echeance = (date_prochaine_visite - today).days

    # IO physiques
    pin_1 = _safe_int(raw.get("PIN_1", "0"))
    pin_2 = _safe_int(raw.get("PIN_2", "0"))
    pin_3 = _safe_int(raw.get("PIN_3", "0"))
    pin_4 = _safe_int(raw.get("PIN_4", "0"))

    # Simulation
    sim = _safe_int(raw.get("SIM", "0"))
    suiv_block = _safe_int(raw.get("suiv_block", "0"))

    # RÃ©seaux / EVOK
    Rem_IP = raw.get("Rem_IP", "")
    Rem_IP_2 = raw.get("Rem_IP_2", "")
    base_url = f"http://{Rem_IP}:5002" if Rem_IP else ""
    base_url_2 = f"http://{Rem_IP_2}:5002" if Rem_IP_2 else ""

    # ------------------------------------------------------------------
    # Construction de l'objet SystemConfig
    # ------------------------------------------------------------------
    cfg = SystemConfig(
        # Infos portique
        nom_portique=raw.get("Nom_portique", ""),
        language=raw.get("language", "FR"),

        # Temps / visites
        date_prochaine_visite=date_prochaine_visite,
        echeance=echeance,

        # Comptage / cellules
        sample_time=float(p["sample_time"]),
        distance_cellules=float(p["distance_cellules"]),
        mode_sans_cellules=int(p["Mode_sans_cellules"]),
        multiple=float(p["multiple"]),
        seuil2=int(p["seuil2"]),
        low=int(p["low"]),
        high=int(p["high"]),
        suiv_block=suiv_block,

        # Activation dÃ©tecteurs
        D1_ON=int(p["D1_ON"]),
        D2_ON=int(p["D2_ON"]),
        D3_ON=int(p["D3_ON"]),
        D4_ON=int(p["D4_ON"]),
        D5_ON=int(p["D5_ON"]),
        D6_ON=int(p["D6_ON"]),
        D7_ON=int(p["D7_ON"]),
        D8_ON=int(p["D8_ON"]),
        D9_ON=int(p["D9_ON"]),
        D10_ON=int(p["D10_ON"]),
        D11_ON=int(p["D11_ON"]),
        D12_ON=int(p["D12_ON"]),

        # Noms dÃ©tecteurs
        D1_nom=raw.get("D1_nom", ""),
        D2_nom=raw.get("D2_nom", ""),
        D3_nom=raw.get("D3_nom", ""),
        D4_nom=raw.get("D4_nom", ""),
        D5_nom=raw.get("D5_nom", ""),
        D6_nom=raw.get("D6_nom", ""),
        D7_nom=raw.get("D7_nom", ""),
        D8_nom=raw.get("D8_nom", ""),
        D9_nom=raw.get("D9_nom", ""),
        D10_nom=raw.get("D10_nom", ""),
        D11_nom=raw.get("D11_nom", ""),
        D12_nom=raw.get("D12_nom", ""),

        # IO physiques
        pin_1=pin_1,
        pin_2=pin_2,
        pin_3=pin_3,
        pin_4=pin_4,

        # Simulation
        sim=sim,

        # CamÃ©ra / rÃ©seau
        camera=int(p["camera"]),
        RTSP=raw.get("RTSP", ""),
        IP=raw.get("IP", ""),

        # RÃ©seaux / EVOK
        Rem_IP=Rem_IP,
        Rem_IP_2=Rem_IP_2,
        base_url=base_url,
        base_url_2=base_url_2,

        # Modbus / eVx / SMS
        modbus=int(p["modbus"]),
        eVx=int(p["eVx"]),
        mod_SMS=int(p["mod_SMS"]),
        SMS=SMS,

        # SMTP
        smtp_server=raw.get("smtp_server", ""),
        port=port,
        login=raw.get("login", ""),
        password=raw.get("password", ""),
        sender=raw.get("sender", ""),
        recipients=recipients,

        # Divers
        db_path=db_path,
    )

    return cfg
