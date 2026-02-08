from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Callable, Optional


@dataclass
class AlarmeConfig:
    """
    Configuration d'une alarme voie.

    - channel_id  : n° de voie (1..12)
    - seuil_haut  : seuil principal de déclenchement (N1 "absolu", ex: seuil2)
    - seuil_bas   : seuil de retour à l'état normal (hystérésis basique)
    - hysteresis  : marge autour des seuils (facultatif)
    - tempo_s     : temps pendant lequel la valeur doit rester au-dessus
                    du seuil effectif pour valider l'alarme
    - n2_factor   : facteur multiplicatif pour l'alarme de niveau 2
                    (N2 = seuil_effectif * n2_factor)
    - multiple    : coefficient du seuil suiveur (fond * multiple)
    - mode_sans_cellules : 1 = portique toujours en mesure (pas de cellules)
                           0 = mode classique (piloté par cellules)
    """
    channel_id: int
    seuil_haut: float
    seuil_bas: float
    hysteresis: float = 0.0
    tempo_s: float = 0.0
    n2_factor: float = 1.5
    multiple: float = 1.0
    mode_sans_cellules: int = 0


class AlarmeThread(threading.Thread):
    """
    Thread d'alarme générique pour 1 voie.

    Il lit une fonction get_val() (par ex. compteur de comptage),
    et met à jour des états globaux similaires à la V1 :

      - alarme_resultat[id] : 0 = OK, 1 = N1, 2 = N2
      - mesure[id]          : dernière valeur mesurée
      - email_send_alarm[id]: 1 sur front montant (0->1 ou 0->2)
      - pdf_gen[id]         : flag à 1 quand une alarme vient d’être déclenchée
                              (à consommer par la logique PDF)
      - fond[id]            : estimation du fond radiologique

    NOUVELLES PARTIES :
      - seuil suiveur : threshold_suiveur = fond * multiple
      - seuil effectif = max(seuil_haut, threshold_suiveur)
      - fond mis à jour hors alarme, sous seuil haut, et (en mode cellule)
        surtout hors passage
      - hook de passage via _get_passage :
          * en mode_sans_cellules == 0 → on ne déclenche pas de NOUVELLE
            alarme si pas de passage (mais on peut laisser retomber une alarme)
    """

    # États partagés entre toutes les voies (comme dans la V1)
    alarme_resultat: Dict[int, int] = {}       # 0=OK, 1=N1, 2=N2
    alarme_mesure: Dict[int, float] = {}              # dernière mesure vue
    email_send_alarm: Dict[int, int] = {}      # 0=non envoyé, 1=à envoyer
    pdf_gen: Dict[int, int] = {}               # 0=pas de PDF, 1=PDF à générer
    fond: Dict[int, float] = {}                # estimation du fond par voie

    def __init__(
        self,
        config: AlarmeConfig,
        get_val: Callable[[], float],
        enabled_flag: Optional[Callable[[], bool]] = None,
        get_passage: Optional[Callable[[], bool]] = None,
        period_s: float = 0.1,
    ) -> None:
        super().__init__(name=f"Alarme_{config.channel_id}")
        self.cfg = config
        self._get_val = get_val
        self._enabled_flag = enabled_flag
        self._get_passage = get_passage
        self._period_s = period_s

        cid = self.cfg.channel_id

        # init des dicts partagés
        self.alarme_resultat.setdefault(cid, 0)
        self.alarme_mesure.setdefault(cid, 0.0)
        self.email_send_alarm.setdefault(cid, 0)
        self.pdf_gen.setdefault(cid, 0)
        self.fond.setdefault(cid, 0.0)

        # timers internes pour la tempo
        self._timer_above = 0.0

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _is_enabled(self) -> bool:
        if self._enabled_flag is None:
            return True
        try:
            return bool(self._enabled_flag())
        except Exception:
            return True

    def _is_passage_active(self) -> bool:
        """
        Retourne True si l'on considère qu'un passage est en cours.

        - Si mode_sans_cellules == 1 → toujours True (portique en mesure permanente)
        - Sinon, si aucun hook de passage n'est fourni → True (fallback)
        - Sinon, on appelle le hook (ex: basé sur etat_cellule_1/2).
        """
        if self.cfg.mode_sans_cellules == 1:
            return True

        if self._get_passage is None:
            return True

        try:
            return bool(self._get_passage())
        except Exception:
            return True

    def _update_fond(self, val: float, passage_actif: bool) -> None:
        """
        Met à jour l'estimation du fond radiologique pour cette voie.

        Stratégie :
          - on ne met à jour le fond que si l'alarme n'est pas active
          - on exclut les valeurs très au-dessus du seuil absolu
          - en mode cellules (mode_sans_cellules == 0), on privilégie
            la mise à jour hors passage.
        """
        cid = self.cfg.channel_id
        if self.alarme_resultat.get(cid, 0) != 0:
            return  # pas de mise à jour du fond sous alarme

        # En mode "avec cellules", on utilise surtout le fond hors passage
        if self.cfg.mode_sans_cellules == 0 and passage_actif:
            return

        # On évite d'utiliser des valeurs très au-dessus du seuil haut absolu
        if val >= self.cfg.seuil_haut:
            return

        old_fond = self.fond.get(cid, 0.0)
        alpha = 0.05  # pondération faible → fond évolue lentement

        if old_fond <= 0.0:
            new_fond = val
        else:
            new_fond = old_fond + alpha * (val - old_fond)

        self.fond[cid] = new_fond

    def _compute_effective_threshold(self, cid: int) -> float:
        """
        Calcule le seuil effectif pour la voie :

        - seuil absolu = seuil_haut (seuil2)
        - seuil suiveur = fond * multiple (si multiple > 0 et fond > 0)
        - seuil effectif = max(seuil absolu, seuil suiveur)
        """
        base = self.cfg.seuil_haut
        fond = self.fond.get(cid, 0.0)

        if self.cfg.multiple > 0.0 and fond > 0.0:
            suiveur = fond * self.cfg.multiple
            return max(base, suiveur)
        return base

    def _compute_alarm_state(self, val: float, passage_actif: bool) -> int:
        """
        Calcule l'état d'alarme (0/1/2) en fonction de la valeur,
        de la config (seuils + tempo + suiveur) et de l'état de passage.

        En mode "avec cellules" (mode_sans_cellules == 0) :
          - si pas de passage → on ne déclenche pas de nouvelle alarme
            (timer remis à zéro, mais on laisse la logique de retour à 0
             gérer la fin d'alarme via l'hystérésis).
        """
        cid = self.cfg.channel_id

        # Si on est en mode "avec cellules" et qu'il n'y a pas de passage,
        # on ne déclenche pas de nouvelle alarme (mais on peut laisser retomber).
        if self.cfg.mode_sans_cellules == 0 and not passage_actif:
            self._timer_above = 0.0
            return 0

        seuil_eff = self._compute_effective_threshold(cid)

        # Gestion de la tempo : si val >= seuil_eff → on accumule le temps,
        # sinon on remet à zéro le compteur.
        if val >= seuil_eff + self.cfg.hysteresis:
            self._timer_above += self._period_s
        else:
            self._timer_above = 0.0

        # Décision d'alarme
        if self.cfg.tempo_s <= 0.0:
            # mode instantané
            active_n1 = val >= seuil_eff
        else:
            # mode temporisé
            active_n1 = self._timer_above >= self.cfg.tempo_s

        if not active_n1:
            return 0  # pas d'alarme

        # N2 si on dépasse largement le seuil effectif
        n2_threshold = seuil_eff * self.cfg.n2_factor
        if val >= n2_threshold:
            return 2

        return 1

    # ------------------------------------------------------------------ #
    # API externe pour reset/acquittement
    # ------------------------------------------------------------------ #
    @classmethod
    def reset_alarm(cls, channel_id: int) -> None:
        """
        Méthode utilitaire pour acquitter l'alarme d'une voie.
        (à appeler depuis la logique d'acquittement ou l'API web).
        """
        cls.alarme_resultat[channel_id] = 0
        cls.email_send_alarm[channel_id] = 0
        cls.pdf_gen[channel_id] = 0

    # ------------------------------------------------------------------ #
    # Boucle principale
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        cid = self.cfg.channel_id

        while True:
            time.sleep(self._period_s)

            if not self._is_enabled():
                # voie désactivée → on force à 0
                if self.alarme_resultat.get(cid, 0) != 0:
                    # si on passe de état alarmé à désactivé → on "nettoie"
                    self.alarme_resultat[cid] = 0
                    self.email_send_alarm[cid] = 0
                    self.pdf_gen[cid] = 0
                continue

            # Lecture de la valeur (typiquement ComptageThread.compteur[cid])
            try:
                val = float(self._get_val())
            except Exception:
                val = 0.0

            self.alarme_mesure[cid] = val

            # État de passage (en fonction des cellules / mode sans cellules)
            passage_actif = self._is_passage_active()

            # Mise à jour du fond (hors alarme, sous seuil haut, typiquement hors passage)
            self._update_fond(val, passage_actif)

            # Calcul du nouvel état d'alarme
            old_state = self.alarme_resultat.get(cid, 0)
            new_state = self._compute_alarm_state(val, passage_actif)

            # Hystérésis basique : si l'alarme est active mais que l'on
            # repasse franchement sous le seuil bas, on retombe à 0.
            if new_state == 0 and old_state != 0:
                if val <= self.cfg.seuil_bas - self.cfg.hysteresis:
                    # retour à la normale
                    self.alarme_resultat[cid] = 0
                    self.email_send_alarm[cid] = 0
                    self.pdf_gen[cid] = 0
                else:
                    # on maintient l'ancien état tant qu'on n'est pas vraiment descendu
                    new_state = old_state

            # Mise à jour des états
            if new_state != old_state:
                self.alarme_resultat[cid] = new_state

                # Front montant d'alarme : on lève les flags
                if old_state == 0 and new_state in (1, 2):
                    self.email_send_alarm[cid] = 1
                    self.pdf_gen[cid] = 1
            else:
                # pas de changement : on ne fait rien de spécial
                pass
