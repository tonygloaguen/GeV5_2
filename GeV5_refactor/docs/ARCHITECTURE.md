# Architecture GeV5 (nouvelle arbo)

- `src/gev5/legacy/` : tout le code historique, inchangé (compatibilité maximale)
- `src/gev5/boot/` : chargement des paramètres + démarrage coordonné (futur)
- `src/gev5/core/` : logique métier (comptage, alarmes, défauts, courbes, vitesse)
- `src/gev5/hardware/` : accès matériel (Unipi, EVOK, caméra, SMS, etc.)
- `src/gev5/web/` : interface Flask / API web
- `src/gev5/utils/` : configuration, logging, helpers
