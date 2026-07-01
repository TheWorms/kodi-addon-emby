# EmbyCon — édition française · `kodi-addon-emby`

<!-- version:auto -->
**Version : 1.13.24**
<!-- /version:auto -->

**Français** · [English](readme.en.md)

Extension Kodi pour parcourir et lire la médiathèque d'un serveur **[Emby](https://emby.media)** (films, séries, musique) directement dans l'interface Kodi.

> [!NOTE]
> Ce dépôt est un **fork francophone enrichi** de [**EmbyCon**](https://github.com/faush01/plugin.video.embycon) de **faush01 (Team B)**, distribué sous licence **GPL-2.0**. L'identifiant de l'extension reste `plugin.video.embycon` afin de préserver la compatibilité des installations et des réglages existants. Tout le mérite de l'addon d'origine revient à ses auteurs ; ce fork ajoute une interface française et plusieurs fonctionnalités décrites ci-dessous.

---

## ✨ Nouveautés de ce fork

- **Interface française complète** — traduction intégrale (`resource.language.fr_fr`), détectée automatiquement selon la langue de Kodi.
- **Masquage des éléments déjà vus** — sur les listes *et* les widgets d'accueil, avec un rafraîchissement fiable : purge du cache au marquage et jeton de rechargement (`&reload`) injecté dans les chemins de widgets pour une mise à jour automatique après un marquage vu/non-vu.
- **Tri côté serveur** — tri par défaut configurable par type de contenu (films, coffrets, séries, saisons, épisodes) avec sens croissant/décroissant.
- **Qualité de lecture automatique** — mesure du débit réseau en arrière-plan (jamais pendant la lecture) et réglage automatique du débit maximal ; mode manuel toujours disponible.
- **Saut de l'intro et du générique** — basé sur les marqueurs détectés par le serveur Emby (`IntroStart`/`IntroEnd`/`CreditsStart`), en mode *Bouton* ou *Automatique*, avec un **repli à durée fixe** (sauter les X premières secondes / proposer le saut X secondes avant la fin) lorsque le serveur n'a pas de marqueur.
- **Sous-titres intelligents** — active automatiquement un sous-titre dans la langue préférée quand l'audio n'est pas dans la langue préférée (comme l'appli web Emby).
- **Lecture de l'épisode suivant** — boîte de dialogue configurable (activation, seuil de déclenchement, pourcentage).
- **Rafraîchissement après lecture** — la liste courante se met à jour peu après la fin d'une lecture.
- **Réglages réorganisés** — 6 catégories claires regroupées par intention (Serveur & compte, Qualité & lecture, Automatisations, Affichage & listes, Services, Avancé).

---

## 📦 Installation

### Via le dépôt TheWorms (recommandé, mises à jour automatiques)

1. Dans Kodi : **Paramètres → Système → Modules complémentaires** et activez **Sources inconnues**.
2. Installez le dépôt TheWorms depuis cette URL (Explorateur de fichiers → *Ajouter une source*, ou installation directe du zip) :
   ```
   https://raw.githubusercontent.com/TheWorms/kodi-repo/main/zips/repository.theworms/repository.theworms.zip
   ```
3. **Modules → Installer depuis un dépôt → TheWorms Repository → Extensions vidéo → EmbyCon**.

### Depuis un zip

Téléchargez la dernière archive depuis les [Releases](https://github.com/TheWorms/kodi-addon-emby/releases) puis, dans Kodi : **Modules → Installer depuis un fichier zip**.

---

## ⚙️ Configuration

1. Ouvrez les réglages de l'extension.
2. **Serveur & compte** : renseignez l'adresse et le port de votre serveur Emby (ou utilisez la détection automatique), puis vos identifiants.
3. Parcourez votre médiathèque depuis l'entrée **EmbyCon** de Kodi, ou ajoutez des **widgets** à votre écran d'accueil.

> Pour que les éléments vus disparaissent des listes et widgets, activez **Affichage & listes → Organisation → Masquer les éléments déjà vus**.

---

## 🖥️ Compatibilité

- **Kodi 21 (Omega)** et versions compatibles Python 3.
- Testé sur CoreELEC (ODROID-N2+).
- Le rafraîchissement automatique des widgets nécessite un skin qui évalue les jetons `$INFO[...]` dans les chemins de widgets (ex. skins dérivés d'Arctic Zephyr).

---

## 🙏 Crédits & licence

- Addon d'origine : **[EmbyCon](https://github.com/faush01/plugin.video.embycon)** par **faush01 / Team B**.
- Fork francophone et fonctionnalités additionnelles : **[TheWorms](https://github.com/TheWorms)**.
- Licence : **[GPL-2.0](LICENSE.txt)** — le code source complet est disponible dans ce dépôt, conformément aux termes de la licence.

Emby est une marque de Emby LLC. Ce projet n'est pas affilié à Emby LLC ni à Kodi/XBMC Foundation.

---

## 🤝 Contribution

Les rapports de bugs et suggestions sont bienvenus via les [issues](https://github.com/TheWorms/kodi-addon-emby/issues). Merci de préciser votre version de Kodi, votre skin et de joindre les lignes de log pertinentes.
