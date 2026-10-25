"""v1.20.0 : genere resources/settings.xml + chaines (en_gb, fr_fr).

Organisation validee (proposition « Réglages EmbyCon réorganisés ») :
7 menus, 93 reglages, une aide par reglage, valeurs lisibles.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(sys.argv[1])
SETTINGS = ROOT / "resources" / "settings.xml"
PO_EN = ROOT / "resources/language/resource.language.en_gb/strings.po"
PO_FR = ROOT / "resources/language/resource.language.fr_fr/strings.po"

FIRST_ID = 30600


# ------------------------------------------------------------------ chaines ---
def _po_blocks(text: str) -> list[str]:
    return text.split("\n\n")


def _block_id(block: str) -> int | None:
    m = re.search(r'^msgctxt "#(\d+)"', block, flags=re.M)
    return int(m.group(1)) if m else None


def _po_unquote(block: str, key: str) -> str:
    lines = block.split("\n")
    out, on = [], False
    for line in lines:
        if line.startswith(key + " "):
            on = True
            out.append(line[len(key) + 1:])
        elif on and line.startswith('"'):
            out.append(line)
        else:
            on = False
    return "".join(s[1:-1] for s in out).replace('\\"', '"').replace("\\\\", "\\")


EXISTING_EN: dict[int, str] = {}
EXISTING_FR: dict[int, str] = {}
for blk in _po_blocks(PO_EN.read_text(encoding="utf-8")):
    i = _block_id(blk)
    if i is not None:
        EXISTING_EN[i] = _po_unquote(blk, "msgid")
for blk in _po_blocks(PO_FR.read_text(encoding="utf-8")):
    i = _block_id(blk)
    if i is not None:
        EXISTING_FR[i] = _po_unquote(blk, "msgstr")

NEW: dict[int, tuple[str, str]] = {}
_by_text: dict[tuple[str, str], int] = {}
_next = [max([FIRST_ID - 1] + [i for i in EXISTING_EN if i >= FIRST_ID]) + 1]


def T(en: str, fr: str) -> int:
    """Identifiant de chaine (reutilise si le meme couple existe deja)."""
    key = (en, fr)
    if key in _by_text:
        return _by_text[key]
    for i, txt in EXISTING_EN.items():
        if txt == en and EXISTING_FR.get(i, "") == fr:
            _by_text[key] = i
            return i
    i = _next[0]
    _next[0] += 1
    NEW[i] = key
    _by_text[key] = i
    return i


# --------------------------------------------------------------- reglages ---
class S:
    def __init__(self, id, kind, en, fr, help_en, help_fr, default=None, **kw):
        self.id, self.kind = id, kind
        self.label = T(en, fr)
        self.help = T(help_en, help_fr)
        self.default = default
        self.kw = kw


def opt(value, en, fr=None):
    return (str(value), T(en, fr if fr is not None else en))


def ref(value, string_id):
    return (str(value), string_id)


NO = ("No", "Non")
YES = ("Yes", "Oui")
NEXT = [opt(0, "Do nothing", "Ne rien faire"),
        opt(1, "Offer the next one, then play it", "Proposer le suivant, puis l'enchaîner"),
        opt(2, "Play the next one without asking", "Enchaîner sans demander")]
SORT_REST = [opt("9a", "Release date, oldest → newest", "Date de sortie, ancien → récent"),
             opt("9d", "Release date, newest → oldest", "Date de sortie, récent → ancien"),
             opt("4d", "Date added, newest first", "Date d'ajout, récent d'abord"),
             opt("4a", "Date added, oldest first", "Date d'ajout, ancien d'abord"),
             opt("2a", "Title, A → Z", "Titre, A → Z"),
             opt("2d", "Title, Z → A", "Titre, Z → A"),
             opt("7d", "Rating, best first", "Note, meilleure d'abord")]
SORT = [opt("0", "Server order", "Ordre du serveur")] + SORT_REST
SORT_BOX = [opt("0", "Collection order in Emby", "Ordre de la collection dans Emby")] + SORT_REST
SORT_SERIE = [opt("0", "Season and episode numbers", "Numéros de saison et d'épisode"),
              opt("9a", "Air date, oldest → newest", "Date de diffusion, ancien → récent"),
              opt("9d", "Air date, newest → oldest", "Date de diffusion, récent → ancien"),
              opt("2a", "Title, A → Z", "Titre, A → Z")]
LANGS = [ref(v, i) for v, i in (("fre", 30481), ("eng", 30482), ("spa", 30483), ("ger", 30484),
                                ("ita", 30485), ("por", 30486), ("jpn", 30487), ("dut", 30488))]
DELETE = [opt(100, "Never", "Jamais"), opt(95, "After 95 % watched", "Après 95 % vus"),
          opt(90, "After 90 % watched", "Après 90 % vus"), opt(80, "After 80 % watched", "Après 80 % vus")]
F_SEC = T("{0:d} s", "{0:d} s")
F_MIN = T("{0:d} min", "{0:d} min")
F_INT = T("{0:d}", "{0:d}")
F_KBPS = T("{0:d} kb/s", "{0:d} kb/s")
F_PCT = T("{0:d} %", "{0:d} %")
F_PX = T("{0:d} px", "{0:d} px")
F_MO = T("{0:d} MB", "{0:d} Mo")
F_HOUR = T("{0:d} h", "{0:d} h")
F_BEFORE_END = T("{0:d} s before the end", "{0:d} s avant la fin")
L_NO = T(*NO)

ACTION = "RunScript(plugin.video.embycon,0,?mode={0})"


def bool_(id, en, fr, hen, hfr, default, **kw):
    return S(id, "bool", en, fr, hen, hfr, default, **kw)


def spin(id, en, fr, hen, hfr, default, lo, step, hi, fmt, minlabel=None, **kw):
    return S(id, "spin", en, fr, hen, hfr, default, lo=lo, step=step, hi=hi, fmt=fmt,
             minlabel=T(*minlabel) if isinstance(minlabel, tuple) else minlabel, **kw)


def slider(id, en, fr, hen, hfr, default, lo, step, hi, fmt, **kw):
    return S(id, "slider", en, fr, hen, hfr, default, lo=lo, step=step, hi=hi, fmt=fmt, **kw)


def ilist(id, en, fr, hen, hfr, default, options, control="list", **kw):
    return S(id, "ilist", en, fr, hen, hfr, default, options=options, control=control, **kw)


def slist(id, en, fr, hen, hfr, default, options, control="list", **kw):
    return S(id, "slist", en, fr, hen, hfr, default, options=options, control=control, **kw)


def action(id, en, fr, hen, hfr, mode, **kw):
    return S(id, "action", en, fr, hen, hfr, None, data=ACTION.format(mode), **kw)


def edit(id, en, fr, hen, hfr, default, fmt="string", hidden=False, vtype="string", **kw):
    return S(id, "edit", en, fr, hen, hfr, default, fmt=fmt, hidden=hidden, vtype=vtype, **kw)


def vis(setting, value, op="is"):
    return {"visible": (op, setting, value)}


CATS = [
 ("lecture", ("Playback", "Lecture"),
  ("What happens when a video starts: resume, languages, quality.",
   "Ce qui se passe quand je lance une vidéo : reprise, langues, qualité."), [
  (("Resume", "Reprise"), [
   bool_("forceAutoResume", "Resume where I left off", "Reprendre là où je m'étais arrêté",
         "Resumes straight from the last position. Off: EmbyCon asks « Resume » or « From the beginning ».",
         "Reprend directement à la dernière position. Désactivé : EmbyCon demande « Reprendre » ou « Depuis le début ».", "true"),
   spin("jump_back_amount", "Go back a little when resuming", "Revenir un peu en arrière à la reprise",
        "Rewinds a few seconds before resuming, to pick up the thread.",
        "Recule de quelques secondes avant de reprendre, pour retrouver le fil.", "15", 0, 1, 60, F_SEC, NO),
   bool_("auto_play_first_version", "Several versions of a movie: play the first", "Plusieurs versions d'un film : lire la première",
         "When a movie exists in several versions (4K, 1080p…), plays the first one without asking.",
         "Quand un film existe en plusieurs versions (4K, 1080p…), lance la première sans demander laquelle.", "false"),
   bool_("play_cinema_intros", "Trailers before the movie", "Bandes-annonces avant le film",
         "Plays the intros set up in Emby (cinema mode) before a movie started from the beginning.",
         "Lit les intros configurées dans Emby (mode cinéma) avant un film lancé depuis le début.", "false"),
   bool_("stopPlaybackOnScreensaver", "Stop the video when the screensaver starts", "Arrêter la vidéo quand l'écran de veille démarre",
         "A paused video is stopped, and its position saved, when the Kodi screensaver starts.",
         "Une vidéo en pause est arrêtée, et sa position enregistrée, quand l'écran de veille de Kodi s'active.", "true"),
  ]),
  (("Audio and subtitles", "Audio et sous-titres"), [
   slist("pref_audio_lang", "My audio language", "Ma langue audio",
         "Used by the automatic subtitle choice below.", "Sert au choix automatique des sous-titres ci-dessous.", "fre", LANGS),
   slist("pref_subtitle_lang", "My subtitle language", "Ma langue de sous-titres",
         "Language used for automatic subtitles and for forced subtitles.",
         "Langue utilisée pour les sous-titres automatiques et les sous-titres forcés.", "fre", LANGS),
   ilist("subtitle_auto_mode", "Subtitles when the audio is not in my language", "Sous-titres si l'audio n'est pas dans ma langue",
         "Audio in another language: subtitles in my language are turned on. Audio in my language: they are turned off. A choice made by hand is always kept.",
         "Audio dans une autre langue : les sous-titres dans ma langue s'activent. Audio dans ma langue : ils sont coupés. Un choix fait à la main est toujours respecté.",
         "0", [opt(0, *NO), opt(1, *YES)], control="spinner"),
   bool_("subtitle_forced_auto", "Forced subtitles in my language", "Sous-titres forcés dans ma langue",
         "Forced subtitles only translate the parts spoken in another language (foreign dialogue, signs).",
         "Les sous-titres forcés ne traduisent que les passages dans une autre langue (dialogues étrangers, panneaux).", "true"),
   ilist("direct_stream_sub_select", "External subtitles: ask which ones", "Sous-titres externes : demander lesquels",
         "For separate subtitle files (.srt…): show a choice list when playback starts.",
         "Pour les fichiers de sous-titres séparés (.srt…) : afficher une liste de choix au lancement.",
         "0", [opt(0, "Never", "Jamais"), opt(1, "If there are several", "S'il y en a plusieurs"), opt(2, "Always", "Toujours")]),
  ]),
  (("Stream quality", "Qualité du flux"), [
   ilist("bitrate_mode", "Quality", "Qualité",
         "Automatic: EmbyCon regularly measures the connection to the server and sets the bitrate. Fixed bitrate: you choose the limit.",
         "Automatique : EmbyCon mesure régulièrement la connexion au serveur et règle le débit. Débit fixe : tu choisis la limite.",
         "0", [opt(1, "Automatic, based on the connection", "Automatique, selon la connexion"), opt(0, "Fixed bitrate", "Débit fixe")]),
   slider("auto_bitrate_margin", "Safety margin", "Marge de sécurité",
          "Share of the measured bitrate actually used. 80 % leaves room if the connection weakens.",
          "Part du débit mesuré vraiment utilisée. 80 % laisse de la marge si la connexion faiblit.",
          "80", 50, 5, 100, F_PCT, parent="bitrate_mode", deps=vis("bitrate_mode", "1")),
   spin("auto_bitrate_min", "Minimum bitrate", "Débit minimum",
        "The bitrate never goes below this, even after a bad measurement.",
        "Le débit ne descend jamais en dessous, même si une mesure est mauvaise.",
        "2000", 0, 500, 20000, F_KBPS, parent="bitrate_mode", deps=vis("bitrate_mode", "1")),
   spin("auto_bitrate_max", "Maximum bitrate", "Débit maximum",
        "Cap, even if the connection allows more.", "Plafond, même si la connexion permet davantage.",
        "0", 0, 5000, 200000, F_KBPS, ("No limit", "Sans limite"), parent="bitrate_mode", deps=vis("bitrate_mode", "1")),
   edit("auto_bitrate_last", "Last measurement", "Dernière mesure",
        "Result of the last connection measurement.", "Résultat de la dernière mesure de la connexion.",
        "", parent="bitrate_mode", deps=vis("bitrate_mode", "1"), readonly=True),
   action("auto_bitrate_measure_now", "Measure now", "Mesurer maintenant",
          "Starts a measurement right away.", "Lance une mesure tout de suite.", "AUTO_BITRATE_NOW",
          parent="bitrate_mode", deps=vis("bitrate_mode", "1")),
   edit("max_stream_bitrate", "Maximum bitrate (kb/s)", "Débit maximal (kb/s)",
        "Limit sent to the Emby server: above it, the server transcodes the video.",
        "Limite envoyée au serveur Emby : au-delà, il transcode la vidéo.",
        "75000", fmt="integer", vtype="number", parent="bitrate_mode", deps=vis("bitrate_mode", "0")),
  ]),
 ]),
 ("enchainements", ("Skips and up next", "Enchaînements"),
  ("Intro, credits, next episode and next movie, and what happens at the end.",
   "Intro, générique, épisode et film suivants, et ce qui se passe à la fin."), [
  (("Intro and credits", "Intro et générique"), [
   ilist("skip_intros", "Series intro", "Intro des séries",
         "Relies on the intro markers detected by Emby.", "S'appuie sur les marqueurs d'intro détectés par Emby.",
         "0", [opt(0, "Do nothing", "Ne rien faire"), opt(1, "« Skip intro » button", "Bouton « Passer l'intro »"),
               opt(2, "Skip automatically", "Passer automatiquement")]),
   spin("skip_intro_fallback_seconds", "Without an Emby marker: skip the start", "Sans marqueur Emby : sauter le début",
        "If Emby has not found the intro, skips this many seconds at the start of each episode.",
        "Si Emby n'a pas repéré l'intro, saute ce nombre de secondes au début de chaque épisode.",
        "0", 0, 5, 180, F_SEC, NO, parent="skip_intros", deps=vis("skip_intros", "0", "!is")),
   ilist("skip_credits", "End credits", "Générique de fin",
         "Relies on the credits markers detected by Emby.", "S'appuie sur les marqueurs de générique détectés par Emby.",
         "0", [opt(0, "Do nothing", "Ne rien faire"), opt(1, "« Skip credits » button", "Bouton « Passer le générique »"),
               opt(2, "Skip automatically", "Passer automatiquement")]),
   spin("skip_credits_fallback_seconds", "Without an Emby marker: offer before the end", "Sans marqueur Emby : proposer avant la fin",
        "If Emby has not found the credits, the skip is offered this many seconds before the end.",
        "Si Emby n'a pas repéré le générique, le saut est proposé ce nombre de secondes avant la fin.",
        "0", 0, 10, 600, F_SEC, NO, parent="skip_credits", deps=vis("skip_credits", "0", "!is")),
  ]),
  (("Next episode", "Épisode suivant"), [
   ilist("next_episode_mode", "At the end of an episode", "À la fin d'un épisode",
         "Offer: a window announces the next episode before the end; if you do nothing, it starts at the end.",
         "Proposer : une fenêtre annonce l'épisode suivant avant la fin ; sans réponse de ta part, il démarre à la fin.",
         "1", NEXT),
   spin("play_next_trigger_time", "Show the offer", "Afficher la proposition",
        "When the « Next episode » window appears.", "Moment où la fenêtre « Épisode suivant » apparaît.",
        "30", 10, 5, 180, F_BEFORE_END, parent="next_episode_mode", deps=vis("next_episode_mode", "1")),
  ]),
  (("Next movie in a collection", "Film suivant d'une collection"), [
   ilist("next_movie_mode", "At the end of a movie in a collection", "À la fin d'un film d'une collection",
         "An Emby collection groups the movies of a saga (Star Wars, Alien…).",
         "Une collection Emby regroupe les films d'une même saga (Star Wars, Alien…).", "1", NEXT),
   ilist("next_movie_trigger_time", "Show the offer", "Afficher la proposition",
         "Used when Emby has no credits marker; otherwise the offer appears when the credits start.",
         "Utilisé quand Emby n'a pas de marqueur de générique ; sinon la proposition apparaît au début du générique.",
         "180", [opt(v, en + " before the end", fr + " avant la fin") for v, en, fr in (
             (30, "30 s", "30 s"), (60, "1 min", "1 min"), (90, "1 min 30", "1 min 30"), (120, "2 min", "2 min"),
             (180, "3 min", "3 min"), (240, "4 min", "4 min"), (300, "5 min", "5 min"), (420, "7 min", "7 min"),
             (600, "10 min", "10 min"), (900, "15 min", "15 min"))],
         control="spinner", parent="next_movie_mode", deps=vis("next_movie_mode", "1")),
   ilist("collection_play_order", "Collection playback order", "Ordre de lecture d'une collection",
         "Used by « Play all » and for the next movie.", "Sert à « Tout lire » et au film suivant.",
         "0", [opt(0, "Oldest to newest", "Du plus ancien au plus récent"), opt(1, "Newest to oldest", "Du plus récent au plus ancien"),
               opt(2, "By title", "Par titre")]),
  ]),
  (("After playback", "Après la lecture"), [
   bool_("auto_refresh_after_playback", "Update the list when coming back", "Mettre à jour la liste en revenant",
         "Refreshes the displayed list (watched, unwatched, resume) when playback stops.",
         "Rafraîchit la liste affichée (vu, non vu, reprise) quand la lecture s'arrête.", "true"),
   ilist("promptDeleteEpisodePercentage", "Offer to delete a watched episode", "Proposer de supprimer un épisode vu",
         "Deletes the episode from the server after confirmation, once this share has been watched.",
         "Supprime l'épisode du serveur après confirmation, une fois cette part regardée.", "100", DELETE, control="spinner"),
   ilist("promptDeleteMoviePercentage", "Offer to delete a watched movie", "Proposer de supprimer un film vu",
         "Deletes the movie from the server after confirmation, once this share has been watched.",
         "Supprime le film du serveur après confirmation, une fois cette part regardée.", "100", DELETE, control="spinner"),
  ]),
 ]),
 ("listes", ("Lists and sorting", "Listes et tri"),
  ("What appears in lists, and in which order.", "Ce qui apparaît dans les listes, et dans quel ordre."), [
  (("Content", "Contenu"), [
   bool_("group_movies", "Group movies of the same collection", "Regrouper les films d'une même collection",
         "In Movies, the movies of a collection are gathered in a single folder.",
         "Dans Films, les films d'une collection sont réunis dans un seul dossier.", "true"),
   bool_("hide_watched", "Hide what I have already watched", "Masquer ce que j'ai déjà vu",
         "Applies to movie, series and episode lists.", "S'applique aux listes de films, séries et épisodes.", "false"),
   ilist("flatten_tvshow_seasons", "Seasons of a series", "Saisons d'une série",
         "How a series opens.", "Comment s'ouvre une série.",
         "0", [opt(0, "Always show them", "Toujours les afficher"), opt(1, "Skip if there is only one", "Sauter s'il n'y en a qu'une"),
               opt(2, "Never: episodes in a row", "Jamais : épisodes à la suite")]),
   bool_("show_all_episodes", "Add « All episodes » in a series", "Ajouter « Tous les épisodes » dans une série",
         "Adds an entry above the seasons that lists every episode of the series.",
         "Ajoute en tête des saisons une entrée qui liste tous les épisodes de la série.", "false"),
   bool_("show_empty_folders", "Show empty folders", "Afficher les dossiers vides",
         "Series, seasons or collections with nothing playable.", "Séries, saisons ou collections sans contenu lisible.", "false"),
  ]),
  (("List order", "Ordre des listes"), [
   slist("list_sort-Movies", "Movies", "Films", "Order of the Movies list.", "Ordre de la liste Films.", "0", SORT),
   slist("list_sort-Series", "Series", "Séries", "Order of the Series list.", "Ordre de la liste Séries.", "0", SORT),
   slist("list_sort-BoxSets", "Collections", "Collections",
         "Order of the Collections list and widget (the skin follows this order).",
         "Ordre de la liste et du widget Collections (le skin suit cet ordre).", "4d", SORT),
   slist("list_sort-InBoxSet", "Movies in a collection", "Films d'une collection",
         "Order of the movies when a collection is opened.", "Ordre des films quand on ouvre une collection.", "9a", SORT_BOX),
   slist("list_sort-InSeries", "Seasons and episodes", "Saisons et épisodes",
         "Order inside a series.", "Ordre à l'intérieur d'une série.", "9d", SORT_SERIE),
   bool_("use_prem_date_for_added", "Skin widgets: release date instead of date added",
         "Widgets du skin : date de sortie au lieu de la date d'ajout",
         "Widgets sorted by « date added » (Arctic's Recently added…) then follow the release date of movies and episodes.",
         "Les widgets triés par « date d'ajout » (Ajouts récents d'Arctic…) suivent alors la date de sortie des films et épisodes.", "false"),
  ]),
  (("List size", "Taille des listes"), [
   spin("itemsPerPage", "Items per page", "Éléments par page",
        "Beyond this, the list is split into pages.", "Au-delà, la liste est découpée en pages.",
        "0", 0, 5, 200, F_INT, ("Everything on one page", "Tout sur une page")),
   slider("show_x_filtered_items", "Items in short lists and widgets", "Éléments des listes courtes et des widgets",
          "Number of items in « Recently added », « In progress »… and in widgets.",
          "Nombre d'éléments de « Ajouts récents », « En cours »… et des widgets.", "20", 5, 1, 100, F_INT),
  ]),
  (("Views", "Vues"), [
   bool_("view_auto_remember", "Remember the view chosen in each list", "Retenir la vue choisie dans chaque liste",
         "List, posters, thumbnails…: the chosen view is applied again on the next visit.",
         "Liste, affiches, vignettes… : la vue choisie est réappliquée à la prochaine visite.", "true"),
   action("views_reset_action", "Forget remembered views", "Oublier les vues retenues",
          "Every list goes back to the skin's default view.", "Toutes les listes reprennent la vue par défaut du skin.", "RESET_VIEWS"),
  ]),
 ]),
 ("fiches", ("Titles and details", "Titres et fiches"),
  ("What titles and the movie and episode details show.", "Ce qu'affichent les titres et les fiches des films et des épisodes."), [
  (("Titles", "Titres"), [
   bool_("addCounts", "Number of unwatched episodes", "Nombre d'épisodes non vus",
         "Added after the name of a series or season, for example « Lupin (3) ».",
         "Ajouté après le nom d'une série ou d'une saison, par exemple « Lupin (3) ».", "false"),
   bool_("addResumePercent", "Percentage already watched", "Pourcentage déjà vu",
         "Added after the title of a started item, for example « Dune (45 %) ».",
         "Ajouté après le titre d'un élément commencé, par exemple « Dune (45 %) ».", "false"),
   bool_("addSubtitleAvailable", "(st) mark when subtitles exist", "Mention (st) si des sous-titres existent",
         "Added after the title, for example « Dune (st) ».", "Ajoutée après le titre, par exemple « Dune (st) ».", "false"),
   slist("episode_name_format", "Episode titles in mixed lists", "Titre des épisodes dans les listes mélangées",
         "For lists that mix several series: Recently added, In progress…",
         "Pour les listes qui mélangent plusieurs séries : Ajouts récents, En cours…",
         "{SeriesName} - {ItemName}",
         [opt("{SeriesName} - {ItemName}", "Lupin - Chapter 1", "Lupin - Chapitre 1"),
          opt("{ItemName}", "Chapter 1", "Chapitre 1"),
          opt("s{SeasonIndex}e{EpisodeIndex} - {ItemName}", "s1e1 - Chapter 1", "s1e1 - Chapitre 1"),
          opt("{SeriesName} - s{SeasonIndex}e{EpisodeIndex} - {ItemName}", "Lupin - s1e1 - Chapter 1", "Lupin - s1e1 - Chapitre 1")]),
  ]),
  (("Details", "Fiches"), [
   bool_("include_overview", "Overview", "Résumé", "The description of the movie or episode.",
         "Le texte de présentation du film ou de l'épisode.", "true"),
   bool_("include_people", "Cast and crew", "Acteurs et équipe", "More complete, but lists load more slowly.",
         "Plus complet, mais les listes se chargent plus lentement.", "false"),
   bool_("include_media", "Technical info (resolution, codecs, audio)", "Infos techniques (résolution, codecs, audio)",
         "Used by the skin for the 4K, HDR, Atmos… logos.", "Utilisées par le skin pour les logos 4K, HDR, Atmos…", "true"),
   bool_("hide_unwatched_details", "Spoiler protection for unwatched episodes", "Anti-spoiler pour les épisodes non vus",
         "Replaces the overview with « [Spoiler Alert] » and the episode image with the series poster.",
         "Remplace le résumé par « [Spoiler Alert] » et l'image de l'épisode par l'affiche de la série.", "false"),
  ]),
  (("Images", "Images"), [
   spin("max_image_width", "Maximum image size", "Taille maximale des images",
        "Shrinks downloaded images, useful on a slow connection.", "Réduit les images téléchargées, utile avec une connexion lente.",
        "0", 0, 128, 4096, F_PX, ("Original", "Originale")),
   bool_("cacheImagesOnScreenSaver", "Prepare images during the screensaver", "Préparer les images pendant l'écran de veille",
         "Downloads list images in the background so they show up immediately.",
         "Télécharge les images des listes en arrière-plan pour qu'elles s'affichent tout de suite.", "false"),
   spin("cacheImagesOnScreenSaver_interval", "Start again every", "Recommencer toutes les",
        "Without a value, preparation only starts again when the library has something new.",
        "Sans valeur, la préparation ne recommence que s'il y a du nouveau dans la bibliothèque.",
        "0", 0, 5, 60, F_MIN, ("When there is something new", "S'il y a du nouveau"),
        parent="cacheImagesOnScreenSaver", deps=vis("cacheImagesOnScreenSaver", "true")),
  ]),
 ]),
 ("hasard", ("Random movie", "Film au hasard"),
  ("The « Movies - Random » widget and the draw card.", "Le widget « Films - Aléatoire » et la fiche de tirage."), [
  (("Draw", "Tirage"), [
   bool_("random_widget_launches", "Opening the widget starts the draw", "Ouvrir le widget lance le tirage",
         "Opening « Movies - Random » from the home screen directly shows a randomly drawn movie, with Play, Next and Previous.",
         "Ouvrir « Films - Aléatoire » depuis l'accueil affiche directement la fiche d'un film tiré au sort, avec Lire, Suivant et Précédent.", "true"),
   bool_("random_movie_unplayed", "Only movies I have not watched", "Seulement des films que je n'ai pas vus",
         "Movies already watched are never drawn.", "Les films déjà vus ne sont jamais tirés.", "true"),
   bool_("random_continuous", "Play another random movie at the end", "Enchaîner un autre film au hasard à la fin",
         "When the movie ends, a new one is drawn with the same criteria and starts. Stopping playback goes back to the home screen.",
         "À la fin du film, un nouveau film est tiré avec les mêmes critères et démarre. Arrêter la lecture ramène à l'accueil.", "false"),
   spin("random_movie_max_minutes", "Maximum movie length", "Durée maximale du film",
        "For a short evening: leaves out movies that are too long.", "Pour une soirée courte : écarte les films trop longs.",
        "0", 0, 10, 240, F_MIN, ("No limit", "Sans limite")),
   spin("random_movie_refresh_interval", "Refresh the widget every", "Renouveler le widget toutes les",
        "A new selection appears on the home screen at this pace.", "Une nouvelle sélection apparaît sur l'accueil à ce rythme.",
        "5", 0, 5, 60, F_MIN, ("Never", "Jamais")),
  ]),
 ]),
 ("serveur", ("Server and account", "Serveur et compte"),
  ("Connection to the Emby server. Set once, rarely changed.", "Connexion au serveur Emby. Réglé une fois, rarement modifié."), [
  (("Server", "Serveur"), [
   action("detect_local_server_action", "Search for the server on the network", "Rechercher le serveur sur le réseau",
          "Looks for an Emby server on the local network and sets it up.",
          "Cherche un serveur Emby sur le réseau local et le configure.", "DETECT_SERVER_USER"),
   ilist("protocol", "Protocol", "Protocole", "HTTPS for a server reachable from the Internet.",
         "HTTPS pour un serveur accessible depuis Internet.", "0", [ref(0, 30391), ref(1, 30392)]),
   bool_("verify_cert", "Check the certificate", "Vérifier le certificat",
         "Only turn this off for a self-signed certificate.", "À désactiver seulement pour un certificat auto-signé.", "true",
         parent="protocol", deps=vis("protocol", "1")),
   edit("ipaddress", "Server address", "Adresse du serveur", "Domain name or IP address, without http:// or port.",
        "Nom de domaine ou adresse IP, sans http:// ni port.", "<none>"),
   edit("port", "Port", "Port", "8096 by default for HTTP, 8920 for HTTPS.", "8096 par défaut pour HTTP, 8920 pour HTTPS.",
        "8096", fmt="integer", vtype="number"),
  ]),
  (("Account", "Compte"), [
   action("change_emby_user_action", "Change user", "Changer d'utilisateur",
          "Pick another account on the Emby server.", "Choisir un autre compte du serveur Emby.", "CHANGE_USER"),
   edit("username", "User", "Utilisateur", "Emby account used by this Kodi.", "Compte Emby utilisé par ce Kodi.", ""),
   edit("password", "Password", "Mot de passe", "Password of the account.", "Mot de passe du compte.", "", hidden=True),
   bool_("save_user_to_settings", "Remember me", "Se souvenir de moi",
         "Keeps the user and password to log in again without typing them.",
         "Garde l'utilisateur et le mot de passe pour se reconnecter sans les retaper.", "true"),
  ]),
  (("This device", "Cet appareil"), [
   edit("deviceName", "Name of this Kodi in Emby", "Nom de ce Kodi dans Emby",
        "Name shown in the Emby dashboard (devices, now playing).",
        "Nom affiché dans le tableau de bord Emby (appareils, lectures en cours).", "EmbyCon"),
  ]),
 ]),
 ("avance", ("Advanced", "Avancé"),
  ("Only change these for playback or connection problems.", "À toucher seulement en cas de problème de lecture ou de connexion."), [
  (("Video transcoding", "Transcodage vidéo"), [
   bool_("allow_direct_file_play", "Play the file directly over the network", "Lire le fichier directement par le réseau",
         "Kodi opens the file on the network share instead of the Emby stream. The server path must be reachable from this Kodi.",
         "Kodi ouvre le fichier sur le partage réseau au lieu du flux Emby. Le chemin du serveur doit être accessible depuis ce Kodi.", "false"),
   ilist("av1_transcode", "AV1 videos", "Vidéos AV1",
         "The ODROID-N2+ processor cannot decode AV1: the server has to transcode it.",
         "Le processeur de l'ODROID-N2+ ne décode pas l'AV1 : le serveur doit le transcoder.",
         "0", [opt(0, "Automatic (transcoded on ODROID-N2+)", "Automatique (transcodées sur ODROID-N2+)"),
               opt(1, "Always transcode", "Toujours transcoder"), opt(2, "Play as is", "Lire telles quelles")]),
   bool_("force_transcode_h265", "Transcode HEVC (h265)", "Transcoder le HEVC (h265)",
         "The server converts these videos before sending them.", "Le serveur convertit ces vidéos avant de les envoyer.", "false"),
   bool_("force_transcode_mpeg2", "Transcode MPEG-2", "Transcoder le MPEG-2",
         "The server converts these videos before sending them.", "Le serveur convertit ces vidéos avant de les envoyer.", "false"),
   bool_("force_transcode_msmpeg4v3", "Transcode DivX (msmpeg4v3)", "Transcoder le DivX (msmpeg4v3)",
         "The server converts these videos before sending them.", "Le serveur convertit ces vidéos avant de les envoyer.", "false"),
   bool_("force_transcode_mpeg4", "Transcode MPEG-4", "Transcoder le MPEG-4",
         "The server converts these videos before sending them.", "Le serveur convertit ces vidéos avant de les envoyer.", "false"),
   slist("playback_max_width", "Maximum width", "Largeur maximale",
         "Above this, the server scales the picture down.", "Au-delà, le serveur réduit l'image.", "1920",
         [opt(v, v + " px" + {"1280": " (720p)", "1920": " (1080p)", "4096": " (4K)"}.get(v, ""))
          for v in ("640", "720", "1024", "1280", "1440", "1600", "1920", "2600", "4096")]),
   bool_("playback_video_force_8", "Convert video to 8 bits", "Convertir la vidéo en 8 bits",
         "Asks the server for 8-bit video (h264), for a screen that shows 10-bit or HDR badly.",
         "Demande au serveur une vidéo 8 bits (h264), pour un écran qui affiche mal le 10 bits ou le HDR.", "false"),
   edit("force_max_stream_bitrate", "Forced transcoding bitrate (kb/s)", "Débit d'un transcodage forcé (kb/s)",
        "Used by « Play with transcoding » in the context menu.", "Utilisé par « Lire en transcodant » du menu contextuel.",
        "7000", fmt="integer", vtype="number"),
  ]),
  (("Audio transcoding", "Transcodage audio"), [
   slist("audio_codec", "Audio codec", "Codec audio", "Format requested when the server transcodes the sound.",
         "Format demandé quand le serveur transcode le son.", "ac3", [opt("ac3", "AC3 (Dolby Digital)"), opt("aac", "AAC")]),
   edit("audio_playback_bitrate", "Audio bitrate (kb/s)", "Débit audio (kb/s)", "Bitrate of the transcoded sound.",
        "Débit du son transcodé.", "256", fmt="integer", vtype="number"),
   ilist("audio_max_channels", "Maximum audio channels", "Canaux audio maximum",
         "Above this, the server reduces the number of channels.", "Au-delà, le serveur réduit le nombre de canaux.", "8",
         [opt(1, "1 (mono)"), opt(2, "2 (stereo)", "2 (stéréo)"), opt(3, "3"), opt(4, "4"), opt(5, "5"),
          opt(6, "6 (5.1)"), opt(7, "7"), opt(8, "8 (7.1)")], control="spinner"),
  ]),
  (("Network", "Réseau"), [
   slider("http_timeout", "Server timeout", "Délai d'attente du serveur", "Beyond this, the request is abandoned.",
          "Au-delà, la requête est abandonnée.", "60", 5, 1, 300, F_SEC),
   slider("network_attempts", "Connection attempts", "Tentatives de connexion", "Number of tries before showing an error.",
          "Nombre d'essais avant d'afficher une erreur.", "3", 1, 1, 10, F_INT),
   slider("websocket_ping_interval", "Keep-alive signal (WebSocket)", "Signal de présence (WebSocket)",
          "Keeps the remote control connection open.", "Garde la connexion de contrôle à distance ouverte.", "20", 5, 5, 120, F_SEC),
   slider("auto_bitrate_test_size", "Bitrate test size", "Taille du test de débit",
          "Amount downloaded to measure the connection (automatic quality and manual test).",
          "Quantité téléchargée pour mesurer la connexion (qualité automatique et test manuel).", "8", 1, 1, 20, F_MO),
  ]),
  (("Cache", "Cache"), [
   spin("cache_duration", "Keep lists in cache", "Garder les listes en cache",
        "Lists already loaded show up instantly during this time.",
        "Les listes déjà chargées s'affichent instantanément pendant cette durée.", "24", 0, 1, 168, F_HOUR, ("Off", "Désactivé")),
   spin("revalidation_interval", "Re-check a cached list at most every", "Revérifier une liste en cache au plus toutes les",
        "Avoids asking the server for the same list every time it is shown.",
        "Évite de redemander la même liste au serveur à chaque affichage.", "10", 0, 1, 120, F_MIN,
        ("Every time", "À chaque affichage"), parent="cache_duration", deps=vis("cache_duration", "0", "!is")),
  ]),
  (("Kodi integration (restart required)", "Intégration à Kodi (redémarrage nécessaire)"), [
   bool_("websocket_enabled", "Remote control from Emby", "Contrôle à distance depuis Emby",
         "Control this Kodi from the Emby app or website, and receive library updates.",
         "Piloter ce Kodi depuis l'application ou le site Emby, et recevoir les mises à jour de la bibliothèque.", "true"),
   bool_("override_contextmenu", "EmbyCon context menu", "Menu contextuel EmbyCon",
         "Replaces the Kodi context menu on EmbyCon items.", "Remplace le menu contextuel de Kodi sur les éléments EmbyCon.", "true"),
   bool_("override_bookmarks", "EmbyCon chapters instead of bookmarks", "Chapitres EmbyCon à la place des signets",
         "Replaces the Kodi « Bookmarks » window with the list of Emby chapters.",
         "Remplace la fenêtre « Signets » de Kodi par la liste des chapitres Emby.", "true"),
  ]),
  (("Troubleshooting", "Dépannage"), [
   bool_("showLoadProgress", "Show loading progress", "Afficher la progression du chargement",
         "A progress bar while lists are loading.", "Une barre de progression pendant le chargement des listes.", "false"),
   bool_("suppressErrors", "Hide connection errors", "Masquer les erreurs de connexion",
         "No more notification when the server does not answer.", "Plus de notification quand le serveur ne répond pas.", "false"),
   bool_("log_debug", "Detailed log (debug)", "Journal détaillé (débogage)",
         "Turn on for a diagnosis, then off again: the log grows quickly.",
         "À activer pour un diagnostic, puis à désactiver : le journal grossit vite.", "false"),
   edit("settings_layout", "Settings layout", "Organisation des réglages", "Internal.", "Interne.", "", hidden_setting=True),
  ]),
 ]),
]


# ------------------------------------------------------------- XML ------------
def x_options(options, indent):
    out = [indent + "<options>"]
    for value, label in options:
        out.append(indent + "\t<option label=\"%d\">%s</option>" % (label, escape(value)))
    out.append(indent + "</options>")
    return out


def x_deps(s, indent):
    deps = s.kw.get("deps")
    readonly = s.kw.get("readonly")
    if not deps and not readonly:
        return []
    out = [indent + "<dependencies>"]
    if deps:
        op, setting, value = deps["visible"]
        out += [indent + "\t<dependency type=\"visible\">",
                indent + "\t\t<condition operator=\"%s\" setting=\"%s\">%s</condition>" % (op, setting, escape(value)),
                indent + "\t</dependency>"]
    if readonly:
        out.append(indent + "\t<dependency type=\"enable\" on=\"property\" name=\"infobool\">false</dependency>")
    out.append(indent + "</dependencies>")
    return out


def x_setting(s, t):
    i1, i2 = t + "\t", t + "\t\t"
    vtype = {"bool": "boolean", "spin": "integer", "slider": "integer", "ilist": "integer", "slist": "string",
             "action": "action"}.get(s.kind, s.kw.get("vtype", "string"))
    parent = s.kw.get("parent")
    head = "%s<setting id=%s type=\"%s\" label=\"%d\" help=\"%d\"%s>" % (
        t, quoteattr(s.id), vtype, s.label, s.help, (" parent=%s" % quoteattr(parent)) if parent else "")
    out = [head, i1 + "<level>0</level>"]
    if s.kw.get("hidden_setting"):
        out.append(i1 + "<visible>false</visible>")
    if s.kind != "action":
        out.append(i1 + ("<default>%s</default>" % escape(s.default) if s.default not in (None, "") else "<default />"))
    # contraintes
    if s.kind in ("spin", "slider"):
        lo = "<minimum label=\"%d\">%d</minimum>" % (s.kw["minlabel"], s.kw["lo"]) if s.kw.get("minlabel") else "<minimum>%d</minimum>" % s.kw["lo"]
        out += [i1 + "<constraints>", i2 + lo, i2 + "<step>%d</step>" % s.kw["step"], i2 + "<maximum>%d</maximum>" % s.kw["hi"], i1 + "</constraints>"]
    elif s.kind in ("ilist", "slist"):
        out += [i1 + "<constraints>"] + x_options(s.kw["options"], i2) + [i1 + "</constraints>"]
    elif s.kind == "edit" and s.kw.get("vtype", "string") == "string":
        out += [i1 + "<constraints>", i2 + "<allowempty>true</allowempty>", i1 + "</constraints>"]
    out += x_deps(s, i1)
    if s.kw.get("hidden_setting"):
        out.append(i1 + "<enable>false</enable>")
    # controle
    if s.kind == "bool":
        out.append(i1 + "<control type=\"toggle\" />")
    elif s.kind == "spin":
        out += [i1 + "<control type=\"spinner\" format=\"string\">", i2 + "<formatlabel>%d</formatlabel>" % s.kw["fmt"], i1 + "</control>"]
    elif s.kind == "slider":
        out += [i1 + "<control type=\"slider\" format=\"integer\">", i2 + "<formatlabel>%d</formatlabel>" % s.kw["fmt"],
                i2 + "<popup>false</popup>", i1 + "</control>"]
    elif s.kind in ("ilist", "slist"):
        if s.kw.get("control") == "spinner":
            out.append(i1 + "<control type=\"spinner\" format=\"string\" />")
        else:
            out += [i1 + "<control type=\"list\" format=\"string\">", i2 + "<heading>%d</heading>" % s.label, i1 + "</control>"]
    elif s.kind == "action":
        out += [i1 + "<data>%s</data>" % escape(s.kw["data"]), i1 + "<control type=\"button\" format=\"action\">",
                i2 + "<close>true</close>", i1 + "</control>"]
    else:
        out += [i1 + "<control type=\"edit\" format=\"%s\">" % s.kw.get("fmt", "string"), i2 + "<heading>%d</heading>" % s.label]
        if s.kw.get("fmt", "string") == "string":
            out.append(i2 + "<hidden>%s</hidden>" % ("true" if s.kw.get("hidden") else "false"))
        out.append(i1 + "</control>")
    out.append(t + "</setting>")
    return out


lines = ['<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
         "<!-- v1.20.0 : genere par scripts/gen_settings.py - organisation en 7 menus -->",
         '<settings version="1">', '\t<section id="plugin.video.embycon">']
ALL_IDS = []
for cid, (cen, cfr), (hen, hfr), groups in CATS:
    lines.append("\t\t<category id=\"%s\" label=\"%d\" help=\"%d\">" % (cid, T(cen, cfr), T(hen, hfr)))
    for gi, ((gen, gfr), settings) in enumerate(groups, 1):
        lines.append("\t\t\t<group id=\"%d\" label=\"%d\">" % (gi, T(gen, gfr)))
        for s in settings:
            ALL_IDS.append(s.id)
            lines += x_setting(s, "\t\t\t\t")
        lines.append("\t\t\t</group>")
    lines.append("\t\t</category>")
lines += ["\t</section>", "</settings>", ""]
SETTINGS.write_text("\n".join(lines), encoding="utf-8")


# ------------------------------------------------------------ ecriture po ---
def po_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def append_po(path: Path, french: bool) -> None:
    text = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
    for i in sorted(NEW):
        en, fr = NEW[i]
        text += "\nmsgctxt \"#%d\"\nmsgid %s\nmsgstr %s\n" % (i, po_quote(en), po_quote(fr if french else ""))
    path.write_text(text, encoding="utf-8")


append_po(PO_EN, False)
append_po(PO_FR, True)
print("reglages :", len(ALL_IDS), "| nouvelles chaines :", len(NEW),  # noqa: T201
      ("| ids %d - %d" % (min(NEW), max(NEW))) if NEW else "")
assert len(ALL_IDS) == len(set(ALL_IDS)), "id en double"
Path(sys.argv[2]).write_text("\n".join(ALL_IDS), encoding="utf-8")
