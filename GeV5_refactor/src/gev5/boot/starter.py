"""
Starter GeV5 - Orchestration principale (version refactorisée et cohérente
avec SystemConfig, le comptage, les alarmes, les défauts et les courbes).

Hypothèses basées sur la V1 :

- Défauts :
    * seuil bas  défaut  = cfg.low
    * seuil haut défaut  = cfg.high

- Alarmes radiologiques :
    * seuil N1 (alarme)  = cfg.seuil2
    * seuil de retour    ≈ 0.8 * cfg.seuil2  (hystérésis simple)
    * seuil N2 (alarme 2)= calculé dans AlarmeThread via n2_factor (par défaut 1.5)
    * seuil suiveur      = fond * cfg.multiple

- Voies :
    * voies 1..4  : électroniques locales, comptage GPIO (PIN_1..PIN_4)
    * voies 5..8  : électronique esclave 1 (Rem_IP)  → à intégrer plus tard
    * voies 9..12 : électronique esclave 2 (Rem_IP_2)→ à intégrer plus tard
"""

from __future__ import annotations

import threading
from logging import Logger
from typing import Dict, List, Callable

from ..utils.config import SystemConfig
from ..utils.logging import get_logger

from ..core.comptage.build import build_all_comptages
from ..core.comptage.comptage import ComptageThread
from ..core.alarmes.build import build_all_alarmes
from ..core.defauts.build import build_all_defauts
from ..core.courbes.build import build_all_courbes

from ..core.alarmes.alarmes import AlarmeThread
from ..core.defauts.defauts import DefautThread
from ..core.courbes.courbes import CourbeThread

from ..hardware.storage.collect_bdf_v2 import BdfCollectorV2
from ..hardware.storage.db_write_v2 import PassageRecorderV2
from ..hardware.storage.rapport_pdf import ReportThread

from ..hardware.io import create_hardware
from ..hardware.passage import PassageService, PassageConfig
from ..hardware.vitesse_chargement import ListWatcher

from ..core.acquittement.acquittement import AcquittementThread, AcquittementConfig

logger: Logger = get_logger("gev5.starter")


class Gev5System:
    """Orchestrateur principal GeV5 (voies / alarmes / défauts / courbes + stockage)."""

    def __init__(self, cfg: SystemConfig) -> None:
        self.cfg = cfg
        self.threads: List[threading.Thread] = []

        # Références vers les threads par famille (types spécifiques)
        self.comptage_threads: List[ComptageThread] = []
        self.alarme_threads: List[AlarmeThread] = []
        self.defaut_threads: List[DefautThread] = []
        self.courbe_threads: List[CourbeThread] = []


        # Stockage V2
        self.bdf_thread: threading.Thread | None = None
        self.passage_thread: threading.Thread | None = None

        # Rapport PDF / email
        self.report_thread: threading.Thread | None = None

        # Backend hardware (simu / prod) + service passage
        self.hw = create_hardware(cfg.sim)
        self.passage_service = PassageService(self.hw, PassageConfig())

        # Acquittement & vitesse
        self.acq_thread: threading.Thread | None = None
        self.vitesse_thread: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    # Helpers de mapping
    # ------------------------------------------------------------------ #
    def _build_pins(self) -> Dict[int, int]:
        """
        Mapping {voie: pin_GPIO}.

        Voies locales (1..4) → PIN_1..PIN_4
        Voies 5..12 → pour l'instant 0 (seront gérées via Rem_IP / eVx
        par d'autres services ; ici on ne crée que le squelette).
        """
        pins: Dict[int, int] = {
            1: self.cfg.pin_1,
            2: self.cfg.pin_2,
            3: self.cfg.pin_3,
            4: self.cfg.pin_4,
        }
        # voies "remote" → placeholder (0)
        for ch in range(5, 13):
            pins[ch] = 0
        return pins

    def _build_d_on_flags(self) -> Dict[int, int]:
        """Mapping {voie: Dn_ON} à partir de SystemConfig."""
        return {
            1: self.cfg.D1_ON,
            2: self.cfg.D2_ON,
            3: self.cfg.D3_ON,
            4: self.cfg.D4_ON,
            5: self.cfg.D5_ON,
            6: self.cfg.D6_ON,
            7: self.cfg.D7_ON,
            8: self.cfg.D8_ON,
            9: self.cfg.D9_ON,
            10: self.cfg.D10_ON,
            11: self.cfg.D11_ON,
            12: self.cfg.D12_ON,
        }

    def _build_passage_flags(self) -> Dict[int, Callable[[], bool]]:
        """
        Construit un dict {voie: callable_bool} indiquant si un passage
        est en cours, basé sur PassageService.

        Même logique pour toutes les voies :
        les cellules pilotent le portique entier.
        """

        def passage_actif() -> bool:
            return self.passage_service.is_passage()

        return {ch: passage_actif for ch in range(1, 13)}

    # ------------------------------------------------------------------ #
    # Démarrage des familles "cœur temps réel"
    # ------------------------------------------------------------------ #
    def start_comptage(self) -> None:
        """
        Démarre les 12 threads de comptage.

        - voies 1..4 : GPIO réels (PIN_1..PIN_4)
        - voies 5..12: pour l’instant, pins=0 (intégration remote à venir)
        """
        pins = self._build_pins()
        d_on = self._build_d_on_flags()

        self.comptage_threads = build_all_comptages(
            sampling=self.cfg.sample_time,  # même rôle que "sampling" V1
            pins=pins,
            d_on_flags=d_on,
            sim=self.cfg.sim,
        )

        for t in self.comptage_threads:
            t.start()
            self.threads.append(t)

        logger.info("Comptage: %d threads démarrés", len(self.comptage_threads))

    def start_defauts(self) -> None:
        """
        Démarre les défauts génériques.

        Mapping V1 → V2 :
        - limite_inferieure (défaut bas)  = cfg.low
        - limite_superieure (défaut haut) = cfg.high
        - période de test ≈ 60 s (comme Defaut_1 V1)
        """
        d_on_flags = self._build_d_on_flags()

        limites_inf = {i: float(self.cfg.low) for i in range(1, 13)}
        limites_sup = {i: float(self.cfg.high) for i in range(1, 13)}

        # brut = compteur[10,20,...,120] comme dans la V1
        get_raw_vals = {
            i: (lambda i=i: ComptageThread.compteur_brut.get(i * 10, 0.0))
            for i in range(1, 13)
        }

        # D_ON par voie
        get_d_on = {
            i: (lambda i=i: d_on_flags[i])
            for i in range(1, 13)
        }

        self.defaut_threads = build_all_defauts(
            limites_inf=limites_inf,
            limites_sup=limites_sup,
            get_raw_vals=get_raw_vals,
            get_d_on_flags=get_d_on,
            period_s=60.0,  # comme le time.sleep(60) des Defaut_X V1
        )

        for t in self.defaut_threads:
            t.start()
            self.threads.append(t)

        logger.info("Défauts: %d threads démarrés", len(self.defaut_threads))

    def start_alarmes(self) -> None:
        """
        Démarre les alarmes génériques.

        V1 :
        - seuil radiologique = seuil2
        - multiple           = multiple (sert au suiveur)
        - Mode_sans_cellules : 0 = alarme déclenchée seulement pendant passage

        Pour cette V2 générique :
        - seuil_haut (N1) = cfg.seuil2
        - seuil_bas       = 0.8 * cfg.seuil2 (hystérésis simple)
        - tempo_s         = 0 (instantané, on pourra faire évoluer)
        - multiple        = cfg.multiple (seuil suiveur = fond * multiple)
        - get_passage_flags basé sur PassageService si mode_sans_cellules == 0
        """
        d_on_flags = self._build_d_on_flags()

        seuil_n1 = float(self.cfg.seuil2)
        seuils_haut = {i: seuil_n1 for i in range(1, 13)}
        seuils_bas = {i: 0.8 * seuil_n1 for i in range(1, 13)}

        # lecture du comptage filtré : compteur[1..12]
        get_vals = {
            i: (lambda i=i: ComptageThread.compteur.get(i, 0.0))
            for i in range(1, 13)
        }

        # activation par voie : Dn_ON == 1
        enabled_flags = {
            i: (lambda i=i: d_on_flags[i] == 1)
            for i in range(1, 13)
        }

        # Hooks passage (cellules) seulement si on n'est PAS en mode sans cellules
        get_passage_flags = None
        if int(self.cfg.mode_sans_cellules) == 0:
            get_passage_flags = self._build_passage_flags()

        self.alarme_threads = build_all_alarmes(
            seuils_haut=seuils_haut,
            seuils_bas=seuils_bas,
            get_vals=get_vals,
            enabled_flags=enabled_flags,
            period_s=0.1,                    # même rythme que le comptage
            hysteresis=0.0,                  # hystérésis déjà géré via seuil_bas
            tempo_s=0.0,                     # instantané pour l'instant
            multiple=float(self.cfg.multiple),
            mode_sans_cellules=int(self.cfg.mode_sans_cellules),
            get_passage_flags=get_passage_flags,
        )

        for t in self.alarme_threads:
            t.start()
            self.threads.append(t)

        logger.info("Alarmes: %d threads démarrés", len(self.alarme_threads))

    def start_courbes(self) -> None:
        """
        Démarre les courbes génériques.

        On échantillonne 1 valeur / seconde par défaut,
        avec une profondeur de 3600 points (~1h).
        """
        get_vals = {
            i: (lambda i=i: ComptageThread.compteur.get(i, 0.0))
            for i in range(1, 13)
        }

        self.courbe_threads = build_all_courbes(
            get_vals=get_vals,
            max_points=3600,
            period_s=1.0,
         )

        for t in self.courbe_threads:
            t.start()
            self.threads.append(t)

        logger.info("Courbes: %d threads démarrés", len(self.courbe_threads))

    # ------------------------------------------------------------------ #
    # Démarrage stockage V2 + rapport PDF
    # ------------------------------------------------------------------ #
    def start_bdf_collector(self) -> None:
        """
        Démarre le collecteur V2 du bruit de fond.

        Il lit AlarmeThread.fond[1..12] et écrit dans Bruit_de_fond.db.
        """
        self.bdf_thread = BdfCollectorV2(interval=30)
        self.bdf_thread.start()
        self.threads.append(self.bdf_thread)
        logger.info("BdfCollectorV2 démarré (interval=30s).")

    def start_passage_recorder(self) -> None:
        """
        Démarre l'enregistreur V2 des passages.

        Il détecte les passages via les cellules et logge dans passages_v2.
        """
        self.passage_thread = PassageRecorderV2()
        self.passage_thread.start()
        self.threads.append(self.passage_thread)
        logger.info("PassageRecorderV2 démarré.")

    def start_report_thread(self) -> None:
        """
        Démarre le thread de génération de rapports PDF (V2),
        branché comme en V1 côté Envoi_email (email_send_rapport).
        """
        noms_detecteurs = {
            1: self.cfg.D1_nom,
            2: self.cfg.D2_nom,
            3: self.cfg.D3_nom,
            4: self.cfg.D4_nom,
            5: self.cfg.D5_nom,
            6: self.cfg.D6_nom,
            7: self.cfg.D7_nom,
            8: self.cfg.D8_nom,
            9: self.cfg.D9_nom,
            10: self.cfg.D10_nom,
            11: self.cfg.D11_nom,
            12: self.cfg.D12_nom,
        }

        self.report_thread = ReportThread(
            Nom_portique=self.cfg.nom_portique,
            Mode_sans_cellules=self.cfg.mode_sans_cellules,
            noms_detecteurs=noms_detecteurs,
            seuil2=self.cfg.seuil2,
            language=self.cfg.language,
        )
        self.report_thread.start()
        self.threads.append(self.report_thread)
        logger.info("ReportThread (PDF V2) démarré.")

    # ------------------------------------------------------------------ #
    # Acquittement + vitesse
    # ------------------------------------------------------------------ #
    def start_acquittement(self) -> None:
        cfg = AcquittementConfig(
            ack_di=5,
            ack_active_high=True,
            confirm_timeout_s=15.0,
        )

        self.acq_thread = AcquittementThread(
            hw=self.hw,
            passage_service=self.passage_service,
            config=cfg,
        )

        self.acq_thread.start()
        self.threads.append(self.acq_thread)
        logger.info("Acquittement V2 démarré.")

    def start_vitesse(self) -> None:
        """
        Démarre le thread de calcul de vitesse (ListWatcher V2).

        - distance_cellules en mètres (ex: 0.75)
        - mode_sans_cellules : 0 ou 1
        """
        distance = float(self.cfg.distance_cellules)
        mss = int(self.cfg.mode_sans_cellules)

        self.vitesse_thread = ListWatcher(distance, mss, self.passage_service)
        self.vitesse_thread.start()
        self.threads.append(self.vitesse_thread)
        logger.info("ListWatcher (vitesse) démarré.")

    # ------------------------------------------------------------------ #
    # Démarrage global
    # ------------------------------------------------------------------ #
    def start_all(self) -> None:
        logger.info("Démarrage GeV5 (cœur voies + stockage V2 + rapport PDF)")

        # Cœur temps réel
        self.start_comptage()
        self.start_defauts()
        self.start_alarmes()
        self.start_courbes()

        # Stockage V2 (fond + passages)
        self.start_bdf_collector()
        self.start_passage_recorder()

        # Rapport PDF (comme avant, mais basé sur V2)
        self.start_report_thread()

        # Acquittement + vitesse
        self.start_acquittement()
        self.start_vitesse()

        logger.info(
            "Tous les threads GeV5 (voies + stockage V2 + rapport PDF + acquittement + vitesse) sont démarrés."
        )


def start_all(cfg: SystemConfig) -> Gev5System:
    """
    Helper de démarrage global, pour compatibilité avec l'ancienne API :

        from gev5.boot import start_all
        system = start_all(cfg)

    Cela crée un Gev5System, lance tous les threads et renvoie l'instance.
    """
    system = Gev5System(cfg)
    system.start_all()
    return system
