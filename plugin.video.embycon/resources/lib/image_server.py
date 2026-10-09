from __future__ import annotations
from typing import Any
import xbmcvfs
import xbmcaddon

import base64
import hashlib
import re
from urllib.parse import urlparse
from random import shuffle

import threading
import http.client
import io
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer

from .simple_logging import SimpleLogging
from .datamanager import DataManager
from .downloadutils import DownloadUtils
from .utils import get_art

log = SimpleLogging(__name__)

PORT_NUMBER = 24276
pil_loaded = False
try:
    from PIL import Image, ImageOps

    pil_loaded = True
except Exception as err:
    pil_loaded = False
    log.debug("PIL not loaded : {0}", str(err))

# v1.14 #6 : cache disque LRU des vignettes téléchargées par le serveur
# d'images. Clé = URL complète de l'image (le paramètre "tag" ajouté par Emby
# change quand l'image change, l'invalidation est donc naturelle). Quota en
# Mo ; quand il est dépassé, les fichiers les plus anciens sont supprimés en
# premier. Le collage reste recomposé à chaque requête pour préserver le
# mélange aléatoire des vignettes.
IMAGE_CACHE_QUOTA_MB = 100

_image_cache_dir: str = ""
_image_cache_store_count = 0


def _get_image_cache_dir() -> str:
    global _image_cache_dir
    if _image_cache_dir == "":
        base_dir = xbmcvfs.translatePath(
            "special://userdata/addon_data/plugin.video.embycon/cache"
        )
        if not xbmcvfs.exists(base_dir):
            xbmcvfs.mkdir(base_dir)
        _image_cache_dir = xbmcvfs.translatePath(
            "special://userdata/addon_data/plugin.video.embycon/cache/images"
        )
        if not xbmcvfs.exists(_image_cache_dir):
            xbmcvfs.mkdir(_image_cache_dir)
    return _image_cache_dir


def _image_cache_path(image_url: str) -> str:
    key = hashlib.md5(image_url.encode("utf-8")).hexdigest()
    return "%s/%s.jpg" % (_get_image_cache_dir(), key)


def _load_image_from_cache(image_url: str) -> bytes | None:
    try:
        cache_path = _image_cache_path(image_url)
        if not xbmcvfs.exists(cache_path):
            return None
        cached_file = xbmcvfs.File(cache_path, "rb")
        data = cached_file.readBytes()
        cached_file.close()
        # réécriture légère pour rafraîchir le mtime (vrai LRU)
        refreshed_file = xbmcvfs.File(cache_path, "wb")
        refreshed_file.write(data)
        refreshed_file.close()
        return data
    except Exception:
        return None


def _store_image_in_cache(image_url: str, data: bytes) -> None:
    global _image_cache_store_count
    try:
        cache_path = _image_cache_path(image_url)
        cache_file = xbmcvfs.File(cache_path, "wb")
        cache_file.write(data)
        cache_file.close()
        _image_cache_store_count += 1
        if _image_cache_store_count >= 20:
            _image_cache_store_count = 0
            _purge_image_cache_if_needed()
    except Exception as cache_error:
        log.debug("Image cache write error : {0}", str(cache_error))


def _purge_image_cache_if_needed() -> None:
    entries: list[tuple[float, str, int]] = []
    total_size = 0
    _, files = xbmcvfs.listdir(_get_image_cache_dir())
    for file_name in files:
        file_path = "%s/%s" % (_get_image_cache_dir(), file_name)
        try:
            file_stat = xbmcvfs.Stat(file_path)
            entries.append((file_stat.st_mtime(), file_path, file_stat.st_size()))
            total_size += file_stat.st_size()
        except Exception:
            continue
    quota_bytes = IMAGE_CACHE_QUOTA_MB * 1024 * 1024
    if total_size <= quota_bytes:
        return
    log.debug("Image cache purge : {0} octets", str(total_size))
    entries.sort(key=lambda entry: entry[0])
    for file_mtime, file_path, file_size in entries:
        if total_size <= quota_bytes * 0.9:
            break
        xbmcvfs.delete(file_path)
        total_size -= file_size


def get_image_links(url: str, maxwidth: int = 0) -> list[dict[str, str]]:
    download_utils = DownloadUtils()
    server = download_utils.get_server()
    if server is None:
        return []

    # url = re.sub("(?i)limit=[0-9]+", "limit=4", url)
    # url = url.replace("{ItemLimit}", "4")
    # url = re.sub("(?i)SortBy=[a-zA-Z]+", "SortBy=Random", url)

    # if not re.search('limit=', url, re.IGNORECASE):
    #     url += "&Limit=4"

    # if not re.search('sortBy=', url, re.IGNORECASE):
    #     url += "&SortBy=Random"

    url = re.sub("(?i)EnableUserData=[a-z]+", "EnableUserData=False", url)
    url = re.sub("(?i)EnableImageTypes=[,a-z]+", "EnableImageTypes=Primary", url)
    url = url.replace("{field_filters}", "BasicSyncInfo")
    url = re.sub("(?i)Fields=[,a-z]+", "Fields=BasicSyncInfo", url)

    if not re.search("enableimagetypes=", url, re.IGNORECASE):
        url += "&EnableImageTypes=Primary"

    if not re.search("fields=", url, re.IGNORECASE):
        url += "&Fields=BasicSyncInfo"

    if not re.search("EnableUserData=", url, re.IGNORECASE):
        url += "&EnableUserData=False"

    data_manager = DataManager()
    result = data_manager.get_content(url)

    items = result.get("Items")
    if not items:
        return []

    art_urls = []
    download_utils = DownloadUtils()
    for iteem in items:
        art = get_art(iteem, server, maxwidth=maxwidth, download_utils=download_utils)
        art_urls.append(art)

    shuffle(art_urls)

    return art_urls


def build_image(path: str) -> bytes:
    log.debug("build_image()")

    log.debug("Request Path : {0}", path)

    request_path = path[1:]

    if request_path == "favicon.ico":
        return bytes()

    decoded_url = base64.b64decode(request_path).decode("utf-8")
    log.debug("decoded_url : {0}", decoded_url)

    # v1.14.1 (audit S6) : n'accepter que les URL du serveur Emby courant —
    # sinon un processus local pouvait faire envoyer le jeton d'acces vers
    # un hote arbitraire
    server = DownloadUtils().get_server()
    if not decoded_url.startswith(server):
        log.error(
            "serveur d'images : URL refusee (hors serveur Emby) : {0}", decoded_url
        )
        return bytes()

    settings = xbmcaddon.Addon()
    max_image_width = int(settings.getSetting("max_image_width"))

    image_urls = get_image_links(decoded_url, maxwidth=max_image_width)

    width, height = 500, 750
    collage = Image.new("RGB", (width, height), (5, 5, 5))  # type: ignore

    cols: int = 2
    rows: int = 2
    thumbnail_width: int = int(width / cols)
    thumbnail_height: int = int(height / rows)
    size: tuple[int, int] = (thumbnail_width, thumbnail_height)
    image_count: int = 0
    for art in image_urls:
        thumb_url = art.get("thumb")
        if thumb_url:
            url_bits = urlparse(thumb_url.strip())

            host_name = url_bits.hostname
            port = url_bits.port
            # user_name = url_bits.username
            # user_password = url_bits.password
            url_path = url_bits.path
            url_query = url_bits.query

            server = "%s:%s" % (host_name, port)
            url_full_path = url_path + "?" + url_query

            log.debug(
                "Loading image from : {0} {1} {2}", image_count, server, url_full_path
            )

            try:
                use_https = url_bits.scheme.lower() == "https"
                if use_https:
                    verify_cert = xbmcaddon.Addon().getSetting("verify_cert") == "true"
                    if verify_cert:
                        conn = http.client.HTTPSConnection(server)
                    else:
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        conn = http.client.HTTPSConnection(server, context=ssl_context)
                else:
                    conn = http.client.HTTPConnection(server)
                cache_key_url = "%s://%s%s" % (
                    url_bits.scheme.lower(),
                    server,
                    url_full_path,
                )
                image_data = _load_image_from_cache(cache_key_url)
                if image_data is None:
                    conn.request("GET", url_full_path)
                    image_responce = conn.getresponse()
                    image_data = image_responce.read()
                    _store_image_in_cache(cache_key_url, image_data)

                loaded_image = Image.open(io.BytesIO(image_data))  # type: ignore
                image = ImageOps.fit(  # type: ignore
                    loaded_image,
                    size,
                    method=Image.LANCZOS,  # type: ignore
                    bleed=0.0,
                    centering=(0.5, 0.5),
                )

                x = int(image_count % cols) * thumbnail_width
                y = int(image_count / cols) * thumbnail_height
                collage.paste(image, (x, y))

                del loaded_image
                del image
                del image_data

            except Exception as con_err:
                log.error("Error loading image : {0}", str(con_err))

            image_count += 1

        if image_count == cols * rows:
            break

    del image_urls

    img_byte_arr: io.BytesIO = io.BytesIO()
    collage.save(img_byte_arr, format="JPEG")
    image_bytes: bytes = img_byte_arr.getvalue()

    return image_bytes


class HttpImageHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002, ANN401
        log_line = format % args
        log.debug(log_line)
        return

    def do_GET(self) -> None:
        log.debug("HttpImageHandler:do_GET()")
        self.serve_image()
        return

    def do_HEAD(self) -> None:
        log.debug("HttpImageHandler:do_HEAD()")
        self.send_response(200)
        self.end_headers()
        return

    def do_QUIT(self) -> None:
        log.debug("HttpImageHandler:do_QUIT()")
        self.send_response(200)
        self.end_headers()
        return

    def serve_image(self) -> None:
        try:
            self._serve_image_unsafe()
        except Exception as serve_error:
            log.error("HttpImageHandler: error serving image : {0}", str(serve_error))
            self.send_response(500)
            self.end_headers()

    def _serve_image_unsafe(self) -> None:
        if pil_loaded:
            image_bytes = build_image(self.path)
            self.send_response(200)
            self.send_header("Content-type", "image/jpeg")
            self.send_header("Content-Length", str(len(image_bytes)))
            self.end_headers()
            self.wfile.write(image_bytes)

        else:
            image_path: str = xbmcvfs.translatePath(
                "special://home/addons/plugin.video.embycon/icon.png"
            )
            self.send_response(200)
            self.send_header("Content-type", "image/png")
            modified = xbmcvfs.Stat(image_path).st_mtime()
            self.send_header("Last-Modified", "%s" % modified)
            image = xbmcvfs.File(image_path)
            size = image.size()
            self.send_header("Content-Length", str(size))
            self.end_headers()
            self.wfile.write(image.readBytes())
            image.close()
            del image


class HttpImageServerThread(threading.Thread):
    keep_running = True

    def __init__(self) -> None:
        threading.Thread.__init__(self)

    def stop(self) -> None:
        self.keep_running = False
        log.debug("HttpImageServerThread:stop called")
        try:
            conn = http.client.HTTPConnection("localhost:%d" % PORT_NUMBER)
            conn.request("QUIT", "/")
            conn.getresponse()
        except Exception:
            pass

    def run(self) -> None:
        log.debug("HttpImageServerThread:started")
        server = HTTPServer(("127.0.0.1", PORT_NUMBER), HttpImageHandler)

        while self.keep_running:
            server.handle_request()

        log.debug("HttpImageServerThread:exiting")
