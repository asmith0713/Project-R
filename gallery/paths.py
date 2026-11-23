"""Turning user-supplied relative paths into real paths, safely."""
from pathlib import Path

from werkzeug.utils import secure_filename

from .config import IMAGES, ROOT, VIDEOS


class BadPath(Exception):
    """A path outside the photo folder, hidden, or otherwise unusable."""


def hidden(rel_parts):
    return any(s.startswith(".") for s in rel_parts)


def resolve(rel):
    """Map a relative path from the client to an absolute path inside ROOT.

    Rejects anything that escapes ROOT (`..`, absolute paths, symlinks out) and
    anything with a dot-prefixed segment, which covers `.trash`, macOS `._` files
    and upload temp files. Every route that touches the filesystem must use this.
    """
    p = (ROOT / (rel or "").strip("/")).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise BadPath(rel)
    if hidden(p.relative_to(ROOT).parts):
        raise BadPath(rel)
    return p


def rel_of(p):
    return p.relative_to(ROOT).as_posix()


def kind(p):
    e = Path(p).suffix.lower()
    return "image" if e in IMAGES else "video" if e in VIDEOS else None


def clean_name(name, fallback="photo"):
    """A safe single path segment. Keeps spaces, emoji and apostrophes that
    secure_filename would strip, but never slashes, dots at the start, or control chars."""
    name = "".join(c for c in (name or "").strip() if " " <= c != "\x7f" and c not in '/\\:*?"<>|')
    name = name.strip(". ")[:120]
    return name or secure_filename(fallback) or fallback


def unique(folder, stem, ext):
    """folder/stem+ext, or stem_1, stem_2... so nothing is ever overwritten."""
    dest, n = folder / f"{stem}{ext}", 1
    while dest.exists():
        dest = folder / f"{stem}_{n}{ext}"
        n += 1
    return dest
