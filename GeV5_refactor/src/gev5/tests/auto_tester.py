#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeV5 auto-tester – version atelier sous-traitant (WebSocket + fallback GPIO)
- Reboot simple
- Qualification guidée (pré-requis + relais + comptage + DI I3/I4/I5)
- Tests manuels sorties/entrées
- Fenêtre principale non fermable
Dépendances: pigpio (pigpiod), websocket-client, tkinter
"""

import os, time, shutil, threading, json
import tkinter as tk
from tkinter import messagebox, ttk
import pigpio
import websocket
import gettext

# ---------- i18n ----------
_ = gettext.gettext
def init_i18n():
    try:
        with open('lang.lng', 'r', encoding='utf-8') as f:
            lng = f.read().strip()
    except Exception:
        lng = 'FR'
    locales = {'English':('en_GB',['en']),'Spanish':('es_ES',['es']),
               'German':('de_DE',['de']),'Português':('pt_PT',['pt'])}
    try:
        if lng in locales:
            dom, langs = locales[lng]
            tr = gettext.translation(dom, localedir='/home/pi/GeV45/locales', languages=langs)
            tr.install(); return tr.gettext
        else:
            gettext.install('None'); return gettext.gettext
    except Exception:
        gettext.install('None'); return gettext.gettext
_ = init_i18n()

# ---------- Paramètres matériels ----------
# Mapping I3/I4/I5 -> GPIO BCM (selon ta conf DI_3/DI_4/DI_5)
DI_GPIO_MAP = {3: 27, 4: 23, 5: 22}

# ---------- EVOK WebSocket ----------
WS_URL = "ws://127.0.0.1:8080/ws"

def _json(v):
    try: return json.loads(v)
    except Exception: return v

def ws_send(payload, timeout=1.0):
    """Fire-and-forget (pour cmd='set') : EVOK peut ne rien renvoyer."""
    ws = websocket.WebSocket()
    ws.settimeout(timeout)
    ws.connect(WS_URL)
    ws.send(json.dumps(payload))
    ws.close()
    return True

# === CORRECTION 1: ws_call lit plusieurs trames et agrège (dict/list/data[]) ===
def ws_call(payload, timeout=1.5, listen_window=0.6):
    """Appel avec réception multi-trames. Retourne une liste d'objets dict."""
    ws = websocket.create_connection(WS_URL, timeout=timeout)
    ws.send(json.dumps(payload))
    end = time.time() + listen_window
    out = []
    while time.time() < end:
        try:
            msg = ws.recv()
        except Exception:
            break
        try:
            data = json.loads(msg)
        except Exception:
            continue
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                out.extend([it for it in data["data"] if isinstance(it, dict)])
            else:
                out.append(data)
        elif isinstance(data, list):
            out.extend([it for it in data if isinstance(it, dict)])
    ws.close()
    return out

def ws_set_relay(circuit, value: int):
    return ws_send({"cmd":"set","dev":"relay","circuit":str(circuit),"value":str(int(value))})

def ws_get_relays():
    """Découvre les relais exposés; fallback 1..8 si vide/non listable."""
    try:
        resp = ws_call({"cmd":"get","dev":"relay"}, timeout=1.0)
        if isinstance(resp, list):
            cs = [str(it.get("circuit")) for it in resp
                  if isinstance(it, dict) and it.get("dev")=="relay" and it.get("circuit") is not None]
            if cs: return cs
    except Exception:
        pass
    return [str(i) for i in range(1, 9)]

# === CORRECTION 2: ws_get_inputs_map robuste (all -> get input -> get di) ===
def ws_get_inputs_map(timeout=1.2):
    """Lit toutes les entrées via WS (dev='input' sinon 'di'). Retourne {circuit:int}."""
    mp = {}

    # 1) snapshot complet
    try:
        frames = ws_call({"cmd":"all"}, timeout=timeout, listen_window=0.8)
        for it in frames:
            if isinstance(it, dict) and it.get("dev") in ("input","di"):
                c, v = it.get("circuit"), it.get("value")
                try: mp[int(c)] = int(v)
                except Exception: pass
        if mp:
            return mp
    except Exception:
        pass

    # 2) liste des inputs
    try:
        frames = ws_call({"cmd":"get","dev":"input"}, timeout=timeout, listen_window=0.8)
        for it in frames:
            if isinstance(it, dict) and it.get("dev") in ("input","di"):
                c, v = it.get("circuit"), it.get("value")
                try: mp[int(c)] = int(v)
                except Exception: pass
        if mp:
            return mp
    except Exception:
        pass

    # 3) fallback "di"
    try:
        frames = ws_call({"cmd":"get","dev":"di"}, timeout=timeout, listen_window=0.8)
        for it in frames:
            if isinstance(it, dict) and it.get("dev") in ("input","di"):
                c, v = it.get("circuit"), it.get("value")
                try: mp[int(c)] = int(v)
                except Exception: pass
        if mp:
            return mp
    except Exception:
        pass

    # 4) dernier filet: interrogations ciblées (I3/I4/I5)
    mp = {}
    for c in (3,4,5):
        try:
            frames = ws_call({"cmd":"get","dev":"input","circuit":int(c)}, timeout=timeout, listen_window=0.5)
            for it in frames:
                if isinstance(it, dict) and it.get("dev") in ("input","di"):
                    try: mp[int(it.get("circuit"))] = int(it.get("value"))
                    except Exception: pass
        except Exception:
            continue
    if mp:
        return mp

    raise TimeoutError("inputs get timed out")

# ---------- Fallback GPIO (pigpio) ----------
# === CORRECTION 3: ne force pas PUD_DOWN par défaut (laisse la polarisation terrain) ===
def gpio_prepare_inputs(pi, channels=DI_GPIO_MAP):
    for _, gpio in channels.items():
        try:
            pi.set_mode(gpio, pigpio.INPUT)
            pi.set_pull_up_down(gpio, pigpio.PUD_OFF)
        except Exception:
            pass

def gpio_read_inputs(pi, channels=DI_GPIO_MAP):
    """Retourne {3:0/1, 4:0/1, 5:0/1} en lisant les GPIO."""
    mp = {}
    for ch, gpio in channels.items():
        try: mp[ch] = int(pi.read(gpio))
        except Exception: mp[ch] = None
    return mp

def read_inputs(pi, channels=(3,4,5), ws_timeout=1.2):
    """Tente WS, sinon bascule en pigpio GPIO direct."""
    try:
        mp = ws_get_inputs_map(timeout=ws_timeout)
        return {ch: mp.get(ch, None) for ch in channels}
    except Exception:
        return gpio_read_inputs(pi, {ch: DI_GPIO_MAP[ch] for ch in channels if ch in DI_GPIO_MAP})

# ============================================================
#                    APPLICATION TKINTER
# ============================================================

class AutoTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title('GeV5 auto-tester')
        self.root.geometry("460x500")
        # Fenêtre principale NON fermable
        self.root.protocol("WM_DELETE_WINDOW", self._block_close)

        # pigpio unique
        self.pi = pigpio.pi()
        if not self.pi.connected:
            messagebox.showerror("pigpio", _("Impossible de se connecter à pigpio (pigpiod lancé ?)."))
            self.root.destroy(); return

        # Prépare GPIO pour fallback
        gpio_prepare_inputs(self.pi)

        self.windows = []
        self.threads = []
        self.running = True

        self._build_main()

    def _block_close(self):
        messagebox.showwarning(_("Action bloquée"),
                               _("La fenêtre principale ne peut pas être fermée pendant l'atelier.\nUtilisez les boutons dédiés."))

    def _build_main(self):
        pad = {"padx": 10, "pady": 8}
        ttk.Style().configure("TButton", padding=6)

        ttk.Label(self.root, text=_("Utilitaires de test pour banc sous-traitant"),
                  font=("Arial", 11, "bold")).pack(pady=10)

        ttk.Button(self.root, text=_("Comptage IO6/IO18 vers IO26/IO16"),
                   command=lambda: self.open_counting_window(E1=26, E2=16, S1=6, S2=18)).pack(**pad)

        ttk.Button(self.root, text=_("Test des sorties (relais)"),
                   command=self.open_output_tester).pack(**pad)
        ttk.Button(self.root, text=_("Test des entrées (I3/I4/I5)"),
                   command=self.open_input_tester).pack(**pad)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", pady=6)

        ttk.Button(self.root, text=_("Qualification complète (guidée)"),
                   command=self.start_full_qualification).pack(**pad)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", pady=6)

        ttk.Button(self.root, text=_("Numéro de série CPU"),
                   command=self.open_serial_window).pack(**pad)
        ttk.Button(self.root, text=_("Nettoyage du Pi"),
                   command=self.open_cleanup_dialog).pack(**pad)
        ttk.Button(self.root, text=_("Redémarrer (Reboot)"),
                   command=self.reboot_now).pack(**pad)

    # ---------- Reboot ----------
    def reboot_now(self):
        if messagebox.askyesno(_("Confirmation"), _("Redémarrer maintenant ?")):
            os.system('sudo reboot')

    # ---------- Comptage ----------
    def open_counting_window(self, E1, E2, S1, S2):
        win = tk.Toplevel(self.root); self.windows.append(win)
        win.title(_("Test du comptage {}/{} vers {}/{}").format(S1, S2, E1, E2))
        win.geometry("560x170")

        ttk.Label(win, text=_("Fréq. sortie S1/S2 = 800 Hz, PWM=50% (simulation de comptage)"),
                  wraplength=520).pack(pady=4)
        lblA = ttk.Label(win, text=_("Voie A: -- cps / Δ -- %"), font=("Consolas", 11))
        lblB = ttk.Label(win, text=_("Voie B: -- cps / Δ -- %"), font=("Consolas", 11))
        lblA.pack(pady=2); lblB.pack(pady=2)

        for E in (E1, E2):
            self.pi.set_mode(E, pigpio.INPUT); self.pi.set_pull_up_down(E, pigpio.PUD_OFF)
        for S in (S1, S2):
            self.pi.set_mode(S, pigpio.OUTPUT); self.pi.set_PWM_frequency(S, 800); self.pi.set_PWM_dutycycle(S, 128)

        state = {"A_cnt":0, "B_cnt":0, "A_prev":None, "B_prev":None, "last":time.time()}
        def cbA(gpio, level, tick): state["A_cnt"] += 1
        def cbB(gpio, level, tick): state["B_cnt"] += 1
        cb_a = self.pi.callback(E1, pigpio.FALLING_EDGE, cbA)
        cb_b = self.pi.callback(E2, pigpio.FALLING_EDGE, cbB)

        def update_labels():
            if not self.running or not win.winfo_exists():
                cb_a.cancel(); cb_b.cancel()
                for S in (S1, S2): self.pi.set_PWM_dutycycle(S, 0)
                return
            now = time.time(); dt = max(0.001, now - state["last"])
            A_cps = state["A_cnt"]/dt; B_cps = state["B_cnt"]/dt
            def var(prev, cur):
                try:
                    if prev is None or cur == 0: return "N.A."
                    return round(100 - 100*(prev/cur), 1)
                except Exception:
                    return "N.A."
            dA = var(state["A_prev"], A_cps); dB = var(state["B_prev"], B_cps)
            lblA.configure(text=f"Voie A: {A_cps:.1f} cps / Δ {dA} %")
            lblB.configure(text=f"Voie B: {B_cps:.1f} cps / Δ {dB} %")
            state["A_prev"], state["B_prev"] = A_cps, B_cps
            state["A_cnt"] = state["B_cnt"] = 0; state["last"] = now
            win.after(200, update_labels)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_count_window(win, cb_a, cb_b, (S1, S2)))
        update_labels()

    def _close_count_window(self, win, cb_a, cb_b, Sout):
        try: cb_a.cancel(); cb_b.cancel()
        except Exception: pass
        try:
            for S in Sout: self.pi.set_PWM_dutycycle(S, 0)
        except Exception: pass
        win.destroy()

    # ---------- Test sorties ----------
    def open_output_tester(self):
        win = tk.Toplevel(self.root); self.windows.append(win)
        win.title(_("Test des sorties (relais EVOK)"))
        win.geometry("520x280")

        ttk.Label(win, text=_("Cycle ON→OFF sur relais 1..8, 1 s ON / 0.1 s OFF (4 passes)")).pack(pady=6)
        pb  = ttk.Progressbar(win, length=460, mode="determinate"); pb.pack(pady=8)
        log = tk.Text(win, height=10, width=68); log.pack(padx=8, pady=6)
        running = {"stop": False}

        def try_set(c, v, attempts=2):
            last = None
            for _ in range(attempts):
                try:
                    ws_set_relay(c, v); return True
                except Exception as e:
                    last = e; time.sleep(0.1)
            raise last

        def worker():
            try:
                circuits = ws_get_relays()
                total_steps = 4*len(circuits)*2
                pb.configure(maximum=total_steps)
                count = 0
                for _ in range(4):
                    if running["stop"] or not self.running: break
                    for c in circuits:
                        if running["stop"] or not self.running: break
                        try_set(c, 1); self._log_text(log, f"Relay {c} -> ON"); self._set_pb(pb, count := count+1)
                        time.sleep(1.0)
                    for c in circuits:
                        if running["stop"] or not self.running: break
                        try_set(c, 0); self._log_text(log, f"Relay {c} -> OFF"); self._set_pb(pb, count := count+1)
                        time.sleep(0.1)
                self._log_text(log, _("Terminé."))
            except Exception as e:
                self._log_text(log, f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()
        win.protocol("WM_DELETE_WINDOW", lambda: (running.update({"stop": True}), win.destroy()))

    # ---------- Test entrées ----------
    def open_input_tester(self):
        win = tk.Toplevel(self.root); self.windows.append(win)
        win.title(_("Test des entrées digitales"))
        win.geometry("460x230")

        status = ttk.Label(win, text="", foreground="red"); status.pack(pady=2)
        lbl1 = ttk.Label(win, text=_('Cellule 1 (I3 carte Automate) = --')); lbl1.pack(pady=2)
        lbl2 = ttk.Label(win, text=_('Cellule 2 (I4 carte Automate) = --')); lbl2.pack(pady=2)
        lbl3 = ttk.Label(win, text=_("Entrée Acq (I5 carte Automate) = --"));  lbl3.pack(pady=2)
        alive = {"ok": True}

        def poll():
            if not alive["ok"] or not self.running or not win.winfo_exists(): return
            mp = read_inputs(self.pi, channels=(3,4,5), ws_timeout=1.0)
            if all(v is None for v in mp.values()):
                status.configure(text="ERR WS/GPIO: aucune lecture possible")
            else:
                status.configure(text="")
            c1 = mp.get(3, "--"); c2 = mp.get(4, "--"); c3 = mp.get(5, "--")
            lbl1.configure(text=_('Cellule 1 (I3 carte Automate) = {}').format(c1 if c1 is not None else "--"))
            lbl2.configure(text=_('Cellule 2 (I4 carte Automate) = {}').format(c2 if c2 is not None else "--"))
            lbl3.configure(text=_('Entrée Acq (I5 carte Automate) = {}').format(c3 if c3 is not None else "--"))
            win.after(300, poll)

        win.protocol("WM_DELETE_WINDOW", lambda: (alive.update({"ok": False}), win.destroy()))
        poll()

    # ---------- Qualification complète ----------
    def _qualify_relays_quick(self, log_widget, passes=2, ton=0.3, toff=0.1):
        """Cycle rapide des relais via WS. True si aucune erreur."""
        try:
            circuits = ws_get_relays()
            self._log_text(log_widget, f"Relais détectés: {', '.join(circuits)}")
            for _ in range(passes):
                for c in circuits: ws_set_relay(c, 1); time.sleep(ton)
                for c in circuits: ws_set_relay(c, 0); time.sleep(toff)
            return True
        except Exception as e:
            self._log_text(log_widget, f"Erreur relais: {e}")
            return False

    def start_full_qualification(self):
        prereq = "\n".join([
            "PRÉREQUIS avant de commencer :",
            "  • Mettre un strap entre S1 et E1",
            "  • Mettre un strap entre S2 et E2",
            "  • Préparer (sans brancher) un strap 5V pour injection sur I3, I4, I5",
            "",
            "Pendant la séquence, l’outil demandera d’appliquer le 5V successivement sur I3 puis I4 puis I5."
        ])
        messagebox.showinfo(_("Qualification complète"), prereq)
        if not messagebox.askyesno(_("Confirmation"), _("Prêt à commencer la qualification ?")):
            return

        win = tk.Toplevel(self.root); self.windows.append(win)
        win.title(_("Qualification complète – en cours"))
        win.geometry("620x400")

        # 6 étapes: [1] Vérifs, [2] Relais, [3] Comptage, [4] I3, [5] I4, [6] I5
        pb  = ttk.Progressbar(win, length=580, mode="determinate", maximum=6); pb.pack(pady=8)
        log = tk.Text(win, height=16, width=82); log.pack(padx=8, pady=6)

        result = {"verifs": False, "relais": False, "comptage": False, "I3": False, "I4": False, "I5": False, "final": False}

        def worker():
            ok_all = True

            # [1/6] Vérifs
            self._log_text(log, _("[1/6] Vérifications préalables (pigpio/EVOK)…"))
            try:
                ping = read_inputs(self.pi, channels=(3,4,5), ws_timeout=1.0)
                self._log_text(log, f"Entrées OK (WS/GPIO): {ping}")
                result["verifs"] = True
            except Exception as e:
                self._log_text(log, f"Entrées indisponibles: {e}")
                ok_all = False
            self._set_pb(pb, 1)

            # [2/6] Relais
            self._log_text(log, _("[2/6] Test relais – 2 passes ON/OFF…"))
            result["relais"] = self._qualify_relays_quick(log, passes=2, ton=0.3, toff=0.1)
            self._log_text(log, "Relais: " + ("OK" if result["relais"] else "KO"))
            if not result["relais"]: ok_all = False
            self._set_pb(pb, 2)

            # [3/6] Comptage
            self._log_text(log, _("[3/6] Test comptage S1/S2 -> E1/E2 à 800 Hz…"))
            try:
                A_cps, B_cps = self._quick_count_test(E1=26, E2=16, S1=6, S2=18, duration_s=1.2)
                self._log_text(log, f"Mesure: A={A_cps:.1f} cps, B={B_cps:.1f} cps")
                result["comptage"] = (A_cps > 50 and B_cps > 50)
                self._log_text(log, ("OK" if result["comptage"] else "KO") + " – seuil 50 cps")
            except Exception as e:
                self._log_text(log, f"Erreur test comptage: {e}")
                ok_all = False
            self._set_pb(pb, 3)

            # [4..6] DI I3/I4/I5
            for step, (idx, name) in enumerate([(3,"I3"), (4,"I4"), (5,"I5")], start=4):
                if not self.running: return
                self._log_text(log, _("[{}/6] Préparer l’injection 5V sur {}…").format(step, name))
                try:
                    initial = read_inputs(self.pi, channels=(idx,), ws_timeout=1.0).get(idx, 0)
                    self._log_text(log, f"{name} état initial = {initial}")
                except Exception as e:
                    self._log_text(log, f"ERR lecture {name}: {e}")
                    ok_all = False; self._set_pb(pb, step); continue

                if not messagebox.askokcancel(_("Injection 5V requise"),
                                              _("Appliquer maintenant le 5V sur {} puis cliquer OK").format(name),
                                              parent=win):
                    self._log_text(log, f"{name} – étape annulée par l’opérateur")
                    ok_all = False; self._set_pb(pb, step); continue

                passed = False; t0 = time.time()
                while time.time()-t0 < 10 and self.running:
                    try:
                        val = read_inputs(self.pi, channels=(idx,), ws_timeout=0.8).get(idx, 0)
                        if val == 1:
                            passed = True; break
                    except Exception:
                        pass
                    time.sleep(0.2)
                result[name] = passed
                self._log_text(log, f"{name} -> {'OK (1 détecté)' if passed else 'KO (pas de 1 détecté)'}")
                if not passed: ok_all = False
                self._set_pb(pb, step)

            result["final"] = ok_all and all([result[k] for k in ("verifs","relais","comptage","I3","I4","I5")])
            self._log_text(log, "\n=== RÉSUMÉ ===")
            self._log_text(log, f"Vérifs: {'OK' if result['verifs'] else 'KO'}  |  Relais: {'OK' if result['relais'] else 'KO'}  |  Comptage: {'OK' if result['comptage'] else 'KO'}")
            self._log_text(log, f"I3: {'OK' if result['I3'] else 'KO'}  |  I4: {'OK' if result['I4'] else 'KO'}  |  I5: {'OK' if result['I5'] else 'KO'}")
            self._log_text(log, f"\nQUALIFICATION: {'OK' if result['final'] else 'KO'}")
            messagebox.showinfo(_("Qualification terminée"),
                                _("Résultat: {}\n\nConsultez le log pour le détail.")
                                .format('OK' if result['final'] else 'KO'),
                                parent=win)

        threading.Thread(target=worker, daemon=True).start()

    def _quick_count_test(self, E1, E2, S1, S2, duration_s=1.0):
        for E in (E1, E2):
            self.pi.set_mode(E, pigpio.INPUT); self.pi.set_pull_up_down(E, pigpio.PUD_OFF)
        for S in (S1, S2):
            self.pi.set_mode(S, pigpio.OUTPUT); self.pi.set_PWM_frequency(S, 800); self.pi.set_PWM_dutycycle(S, 128)
        counts = {"A":0, "B":0}
        def cbA(gpio, level, tick): counts["A"] += 1
        def cbB(gpio, level, tick): counts["B"] += 1
        cb_a = self.pi.callback(E1, pigpio.FALLING_EDGE, cbA)
        cb_b = self.pi.callback(E2, pigpio.FALLING_EDGE, cbB)
        t0 = time.time()
        while time.time()-t0 < duration_s and self.running: time.sleep(0.05)
        cb_a.cancel(); cb_b.cancel()
        for S in (S1, S2): self.pi.set_PWM_dutycycle(S, 0)
        dt = max(0.001, time.time()-t0)
        return counts["A"]/dt, counts["B"]/dt

    # ---------- Numéro de série ----------
    def open_serial_window(self):
        win = tk.Toplevel(self.root); self.windows.append(win)
        win.title(_("Numéro de série")); win.geometry("520x110")
        serial = "ERROR000000000"
        try:
            with open('/proc/cpuinfo','r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip(); break
        except Exception as e:
            serial = f"ERR: {e}"
        ttk.Label(win, text=_("Numéro de série = {}").format(serial),
                  font=("Consolas", 12)).pack(pady=16)

    # ---------- Nettoyage ----------
    def open_cleanup_dialog(self):
        win = tk.Toplevel(self.root); self.windows.append(win)
        win.title(_("Nettoyage du Pi")); win.geometry("560x360")

        ttk.Label(win, text=_("Sélectionne les répertoires à vider :")).pack(pady=6)
        paths = [
            '/home/pi/Partage/rapports',
            '/home/pi/Partage/photo',
            '/home/pi/Partage/logs',
            '/home/pi/Partage/Export',
            '/home/pi/Partage/Base_donnees'
        ]
        vars_ = []
        for p in paths:
            v = tk.BooleanVar(value=True)
            ttk.Checkbutton(win, text=p, variable=v).pack(anchor="w", padx=12)
            vars_.append((v,p))
        wifi_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(win, text=_("Couper le Wi-Fi et effacer la conf wpa_supplicant"),
                        variable=wifi_var).pack(anchor="w", padx=12, pady=6)
        log = tk.Text(win, height=8, width=68); log.pack(padx=8, pady=6)

        def do_cleanup():
            if not messagebox.askyesno(_("Confirmation"),
                                       _("Action irréversible. Confirmer la suppression ?"),
                                       parent=win): return
            if not messagebox.askokcancel(_("Confirmation finale"),
                                          _("Vider les répertoires sélectionnés MAINTENANT ?"),
                                          parent=win): return
            for v, path in vars_:
                if not v.get(): continue
                if path in ['/', '/home', '/home/pi']:
                    self._log_text(log, f"BLK {path}"); continue
                if os.path.isdir(path):
                    try:
                        for name in os.listdir(path):
                            fp = os.path.join(path, name)
                            if os.path.isfile(fp) or os.path.islink(fp):
                                os.unlink(fp); self._log_text(log, f"DEL {fp}")
                            elif os.path.isdir(fp):
                                shutil.rmtree(fp); self._log_text(log, f"RMDIR {fp}")
                    except Exception as e:
                        self._log_text(log, f"ERR {path}: {e}")
                else:
                    self._log_text(log, f"SKIP {path} (absent)")
            if wifi_var.get():
                try:
                    os.system("sudo ifconfig wlan0 down")
                    os.system("sudo cp /dev/null /etc/wpa_supplicant/wpa_supplicant.conf")
                    self._log_text(log, "Wi-Fi OFF + conf effacée")
                except Exception as e:
                    self._log_text(log, f"ERR Wi-Fi: {e}")
            self._log_text(log, _("Nettoyage terminé."))
            self._post_cleanup_actions()

        ttk.Button(win, text=_("Lancer le nettoyage"), command=do_cleanup).pack(pady=6)

    def _post_cleanup_actions(self):
        act = tk.Toplevel(self.root)
        act.title(_("Actions après nettoyage")); act.geometry("300x150")
        ttk.Label(act, text=_("Que souhaitez-vous faire ?")).pack(pady=12)
        btnf = ttk.Frame(act); btnf.pack(pady=8)
        ttk.Button(btnf, text=_("Redémarrer"), command=lambda: os.system('sudo reboot')).grid(row=0, column=0, padx=10)
        ttk.Button(btnf, text=_("Éteindre"),    command=lambda: os.system('sudo poweroff')).grid(row=0, column=1, padx=10)

    # ---------- Utils ----------
    def _log_text(self, widget, line):
        try: widget.insert("end", line + "\n"); widget.see("end")
        except Exception: pass

    def _set_pb(self, pb, value):
        try: pb['value'] = value; pb.update_idletasks()
        except Exception: pass

def main():
    root = tk.Tk()
    app = AutoTesterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
