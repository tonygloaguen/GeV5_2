#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application/automation.py
══════════════════════════════════════════════════════════════
Logique d'automatisme — Programme utilisateur

Fonctionne comme un automate programmable (PLC) :
  Boucle cyclique → Lecture DI → Traitement → Écriture RO

Scénario de démonstration :
  • DI1 = Bouton Marche     → Active RO1 (Moteur)
  • DI2 = Bouton Arrêt      → Désactive RO1
  • DI3 = Capteur niveau    → Active RO2 (Pompe) en suivi direct
  • DI4 = Arrêt d'urgence   → Désactive TOUS les relais
  • DI5 = Mode auto         → RO8 clignote (voyant)

Communique UNIQUEMENT via l'API (jamais directement le Core).
══════════════════════════════════════════════════════════════
"""

import time
from API import UniPiAPI


class AutomationProgram:
    """
    Programme d'automatisme utilisant l'API UniPi.

    Écrivez votre logique métier dans la méthode _scan_cycle().
    Le code est identique à ce que vous feriez avec une vraie carte.

    Args:
        api: Instance de UniPiAPI
    """

    def __init__(self, api: UniPiAPI):
        self._api = api
        self._running = False
        self._cycle_count = 0

    # ═══════════════════════════════════════════════════════════
    #  BOUCLE PRINCIPALE
    # ═══════════════════════════════════════════════════════════

    def run(self, cycle_time_ms: int = 100):
        """
        Démarrer la boucle d'automatisme.

        Args:
            cycle_time_ms: Temps de cycle en millisecondes (défaut: 100ms)
        """
        self._running = True
        print(f"\n🔧 Automatisme démarré (cycle: {cycle_time_ms}ms)")
        print("   Assignations des entrées :")
        print("   ├── DI1 = Marche moteur   → RO1")
        print("   ├── DI2 = Arrêt moteur    → RO1 OFF")
        print("   ├── DI3 = Capteur niveau  → RO2 (pompe)")
        print("   ├── DI4 = ARRÊT URGENCE   → tout OFF")
        print("   └── DI5 = Mode auto       → RO8 clignote")
        print()

        while self._running:
            try:
                self._scan_cycle()
                self._cycle_count += 1
                time.sleep(cycle_time_ms / 1000.0)
            except Exception as e:
                print(f"❌ Erreur cycle #{self._cycle_count}: {e}")
                time.sleep(1)

    def stop(self):
        """Arrêter proprement la boucle."""
        self._running = False
        print("⏹  Automatisme arrêté")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # ═══════════════════════════════════════════════════════════
    #  CYCLE DE SCAN (votre logique métier ici)
    # ═══════════════════════════════════════════════════════════

    def _scan_cycle(self):
        """
        Un cycle de scan : LECTURE → TRAITEMENT → ÉCRITURE.

        ┌─────────────────────────────────────────────────┐
        │  Modifiez cette méthode pour votre application  │
        └─────────────────────────────────────────────────┘
        """

        # ── PHASE 1 : LECTURE DES ENTRÉES ──
        di1_marche   = self._api.read_di(1)
        di2_arret    = self._api.read_di(2)
        di3_niveau   = self._api.read_di(3)
        di4_urgence  = self._api.read_di(4)
        di5_auto     = self._api.read_di(5)

        # ── PHASE 2 : TRAITEMENT LOGIQUE ──

        # --- Arrêt d'urgence (priorité absolue) ---
        if di4_urgence:
            for i in range(1, self._api.NB_RO + 1):
                self._api.set_ro(i, False)
            return

        # --- Marche/Arrêt moteur (RO1) — logique à accrochage ---
        ro1_etat = self._api.read_ro(1)
        if di1_marche and not di2_arret:
            if not ro1_etat:
                self._api.set_ro(1, True)
        elif di2_arret:
            if ro1_etat:
                self._api.set_ro(1, False)

        # --- Capteur niveau → Pompe (RO2) — suivi direct ---
        self._api.set_ro(2, di3_niveau)

        # --- Mode auto → Clignotement RO8 (voyant) ---
        if di5_auto:
            if self._cycle_count % 5 == 0:
                self._api.toggle_ro(8)
        else:
            if self._api.read_ro(8):
                self._api.set_ro(8, False)