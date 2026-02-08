from __future__ import annotations

"""
Acquittement V2 — basé sur le moteur GeV5 refactorisé.

Rôle :
- Surveiller une entrée "acquittement" (DI ack) via HardwarePort.
- Valider l'acquittement avec :
    * double appui (2 fronts montants dans un délai donné)
    * cellules libres et stables
    * présence d'au moins une alarme active
- Sur confirmation :
    * reset des alarmes via AlarmeThread.reset_alarm()
    * mise à jour d'un petit état partagé (eta_acq) pour l'UI / supervision.

Différences par rapport à la V1 :
- Plus de dépendance à alarme_1..12 : on utilise AlarmeThread.alarme_resultat.
- Plus de dépendance directe à Svr_Unipi ou au simulateur : on passe par HardwarePort.
- Zenity supprimé pour l'instant (peut être réintroduit si vraiment utile).
"""

import threading
import time
from dataclasses import dataclass
from typing import Dict

from ...hardware.io import HardwarePort
from ...hardware.passage import PassageService
from ..alarmes.alarmes import AlarmeThread  


@dataclass
class AcquittementConfig:
    ack_di: int = 5              # DI utilisée pour l'acquittement (ex: DI5)
    ack_active_high: bool = True # True si 1 = appui, False si 0 = appui
    confirm_timeout_s: float = 15.0  # délai max entre les 2 appuis
    poll_period_s: float = 0.1       # période de polling de l'entrée


class AcquittementThread(threading.Thread):
    """
    Thread d'acquittement générique (V2).

    États exposés :
      - eta_acq[1] : 0 = pas d'acquittement, 1 = acquittement confirmé
      - eta_acq[2] : message texte (info / erreur / statut)
    """

    eta_acq: Dict[int, object] = {1: 0, 2: None}

    def __init__(
        self,
        hw: HardwarePort,
        passage_service: PassageService,
        config: AcquittementConfig | None = None,
    ) -> None:
        super().__init__(name="AcquittementThread")
        self.hw = hw
        self.passage_service = passage_service
        self.cfg = config or AcquittementConfig()

        # internes
        self._last_ack_level: int = 0
        self._waiting_confirm: bool = False
        self._confirm_deadline: float = 0.0

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _read_ack_level(self) -> int:
        """Lit la DI d'acquittement et retourne 0/1 logique."""
        raw = int(self.hw.read_di(self.cfg.ack_di))
        if self.cfg.ack_active_high:
            return 1 if raw == 1 else 0
        return 0 if raw == 1 else 1

    def _has_active_alarm(self) -> bool:
        """Retourne True si au moins une alarme est active (N1 ou N2)."""
        try:
            return any(v != 0 for v in AlarmeThread.alarme_resultat.values())
        except Exception:
            return False

    def _reset_eta_acq(self) -> None:
        self.eta_acq[1] = 0
        self.eta_acq[2] = None

    def _set_message(self, msg: str) -> None:
        self.eta_acq[2] = msg

    def _cancel_confirm(self, reason: str | None = None) -> None:
        self._waiting_confirm = False
        if reason:
            self._set_message(reason)

    def _confirm_ack(self, mode: str) -> None:
        """
        Confirmation effective de l'acquittement :
        - reset des alarmes pour toutes les voies
        - mise à jour de eta_acq
        """
        self._waiting_confirm = False

        # Reset de toutes les voies 1..12 (aligné avec GeV5)
        for ch in range(1, 13):
            try:
                AlarmeThread.reset_alarm(ch)
            except Exception:
                # on ne casse pas l'acquittement pour une voie en erreur
                continue

        self.eta_acq[1] = 1
        self._set_message(f"Acquittement confirmé ({mode})")
        print(f"[ACK] ✅ Acquittement confirmé ({mode})")

    # ------------------------------------------------------------------ #
    # Boucle principale
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        while True:
            try:
                # 1) Si plus aucune alarme active → reset état acquittement + annulation demande
                if not self._has_active_alarm():
                    if self.eta_acq[1] != 0 or self.eta_acq[2] is not None:
                        # on laisse 2 s pour affichage éventuel puis reset
                        time.sleep(2.0)
                    self._reset_eta_acq()
                    self._waiting_confirm = False

                # 2) Lecture entrée acquittement
                ack_now = self._read_ack_level()
                front_ack = (ack_now == 1 and self._last_ack_level == 0)
                self._last_ack_level = ack_now

                # 3) Gestion du timeout de confirmation / annulation auto
                if self._waiting_confirm:
                    now = time.monotonic()
                    if now >= self._confirm_deadline:
                        print("[ACK] ⏳ Timeout de confirmation")
                        self._cancel_confirm("Timeout confirmation acquittement")
                    else:
                        # Si les cellules deviennent instables pendant l'attente → annuler
                        if not self.passage_service.are_cells_free_and_stable():
                            print("[ACK] ❌ Cellules instables, annulation demande acquittement")
                            self._cancel_confirm("Cellules instables, acquittement annulé")

                # 4) Traitement du front montant d'acquittement
                if front_ack:
                    self._handle_ack_front()

                time.sleep(self.cfg.poll_period_s)

            except Exception as e:
                print(f"[ACK] ERR run(): {e}")
                time.sleep(0.2)

    # ------------------------------------------------------------------ #
    # Gestion d'un front montant sur l'entrée ACK
    # ------------------------------------------------------------------ #
    def _handle_ack_front(self) -> None:
        print("[ACK] Front montant détecté")

        # Pas d'alarme active → rien à acquitter
        if not self._has_active_alarm():
            self._set_message("Aucune alarme active à acquitter")
            print("[ACK] ⚠️ Pas d'alarme active, acquittement ignoré")
            return

        # Cellules doivent être libres et stables
        if not self.passage_service.are_cells_free_and_stable():
            self._set_message("Cellules non stables, acquittement ignoré")
            print("[ACK] ⚠️ Cellules non stables, acquittement ignoré")
            return

        # Premier appui → demande de confirmation
        if not self._waiting_confirm:
            self._waiting_confirm = True
            self._confirm_deadline = time.monotonic() + self.cfg.confirm_timeout_s
            self._set_message("Appui acquittement détecté, confirmer par un 2e appui")
            print("[ACK] 🟡 Demande de confirmation (2e appui requis)")
            return

        # Deuxième appui dans le délai → acquittement validé
        print("[ACK] 🟢 Confirmation par 2e appui")
        self._confirm_ack("double appui DI")
