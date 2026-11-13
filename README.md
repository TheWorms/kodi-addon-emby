<!-- logo:start -->
<p align="center"><img src="plugin.video.embycon/icon.png" alt="Logo" width="160"></p>
<!-- logo:end -->

# EmbyCon — édition française · `kodi-addon-emby`

<!-- version:auto -->
**Version : 1.22.6**
<!-- /version:auto -->

**Français** · [English](readme.en.md)

Extension Kodi pour parcourir et lire la médiathèque d'un serveur **[Emby](https://emby.media)** (films, séries, musique) directement dans l'interface Kodi.

> [!NOTE]
> Ce dépôt est un **fork francophone enrichi** de [**EmbyCon**](https://github.com/faush01/plugin.video.embycon) de **faush01 (Team B)**, distribué sous licence **GPL-2.0**. L'identifiant de l'extension reste `plugin.video.embycon` afin de préserver la compatibilité des installations et des réglages existants. Tout le mérite de l'addon d'origine revient à ses auteurs ; ce fork ajoute une interface française et plusieurs fonctionnalités décrites ci-dessous.

---

## Nouveautés de ce fork

- **Interface française complète** — traduction intégrale (`resource.language.fr_fr`), détectée automatiquement selon la langue de Kodi.
- **Masquage des éléments déjà vus** — sur les listes *et* les widgets d'accueil, avec un rafraîchissement fiable : purge du cache au marquage et jeton de rechargement (`&reload`) injecté dans les chemins de widgets pour une mise à jour automatique après un marquage vu/non-vu.
- **Tri configurable par liste** — films, séries, collections, films d'une collection, saisons et épisodes : le critère et le sens tiennent en un seul réglage (« Date de sortie, ancien → récent »…).
- **Qualité de lecture automatique** — mesure du débit réseau en arrière-plan (jamais pendant la lecture) et réglage automatique du débit maximal ; mode manuel toujours disponible.
- **Saut de l'intro et du générique** — basé sur les marqueurs détectés par le serveur Emby (`IntroStart`/`IntroEnd`/`CreditsStart`), en mode *Bouton* ou *Automatique*, avec un **repli à durée fixe** (sauter les X premières secondes / proposer le saut X secondes avant la fin) lorsque le serveur n'a pas de marqueur.
- **Sous-titres intelligents** — active automatiquement un sous-titre dans la langue préférée quand l'audio n'est pas dans la langue préférée (comme l'appli web Emby).
- **Épisode et film suivants** — une fenêtre propose la suite avant la fin puis l'enchaîne, ou l'enchaînement se fait sans demander.
- **Rafraîchissement après lecture** — la liste courante se met à jour peu après la fin d'une lecture.
- **Réglages réorganisés** — 7 menus (Lecture, Enchaînements, Listes et tri, Titres et fiches, Film au hasard, Serveur et compte, Avancé), avec une phrase d'aide par réglage.

---

## Journal des versions

### 1.22 · version actuelle

**Lecture**

- **Pistes automatiques en lecture réduite** — quand la vidéo est transcodée (connexion ou matériel), l'audio et les sous-titres sont choisis d'après vos langues, avec les mêmes règles qu'en lecture directe. Réglage *Lecture → Audio et sous-titres → Pistes d'une lecture réduite* : *Automatique* ou *Me demander*.
- **Menu des pistes au style du clic droit** — le choix automatique est déjà sélectionné et marqué *AUTO* ; Retour le conserve.
- **Diagnostic de la qualité automatique** — le journal de Kodi indique pour chaque lecture la vidéo, la limite de débit et la décision du serveur ; une notification prévient si le serveur transcode trop lentement.

**Listes**

- **Collections déjà vues masquées** — option *Listes et tri → Contenu → Masquer les collections déjà vues dans les widgets*.

**Corrections**

- Plus de gel de Kodi en revenant d'un film lancé depuis une recherche : les résultats reviennent sans rouvrir le clavier, et Retour ne mène plus à l'explorateur.

<details>
<summary><b>1.21</b> · film au hasard, bouton Passer, nouvelle icône, retour d'un film</summary>

- **Film au hasard** — retour à l'accueil à l'arrêt, à la fin et depuis le plein écran ; lecture continue qui enchaîne un autre film tiré au hasard ; une fin de lecture naturelle compte comme vue jusqu'au bout.
- **Bouton « Passer »** (intro et générique) — disparaît après le délai réglé ; libellé traduit.
- **Nouvelle icône** — la mascotte, aussi dans les notifications et les fenêtres de l'extension.
- **Retour d'un film immédiat** — la liste réapparaît aussitôt au lieu d'une fenêtre Vidéos vide ; Retour vers une liste parente est instantané ; plus de boîte de progression par-dessus l'accueil.

</details>

<details>
<summary><b>1.20</b> · réglages en 7 menus, ordre des collections</summary>

- **Réglages réorganisés en 7 menus** — renommés, avec une phrase d'aide par réglage : 93 réglages au lieu de 110, doublons fusionnés, valeurs lisibles (« Désactivé », « Sans limite »). Les réglages existants sont convertis automatiquement à la mise à jour.
- **Widget Collections** — garde l'ordre EmbyCon, quel que soit le sens de tri du skin.
- **Films d'une collection** — du plus ancien au plus récent, pour suivre une saga d'année en année.
- **Épisode suivant** — même fonctionnement que pour les films : proposer puis enchaîner, ou enchaîner sans demander.

</details>

<details>
<summary><b>1.15</b> · film au hasard, collections, sous-titres forcés, tris et vues, cache des listes</summary>

- **Film au hasard** — fiche plein écran sur le fanart du film avec *Lire*, *Suivant*, *Précédent* et *Annuler* ; filtres « non vus » et durée maximale. Ouvrir le widget « Films - Aléatoire » lance directement le tirage.
- **Collections de films** — *Tout lire* une collection, et enchaînement du **film suivant** : proposé au début du générique (ou quelques minutes avant la fin), puis lancé automatiquement.
- **Dates des collections** — Emby ne date pas les collections : EmbyCon calcule leur date de sortie à partir de leurs films, en parallèle, avec un cache disque préparé par le service. Les tris par date fonctionnent donc aussi sur les collections, et le sens de tri d'EmbyCon pilote le widget Collections d'Arctic.
- **Sous-titres forcés** — affichés automatiquement dans votre langue (dialogues étrangers, panneaux).
- **Tris et vues** — un tri par défaut pour chaque type de liste, widget « Collections - Ajouts récents », et la vue choisie (liste, affiches, vignettes…) retenue pour chaque catégorie.
- **Réglages simplifiés** — sous-réglages affichés seulement quand ils servent, doublons fusionnés ; qualité automatique fiabilisée.
- **Cache des listes en base SQLite + ETag** — la navigation consomme quelques Ko au lieu de dizaines de Mo ; pagination des grandes listes, robustesse réseau (retries, websocket stabilisée, garde 401 à l'authentification) et contrôle CI (`ruff` + tests) à chaque push.

</details>

---

## Installation

### Via le dépôt TheWorms (mises à jour automatiques)

1. Dans Kodi : **Paramètres → Système → Modules complémentaires** et activez **Sources inconnues**.
2. Installez le dépôt TheWorms depuis cette URL (Explorateur de fichiers → *Ajouter une source*, ou installation directe du zip) :
   ```
   https://raw.githubusercontent.com/TheWorms/kodi-repo/main/zips/repository.theworms/repository.theworms.zip
   ```
3. **Modules → Installer depuis un dépôt → TheWorms Repository → Extensions vidéo → EmbyCon**.

---

## Configuration

1. Ouvrez les réglages de l'extension.
2. **Serveur et compte** : renseignez l'adresse et le port de votre serveur Emby (ou utilisez la détection automatique), puis vos identifiants.
3. Parcourez votre médiathèque depuis l'entrée **EmbyCon** de Kodi, ou ajoutez des **widgets** à votre écran d'accueil.

> Pour que les éléments vus disparaissent des listes et widgets, activez **Listes et tri → Contenu → Masquer ce que j'ai déjà vu**.

---

## Compatibilité

- **Kodi 21 (Omega)** et versions compatibles Python 3.
- Testé sur CoreELEC (ODROID-N2+).
- Le rafraîchissement automatique des widgets nécessite un skin qui évalue les jetons `$INFO[...]` dans les chemins de widgets (ex. skins dérivés d'Arctic Zephyr).

---

## Crédits & licence

- Addon d'origine : **[EmbyCon](https://github.com/faush01/plugin.video.embycon)** par **faush01 / Team B**.
- Fork francophone et fonctionnalités additionnelles : **[TheWorms](https://github.com/TheWorms)**.
- Licence : **[GPL-2.0](LICENSE.txt)** — le code source complet est disponible dans ce dépôt, conformément aux termes de la licence.

Emby est une marque de Emby LLC. Ce projet n'est pas affilié à Emby LLC ni à Kodi/XBMC Foundation.

---

## Contribution

Les rapports de bugs et suggestions sont bienvenus via les [issues](https://github.com/TheWorms/kodi-addon-emby/issues). Merci de préciser votre version de Kodi, votre skin et de joindre les lignes de log pertinentes.
