
📄 **Contenu COMPLET**

```markdown
# UNIPI Simul

Simulateur matériel **UNIPI** destiné au projet **GeV5**.

Ce module permet de développer et tester GeV5 **sans matériel physique**, en simulant les entrées/sorties et les comportements attendus.

---

## 🎯 Objectifs

- Simuler les E/S matérielles UNIPI
- Tester la logique GeV5 hors site
- Accélérer le développement
- Réduire la dépendance au matériel réel

---

## 🧱 Principe

Le simulateur reproduit :
- états d’entrées
- commandes de sorties
- événements matériels
- scénarios nominal / défaut

Il se substitue aux drivers matériels réels.

---

## 🔗 Intégration avec GeV5_refactor

- Utilisé en **mode simulation**
- Appelé par GeV5_refactor
- Permet des tests reproductibles


---

## 🧪 Utilisation

Selon l’implémentation :
- lancement manuel
- import comme module
- scénario de test automatisé

Exemple générique :

```bash
python main.py
