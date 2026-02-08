#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import datetime
import os

# --- Configuration ---
SNAPSHOT_URL = "http://192.168.11.55/snapshot.jpg"  # à adapter
OUT_DIR = "/home/pi/Partage/photo"                  # dossier de destination

# --- Création du dossier si besoin ---
os.makedirs(OUT_DIR, exist_ok=True)

def prendre_photo():
    try:
        # Requête HTTP
        response = requests.get(SNAPSHOT_URL, stream=True, timeout=5)
        if response.status_code == 200:
            # Génération du nom de fichier
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(OUT_DIR, f"photo_{timestamp}.jpg")
            # Écriture du fichier image
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"✅ Photo enregistrée : {filename}")
        else:
            print(f"❌ Erreur HTTP ({response.status_code})")
    except Exception as e:
        print(f"⚠️ Erreur lors de la prise de photo : {e}")

if __name__ == "__main__":
    prendre_photo()
