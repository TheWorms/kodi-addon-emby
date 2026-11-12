# Gnu General Public License - see LICENSE.TXT
"""v1.22.0 : choix des pistes audio et sous-titres d'une lecture transcodee.

Quand la video doit etre reduite (transcodage), le serveur ne garde qu'UNE
piste audio et grave ou fournit UN sous-titre : il faut les lui donner avant
la lecture. Jusqu'ici EmbyCon posait deux questions a chaque fois ; ce module
choisit automatiquement d'apres les langues preferees, avec les memes regles
que la lecture directe (apply_intelligent_subtitle), ou prepare des listes
lisibles pour le choix manuel.

Module sans dependance Kodi : testable hors Kodi.
"""

from __future__ import annotations

from typing import Callable

# correspondance de langue tolerante (codes ISO 639-2/B et /T, codes 2 lettres,
# noms courants FR/EN) — deplace depuis play_utils (v1.18)
LANG_ALIASES = {
    "fre": {"fre", "fra", "fr", "french", "francais", "français"},
    "eng": {"eng", "en", "english", "anglais"},
    "spa": {"spa", "es", "spanish", "espanol", "español", "espagnol"},
    "ger": {"ger", "deu", "de", "german", "allemand"},
    "ita": {"ita", "it", "italian", "italien"},
    "por": {"por", "pt", "portuguese", "portugais"},
    "jpn": {"jpn", "ja", "japanese", "japonais"},
    "dut": {"dut", "nld", "nl", "dutch", "neerlandais", "néerlandais"},
}

# mots qui signalent une piste audio de commentaire (jamais choisie d'office)
_COMMENTARY = ("comment", "director", "réalisateur", "realisateur")


def lang_matches(stream_lang: str, pref_code: str) -> bool:
    """Vrai si la langue d'un flux correspond au code de langue prefere."""
    if not stream_lang or not pref_code:
        return False
    s = stream_lang.strip().lower()
    aliases = LANG_ALIASES.get(pref_code, {pref_code})
    for a in aliases:
        if s == a or s.startswith(a):
            return True
    return False


def canonical_lang(lang: str) -> str | None:
    """Code canonique (cle de LANG_ALIASES) d'une langue de flux, ou None."""
    if not lang:
        return None
    s = lang.strip().lower()
    for code, aliases in LANG_ALIASES.items():
        for a in aliases:
            if s == a or s.startswith(a):
                return code
    return s


def _audios(streams: list) -> list:
    return [s for s in streams or [] if s.get("Type") == "Audio"]


def _subtitles(streams: list) -> list:
    return [s for s in streams or [] if s.get("Type") == "Subtitle"]


def _is_commentary(stream: dict) -> bool:
    title = str(stream.get("Title") or stream.get("DisplayTitle") or "").lower()
    return any(word in title for word in _COMMENTARY)


def choose_audio(streams: list, pref_audio: str, default_index) -> int | None:
    """Index Emby de la piste audio : langue preferee, sinon celle du serveur.

    Parmi les pistes de la langue preferee : pas de commentaire, la piste par
    defaut d'abord, puis la plus riche en canaux.
    """
    audios = _audios(streams)
    if not audios:
        return None
    if pref_audio:
        matches = [
            s
            for s in audios
            if lang_matches(s.get("Language", ""), pref_audio) and not _is_commentary(s)
        ]
        if matches:
            matches.sort(
                key=lambda s: (not s.get("IsDefault"), -(s.get("Channels") or 0))
            )
            return matches[0].get("Index")
    for s in audios:
        if s.get("Index") == default_index:
            return default_index
    plain = [s for s in audios if not _is_commentary(s)] or audios
    return plain[0].get("Index")


def choose_subtitle(
    streams: list,
    audio_lang: str,
    pref_audio: str,
    pref_sub: str,
    subs_if_foreign: bool,
    forced_auto: bool,
) -> int | None:
    """Index Emby du sous-titre a fournir, ou None (aucun).

    Memes regles que la lecture directe :
    - audio dans une autre langue que la mienne (et reglage « Sous-titres si
      l'audio n'est pas dans ma langue » actif) : sous-titres complets dans ma
      langue, a defaut des sous-titres forces dans ma langue ;
    - sinon : sous-titres forces seulement (passages etrangers, panneaux),
      dans la langue de l'audio ou dans ma langue, si le reglage est actif.
    Une langue audio inconnue n'est pas consideree comme etrangere.
    """
    subs = _subtitles(streams)
    if not subs:
        return None
    foreign = (
        bool(audio_lang)
        and bool(pref_audio)
        and not lang_matches(audio_lang, pref_audio)
    )
    if subs_if_foreign and pref_sub and foreign:
        mine = [s for s in subs if lang_matches(s.get("Language", ""), pref_sub)]
        full = [s for s in mine if not s.get("IsForced")]
        full.sort(key=lambda s: not s.get("IsDefault"))
        if full:
            return full[0].get("Index")
        if mine:
            return mine[0].get("Index")
        return None
    if not forced_auto:
        return None
    forced = [s for s in subs if s.get("IsForced")]
    audio_code = canonical_lang(audio_lang) if audio_lang else None
    if audio_code:
        for s in forced:
            if canonical_lang(s.get("Language", "")) == audio_code:
                return s.get("Index")
    if pref_sub:
        for s in forced:
            if lang_matches(s.get("Language", ""), pref_sub):
                return s.get("Index")
    return None


def stream_language(streams: list, index) -> str:
    for s in streams or []:
        if s.get("Index") == index:
            return str(s.get("Language") or "")
    return ""


# ------------------------------------------------------------ libelles ---


def language_name(code: str, names: dict, unknown: str) -> str:
    """Nom lisible d'une langue (« Français ») a partir de son code."""
    if not code:
        return unknown
    canon = canonical_lang(code) or code
    return names.get(canon, code.upper() if len(code) <= 3 else code)


def _channels(stream: dict) -> str:
    layout = str(stream.get("ChannelLayout") or "")
    if layout:
        return layout
    channels = stream.get("Channels")
    return {1: "mono", 2: "stéréo", 6: "5.1", 8: "7.1"}.get(
        channels, str(channels or "")
    )


def audio_label(stream: dict, names: dict, words: dict) -> str:
    """« Français (VFF) — EAC3 5.1 · défaut »."""
    name = language_name(str(stream.get("Language") or ""), names, words["unknown"])
    title = str(stream.get("Title") or "").strip()
    if title and title.lower() != name.lower():
        name = "%s (%s)" % (name, title)
    tech = " ".join(
        p for p in (str(stream.get("Codec") or "").upper(), _channels(stream)) if p
    )
    label = "%s — %s" % (name, tech) if tech else name
    if stream.get("IsDefault"):
        label += " · " + words["default"]
    return label


def subtitle_label(stream: dict, names: dict, words: dict) -> str:
    """« Français · forcés · externe »."""
    name = language_name(str(stream.get("Language") or ""), names, words["unknown"])
    title = str(stream.get("Title") or "").strip()
    if title and title.lower() != name.lower():
        name = "%s (%s)" % (name, title)
    tags = []
    if stream.get("IsForced"):
        tags.append(words["forced"])
    if stream.get("IsDefault"):
        tags.append(words["default"])
    if stream.get("IsExternal"):
        tags.append(words["external"])
    return " · ".join([name] + tags)


def menu(
    streams: list,
    kind: str,
    names: dict,
    words: dict,
    preselect_index,
    none_label: str | None = None,
) -> tuple[list, list, int]:
    """(libelles, index Emby correspondants, position pre-selectionnee)."""
    chosen = _audios(streams) if kind == "Audio" else _subtitles(streams)
    make: Callable = audio_label if kind == "Audio" else subtitle_label
    labels, indexes = [], []
    if none_label is not None:
        labels.append(none_label)
        indexes.append(None)
    for s in chosen:
        labels.append(make(s, names, words))
        indexes.append(s.get("Index"))
    try:
        pre = indexes.index(preselect_index)
    except ValueError:
        pre = 0
    return labels, indexes, pre
