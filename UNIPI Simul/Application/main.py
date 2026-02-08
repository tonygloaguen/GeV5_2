"""
Application/main.py — Point d'entrée du simulateur UniPi 1.1 pour GeV5
═══════════════════════════════════════════════════════════════════════

Lance dans l'ordre :
  1. API UniPi (état interne partagé)
  2. Faux serveur EVOK sur 127.0.0.1:8080 (REST + WebSocket)
  3. GUI Tkinter (thread principal)

Ensuite, démarrer GeV5 normalement (sim=0) :
  GeV5 se connecte à 127.0.0.1:8080 comme si c'était le vrai EVOK.

Usage :
    cd UNIPI SIMUL/
    python run.py
"""

import sys
import time

from API import UniPiAPI
from Web.evok_server import FakeEvokServer
from Web.gui import UniPiGUI


def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║   UniPi 1.1 — Simulateur EVOK pour GeV5              ║")
    print("╠═══════════════════════════════════════════════════════╣")
    print("║   REST  → http://127.0.0.1:8080/rest/di/             ║")
    print("║   WS    → ws://127.0.0.1:8080/ws                     ║")
    print("║                                                       ║")
    print("║   Svr_Unipi.py lit les DI via REST (poll)             ║")
    print("║   relais.py écrit les RO via WebSocket                ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()

    # ── 1. API (état partagé) ──
    api = UniPiAPI()
    print("✅ API initialisée")

    # ── 2. Initialiser les RO selon les valeurs par défaut de relais.py ──
    # relais.py au démarrage :
    #   RO1=ON (défaut séc+), RO5=ON (défaut séc+), tout le reste=OFF
    api.set_ro(1, True)   # Défaut — sécurité positive (repos = fermé)
    api.set_ro(5, True)   # Défaut — sécurité positive (repos = fermé)
    print("✅ RO initialisées (RO1=ON, RO5=ON — sécurité positive)")

    # ── 3. GUI (on la crée d'abord pour le callback de log) ──
    gui = UniPiGUI(api, title="UniPi 1.1 — Simulateur EVOK (GeV5)")

    # ── 4. Faux serveur EVOK ──
    try:
        evok = FakeEvokServer(api, port=8080, log_callback=gui.log_evok)
        evok.start()
    except OSError:
        print("❌ Port 8080 occupé. Arrêtez le vrai EVOK ou tout autre service.")
        sys.exit(1)

    print()
    print("🚀 Prêt ! Démarrez GeV5 avec sim=0.")
    print("   Les DI3/DI4/DI5 sont contrôlables dans la GUI.")
    print("   Les RO1-8 s'actualisent quand relais.py envoie ses commandes WS.")
    print()

    # ── 5. GUI dans le thread principal (Tkinter l'exige) ──
    try:
        gui.run()
    except KeyboardInterrupt:
        pass
    finally:
        evok.stop()
        print("✅ Simulateur arrêté")


if __name__ == "__main__":
    main()
