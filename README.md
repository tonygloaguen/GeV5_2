# GeV5 – Monorepo

Monorepo regroupant les composants logiciels du système **GeV5** :
- cœur applicatif
- simulateur matériel UNIPI

Ce dépôt permet de développer, tester et maintenir l’ensemble de la chaîne logicielle dans un référentiel unique.

---

## 📦 Projets inclus

### `GeV5_refactor/`
Cœur applicatif GeV5.
- Logique métier
- Gestion matériel
- API / Web
- Stockage, alarmes, comptage, simulation

> Projet principal déployé sur cible (industrielle / embarquée).

---

### `UNIPI Simul/`
Simulateur matériel UNIPI.
- Simulation d’entrées / sorties
- Tests hors matériel réel
- Support développement et validation

> Utilisé en environnement de développement et de test.

---

## 🗂️ Organisation du dépôt

```text
GeV5/
├─ README.md
├─ .gitignore
├─ .github/
│  └─ workflows/
│     └─ ci.yml
├─ GeV5_refactor/
│  ├─ src/
│  ├─ tests/
│  ├─ requirements.txt
│  └─ README.md
└─ UNIPI Simul/
   ├─ src/
   ├─ tests/
   └─ README.md
