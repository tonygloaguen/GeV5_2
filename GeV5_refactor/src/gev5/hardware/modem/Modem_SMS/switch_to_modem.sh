#!/bin/bash

echo "=== Script de bascule HiLink ➜ USB modem ==="

# === Identifier le périphérique USB ===
VENDOR_ID="12d1"
PRODUCT_ID_HILINK="1f01"    # Exemple courant pour HiLink (CD-ROM)
PRODUCT_ID_MODEM="14db"     # Exemple courant pour modem

# === Vérifier la clé actuelle ===
echo "Liste des périphériques USB Huawei détectés :"
lsusb | grep $VENDOR_ID

# === Utiliser usb_modeswitch ===
echo "Bascule en cours..."

sudo usb_modeswitch -v 0x$VENDOR_ID -p 0x$PRODUCT_ID_HILINK \
    -M "55534243123456780000000000000011062000000100000000000000000000"

sleep 5

echo "Vérifie avec lsusb si le nouveau Product ID apparaît (ex: $PRODUCT_ID_MODEM)."
echo "Si oui, ports /dev/ttyUSBx devraient apparaître."
echo "Ensuite, tu pourras envoyer les commandes AT sur /dev/ttyUSB1."

echo "✅ Bascule terminée."
