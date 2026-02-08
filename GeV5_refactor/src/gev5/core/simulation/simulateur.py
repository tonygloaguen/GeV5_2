#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simulateur.py — Compatible main.py (app = simulateur.Application(); app.mainloop())
- UI Tk confinée au thread principal (aucun worker)
- Cellules S1/S2: commande manuelle + passages simulés
- Passage manuel: vitesse en km/h, distance S1–S2 (m), longueur objet (m)
- Série aléatoire: nb passages, intervalle min/max (ms), vitesse min/max (km/h), sens aléatoire
- Multiplicateur global (impacte les modules de comptage) + presets
- Démarrage ≈ 1000 cps (multiplier = 0.10) si base=10k cps
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import random
import time

# 🔗 Cellules
try:
    from ...hardware import etat_cellule_1, etat_cellule_2  # type: ignore
except Exception:
    etat_cellule_1 = None
    etat_cellule_2 = None

# 🔗 Comptage (injection pulses)
try:
    from ...core.comptage.comptage import ComptageThread  # type: ignore
except Exception:
    ComptageThread = None


class Application(tk.Tk):
    # Variables exposées aux autres modules (inchangé)
    variable1  = {0: 0}      # Cellule S1 (0/1)
    variable2  = {0: 0}      # Cellule S2 (0/1)
    acqui      = {0: 0}      # Acquittement (impulsion)
    multiplier = {0: 0.10}   # Multiplicateur (~1000 cps au boot si base=10k)

    def __init__(self):
        super().__init__()
        self.title("Simulateur Portique (km/h + Aléatoire)")
        self.geometry("760x520")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Sécurité: impose 0.10 au boot
        Application.multiplier[0] = 0.10

        # État interne (aucun thread)
        self._rnd_left = 0

        # Moniteur simple
        self._last_action = tk.StringVar(value="(idle)")
        self._state_text  = tk.StringVar(value="S1=0  S2=0  mult=0.10")
        self._passages_count = 0

        # ---- Simulation comptage ----
        self._sim_base_cps = 10000.0   # base cps avant multiplier (0.10 => ~1000 cps)
        self._sim_dt_s = 0.10          # cadence d'injection (s) - à aligner sur sample_time idéalement

        self._build_ui()
        self._bind_keys()

        # Recalage éventuel si un autre module modifie multiplier au boot
        self.after(300, self._enforce_boot_multiplier)

        # Refresh UI
        self._refresh_ui()

        # Injection pulses (sans thread)
        self.after(100, self._inject_counts_tick)

    # ===================== UI =====================
    def _build_ui(self):
        padx, pady = 10, 8

        # --- Cellules & Passage manuel ---
        frm_cells = ttk.LabelFrame(self, text="Cellules / Passage manuel")
        frm_cells.grid(row=0, column=0, sticky="ew", padx=padx, pady=pady)

        self.var_s1 = tk.IntVar(value=Application.variable1[0])
        self.var_s2 = tk.IntVar(value=Application.variable2[0])

        ttk.Checkbutton(
            frm_cells, text="S1 (amont)", variable=self.var_s1, command=self._apply_s1
        ).grid(row=0, column=0, padx=6, pady=4, sticky="w")

        ttk.Checkbutton(
            frm_cells, text="S2 (aval)", variable=self.var_s2, command=self._apply_s2
        ).grid(row=0, column=1, padx=6, pady=4, sticky="w")

        p = ttk.Frame(frm_cells)
        p.grid(row=1, column=0, columnspan=3, sticky="w", pady=6)

        ttk.Label(p, text="Distance S1–S2 (m):").grid(row=0, column=0, sticky="e")
        self.dist_m = tk.DoubleVar(value=0.75)
        ttk.Entry(p, width=7, textvariable=self.dist_m).grid(row=0, column=1, padx=6)

        ttk.Label(p, text="Longueur objet (m):").grid(row=0, column=2, sticky="e")
        self.obj_m = tk.DoubleVar(value=10.0)
        ttk.Entry(p, width=7, textvariable=self.obj_m).grid(row=0, column=3, padx=6)

        ttk.Label(p, text="Vitesse (km/h):").grid(row=0, column=4, sticky="e")
        self.speed_kmh = tk.DoubleVar(value=6.0)
        ttk.Entry(p, width=7, textvariable=self.speed_kmh).grid(row=0, column=5, padx=6)

        ttk.Button(frm_cells, text="Passage 1 → 2", command=lambda: self._passage("12"))\
            .grid(row=2, column=0, padx=6, pady=4)
        ttk.Button(frm_cells, text="Passage 2 → 1", command=lambda: self._passage("21"))\
            .grid(row=2, column=1, padx=6, pady=4)

        ttk.Button(frm_cells, text="Pulse S1 (100ms)", command=lambda: self._test_pulse("S1"))\
            .grid(row=3, column=0, padx=6, pady=2)
        ttk.Button(frm_cells, text="Pulse S2 (100ms)", command=lambda: self._test_pulse("S2"))\
            .grid(row=3, column=1, padx=6, pady=2)

        # --- Série aléatoire ---
        frm_rand = ttk.LabelFrame(self, text="Série aléatoire (vitesses en km/h)")
        frm_rand.grid(row=1, column=0, sticky="ew", padx=padx, pady=pady)

        self.nb_passages = tk.IntVar(value=1)
        self.gap_min_ms  = tk.IntVar(value=3000)
        self.gap_max_ms  = tk.IntVar(value=3000)
        self.vmin_kmh    = tk.DoubleVar(value=3.0)
        self.vmax_kmh    = tk.DoubleVar(value=10.0)
        self.rand_dir    = tk.BooleanVar(value=True)

        ttk.Label(frm_rand, text="Nb:").grid(row=0, column=0, sticky="e")
        ttk.Entry(frm_rand, width=6, textvariable=self.nb_passages).grid(row=0, column=1, padx=4)
        ttk.Label(frm_rand, text="Intervalle min (ms):").grid(row=0, column=2, sticky="e")
        ttk.Entry(frm_rand, width=7, textvariable=self.gap_min_ms).grid(row=0, column=3, padx=4)
        ttk.Label(frm_rand, text="max:").grid(row=0, column=4, sticky="e")
        ttk.Entry(frm_rand, width=7, textvariable=self.gap_max_ms).grid(row=0, column=5, padx=4)

        ttk.Label(frm_rand, text="V min (km/h):").grid(row=1, column=0, sticky="e")
        ttk.Entry(frm_rand, width=6, textvariable=self.vmin_kmh).grid(row=1, column=1, padx=4)
        ttk.Label(frm_rand, text="V max (km/h):").grid(row=1, column=2, sticky="e")
        ttk.Entry(frm_rand, width=6, textvariable=self.vmax_kmh).grid(row=1, column=3, padx=4)
        ttk.Checkbutton(frm_rand, text="Sens aléatoire", variable=self.rand_dir)\
            .grid(row=1, column=4, columnspan=2, sticky="w")

        ttk.Button(frm_rand, text="Lancer série", command=self._launch_random)\
            .grid(row=2, column=5, padx=6, pady=6)

        # --- Multiplier + presets ---
        frm_mult = ttk.LabelFrame(self, text="Comptage (multiplier)")
        frm_mult.grid(row=2, column=0, sticky="ew", padx=padx, pady=pady)

        self.mult_var = tk.DoubleVar(value=float(Application.multiplier[0]))
        ttk.Label(frm_mult, text="Multiplier:").grid(row=0, column=0, padx=6, sticky="e")
        ttk.Entry(frm_mult, width=8, textvariable=self.mult_var).grid(row=0, column=1, padx=6)
        ttk.Button(frm_mult, text="Appliquer", command=self._apply_multiplier).grid(row=0, column=2, padx=6)

        p2 = ttk.Frame(frm_mult)
        p2.grid(row=1, column=0, columnspan=3, pady=6)

        ttk.Button(p2, text="Défaut ≈100 cps", command=lambda: self._set_multiplier(0.01)).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(p2, text="Fond ≈1000 cps",  command=lambda: self._set_multiplier(0.10)).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(p2, text="Alarme 1 ≈5000",  command=lambda: self._set_multiplier(0.50)).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(p2, text="Alarme 2 ≈15000", command=lambda: self._set_multiplier(1.50)).grid(row=0, column=3, padx=4, pady=4)

        self.lbl_est = ttk.Label(frm_mult, text=self._est_text())
        self.lbl_est.grid(row=2, column=0, columnspan=3, pady=4)

        # --- Acquittement ---
        frm_acq = ttk.Frame(self)
        frm_acq.grid(row=3, column=0, sticky="ew", padx=padx, pady=pady)
        ttk.Button(frm_acq, text="ACQUIT (1s)", command=self._acquit).grid(row=0, column=0, padx=6)
        ttk.Label(frm_acq, text="Raccourcis: [Espace]=Acquit  [A]=1→2  [Z]=2→1")\
            .grid(row=0, column=1, padx=8)

        # --- Moniteur ---
        frm_mon = ttk.LabelFrame(self, text="Moniteur")
        frm_mon.grid(row=4, column=0, sticky="ew", padx=padx, pady=pady)
        ttk.Label(frm_mon, textvariable=self._state_text, width=60).grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(frm_mon, text="Dernière action:").grid(row=1, column=0, sticky="w", padx=6)
        ttk.Label(frm_mon, textvariable=self._last_action, width=60).grid(row=2, column=0, padx=6, pady=2, sticky="w")
        self._passages_lbl = ttk.Label(frm_mon, text="Passages cumulés: 0")
        self._passages_lbl.grid(row=3, column=0, sticky="w", padx=6, pady=2)

    def _bind_keys(self):
        self.bind("<space>", lambda e: self._acquit())
        self.bind("a",      lambda e: self._passage("12"))
        self.bind("z",      lambda e: self._passage("21"))

    # ===================== Injection pulses =====================
    def _inject_counts_tick(self):
        if ComptageThread is not None:
            mult = float(Application.multiplier[0])
            cps = self._sim_base_cps * mult
            dt = float(self._sim_dt_s)

            pulses = int(max(0.0, cps) * dt)

            for ch in range(1, 13):
                ComptageThread.cpt_impulsions[ch] = ComptageThread.cpt_impulsions.get(ch, 0) + pulses

        self.after(int(self._sim_dt_s * 1000), self._inject_counts_tick)

    # ===================== Multiplier =====================
    def _apply_multiplier(self):
        try:
            v = float(self.mult_var.get())
        except Exception:
            v = 1.0
        v = max(0.001, min(5.0, v))
        Application.multiplier[0] = v
        self.mult_var.set(v)
        self.lbl_est.config(text=self._est_text())
        self._update_state_text()

    def _set_multiplier(self, v):
        Application.multiplier[0] = max(0.001, min(5.0, float(v)))
        self.mult_var.set(Application.multiplier[0])
        self.lbl_est.config(text=self._est_text())
        self._update_state_text()

    def _enforce_boot_multiplier(self):
        if float(Application.multiplier[0]) > 0.10:
            Application.multiplier[0] = 0.10
            try:
                self.mult_var.set(0.10)
            except Exception:
                pass
        self.lbl_est.config(text=self._est_text())
        self._update_state_text()

    def _est_text(self):
        est = self._sim_base_cps * float(Application.multiplier[0])
        return f"Estimation ≈ {est:,.0f} cps".replace(",", " ")

    # ===================== Cellules / Passage =====================
    def _apply_s1(self):
        Application.variable1[0] = 1 if self.var_s1.get() else 0
        self._push_cells_to_watchers()
        self._last_action.set(self._stamp(f"S1={Application.variable1[0]}"))
        self._update_state_text()

    def _apply_s2(self):
        Application.variable2[0] = 1 if self.var_s2.get() else 0
        self._push_cells_to_watchers()
        self._last_action.set(self._stamp(f"S2={Application.variable2[0]}"))
        self._update_state_text()

    def _push_cells_to_watchers(self):
        if etat_cellule_1 is not None and hasattr(etat_cellule_1, "InputWatcher"):
            try:
                etat_cellule_1.InputWatcher.cellules[1] = int(Application.variable1[0])
            except Exception:
                pass
        if etat_cellule_2 is not None and hasattr(etat_cellule_2, "InputWatcher"):
            try:
                etat_cellule_2.InputWatcher.cellules[2] = int(Application.variable2[0])
            except Exception:
                pass

    @staticmethod
    def _kmh_to_mps(kmh: float) -> float:
        return max(0.01, float(kmh) * 1000.0 / 3600.0)

    def _timings_from_speed(self, kmh: float):
        v = self._kmh_to_mps(kmh)
        dist = max(0.01, float(self.dist_m.get()))
        obj  = max(0.01, float(self.obj_m.get()))
        gap_ms  = int((dist / v) * 1000.0)
        t_on_ms = int((obj  / v) * 1000.0)
        return max(10, gap_ms), max(20, t_on_ms)

    def _passage(self, direction="12", kmh=None):
        if kmh is None:
            kmh = float(self.speed_kmh.get())
        gap_ms, t_on_ms = self._timings_from_speed(kmh)

        Application.variable1[0] = 0; self.var_s1.set(0)
        Application.variable2[0] = 0; self.var_s2.set(0)
        self._push_cells_to_watchers()

        if direction == "12":
            steps = [
                (0,      lambda: self._set_cell("S1", 1)),
                (gap_ms, lambda: self._set_cell("S2", 1)),
                (t_on_ms,lambda: self._set_cell("S1", 0)),
                (gap_ms, lambda: self._set_cell("S2", 0)),
            ]
        else:
            steps = [
                (0,      lambda: self._set_cell("S2", 1)),
                (gap_ms, lambda: self._set_cell("S1", 1)),
                (t_on_ms,lambda: self._set_cell("S2", 0)),
                (gap_ms, lambda: self._set_cell("S1", 0)),
            ]

        self._passages_count += 1
        self._passages_lbl.config(text=f"Passages cumulés: {self._passages_count}")
        self._last_action.set(self._stamp(f"Passage {direction} @ {kmh:.2f} km/h"))

        self._run_steps(steps)

    def _set_cell(self, which, val):
        if which == "S1":
            Application.variable1[0] = 1 if val else 0
            self.var_s1.set(Application.variable1[0])
        else:
            Application.variable2[0] = 1 if val else 0
            self.var_s2.set(Application.variable2[0])

        self._push_cells_to_watchers()
        self._update_state_text()

    def _run_steps(self, steps, i=0):
        if i >= len(steps):
            return
        delay, func = steps[i]
        self.after(max(1, int(delay)), lambda: (func(), self._run_steps(steps, i + 1)))

    # ===================== Série aléatoire =====================
    def _launch_random(self):
        try:
            self._rnd_left = max(1, int(self.nb_passages.get()))
        except Exception:
            self._rnd_left = 5
        self._random_next()

    def _random_next(self):
        if self._rnd_left <= 0:
            return

        try:
            vmin = float(self.vmin_kmh.get()); vmax = float(self.vmax_kmh.get())
        except Exception:
            vmin, vmax = 3.0, 10.0
        if vmax < vmin:
            vmin, vmax = vmax, vmin
        vmin = max(0.5, vmin); vmax = max(vmin, vmax)

        kmh = random.uniform(vmin, vmax)
        direction = random.choice(("12", "21")) if self.rand_dir.get() else "12"
        self._passage(direction=direction, kmh=kmh)

        try:
            gmin = int(self.gap_min_ms.get()); gmax = int(self.gap_max_ms.get())
        except Exception:
            gmin, gmax = 300, 1500
        if gmax < gmin:
            gmin, gmax = gmax, gmin
        gap = random.randint(max(0, gmin), max(gmin, gmax))

        self._rnd_left -= 1
        self.after(gap, self._random_next)

    # ===================== Tests / Acquittement =====================
    def _test_pulse(self, which):
        self._set_cell(which, 1)
        self.after(100, lambda: self._set_cell(which, 0))
        self._last_action.set(self._stamp(f"Pulse {which}"))

    def _acquit(self):
        Application.acqui[0] = 1
        self._last_action.set(self._stamp("ACQUIT=1"))
        self.after(1000, self._set_acq0)

    def _set_acq0(self):
        Application.acqui[0] = 0
        self._last_action.set(self._stamp("ACQUIT=0"))

    # ===================== Moniteur =====================
    def _refresh_ui(self):
        self.var_s1.set(Application.variable1[0])
        self.var_s2.set(Application.variable2[0])
        self._update_state_text()
        self.after(500, self._refresh_ui)

    def _update_state_text(self):
        self._state_text.set(
            f"S1={Application.variable1[0]}  S2={Application.variable2[0]}  mult={Application.multiplier[0]:.2f}"
        )

    def _stamp(self, msg: str) -> str:
        return time.strftime("%H:%M:%S") + "  " + msg

    # ===================== Autopilot ======================

    def start_autopilot(self) -> None:
            """
            Démarre automatiquement :
            - un fond stable (multiplier à 0.10)
            - un passage toutes les X secondes
            """
            self._set_multiplier(0.10)
            self._last_action.set(self._stamp("AUTO: fond ~1000 cps + passages ON"))
            self.after(1500, self._auto_passage_loop)

    def _auto_passage_loop(self) -> None:
            # un passage toutes les 5s, vitesse 6 km/h, sens alterné
            direction = "12" if (self._passages_count % 2 == 0) else "21"
            self._passage(direction=direction, kmh=6.0)
            self.after(5000, self._auto_passage_loop)

    # ===================== Fermeture =====================
    def _on_close(self):
        try:
            self.destroy()
        except Exception:
            pass


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
