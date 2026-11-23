"""Favorites and the trash: small JSON stores with atomic writes."""
import json, os, secrets, shutil, threading, time
from pathlib import Path

from .config import FAVORITES, TRASH, TRASH_DAYS
from .paths import clean_name, kind, resolve, unique


def _load(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


class Favorites:
    """A set of relative paths, kept in sync when files move or get renamed."""

    def __init__(self):
        self._lock = threading.Lock()
        self.paths = set(_load(FAVORITES, []))

    def set(self, rels, on):
        with self._lock:
            (self.paths.update if on else self.paths.difference_update)(rels)
            _save(FAVORITES, sorted(self.paths))

    def moved(self, old, new):
        """A file or folder was renamed/moved: carry its favorites (and its children's) along."""
        with self._lock:
            changed = False
            for p in list(self.paths):
                if p == old or p.startswith(old + "/"):
                    self.paths.discard(p)
                    self.paths.add(new + p[len(old):])
                    changed = True
            if changed:
                _save(FAVORITES, sorted(self.paths))

    def drop(self, rels):
        self.set(rels, False)


class Trash:
    """Deleted files go to ROOT/.trash/<id>/<name> (same drive, so it's a cheap rename)
    and are removed for good after TRASH_DAYS. The manifest remembers where each came from."""

    MANIFEST = TRASH / "manifest.json"

    def __init__(self):
        self._lock = threading.Lock()

    def _read(self):
        return _load(self.MANIFEST, {})

    def put(self, rel):
        src = resolve(rel)
        if not src.is_file():
            raise FileNotFoundError(rel)
        with self._lock:
            m = self._read()
            tid = secrets.token_hex(8)
            (TRASH / tid).mkdir(parents=True)
            os.replace(src, TRASH / tid / src.name)
            m[tid] = {"name": src.name, "from": rel, "deleted": time.time()}
            _save(self.MANIFEST, m)
        return tid

    def file(self, tid):
        m = self._read().get(tid)
        if not m or not tid.isalnum():
            return None
        p = TRASH / tid / m["name"]
        return p if p.is_file() else None

    def list(self):
        self.purge()
        out = []
        for tid, m in self._read().items():
            out.append({"id": tid, "name": m["name"], "from": m["from"], "kind": kind(m["name"]),
                        "deleted": m["deleted"], "expires": m["deleted"] + TRASH_DAYS * 86400})
        return sorted(out, key=lambda x: -x["deleted"])

    def restore(self, tid):
        """Put a file back where it came from (recreating the folder if needed).
        Returns the restored relative path."""
        with self._lock:
            m = self._read()
            e = m.get(tid)
            p = self.file(tid)
            if not e or not p:
                raise FileNotFoundError(tid)
            parent = Path(e["from"]).parent.as_posix()
            folder = resolve("" if parent == "." else parent)
            folder.mkdir(parents=True, exist_ok=True)
            stem, ext = Path(e["name"]).stem, Path(e["name"]).suffix
            dest = unique(folder, clean_name(stem), ext)
            os.replace(p, dest)
            shutil.rmtree(TRASH / tid, ignore_errors=True)
            del m[tid]
            _save(self.MANIFEST, m)
            return dest.relative_to(resolve("")).as_posix()

    def remove(self, tids):
        with self._lock:
            m = self._read()
            for tid in tids:
                if tid in m and tid.isalnum():
                    shutil.rmtree(TRASH / tid, ignore_errors=True)
                    del m[tid]
            _save(self.MANIFEST, m)

    def purge(self):
        cutoff = time.time() - TRASH_DAYS * 86400
        old = [tid for tid, e in self._read().items() if e["deleted"] < cutoff]
        if old:
            self.remove(old)
