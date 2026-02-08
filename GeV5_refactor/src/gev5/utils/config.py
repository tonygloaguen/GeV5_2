# src/gev5/utils/config.py
from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class SystemConfig:
    """
    Représentation typée de tous les paramètres système GeV5.

    Cette dataclass reprend la logique de GeV5_Moteur.py :
    - lecture de Parametres.db
    - conversions de types
    """

    # Infos portique
    nom_portique: str
    language: str

    # Temps / visites
    date_prochaine_visite: date
    echeance: int  # jours restants avant visite

    # Comptage / cellules
    sample_time: float
    distance_cellules: float
    mode_sans_cellules: int
    multiple: float
    seuil2: int
    low: int
    high: int
    suiv_block: int

    # Activation détecteurs (1..12)
    D1_ON: int
    D2_ON: int
    D3_ON: int
    D4_ON: int
    D5_ON: int
    D6_ON: int
    D7_ON: int
    D8_ON: int
    D9_ON: int
    D10_ON: int
    D11_ON: int
    D12_ON: int

    # Noms détecteurs
    D1_nom: str
    D2_nom: str
    D3_nom: str
    D4_nom: str
    D5_nom: str
    D6_nom: str
    D7_nom: str
    D8_nom: str
    D9_nom: str
    D10_nom: str
    D11_nom: str
    D12_nom: str

    # IO physiques (GPIO / EVOK)
    pin_1: int
    pin_2: int
    pin_3: int
    pin_4: int

    # Simulation
    sim: int

    # Caméra / RTSP / IP
    camera: int
    RTSP: str
    IP: str

    # Réseaux Remoting / EVOK
    Rem_IP: str
    Rem_IP_2: str
    base_url: str
    base_url_2: str

    # Modbus / eVx / SMS
    modbus: int
    eVx: int
    mod_SMS: int
    SMS: List[str]

    # SMTP / email
    smtp_server: str
    port: Optional[int]
    login: str
    password: str
    sender: str
    recipients: List[str]

    # Divers
    db_path: str
