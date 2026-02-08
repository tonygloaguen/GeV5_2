#!/usr/bin/env python3
"""
run.py — Lanceur principal du simulateur UniPi 1.1 (faux EVOK)
═══════════════════════════════════════════════════════════════
Placez ce fichier à la racine du projet.
Double-cliquez ou exécutez : python run.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Application.main import main

if __name__ == "__main__":
    main()
