# Références de performance — v1.13.29 (base v1.14)

Mesures à réaliser sur l'ODROID-N2+ (CoreELEC, Kodi 21) **avant** d'appliquer
les optimisations v1.14 (Phase 0 du brief). Objectif : mesurer un gain de
-30 % sur les listes en fin de développement (§6.4 du brief).

## Protocole

- Kodi fraîchement redémarré, cache de l'addon vidé avant chaque série
  (dossiers `special://userdata/addon_data/plugin.video.embycon/cache/`)
- 3 mesures par cas, on retient la **médiane**
- Chronomètre manuel suffisant : déclencher l'action → arrêt quand la liste
  est affichée

## Temps de chargement des listes (médiane, secondes)

| Cas | v1.13.29 (référence) | Observations |
|---|---|---|
| Films — page 1 | | |
| Séries — page 1 | | |
| Saison complète (épisodes) | | |
| Boxsets | | |
| Widgets skin au démarrage Kodi | | |

## Lecture

| Cas | v1.13.29 (référence) | Observations |
|---|---|---|
| Démarrage de lecture direct-play | | |
| Démarrage de lecture transcodée | | |
| Fichier AV1 (comportement constaté) | | écran noir attendu avant le correctif 11 |

## Conditions de la mesure

- Date / heure :
- Version CoreELEC / Kodi :
- Serveur Emby (version, connexion LAN/Wi-Fi) :
- Nombre d'éléments dans la médiathèque :
