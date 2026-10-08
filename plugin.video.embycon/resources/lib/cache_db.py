# Gnu General Public License - see LICENSE.TXT
"""v1.14 : cache SQLite des listes (et des reponses HTTP des la phase 2b).

Remplace les fichiers cache_<md5>.pickle du dossier cache/ par une base
unique, plus robuste et plus rapide :

  - special://userdata/addon_data/plugin.video.embycon/cache.db
  - journal_mode=WAL : lectures concurrentes sans bloquer l'affichage
  - synchronous=NORMAL : compromis securite / vitesse adapte au cache

Les entrees de la table "items" sont des pickles de CacheItem avec une
date d'expiration (reglage cache_duration en heures).
"""
from __future__ import annotations

import os
import pickle
import sqlite3
import threading
import time
from typing import Any

import xbmcaddon
import xbmcvfs

from .simple_logging import SimpleLogging

log = SimpleLogging(__name__)

# Un seul objet connection partage entre les threads Kodi, protege par un verrou.
_conn: sqlite3.Connection | None = None
_lock = threading.Lock()

def _chemin_base() -> str:
    profil = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
    xbmcvfs.mkdirs(profil)

    return os.path.join(profil, "cache.db")

def _connexion() -> sqlite3.Connection | None:
    """Retourne la connexion SQLite partagee (creee au premier appel)."""
    global _conn
    if _conn is not None:
        return _conn
    try:
        _conn = sqlite3.connect(_chemin_base(), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                pickle BLOB,
                expires_at INTEGER
            )
            """
        )
        # v1.14 phase 2b : cache des reponses HTTP ( ETag / If-None-Match ).
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_responses (
                url_hash TEXT PRIMARY KEY,
                etag TEXT,
                body BLOB,
                expires_at INTEGER
            )
            """
        )
        _conn.commit()
    except Exception as erreur:
        log.error("cache_db : initialisation de la base impossible : {0}", erreur)
        _conn = None
    return _conn

def charge_item(id_cache: str) -> Any | None:
    """Retourne l'objet cache pour cet identifiant, ou None (absent / expire)."""
    try:
        with _lock:
            conn = _connexion()
            if conn is None:
                return None
            ligne = conn.execute(
                "SELECT pickle, expires_at FROM items WHERE id = ?",
                (id_cache,),
            ).fetchone()
            if ligne is None:
                return None
            if ligne[1] is not None and ligne[1] < time.time():
                conn.execute("DELETE FROM items WHERE id = ?", (id_cache,))
                conn.commit()
                return None
            return pickle.loads(ligne[0])
    except Exception as erreur:
        log.error("cache_db : charge_item echoue : {0}", erreur)
        return None

def sauve_item(id_cache: str, element: Any, duree_secondes: int) -> None:
    """Enregistre un objet dans la base avec une duree de vie en secondes."""
    if duree_secondes <= 0:
        return
    try:
        with _lock:
            conn = _connexion()
            if conn is None:
                return
            conn.execute(
                "INSERT OR REPLACE INTO items (id, pickle, expires_at) VALUES (?, ?, ?)",
                (id_cache, pickle.dumps(element), int(time.time() + duree_secondes)),
            )
            conn.commit()
    except Exception as erreur:
        log.error("cache_db : sauve_item echoue : {0}", erreur)

def supprime_item(id_cache: str) -> None:
    """Supprime une entree du cache de listes."""
    try:
        with _lock:
            conn = _connexion()
            if conn is None:
                return
            conn.execute("DELETE FROM items WHERE id = ?", (id_cache,))
            conn.commit()
    except Exception as erreur:
        log.error("cache_db : supprime_item echoue : {0}", erreur)

def purge_expire() -> int:
    """Supprime les entrees expirees ( listes et reponses HTTP ). Retourne le total."""
    total = 0
    try:
        with _lock:
            conn = _connexion()
            if conn is None:
                return 0
            maintenant = int(time.time())
            curseur = conn.execute(
                "DELETE FROM items WHERE expires_at < ?", (maintenant,)
            )
            total = curseur.rowcount if curseur.rowcount > 0 else 0
            curseur = conn.execute(
                "DELETE FROM http_responses WHERE expires_at < ?", (maintenant,)
            )
            if curseur.rowcount > 0:
                total += curseur.rowcount
            conn.commit()
    except Exception as erreur:
        log.error("cache_db : purge_expire echoue : {0}", erreur)
    return total

def purge_tout() -> int:
    """Vide integralement le cache de listes. Retourne le nombre d'entrees."""
    total = 0
    try:
        with _lock:
            conn = _connexion()
            if conn is None:
                return 0
            curseur = conn.execute("DELETE FROM items")
            total = curseur.rowcount if curseur.rowcount > 0 else 0
            conn.commit()
    except Exception as erreur:
        log.error("cache_db : purge_tout echoue : {0}", erreur)
    return total


def _duree_cache_http() -> int:
    """v1.14 phase 2b : duree du cache HTTP ( reglage cache_duration, heures )."""
    try:
        heures = int(xbmcaddon.Addon().getSetting("cache_duration"))
    except (TypeError, ValueError):
        heures = 24
    if heures <= 0:
        return 0
    return heures * 3600


def charge_reponse(url_hash: str) -> tuple[str, bytes] | None:
    """Retourne ( etag, corps ) de la reponse HTTP cachee, ou None.

    v1.14 phase 2b : sert a envoyer If-None-Match et a reutiliser le corps
    tel quel si le serveur repond 304 ( non modifie ).
    """
    if _duree_cache_http() <= 0:
        return None
    try:
        with _lock:
            conn = _connexion()
            if conn is None:
                return None
            ligne = conn.execute(
                "SELECT etag, body, expires_at FROM http_responses WHERE url_hash = ?",
                (url_hash,),
            ).fetchone()
            if ligne is None:
                return None
            if ligne[2] is not None and ligne[2] < time.time():
                conn.execute(
                    "DELETE FROM http_responses WHERE url_hash = ?", (url_hash,)
                )
                conn.commit()
                return None
            return ligne[0], ligne[1]
    except Exception as erreur:
        log.error("cache_db : charge_reponse echoue : {0}", erreur)
        return None


def sauve_reponse(url_hash: str, etag: str, corps: bytes) -> None:
    """Enregistre une reponse HTTP ( ETag + corps ) pour revalidation future."""
    duree = _duree_cache_http()
    if duree <= 0:
        return
    try:
        with _lock:
            conn = _connexion()
            if conn is None:
                return
            conn.execute(
                "INSERT OR REPLACE INTO http_responses"
                " (url_hash, etag, body, expires_at) VALUES (?, ?, ?, ?)",
                (url_hash, etag, corps, int(time.time() + duree)),
            )
            conn.commit()
    except Exception as erreur:
        log.error("cache_db : sauve_reponse echoue : {0}", erreur)
