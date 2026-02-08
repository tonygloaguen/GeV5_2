#  -*- coding: utf-8  -*-
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC)) if str(SRC) not in sys.path else None

# Importation de la fonction main depuis le module 'main' dans le dossier src
from src.gev5.main import main 

if __name__ == "__main__":
    # Appel de la fonction main() depuis ce script uniquement si celui-ci est exécuté directement et non importé
    main()