"""Paths, limits and file types. Everything is configured with environment variables."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("PHOTO_DIR", BASE / "photos")).resolve()
PORT = int(os.environ.get("PORT", 8080))

CACHE = BASE / ".cache"            # thumbnails, converted photos, library index (safe to delete)
AUTH = Path(os.environ.get("GALLERY_AUTH", BASE / ".auth.json"))  # hash + session secret (`app.py setpass`)
FAVORITES = Path(os.environ.get("GALLERY_FAVORITES", BASE / ".favorites.json"))
DIST = BASE / "web" / "dist"       # built frontend (`npm run build` in web/)
TRASH = ROOT / ".trash"            # deleted files wait here for TRASH_DAYS

IMAGES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".dng"}
VIDEOS = {".mp4", ".mov", ".m4v", ".webm"}
RAW = {".dng"}
CONVERT = {".heic", ".heif", ".tif", ".tiff", ".dng"}  # browsers can't show these as-is

THUMB_SIDE = 640
VIEW_SIDE = 2560
MAX_UPLOAD = 2 * 1024 ** 3             # biggest single upload
MIN_FREE = 500 * 1024 ** 2             # refuse uploads below this much free space
SESSION_HOURS = 12
TRASH_DAYS = 30
LOCKOUT_TRIES, LOCKOUT_SECONDS = 5, 300
