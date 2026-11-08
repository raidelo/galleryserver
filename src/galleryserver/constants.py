import mimetypes
from pathlib import Path

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
VIDEO_EXT = {
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".mkv",
    ".avi",
    ".ogv",
    ".mpg",
    ".mpeg",
}
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

PACKAGE_NAME = "galleryserver"
