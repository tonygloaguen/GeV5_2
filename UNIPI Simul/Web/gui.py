"""
Web/gui.py — Interface graphique Tkinter du simulateur UniPi 1.1
═══════════════════════════════════════════════════════════════
Affichage adapté au projet GeV5 :

  ┌──────────────────────────────┐  ┌──────────────────────────────┐
  │  ENTRÉES DIGITALES           │  │  SORTIES RELAIS              │
  │                              │  │                              │
  │  DI3  ● Cellule S1     [▶]  │  │  RO1  ● Défaut (séc+)       │
  │  DI4  ● Cellule S2     [▶]  │  │  RO2  ● Cellule             │
  │  DI5  ● Acquittement   [▶]  │  │  RO3  ● Alarme N1           │
  │  ─────────────────────────── │  │  RO4  ● Alarme N2           │
  │  DI1..DI14 (autres)         │  │  RO5  ● Défaut (séc+)       │
  └──────────────────────────────┘  │  RO6  ● Alarme              │
                                    │  RO7  ● Alarme N2           │
  ┌──────────────────────────────┐  │  RO8  ● Cellule             │
  │  📋 Journal (EVOK + I/O)    │  └──────────────────────────────┘
  └──────────────────────────────┘

Les RO sont pilotées par GeV5 via WebSocket → lecture seule dans la GUI.
Les DI sont simulées par l'opérateur via la GUI → lues par GeV5 via REST.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

from API import UniPiAPI


# ── Labels GeV5 ────────────────────────────────────────────
DI_GEV5 = {
    3: "Cellule S1",
    4: "Cellule S2",
    5: "Acquittement",
}
DI_PRIORITY = [3, 4, 5]  # DI affichées en premier (section prioritaire)

RO_GEV5 = {
    1: "Défaut (séc+)",
    2: "Cellule",
    3: "Alarme N1",
    4: "Alarme N2",
    5: "Défaut (séc+)",
    6: "Alarme",
    7: "Alarme N2",
    8: "Cellule",
}


class UniPiGUI:
    """Interface Tkinter adaptée GeV5. Communique uniquement via l'API."""

    # ── Palette ─────────────────────────────────────────
    BG       = "#1e1e2e"
    PANEL    = "#2a2a3d"
    TEXT     = "#cdd6f4"
    ON       = "#a6e3a1"
    OFF      = "#585b70"
    RELAY_ON = "#f9e2af"
    BTN_DI   = "#89b4fa"
    BTN_RO   = "#fab387"
    HEADER   = "#b4befe"
    LOG_BG   = "#11111b"
    BORDER   = "#45475a"
    ACCENT   = "#f38ba8"
    WARN     = "#f9e2af"

    REFRESH_MS = 100

    def __init__(self, api: UniPiAPI, title: str = "UniPi 1.1 — Simulateur GeV5"):
        self._api = api
        self._title = title
        self._running = False
        self._root: Optional[tk.Tk] = None

        self._di_indicators: dict = {}
        self._di_labels: dict = {}
        self._ro_indicators: dict = {}
        self._ro_labels: dict = {}
        self._log_text: Optional[tk.Text] = None
        self._log_buffer: list = []
        self._evok_status_lbl = None

        self._api.on_di_change(self._cb_di)
        self._api.on_ro_change(self._cb_ro)

    # ═══════════════════════════════════════════════════════
    #  CONSTRUCTION
    # ═══════════════════════════════════════════════════════

    def _build(self):
        root = tk.Tk()
        root.title(self._title)
        root.configure(bg=self.BG)
        root.resizable(True, True)
        root.minsize(900, 680)
        self._root = root

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT,
                         font=("Consolas", 10))
        style.configure("Header.TLabel", background=self.PANEL,
                         foreground=self.HEADER, font=("Consolas", 13, "bold"))
        style.configure("Sub.TLabel", background=self.PANEL,
                         foreground=self.OFF, font=("Consolas", 8))
        style.configure("Status.TLabel", background=self.PANEL,
                         foreground=self.TEXT, font=("Consolas", 9))

        # Barre de titre
        self._build_titlebar(root)

        # Conteneur principal
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=10, pady=5)

        # Colonne gauche : DI
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self._build_di_priority(left)
        self._build_di_others(left)

        # Séparateur
        tk.Frame(main, bg=self.BORDER, width=2).pack(side="left", fill="y", padx=5)

        # Colonne droite : RO
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self._build_ro_panel(right)

        # Journal
        self._build_log(root)

        # Barre statut
        self._build_statusbar(root)

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Barre titre ─────────────────────────────────────

    def _build_titlebar(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=10, pady=(10, 5))

        tk.Label(f, text="🔌  SIMULATEUR  UniPi 1.1  —  GeV5",
                  bg=self.BG, fg=self.HEADER,
                  font=("Consolas", 15, "bold")).pack(side="left")

        tk.Button(f, text="⟳ RESET", command=self._action_reset,
                   bg=self.ACCENT, fg="#1e1e2e", font=("Consolas", 10, "bold"),
                   relief="flat", padx=10, cursor="hand2").pack(side="right")

    # ── DI prioritaires (S1, S2, ACK) ──────────────────

    def _build_di_priority(self, parent):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill="x", padx=0, pady=(0, 5))

        ttk.Label(frame, text="📥  ENTRÉES GeV5 (DI prioritaires)",
                   style="Header.TLabel").pack(pady=(10, 2))
        ttk.Label(frame, text="Cliquez pour simuler un capteur / bouton",
                   style="Sub.TLabel").pack()

        grid = ttk.Frame(frame, style="Panel.TFrame")
        grid.pack(padx=10, pady=10, fill="x")
        grid.columnconfigure(0, weight=1)

        for row, di_idx in enumerate(DI_PRIORITY):
            label = DI_GEV5.get(di_idx, f"DI{di_idx}")
            self._build_di_row(grid, row, di_idx, label, priority=True)

    # ── DI secondaires (DI1..14 sauf 3,4,5) ────────────

    def _build_di_others(self, parent):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill="both", expand=True, padx=0, pady=(5, 0))

        ttk.Label(frame, text="📥  Autres entrées (DI)",
                   style="Header.TLabel").pack(pady=(8, 2))

        grid = ttk.Frame(frame, style="Panel.TFrame")
        grid.pack(padx=10, pady=5, fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        others = [i for i in range(1, self._api.NB_DI + 1) if i not in DI_PRIORITY]
        for pos, di_idx in enumerate(others):
            r, c = divmod(pos, 2)
            cell = tk.Frame(grid, bg=self.PANEL)
            cell.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
            self._build_di_row(cell, 0, di_idx, f"DI{di_idx}", priority=False, inline=True)

    def _build_di_row(self, parent, row, di_idx, label, priority=False, inline=False):
        """Construit une ligne DI : LED + label + bouton toggle."""
        if inline:
            cell = parent
        else:
            cell = tk.Frame(parent, bg=self.PANEL)
            cell.grid(row=row, column=0, padx=5, pady=4, sticky="ew")

        # LED
        size = 20 if priority else 16
        canvas = tk.Canvas(cell, width=size, height=size,
                            bg=self.PANEL, highlightthickness=0)
        canvas.pack(side="left", padx=(8, 4))
        m = size - 2
        canvas.create_oval(2, 2, m, m, fill=self.OFF, outline=self.BORDER, tags="led")
        self._di_indicators[di_idx] = canvas

        # Label
        font = ("Consolas", 11 if priority else 9)
        w = 22 if priority else 14
        lbl = tk.Label(cell, text=f"DI{di_idx}: OFF  {label}",
                        bg=self.PANEL, fg=self.TEXT, font=font,
                        width=w, anchor="w")
        lbl.pack(side="left")
        self._di_labels[di_idx] = (lbl, label)

        # Bouton
        btn_font = ("Consolas", 9 if priority else 7, "bold")
        tk.Button(
            cell, text="Toggle",
            bg=self.BTN_DI, fg="#1e1e2e", font=btn_font,
            relief="flat", padx=6, cursor="hand2",
            command=lambda idx=di_idx: self._api.toggle_di(idx)
        ).pack(side="right", padx=5)

    # ── RO (pilotées par GeV5 via WS) ──────────────────

    def _build_ro_panel(self, parent):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="📤  SORTIES RELAIS (RO)",
                   style="Header.TLabel").pack(pady=(10, 2))
        ttk.Label(frame, text="Pilotées par GeV5 via WebSocket — lecture seule",
                   style="Sub.TLabel").pack()

        grid = ttk.Frame(frame, style="Panel.TFrame")
        grid.pack(padx=10, pady=10, fill="both", expand=True)
        grid.columnconfigure(0, weight=1)

        for i in range(1, self._api.NB_RO + 1):
            label = RO_GEV5.get(i, "")
            cell = tk.Frame(grid, bg=self.PANEL)
            cell.grid(row=i - 1, column=0, padx=5, pady=3, sticky="ew")

            # LED
            canvas = tk.Canvas(cell, width=20, height=20,
                                bg=self.PANEL, highlightthickness=0)
            canvas.pack(side="left", padx=(8, 4))
            canvas.create_oval(2, 2, 18, 18, fill=self.OFF,
                                outline=self.BORDER, tags="led")
            self._ro_indicators[i] = canvas

            # Label
            lbl = tk.Label(cell, text=f"RO{i}: OFF  {label}",
                            bg=self.PANEL, fg=self.TEXT,
                            font=("Consolas", 11), width=28, anchor="w")
            lbl.pack(side="left")
            self._ro_labels[i] = (lbl, label)

            # Bouton forçage manuel (optionnel, utile pour debug)
            tk.Button(
                cell, text="Force",
                bg=self.BTN_RO, fg="#1e1e2e",
                font=("Consolas", 7, "bold"), relief="flat",
                padx=4, cursor="hand2",
                command=lambda idx=i: self._api.toggle_ro(idx)
            ).pack(side="right", padx=5)

    # ── Journal ─────────────────────────────────────────

    def _build_log(self, parent):
        frame = tk.Frame(parent, bg=self.BORDER)
        frame.pack(fill="x", padx=10, pady=5)

        tk.Label(frame, text="📋 Journal EVOK + I/O",
                  bg=self.LOG_BG, fg=self.HEADER,
                  font=("Consolas", 9, "bold"), anchor="w"
                  ).pack(fill="x", padx=1, pady=(1, 0))

        self._log_text = tk.Text(
            frame, height=7, bg=self.LOG_BG, fg=self.TEXT,
            font=("Consolas", 9), relief="flat", state="disabled",
            wrap="word", padx=5, pady=3
        )
        self._log_text.pack(fill="x", padx=1, pady=(0, 1))

        self._log_text.tag_configure("di_on",  foreground=self.ON)
        self._log_text.tag_configure("di_off", foreground=self.OFF)
        self._log_text.tag_configure("ro_on",  foreground=self.RELAY_ON)
        self._log_text.tag_configure("ro_off", foreground=self.OFF)
        self._log_text.tag_configure("evok",   foreground="#89b4fa")
        self._log_text.tag_configure("info",   foreground="#cba6f7")

    # ── Barre statut ────────────────────────────────────

    def _build_statusbar(self, parent):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill="x", padx=10, pady=(0, 10))

        self._evok_status_lbl = ttk.Label(
            frame,
            text="  EVOK :8080 — En attente de connexion GeV5…",
            style="Status.TLabel"
        )
        self._evok_status_lbl.pack(fill="x", padx=5, pady=3)

    # ═══════════════════════════════════════════════════════
    #  CALLBACKS → journal
    # ═══════════════════════════════════════════════════════

    def _cb_di(self, index: int, state: bool):
        label = DI_GEV5.get(index, "")
        s = "ON  ▲" if state else "OFF ▼"
        tag = "di_on" if state else "di_off"
        self._log(f"DI{index:02d} → {s}  {label}", tag)

    def _cb_ro(self, index: int, state: bool):
        label = RO_GEV5.get(index, "")
        s = "ON  ▲" if state else "OFF ▼"
        tag = "ro_on" if state else "ro_off"
        self._log(f"RO{index:02d} → {s}  {label}", tag)

    def log_evok(self, msg: str):
        """Appelé par le serveur EVOK pour afficher des messages."""
        self._log(f"[EVOK] {msg}", "evok")

    def _log(self, message: str, tag: str = "info"):
        ts = time.strftime("%H:%M:%S")
        self._log_buffer.append((f"[{ts}] {message}\n", tag))

    # ═══════════════════════════════════════════════════════
    #  ACTIONS
    # ═══════════════════════════════════════════════════════

    def _action_reset(self):
        self._api.reset()
        self._log("RESET — Toutes les I/O remises à zéro", "info")

    # ═══════════════════════════════════════════════════════
    #  RAFRAÎCHISSEMENT
    # ═══════════════════════════════════════════════════════

    def _refresh(self):
        if not self._running:
            return

        # DI
        for i in range(1, self._api.NB_DI + 1):
            if i not in self._di_indicators:
                continue
            state = self._api.read_di(i)
            color = self.ON if state else self.OFF
            self._di_indicators[i].itemconfig("led", fill=color)
            lbl_widget, lbl_text = self._di_labels[i]
            txt = " ON" if state else "OFF"
            lbl_widget.config(text=f"DI{i}: {txt}  {lbl_text}")

        # RO
        for i in range(1, self._api.NB_RO + 1):
            if i not in self._ro_indicators:
                continue
            state = self._api.read_ro(i)
            color = self.RELAY_ON if state else self.OFF
            self._ro_indicators[i].itemconfig("led", fill=color)
            lbl_widget, lbl_text = self._ro_labels[i]
            txt = " ON" if state else "OFF"
            lbl_widget.config(text=f"RO{i}: {txt}  {lbl_text}")

        # Journal
        if self._log_buffer:
            self._log_text.config(state="normal")
            for msg, tag in self._log_buffer:
                self._log_text.insert("end", msg, tag)
            self._log_text.see("end")
            self._log_text.config(state="disabled")
            self._log_buffer.clear()

        self._root.after(self.REFRESH_MS, self._refresh)

    # ═══════════════════════════════════════════════════════
    #  LANCEMENT
    # ═══════════════════════════════════════════════════════

    def run(self):
        """Bloquant — lance la boucle Tkinter."""
        self._build()
        self._running = True
        self._log("Simulateur UniPi 1.1 (GeV5) démarré", "info")
        self._log("En attente de connexion GeV5 sur :8080…", "evok")
        self._root.after(self.REFRESH_MS, self._refresh)
        self._root.mainloop()

    def run_threaded(self) -> threading.Thread:
        """Non-bloquant — GUI dans un thread daemon."""
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        time.sleep(0.5)
        return t

    def _on_close(self):
        self._running = False
        if self._root:
            self._root.destroy()

    @property
    def is_running(self) -> bool:
        return self._running
