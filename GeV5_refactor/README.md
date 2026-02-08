# GeV5_refactor

Cœur applicatif du système **GeV5**.  
Ce projet contient l’ensemble de la logique métier, des interfaces matérielles, des services API/Web et des mécanismes de stockage et d’alarme.

Il constitue le **composant principal déployé sur cible industrielle**.

---

## 🎯 Rôle du projet

- Pilotage matériel
- Traitement des événements et états système
- Comptage, alarmes, défauts
- API et interface Web
- Stockage local et génération de rapports
- Mode simulation (sans matériel réel)

---

## 🧱 Architecture (vue logique)

src/gev5/
├─ api_server/ # API / serveur applicatif
├─ boot/ # Démarrage et initialisation
├─ core/ # Logique métier (alarmes, comptage, courbes…)
├─ hardware/ # Interfaces matérielles
├─ utils/ # Configuration, logs, chemins
├─ web/ # Interface Web
└─ main.py # Point d’entrée

flowchart TB

    %% Entrées externes
    HW[Matériel réel<br/>(capteurs, E/S)]
    SIM[UNIPI Simul<br/>(simulateur matériel)]

    %% Cœur GeV5
    subgraph GEV5[GeV5_refactor]
        BOOT[Boot / Starter]
        CORE[Core métier]
        API[API Server]
        WEB[Interface Web]
        STORE[Stockage & Données]
        LOGS[Logs & Monitoring]
    end

    %% Relations internes
    BOOT --> CORE
    CORE --> API
    CORE --> WEB
    CORE --> STORE
    CORE --> LOGS

    %% Matériel / Simulation
    HW --> CORE
    SIM --> CORE

    %% Accès utilisateur
    API --> CLIENT[Clients externes]
    WEB --> USER[Utilisateur]

flowchart LR

    subgraph CORE[Core métier GeV5]
        AL[Alarmes]
        CP[Comptage]
        DF[Défauts]
        VT[Vitesse]
        SM[Simulation]
        ST[System State]
    end

    AL --> ST
    CP --> ST
    DF --> ST
    VT --> ST
    SM --> ST

sequenceDiagram
    autonumber

    participant SYS as Système (OS)
    participant BOOT as Boot / Starter
    participant CORE as Core métier
    participant HW as Matériel / UNIPI
    participant API as API Server
    participant WEB as Interface Web
    participant USER as Utilisateur

    SYS ->> BOOT: Démarrage système
    BOOT ->> CORE: Initialisation (config, état)
    CORE ->> HW: Initialisation E/S\n(ou simulateur)
    HW -->> CORE: État initial / signaux

    CORE ->> API: Démarrage API
    CORE ->> WEB: Démarrage interface Web

    USER ->> API: Requête (état, données)
    API ->> CORE: Lecture état système
    CORE -->> API: Données / événements
    API -->> USER: Réponse JSON

    USER ->> WEB: Accès interface
    WEB ->> CORE: Lecture / actions autorisées
    CORE -->> WEB: Données affichées

## Séquence de démarrage

flowchart LR

    %% Environnements
    DEV[PC Développeur]
    TARGET[Cible industrielle]
    SIM[PC / VM Simulation]

    %% Déploiement DEV
    subgraph DEVENV[Développement]
        DEV_CODE[GeV5_refactor]
        DEV_SIM[UNIPI Simul]
    end

    %% Déploiement PROD
    subgraph PRODENV[Production]
        PROD_CODE[GeV5_refactor]
        PROD_HW[Matériel réel]
    end

    %% Liaisons
    DEV --> DEV_CODE
    DEV_CODE --> DEV_SIM

    TARGET --> PROD_CODE
    PROD_CODE --> PROD_HW

    %% Accès utilisateurs
    USER[Utilisateur] --> PROD_CODE

---

## ⚙️ Prérequis

- Python ≥ 3.10
- Environnement Linux ou Windows
- Accès matériel (optionnel, selon mode)

---

## 🧪 Installation (développement)

```bash
cd GeV5_refactor
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate sous Windows
pip install -r requirements.txt

