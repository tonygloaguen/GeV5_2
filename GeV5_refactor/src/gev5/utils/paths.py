# gev5/utils/paths.py
"""
Centralisation des chemins utilisés par GeV5.

Objectif :
- une seule source de vérité pour le répertoire `partage/`
- chemins des bases SQLite (Parametres.db, Db_GeV5.db, Bruit_de_fond.db)
- chemins des répertoires rapports / exports / photos / logs
"""

from __future__ import annotations

from pathlib import Path

# Racine du package gev5 (…/gev5)
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

# Répertoire de partage local au projet (…/gev5/partage)
PARTAGE_DIR = PACKAGE_ROOT / "partage"

# Sous-répertoires de partage
DB_DIR = PARTAGE_DIR / "Base_donnees"
RAPPORTS_DIR = PARTAGE_DIR / "rapports"
PHOTO_DIR = PARTAGE_DIR / "photo"
EXPORT_DIR = PARTAGE_DIR / "Export"
LOGS_DIR = PARTAGE_DIR / "logs"

# Chemins des bases SQLite
PARAM_DB_PATH = DB_DIR / "Parametres.db"
GEV5_DB_PATH = DB_DIR / "Db_GeV5.db"
BRUIT_FOND_DB_PATH = DB_DIR / "Bruit_de_fond.db"


def ensure_partage_structure() -> None:
    """
    Crée les répertoires `partage` si nécessaire.

    - N'écrase aucune base existante.
    - Utile en dev, ou au premier démarrage sur une nouvelle machine.
    """
    for d in (PARTAGE_DIR, DB_DIR, RAPPORTS_DIR, PHOTO_DIR, EXPORT_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
