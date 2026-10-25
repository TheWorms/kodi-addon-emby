"""Tests v1.17 « Film suivant » d'une collection."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import kodi_stubs  # noqa: E402

kodi_stubs.install()

import lib.play_utils as pu  # noqa: E402
from lib.playnext import next_trigger_time  # noqa: E402

SAGA = [
    {"Id": "m1", "Type": "Movie", "Name": "Episode I", "PremiereDate": "1999-05-19T00:00:00Z"},
    {"Id": "m2", "Type": "Movie", "Name": "Episode II", "PremiereDate": "2002-05-16T00:00:00Z"},
    {"Id": "m3", "Type": "Movie", "Name": "Episode III", "PremiereDate": "2005-05-19T00:00:00Z"},
]


def _settings(**valeurs):
    return SimpleNamespace(getSetting=lambda cle: valeurs.get(cle, ""))


# --- next_in_list ---------------------------------------------------------


def test_film_suivant_dans_la_liste() -> None:
    assert pu.next_in_list(SAGA, "m1")["Id"] == "m2"
    assert pu.next_in_list(SAGA, "m3") is None
    assert pu.next_in_list(SAGA, "absent") is None


# --- declenchement du dialogue -----------------------------------------------


def test_declenchement_film_mode_dialogue() -> None:
    data = {"item_type": "Movie", "next_episode": SAGA[1], "credits_start": 0}
    reglages = _settings(next_movie_mode="1", next_movie_trigger_time="180")
    assert next_trigger_time(data, reglages, 7200) == 180


def test_declenchement_film_au_marqueur_de_generique() -> None:
    # generique a 1h55 sur un film de 2h -> dialogue 5 min avant la fin
    data = {
        "item_type": "Movie",
        "next_episode": SAGA[1],
        "credits_start": (115 * 60) * 10000000,
    }
    reglages = _settings(next_movie_mode="1", next_movie_trigger_time="180")
    assert next_trigger_time(data, reglages, 7200) == 300


def test_pas_de_dialogue_en_mode_auto_ou_desactive() -> None:
    data = {"item_type": "Movie", "next_episode": SAGA[1]}
    assert next_trigger_time(data, _settings(next_movie_mode="2"), 7200) == 0
    assert next_trigger_time(data, _settings(next_movie_mode="0"), 7200) == 0


def test_episode_inchange() -> None:
    data = {"item_type": "Episode", "next_episode": {"Id": "e2"}}
    assert next_trigger_time(data, _settings(play_next_trigger_time="45"), 2400) == 45
    # v1.19 : 0 = jamais (plus d'interrupteur separe)
    assert next_trigger_time(data, _settings(play_next_trigger_time="0"), 2400) == 0


def test_rien_sans_element_suivant() -> None:
    assert next_trigger_time({"item_type": "Movie", "next_episode": None}, _settings(), 1) == 0
    assert next_trigger_time(None, _settings(), 1) == 0


# --- recherche de la collection -------------------------------------------------


def _fake_serveur(monkeypatch, collections, contexte="", mode="1"):
    """collections : {boxset_id: (nom, tmdb_id, [films])}."""
    urls = []

    def get_content(url):
        urls.append(url)
        if "AnyProviderIdEquals=tmdb." in url:
            tmdb = url.split("AnyProviderIdEquals=tmdb.")[1].split("&")[0]
            return {
                "Items": [
                    {"Id": bid, "Name": nom}
                    for bid, (nom, tid, _f) in collections.items()
                    if tid == tmdb
                ]
            }
        if "ParentId=" in url:
            bid = url.split("ParentId=")[1].split("&")[0]
            return {"Items": list(collections.get(bid, ("", "", []))[2])}
        if "/Items/" in url:
            bid = url.split("/Items/")[1].split("?")[0]
            return {"Name": collections.get(bid, ("",))[0]}
        return None

    monkeypatch.setattr(pu, "DataManager", lambda: SimpleNamespace(get_content=get_content))
    monkeypatch.setattr(
        pu, "HomeWindow", lambda: SimpleNamespace(get_property=lambda _k: contexte)
    )
    monkeypatch.setattr(
        pu.xbmcaddon,
        "Addon",
        lambda: _settings(next_movie_mode=mode, collection_play_order="0"),
        raising=False,
    )
    return urls


def test_collection_tmdb(monkeypatch) -> None:
    _fake_serveur(monkeypatch, {"bs1": ("Star Wars", "10", SAGA)})
    film = {"Id": "m1", "Type": "Movie", "ProviderIds": {"TmdbCollection": "10"}}
    suivant = pu.find_next_movie(film)
    assert suivant["Id"] == "m2"
    assert suivant["CollectionName"] == "Star Wars"


def test_collection_parcourue_prioritaire(monkeypatch) -> None:
    # collection manuelle (sans id TMDb) d'ou le film a ete lance ; le
    # serveur la renvoie dans le desordre : l'ordre de sortie fait foi
    perso = [SAGA[2], SAGA[0]]
    _fake_serveur(monkeypatch, {"perso": ("Mes favoris", "", perso)}, contexte="perso")
    suivant = pu.find_next_movie({"Id": "m1", "Type": "Movie", "ProviderIds": {}})
    assert suivant["Id"] == "m3"
    assert suivant["CollectionName"] == "Mes favoris"


def test_ordre_serveur_ignore(monkeypatch) -> None:
    """v1.18.2 : Emby peut renvoyer la collection dans son ordre d'affichage."""
    desordre = [SAGA[2], SAGA[0], SAGA[1]]
    _fake_serveur(monkeypatch, {"bs1": ("Star Wars", "10", desordre)})
    film = {"Id": "m1", "Type": "Movie", "ProviderIds": {"TmdbCollection": "10"}}
    assert pu.find_next_movie(film)["Id"] == "m2"


def test_contexte_perime_ignore(monkeypatch) -> None:
    # derniere collection parcourue sans rapport : on passe a la collection TMDb
    _fake_serveur(
        monkeypatch,
        {"autre": ("Autre", "", [{"Id": "x", "Type": "Movie"}]), "bs1": ("Star Wars", "10", SAGA)},
        contexte="autre",
    )
    film = {"Id": "m2", "Type": "Movie", "ProviderIds": {"tmdbcollection": "10"}}
    assert pu.find_next_movie(film)["Id"] == "m3"


def test_dernier_film_ou_mode_desactive(monkeypatch) -> None:
    _fake_serveur(monkeypatch, {"bs1": ("Star Wars", "10", SAGA)})
    film = {"Id": "m3", "Type": "Movie", "ProviderIds": {"TmdbCollection": "10"}}
    assert pu.find_next_movie(film) is None
    urls = _fake_serveur(monkeypatch, {"bs1": ("Star Wars", "10", SAGA)}, mode="0")
    assert pu.find_next_movie({"Id": "m1", "Type": "Movie"}) is None
    assert urls == []  # mode desactive : aucune requete


def test_film_hors_collection(monkeypatch) -> None:
    _fake_serveur(monkeypatch, {})
    assert pu.find_next_movie({"Id": "solo", "Type": "Movie", "ProviderIds": {}}) is None


# --- enchainement automatique en fin de film --------------------------------


def _fin_de_film(monkeypatch, position, mode="2", deja_traite=False):
    envois = []
    monkeypatch.setattr(pu, "send_event_notification", lambda m, d: envois.append((m, d)))
    monkeypatch.setattr(
        pu.xbmcaddon,
        "Addon",
        lambda: _settings(
            next_movie_mode=mode,
            promptPlayNextEpisodePercentage="100",
            promptPlayNextEpisodePercentage_prompt="true",
            promptDeleteEpisodePercentage="100",
            promptDeleteMoviePercentage="100",
        ),
        raising=False,
    )
    data = {
        "item_type": "Movie",
        "next_episode": {"Id": "m2", "Name": "Episode II"},
        "currentPossition": position,
        "duration": 100,
        "can_delete": False,
    }
    if deja_traite:
        data["next_handled"] = True
    pu.prompt_for_stop_actions("m1", data)
    return envois


def test_enchainement_auto_en_fin_de_film(monkeypatch) -> None:
    envois = _fin_de_film(monkeypatch, 97)
    assert envois == [
        (
            "embycon_play_action",
            {"item_id": "m2", "auto_resume": "-1", "force_transcode": False},
        )
    ]


def test_pas_d_enchainement_si_arret_en_cours_de_film(monkeypatch) -> None:
    assert _fin_de_film(monkeypatch, 40) == []


def test_mode_dialogue_enchaine_aussi_sans_refus(monkeypatch) -> None:
    """v1.18.1 : le dialogue propose, puis le suivant demarre a la fin."""
    assert len(_fin_de_film(monkeypatch, 97, mode="1")) == 1


def test_pas_de_double_lancement_ni_apres_refus(monkeypatch) -> None:
    # « Play Now » deja clique, ou dialogue ferme par Retour
    assert _fin_de_film(monkeypatch, 97, mode="1", deja_traite=True) == []
    assert _fin_de_film(monkeypatch, 97, mode="2", deja_traite=True) == []


def test_mode_desactive_n_enchaine_pas(monkeypatch) -> None:
    assert _fin_de_film(monkeypatch, 97, mode="0") == []
