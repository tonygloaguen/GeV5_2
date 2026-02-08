import os
import sys
import time
import shutil
import threading
import zipfile
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import queue
import pyudev

import socket
import subprocess
from datetime import datetime

# --- Journalisation robuste (rotation) ---
import logging, traceback
from logging.handlers import RotatingFileHandler

LOG_PATH = "/home/pi/usb_monitor.log"
logger = logging.getLogger("usbmonitor")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=3)
_formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
_handler.setFormatter(_formatter)
logger.addHandler(_handler)

def _excepthook(exc_type, exc, tb):
    logger.critical("Uncaught exception: %s\n%s", exc, "".join(traceback.format_tb(tb)))
sys.excepthook = _excepthook


class USBMonitor(threading.Thread):
    def __init__(self, watch_dir="/media/pi", source_dir="/home/pi/Partage",
                 update_dir="/home/pi/GeV5", message_queue=None):
        super().__init__(daemon=True)
        self.watch_dir = watch_dir.rstrip("/")
        self.source_dir = source_dir
        self.update_dir = update_dir
        self.username = "admin"       # ⚠️ à externaliser (config/env) en prod
        self.password = "password"    # ⚠️ à externaliser (config/env) en prod
        self.message_queue = message_queue

        # État runtime
        self.progress = None
        self.cancel_event = threading.Event()
        self.worker_lock = threading.Lock()
        self.active_mount = None   # ex: /media/pi/XXX
        self.active_src = None     # ex: /dev/sda1

    # ------------- Helpers montage -------------
    def _list_mounts_under_media(self):
        mounts = []
        with open('/proc/mounts', 'r') as f:
            for line in f:
                src, mnt, *_ = line.split()
                if mnt.startswith(self.watch_dir + '/'):
                    mounts.append((src, mnt))
        return mounts

    def is_mount_alive(self, mount_point: str) -> bool:
        """Vérifie que mount_point est toujours monté et accessible en écriture."""
        try:
            alive = any(mnt == mount_point for _, mnt in self._list_mounts_under_media())
            if not alive:
                return False
            return os.path.ismount(mount_point) and os.access(mount_point, os.W_OK)
        except Exception:
            return False

    def src_for_mount(self, mount_point: str):
        """Retourne /dev/... de ce mount si connu."""
        for src, mnt in self._list_mounts_under_media():
            if mnt == mount_point:
                return src
        return None

    def get_mount_point(self, device_path):
        """Trouve un point de montage correspondant au device_path via /proc/mounts."""
        with open('/proc/mounts', 'r') as f:
            for line in f:
                if device_path == line.split()[0]:
                    return line.split()[1]
        return None

    # ------------- UDEV -------------
    def run(self):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='block')
        monitor.start()

        observer = pyudev.MonitorObserver(monitor, callback=self.handle_event, name='usb-observer')
        observer.start()
        observer.join()

    def safe_device_desc(self, device):
        try:
            base = {
                "subsystem": getattr(device, "subsystem", None),
                "device_node": getattr(device, "device_node", None),
                "sys_name": getattr(device, "sys_name", None),
                "action": getattr(device, "action", None),
            }
            try:
                props = dict(device)
            except Exception:
                props = {}
            base["props_keys"] = list(props.keys())[:12]
            return base
        except Exception:
            return {"error": "device introspection failed"}

    # ✅ Signature corrigée : callback reçoit SEULEMENT 'device'
    def handle_event(self, device):
        try:
            if device is None:
                logger.warning("udev event avec device=None")
                return

            action = getattr(device, "action", None)
            subsystem = getattr(device, "subsystem", None)
            if subsystem != "block" or action not in ("add", "remove"):
                return

            devnode = getattr(device, "device_node", None)
            sys_name = getattr(device, "sys_name", None)
            logger.info("udev event action=%s dev=%s sys=%s desc=%s",
                        action, devnode, sys_name, self.safe_device_desc(device))

            # --- Arrivée d'un périphérique ---
            if action == 'add':
                before = set(self._list_mounts_under_media())
                time.sleep(10)  # laisser l’automount travailler (adapter si besoin)
                after = set(self._list_mounts_under_media())
                new_mounts = list(after - before)

                # Fallback via /proc/mounts si pas trouvé
                if not new_mounts and devnode:
                    mp = self.get_mount_point(devnode)
                    if mp:
                        new_mounts = [(devnode, mp)]

                if not new_mounts:
                    self.send_message("Clé USB détectée mais aucun point de montage trouvé sous /media/pi.")
                    logger.info("Aucun nouveau montage détecté pour dev=%s", devnode)
                    return

                # Choix du montage le plus pertinent
                chosen = None
                for src, mnt in new_mounts:
                    if sys_name and sys_name in (src or ""):
                        chosen = (src, mnt)
                        break
                if not chosen:
                    chosen = new_mounts[-1]

                src, mount_point = chosen
                self.send_message(f"Clé USB montée détectée : {mount_point}")
                logger.info("Mount choisi src=%s mnt=%s", src, mount_point)

                def work():
                    with self.worker_lock:
                        self.cancel_event.clear()
                        self.active_mount = mount_point
                        self.active_src = src
                        try:
                            self.handle_usb_drive(mount_point)
                        except Exception as e:
                            logger.error("handle_usb_drive error: %s\n%s", e, traceback.format_exc())
                            self.send_message(f"Erreur traitement clé : {e}")
                        finally:
                            self.active_mount = None
                            self.active_src = None
                            self.cancel_event.clear()

                threading.Thread(target=work, daemon=True).start()
                return

            # --- Retrait d'un périphérique ---
            if action == 'remove':
                match = False
                if self.active_mount:
                    try:
                        src = self.src_for_mount(self.active_mount)
                    except Exception:
                        src = None
                    if devnode and src and devnode == src:
                        match = True
                    if (not match) and sys_name and src and sys_name in src:
                        match = True
                if match:
                    self.cancel_event.set()
                    self.send_message("Clé USB retirée — annulation des opérations en cours.")
                    logger.info("Annulation demandée suite à remove dev=%s", devnode)
                return

        except Exception as e:
            logger.error("handle_event exception: %s\n%s", e, traceback.format_exc())
            self.send_message(f"Erreur détection USB (détails dans le log) : {e}")

    # ------------- Traitements métier -------------
    def handle_usb_drive(self, drive):
        try:
            # Nettoyage d’un .part éventuel laissé par un arrachement précédent
            part_path = os.path.join(drive, "Partage_backup.zip.part")
            try:
                if os.path.exists(part_path):
                    os.remove(part_path)
            except Exception:
                pass

            self.backup_directory_to_usb(drive)
            if not self.cancel_event.is_set():
                self.update_from_usb(drive)
        except Exception as e:
            self.send_message(f"Erreur de traitement de la clé USB {drive} : {e}")
            logger.error("handle_usb_drive outer error: %s\n%s", e, traceback.format_exc())

    def get_network_info(self):
        """Retourne le contenu texte pour network_info.txt (intégré dans le ZIP)."""
        try:
            ip_address = subprocess.getoutput("hostname -I | awk '{print $1}'").strip()
            if not ip_address:
                ip_address = socket.gethostbyname(socket.gethostname())

            gateway = subprocess.getoutput("ip route | grep default | awk '{print $3}'").strip()
            dns = subprocess.getoutput("grep -E '^nameserver' /etc/resolv.conf | awk '{print $2}' | paste -sd ',' -").strip()
            hostname = socket.gethostname()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            content = (
                f"Adresse IP : {ip_address}\n"
                f"Passerelle : {gateway}\n"
                f"DNS        : {dns}\n"
                f"Nom hôte   : {hostname}\n"
                f"Date/Heure : {now}\n"
            )
            return content
        except Exception as e:
            return f"Erreur récupération IP : {e}"

    def backup_directory_to_usb(self, drive):
        root_win = None
        try:
            if not self.is_mount_alive(drive):
                self.send_message("La clé n’est plus montée. Abandon de la sauvegarde.")
                return
            if self.cancel_event.is_set():
                return

            # UI (⚠️ idéalement déplacer l’UI dans le thread principal)
            root_win = tk.Tk()
            root_win.title("Progression du transfert")
            root_win.geometry("360x120")
            tk.Label(root_win, text="Transfert en cours...").pack(pady=10)
            self.progress = ttk.Progressbar(root_win, orient='horizontal', length=320, mode='determinate')
            self.progress.pack(pady=10)
            root_win.update()

            total_files = sum([len(files) for _, _, files in os.walk(self.source_dir)]) or 1
            current_file = 0

            final_zip = os.path.join(drive, "Partage_backup.zip")
            temp_zip = final_zip + ".part"

            if os.path.exists(final_zip):
                self.send_message("Le fichier Partage_backup.zip existe déjà sur la clé USB (sauvegarde ignorée).")
                root_win.destroy()
                return

            # Écriture dans un .part d’abord
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root_dir, _, files in os.walk(self.source_dir):
                    if self.cancel_event.is_set() or not self.is_mount_alive(drive):
                        raise RuntimeError("Annulé : clé retirée pendant la sauvegarde.")

                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        arcname = os.path.relpath(file_path, self.source_dir)

                        zipf.write(file_path, arcname)

                        current_file += 1
                        self.progress['value'] = (current_file / total_files) * 100
                        root_win.update_idletasks()

                # Ajout des métadonnées réseau
                if self.cancel_event.is_set() or not self.is_mount_alive(drive):
                    raise RuntimeError("Annulé : clé retirée pendant la sauvegarde.")
                zipf.writestr("network_info.txt", self.get_network_info())

            # Rename atomique .part -> .zip
            if self.cancel_event.is_set() or not self.is_mount_alive(drive):
                raise RuntimeError("Annulé : clé retirée avant finalisation.")
            os.replace(temp_zip, final_zip)

            self.send_message("Transfert terminé avec succès.")
            root_win.destroy()

        except Exception as e:
            self.send_message(f"Erreur lors du transfert : {e}")
            logger.error("backup_directory_to_usb error: %s\n%s", e, traceback.format_exc())
            try:
                if 'temp_zip' in locals() and os.path.exists(temp_zip):
                    os.remove(temp_zip)
            except Exception:
                pass
            try:
                if root_win is not None:
                    root_win.destroy()
            except Exception:
                pass

    def update_from_usb(self, drive):
        try:
            if self.cancel_event.is_set() or not self.is_mount_alive(drive):
                self.send_message("Clé non disponible, mise à jour ignorée.")
                return

            update_file = os.path.join(drive, "update_GEV5.zip")
            if not os.path.exists(update_file):
                return

            self.send_message("Mise à jour détectée.")
            if not self.authenticate():
                self.send_message("Authentification échouée. Mise à jour annulée.")
                return

            tmp_dir = os.path.join(self.update_dir, "_incoming_tmp")
            os.makedirs(tmp_dir, exist_ok=True)

            with zipfile.ZipFile(update_file, 'r') as zipf:
                for member in zipf.namelist():
                    if self.cancel_event.is_set():
                        raise RuntimeError("Annulé : clé retirée pendant la mise à jour.")
                    zipf.extract(member, tmp_dir)

            # Sauvegarde et déploiement
            for root_dir, _, files in os.walk(tmp_dir):
                rel = os.path.relpath(root_dir, tmp_dir)
                dest_dir = os.path.join(self.update_dir, rel) if rel != '.' else self.update_dir
                os.makedirs(dest_dir, exist_ok=True)

                for f in files:
                    if self.cancel_event.is_set():
                        raise RuntimeError("Annulé : mise à jour interrompue.")
                    src_path = os.path.join(root_dir, f)
                    dest_path = os.path.join(dest_dir, f)
                    if os.path.exists(dest_path):
                        backup_path = os.path.join(self.update_dir, "old", rel, f) if rel != '.' else os.path.join(self.update_dir, "old", f)
                        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                        shutil.move(dest_path, backup_path)
                    shutil.move(src_path, dest_path)

            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

            self.send_message("Mise à jour terminée avec succès.")

        except Exception as e:
            self.send_message(f"Erreur lors de la mise à jour : {e}")
            logger.error("update_from_usb error: %s\n%s", e, traceback.format_exc())

    def authenticate(self):
        root = tk.Tk()
        root.withdraw()
        try:
            username = simpledialog.askstring("Login", "Entrez votre nom d'utilisateur:", parent=root)
            password = simpledialog.askstring("Mot de passe", "Entrez votre mot de passe:", parent=root, show='*')
            return (username == self.username and password == self.password)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def send_message(self, message):
        if self.message_queue:
            self.message_queue.put(message)
        logger.info("UI message: %s", message)

def run_headless():
    """Mode service pour le portique : pas de Tk, pas de fenêtres."""
    message_queue = queue.Queue()
    usb_monitor = USBMonitor(message_queue=message_queue)
    usb_monitor.start()

    while True:
        # on consomme les messages pour éviter que la queue gonfle
        while not message_queue.empty():
            msg = message_queue.get()
            logger.info("USB(headless): %s", msg)
        time.sleep(1)

def main():
    message_queue = queue.Queue()
    usb_monitor = USBMonitor(message_queue=message_queue)
    usb_monitor.start()

    root = tk.Tk()
    root.withdraw()

    def process_queue():
        while not message_queue.empty():
            message = message_queue.get()
            messagebox.showinfo("Information", message)
        root.after(100, process_queue)

    root.after(100, process_queue)
    root.mainloop()


if __name__ == "__main__":
    main()
