import threading
import time
import os
import sys
import websocket
from datetime import datetime

# ---- lecture CPU sans psutil ----
def _read_cpu_percent(interval=0.4):
    """Retourne l'utilisation CPU totale en % sur l'intervalle."""
    def read():
        with open("/proc/stat", "r") as f:
            line = f.readline()
        parts = line.split()
        # cpu  user nice system idle iowait irq softirq steal guest guest_nice
        vals = list(map(int, parts[1:]))
        idle = vals[3] + vals[4]
        total = sum(vals)
        return idle, total

    try:
        idle1, total1 = read()
        time.sleep(interval)
        idle2, total2 = read()
    except Exception:
        # si on n'arrive pas à lire, on renvoie 0 pour ne pas rebooter pour rien
        return 0.0

    idle_delta = idle2 - idle1
    total_delta = total2 - total1
    if total_delta <= 0:
        return 0.0
    usage = 100.0 * (1.0 - (idle_delta / total_delta))
    return usage


# Fonction pour surveiller les threads + le CPU
def monitor_threads():
    time.sleep(2)
    initial_threads = {t.name for t in threading.enumerate()}
    print(f"Nombre initial de threads : {len(initial_threads)}")

    # --- paramètres watchdog CPU ---
    CPU_THRESHOLD = 40.0          # % au-dessus duquel on considère que ça déconne
    CHECK_INTERVAL = 10           # on est déjà à 10 s dans ta boucle
    DURATION_SEC = 30 * 60        # 30 minutes
    MAX_OVER = DURATION_SEC // CHECK_INTERVAL   # 180 checks consécutifs

    cpu_over_count = 0

    while True:
        time.sleep(CHECK_INTERVAL)

        # --- 1) surveillance threads comme avant ---
        current_threads = {t.name for t in threading.enumerate()}
        missing_threads = initial_threads - current_threads

        if missing_threads:
            for thread_name in missing_threads:
                print(f"Thread KO détecté : {thread_name}")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Erreur serveur fatale, reboot en cours...")

                # Commande WebSocket vers Unipi
                try:
                    ws = websocket.WebSocket()
                    ws.connect("ws://127.0.0.1/ws")
                    ws.send('{"cmd":"set","dev":"relay","circuit":"1","value":"0"}')  # Défaut
                    ws.send('{"cmd":"set","dev":"relay","circuit":"5","value":"0"}')  # Défaut
                    ws.close()
                except Exception as e:
                    print(f"Erreur WebSocket : {e}")

                time.sleep(5)
                os.system("sudo reboot")

        # on met à jour la liste de référence
        initial_threads = current_threads

        # --- 2) watchdog CPU intégré ---
        cpu = _read_cpu_percent(0.4)
        # print(f"[WDG-CPU] {cpu:.1f}%")  # debug

        if cpu > CPU_THRESHOLD:
            cpu_over_count += 1
        else:
            # on redescend → on remet le compteur à zéro
            cpu_over_count = 0

        # si on a dépassé 30 min au-dessus de 50 %
        if cpu_over_count >= MAX_OVER:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] CPU > {CPU_THRESHOLD}% pendant 30 min -> reboot")

            # même séquence que pour le thread KO
            try:
                ws = websocket.WebSocket()
                ws.connect("ws://127.0.0.1/ws")
                ws.send('{"cmd":"set","dev":"relay","circuit":"1","value":"0"}')
                ws.send('{"cmd":"set","dev":"relay","circuit":"5","value":"0"}')
                ws.close()
            except Exception as e:
                print(f"Erreur WebSocket (CPU): {e}")

            time.sleep(5)
            os.system("sudo reboot")
