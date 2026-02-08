# GeV5 – Portique de détection radiologique (Refactor V2)

GeV5 est un **logiciel de portique de détection de radioactivité** développé en Python, destiné à fonctionner sur des systèmes embarqués (Raspberry Pi / Unipi) comme sur poste de simulation.  
Cette version **V2** est une refonte complète et industrialisée de la V1 historique.

---

## 🎯 Objectifs du projet

- Assurer une **détection radiologique fiable et continue**
- Gérer **comptage, alarmes, défauts, courbes et événements de passage**
- Séparer clairement :
  - le **cœur métier**
  - le **matériel**
  - le **stockage**
  - la **simulation**
- Permettre :
  - la simulation logicielle
  - l’extension future (API, supervision, matériel distant)

---

## 🧠 Architecture générale

Le projet suit une architecture **modulaire et orientée services**, avec des threads indépendants et synchronisés par états partagés.

src/
└─ gev5/
├─ boot/ # Démarrage et orchestration globale
├─ core/ # Logique métier (comptage, alarmes, défauts, courbes)
├─ hardware/ # Abstraction matériel (Unipi / Simulateur)
├─ storage/ # Bases de données, enregistrements, rapports
├─ simulation/ # Simulateur Tkinter
└─ tests/ # Outils de test et d’inspection

markdown
Copier le code

---

## 🔩 Modules principaux

### 🔢 Comptage
- Comptage continu par voie (1 à 12)
- Filtrage temporel
- Compatible GPIO / simulation

### 🚨 Alarmes radiologiques
- Seuils N1 / N2
- Hystérésis
- Alarme suiveuse basée sur le bruit de fond
- Déclenchement conditionné au passage (cellules)

### ⚠️ Défauts techniques
- Défaut bas / haut
- Surveillance périodique
- Activation par voie

### 📈 Courbes
- Historique glissant par voie
- Paramétrable (période / profondeur)

### 🚪 Passage & cellules
- Gestion centralisée via `PassageService`
- Compatible matériel réel ou simulateur
- Utilisé par :
  - alarmes
  - acquittement
  - calcul de vitesse

### ✅ Acquittement V2
- Double appui
- Vérification de stabilité des cellules
- Timeout de confirmation
- Réinitialisation centralisée des alarmes

### 🏎️ Vitesse de passage
- Calcul basé sur S1 / S2
- Détection du sens (1→2 ou 2→1)
- Inhibition si alarme active
- Compatible simulation

---

## 🧪 Simulation

Un simulateur Tkinter est intégré :

- Cellules S1 / S2
- Bouton d’acquittement
- Passages manuels ou aléatoires
- Vitesse paramétrable

➡ Permet de tester **l’intégralité du moteur sans matériel**.

---

## 🗄️ Stockage & rapports

- Enregistrement du bruit de fond (SQLite)
- Enregistrement des passages
- Génération automatique de **rapports PDF**
- Prévu pour intégration email / supervision

---

## ▶️ Lancement

### Prérequis
- Python 3.10+
- Environnement Windows / Linux

### Installation
```bash
pip install -r requirements.txt
Exécution
bash
Copier le code
python run.py
Le mode simulation / production est déterminé par la configuration (SystemConfig).

🧩 Configuration
La configuration est centralisée via SystemConfig :

seuils radiologiques

paramètres matériels

activation des voies

mode avec / sans cellules

paramètres de simulation

🔄 État du système (V2)
Les états globaux sont accessibles via un point unique :

python
Copier le code
SystemState.get_counts()
SystemState.get_alarm_states()
SystemState.get_defauts()
SystemState.get_curves()
➡ Base prête pour une API REST ou une interface web.

🚀 Roadmap
 API REST (FastAPI)

 Supervision web temps réel

 Intégration matériel distant (Rem_IP)

 Tests unitaires automatisés

 Packaging / déploiement industriel

📌 Historique
V1 : implémentation monolithique par voie

V2 : refactor complet, modulaire, testable, extensible

Le dossier V1/ est conservé à titre d’archive et de référence.

👤 Auteur
Projet conçu et développé par Tony Gloaguen
Responsable technique – Radioprotection – Développement logiciel embarqué

📄 Licence
Projet interne / professionnel – diffusion contrôlée.