#!/bin/bash
LOGFILE="/home/pi/Partage/logs/GeV5_Moteur.log"
exec > >(tee -a "$LOGFILE") 2>&1
echo "Starting script"

# Exécution du script Python avec l'option -u pour désactiver le buffering
python3 -u /home/pi/GeV5/GeV5_Moteur.py

echo "Script finished"
