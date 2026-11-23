"""An in-memory index of every photo and video, cached to disk.

Reading EXIF/ffprobe for ~1,000 files takes 30-40 s on a Pi, so results are kept in
.cache/library.json keyed by path + mtime + size. `refresh()` re-walks the folder tree
(cheap: stat only) and reads metadata only for new or changed files.
"""
import hashlib, json, os, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import CACHE, ROOT
from .media import read_meta
from .paths import kind

INDEX = CACHE / f"library-{hashlib.sha1(str(ROOT).encode()).hexdigest()[:10]}.json"  # one per photo folder
FRESH_SECONDS = 10  # how long a walk is trusted before the next request re-walks


class Library:
    def __init__(self):
        self.items = {}          # rel path -> meta
        self.folders = set()     # rel paths of every visible folder ("" = root)
        self._lock = threading.RLock()
        self._walked = 0.0
        self.scanning = False
        try:
            self.items = json.loads(INDEX.read_text()).get("items", {})
        except (OSError, ValueError):
            pass

    def _walk(self):
        files, folders = {}, {""}
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            rel_dir = os.path.relpath(dirpath, ROOT)
            rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
            for d in dirnames:
                folders.add(f"{rel_dir}/{d}" if rel_dir else d)
            for f in filenames:
                k = kind(f)
                if f.startswith(".") or not k:
                    continue
                full = os.path.join(dirpath, f)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                files[f"{rel_dir}/{f}" if rel_dir else f] = (full, k, st)
        return files, folders

    def refresh(self, force=False):
        with self._lock:
            if not force and time.time() - self._walked < FRESH_SECONDS:
                return
            files, folders = self._walk()
            todo = [(rel, v) for rel, v in files.items()
                    if (old := self.items.get(rel)) is None
                    or old["mtime"] != v[2].st_mtime_ns or old["size"] != v[2].st_size]
            gone = self.items.keys() - files.keys()
            if todo:
                self.scanning = True
                with ThreadPoolExecutor(4) as pool:
                    metas = pool.map(lambda t: read_meta(Path(t[1][0]), t[1][1], t[1][2]), todo)
                    for (rel, _), meta in zip(todo, metas):
                        self.items[rel] = meta
                self.scanning = False
            for rel in gone:
                del self.items[rel]
            self.folders = folders
            self._walked = time.time()
            if todo or gone:
                self._save()

    def _save(self):
        CACHE.mkdir(exist_ok=True)
        tmp = INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps({"items": self.items}))
        os.replace(tmp, INDEX)

    def invalidate(self):
        """Call after changing files so the next request re-walks immediately."""
        self._walked = 0.0

    def snapshot(self):
        self.refresh()
        with self._lock:
            return dict(self.items), set(self.folders)

    def warm(self):
        threading.Thread(target=self.refresh, kwargs={"force": True}, daemon=True).start()
