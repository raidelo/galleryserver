#!/usr/bin/env python3
"""
Galería local: sirve el directorio actual como galería de imágenes, GIFs y vídeos.

Uso:
    python gallery.py            # sirve el directorio actual
    python gallery.py ~/Fotos    # sirve otro directorio
    python gallery.py -p 9000 --no-browser

Sin dependencias obligatorias. Si Pillow está instalado se generan miniaturas
reales; si ffmpeg está en el PATH también se generan para vídeos.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from collections import OrderedDict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ---------------------------------------------------------------- capacidades

try:
    from PIL import Image, ImageOps

    HAS_PIL = True
except Exception:  # Pillow no instalado
    HAS_PIL = False

FFMPEG = shutil.which("ffmpeg")

# ---------------------------------------------------------------- constantes

IMAGE_EXT = {
    ".jpg",
    ".jpeg",
    ".jfif",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".avif",
    ".heic",
    ".heif",
    ".ico",
}
GIF_EXT = {".gif"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi", ".ogv", ".mpg", ".mpeg"}
MEDIA_EXT = IMAGE_EXT | GIF_EXT | VIDEO_EXT

SKIP_DIRS = {
    "__pycache__",
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    ".cache",
    ".venv",
    "venv",
    ".DS_Store",
    "$RECYCLE.BIN",
}

STATIC_DIR = Path(__file__).resolve().parent / "static"

mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("video/x-matroska", ".mkv")
mimetypes.add_type("video/quicktime", ".mov")

# Estado global, fijado en main()
ROOT = Path.cwd()
SHOW_HIDDEN = False

# ---------------------------------------------------------------- utilidades


def kind_of(name: str) -> str | None:
    ext = os.path.splitext(name)[1].lower()
    if ext in GIF_EXT:
        return "gif"
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    return None


def is_hidden(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIRS


_num_re = re.compile(r"(\d+)")


def natural_key(name: str):
    """Ordena 'foto2' antes que 'foto10'."""
    return [int(p) if p.isdigit() else p.lower() for p in _num_re.split(name)]


def rel_of(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return "" if rel == "." else rel


def resolve_rel(rel: str) -> Path:
    """Convierte una ruta relativa de la petición en una ruta real dentro de ROOT."""
    rel = (rel or "").strip().lstrip("/")
    target = (ROOT / rel).resolve()
    if target != ROOT and ROOT not in target.parents:
        raise PermissionError(rel)
    return target


def scandir_sorted(path: Path):
    try:
        entries = list(os.scandir(path))
    except OSError:
        return []
    entries.sort(key=lambda e: natural_key(e.name))
    return entries


# ---------------------------------------------------------------- escaneo


def list_directory(folder: Path) -> dict:
    """Contenido directo de una carpeta + vista previa de cada subcarpeta."""
    folders, items = [], []

    for entry in scandir_sorted(folder):
        if not SHOW_HIDDEN and is_hidden(entry.name):
            continue
        try:
            if entry.is_dir(follow_symlinks=False):
                preview = preview_folder(Path(entry.path))
                folders.append(
                    {
                        "name": entry.name,
                        "path": rel_of(Path(entry.path)),
                        "thumbs": preview["thumbs"],
                        "media": preview["media"],
                        "subfolders": preview["subfolders"],
                        "partial": preview["partial"],
                    }
                )
            elif entry.is_file(follow_symlinks=False):
                kind = kind_of(entry.name)
                if not kind:
                    continue
                stat = entry.stat()
                items.append(
                    {
                        "name": entry.name,
                        "path": rel_of(Path(entry.path)),
                        "kind": kind,
                        "size": stat.st_size,
                        "mtime": int(stat.st_mtime),
                    }
                )
        except OSError:
            continue

    crumbs = [{"name": ROOT.name or "/", "path": ""}]
    parts = rel_of(folder).split("/") if rel_of(folder) else []
    for i, part in enumerate(parts):
        crumbs.append({"name": part, "path": "/".join(parts[: i + 1])})

    return {
        "path": rel_of(folder),
        "name": folder.name or str(folder),
        "crumbs": crumbs,
        "folders": folders,
        "items": items,
    }


def preview_folder(folder: Path, want: int = 4, budget: int = 500) -> dict:
    """Mira dentro de una carpeta (hasta 2 niveles) para sacar miniaturas y cuentas.

    El escaneo tiene presupuesto de entradas para que abrir un directorio
    grande siga siendo instantáneo.
    """
    thumbs: list[str] = []
    media = subfolders = scanned = 0
    partial = False
    queue: list[tuple[Path, int]] = [(folder, 0)]

    while queue:
        current, depth = queue.pop(0)
        for entry in scandir_sorted(current):
            scanned += 1
            if scanned > budget:
                partial = True
                queue.clear()
                break
            if not SHOW_HIDDEN and is_hidden(entry.name):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if depth == 0:
                        subfolders += 1
                    if depth < 1:
                        queue.append((Path(entry.path), depth + 1))
                elif entry.is_file(follow_symlinks=False) and kind_of(entry.name):
                    media += 1
                    if len(thumbs) < want:
                        thumbs.append(rel_of(Path(entry.path)))
            except OSError:
                continue

    return {
        "thumbs": thumbs,
        "media": media,
        "subfolders": subfolders,
        "partial": partial,
    }


# ---------------------------------------------------------------- miniaturas

_cache: "OrderedDict[tuple, bytes]" = OrderedDict()
_cache_lock = threading.Lock()
CACHE_MAX = 500


def cache_get(key):
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def cache_put(key, value):
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)


def make_image_thumb(path: Path, size: int) -> bytes | None:
    if not HAS_PIL:
        return None
    try:
        with Image.open(path) as im:
            im.seek(0) if getattr(im, "is_animated", False) else None
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((size, size), Image.LANCZOS)
            buf = __import__("io").BytesIO()
            im.save(buf, "JPEG", quality=82, optimize=True)
            return buf.getvalue()
    except:  # noqa: E722
        return None


def make_video_thumb(path: Path, size: int) -> bytes | None:
    if not FFMPEG:
        return None
    cmd = [
        FFMPEG,
        "-v",
        "error",
        "-ss",
        "1",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={size}:{size}:force_original_aspect_ratio=decrease",
        "-f",
        "image2",
        "-c:v",
        "mjpeg",
        "-",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=20, check=False).stdout
        return out or None
    except Exception:
        return None


def thumbnail(path: Path, size: int) -> tuple[bytes, str] | None:
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    key = (str(path), mtime, size)
    cached = cache_get(key)
    if cached is not None:
        return cached, "image/jpeg"

    kind = kind_of(path.name)
    data = (
        make_video_thumb(path, size)
        if kind == "video"
        else make_image_thumb(path, size)
    )
    if data is None:
        return None
    cache_put(key, data)
    return data, "image/jpeg"


# ---------------------------------------------------------------- servidor


class Handler(BaseHTTPRequestHandler):
    server_version = "Galeria/1.0"
    protocol_version = "HTTP/1.1"

    # --- helpers de respuesta

    def _headers(self, status, ctype, length, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def send_bytes(self, data: bytes, ctype: str, status=HTTPStatus.OK, extra=None):
        self._headers(status, ctype, len(data), extra)
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, obj, status=HTTPStatus.OK):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_bytes(
            payload,
            "application/json; charset=utf-8",
            status,
            {"Cache-Control": "no-store"},
        )

    def send_error_json(self, status, message):
        self.send_json({"error": message}, status)

    def send_file(self, path: Path, cache="no-store", inline=True):
        try:
            stat = path.stat()
        except OSError:
            return self.send_error_json(HTTPStatus.NOT_FOUND, "No existe el archivo")

        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = stat.st_size
        extra = {
            "Accept-Ranges": "bytes",
            "Cache-Control": cache,
            "Last-Modified": self.date_time_string(int(stat.st_mtime)),
        }
        if not inline:
            quoted = urllib.parse.quote(path.name)
            extra["Content-Disposition"] = f"attachment; filename*=UTF-8''{quoted}"

        start, end = 0, size - 1
        status = HTTPStatus.OK
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            try:
                first, _, last = rng[6:].partition("-")
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                else:  # sufijo: bytes=-500
                    start = max(0, size - int(last))
                end = min(end, size - 1)
                if start > end or start >= size:
                    raise ValueError
                status = HTTPStatus.PARTIAL_CONTENT
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"
            except ValueError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

        length = end - start + 1
        self._headers(status, ctype, length, extra)
        if self.command == "HEAD":
            return
        remaining = length
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                while remaining > 0:
                    chunk = fh.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except BrokenPipeError, ConnectionResetError:
            pass  # el navegador cortó la descarga (normal al saltar en un vídeo)

    # --- rutas

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if route in ("/", "/index.html"):
                return self.serve_static("index.html")
            if route.startswith("/static/"):
                return self.serve_static(route[len("/static/") :])
            if route == "/api/config":
                return self.send_json(
                    {
                        "root": ROOT.name or str(ROOT),
                        "rootPath": str(ROOT),
                        "thumbnails": HAS_PIL,
                        "videoThumbnails": bool(FFMPEG),
                    }
                )
            if route == "/api/list":
                folder = resolve_rel(query.get("p", [""])[0])
                if not folder.is_dir():
                    return self.send_error_json(
                        HTTPStatus.NOT_FOUND, "No es una carpeta"
                    )
                return self.send_json(list_directory(folder))
            if route == "/api/thumb":
                return self.serve_thumb(query)
            if route == "/media":
                path = resolve_rel(query.get("p", [""])[0])
                if not path.is_file() or not kind_of(path.name):
                    return self.send_error_json(
                        HTTPStatus.NOT_FOUND, "No es un archivo de la galería"
                    )
                download = query.get("dl", ["0"])[0] == "1"
                return self.send_file(
                    path, cache="public, max-age=86400", inline=not download
                )
        except PermissionError:
            return self.send_error_json(
                HTTPStatus.FORBIDDEN, "Ruta fuera del directorio servido"
            )
        except BrokenPipeError, ConnectionResetError:
            return
        except Exception as exc:  # noqa: BLE001
            return self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        self.send_error_json(HTTPStatus.NOT_FOUND, "Ruta desconocida")

    def serve_thumb(self, query):
        path = resolve_rel(query.get("p", [""])[0])
        if not path.is_file() or not kind_of(path.name):
            return self.send_error_json(
                HTTPStatus.NOT_FOUND, "No es un archivo de la galería"
            )
        try:
            size = max(64, min(1024, int(query.get("s", ["360"])[0])))
        except ValueError:
            size = 360

        result = thumbnail(path, size)
        if result is None:
            # Sin Pillow/ffmpeg: las imágenes se sirven enteras, los vídeos no tienen póster.
            if kind_of(path.name) == "video":
                return self.send_error_json(
                    HTTPStatus.NOT_FOUND, "Sin miniatura: falta ffmpeg"
                )
            return self.send_file(path, cache="public, max-age=3600")
        data, ctype = result
        self.send_bytes(data, ctype, extra={"Cache-Control": "public, max-age=86400"})

    def serve_static(self, name: str):
        target = (STATIC_DIR / name).resolve()
        if STATIC_DIR not in target.parents and target != STATIC_DIR:
            return self.send_error_json(HTTPStatus.FORBIDDEN, "Ruta no permitida")
        if not target.is_file():
            return self.send_error_json(
                HTTPStatus.NOT_FOUND, f"Falta {name} en static/"
            )
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        data = target.read_bytes()
        self.send_bytes(data, ctype, extra={"Cache-Control": "no-cache"})

    def log_message(self, format, *args):
        if os.environ.get("GALERIA_VERBOSE"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


# ---------------------------------------------------------------- arranque


def free_port(host: str, port: int) -> int:
    for candidate in range(port, port + 20):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
                return candidate
            except OSError:
                continue
    raise SystemExit(f"No hay puertos libres entre {port} y {port + 19}.")


def main():
    global ROOT, SHOW_HIDDEN

    parser = argparse.ArgumentParser(description="Sirve una carpeta como galería web.")
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="carpeta a servir (por defecto: la actual)",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=8800, help="puerto (por defecto 8800)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="interfaz; usa 0.0.0.0 para la red local"
    )
    parser.add_argument(
        "--all", action="store_true", help="incluye archivos y carpetas ocultos"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="no abre el navegador"
    )
    args = parser.parse_args()

    ROOT = Path(args.directory).expanduser().resolve()
    SHOW_HIDDEN = args.all
    if not ROOT.is_dir():
        raise SystemExit(f"{ROOT} no es una carpeta.")
    if not STATIC_DIR.is_dir():
        raise SystemExit(f"Falta la carpeta static/ junto a {Path(__file__).name}.")

    port = free_port(args.host, args.port)
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{port}/"

    print(f"Galería de {ROOT}")
    print(f"Abre {url}")
    if not HAS_PIL:
        print(
            "Miniaturas: sin Pillow, se cargan las imágenes completas (pip install pillow para acelerarlo)."
        )
    if not FFMPEG:
        print(
            "Vídeos: sin ffmpeg no hay fotograma de portada; se muestra una ficha con el nombre."
        )
    print("Ctrl+C para parar.")

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    server = ThreadingHTTPServer((args.host, port), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor parado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
