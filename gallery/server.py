"""Flask app: login, JSON API, media files, and the built Svelte frontend."""
import gzip, json, os, secrets, shutil, time
from functools import wraps
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, jsonify, redirect, request, send_file, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from . import media
from .config import (AUTH, CODE_CHECKS, CODE_WINDOW, CONVERT, DIST, HIDDEN_IDLE_SECONDS, IMAGES,
                     LOCKOUT_SECONDS, LOCKOUT_TRIES, MAX_UPLOAD, MIN_FREE, ROOT, SESSION_HOURS,
                     VIDEOS)
from .library import Library
from .paths import BadPath, clean_name, kind, rel_of, resolve, unique
from .store import Favorites, Hidden, Trash

auth = json.loads(AUTH.read_text()) if AUTH.exists() else {"hash": "", "secret": secrets.token_hex(32)}
app = Flask(__name__, static_folder=None)
app.secret_key = auth["secret"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                  PERMANENT_SESSION_LIFETIME=SESSION_HOURS * 3600,
                  MAX_CONTENT_LENGTH=MAX_UPLOAD + 1024 ** 2)

library, favorites, trash, hidden = Library(), Favorites(), Trash(), Hidden()
fails = {}  # ip -> (wrong tries, locked until); resets on restart
code_checks = {}  # ip -> recent secret-code check times


# ---------- helpers ----------

def fail(status, message):
    r = jsonify(error=message)
    r.status_code = status
    abort(r)


def unlocked():
    """Hidden albums are open for this session (and stay open while being used)."""
    if session.get("hidden_until", 0) > time.time():
        session["hidden_until"] = time.time() + HIDDEN_IDLE_SECONDS
        return True
    session.pop("hidden_until", None)
    return False


def visible(rel):
    return not hidden.is_hidden(rel) or unlocked()


def path_arg(rel):
    """resolve() plus the hidden-album check: while locked, anything inside a hidden
    album answers exactly like a path that doesn't exist."""
    try:
        p = resolve(rel)
    except BadPath:
        fail(404, "Not found")
    if not visible(rel_of(p)):
        fail(404, "Not found")
    return p


def body():
    return request.get_json(silent=True) or {}


def need_login(f):
    @wraps(f)
    def wrap(*a, **k):
        if not session.get("ok"):
            fail(401, "Sign in first")
        if request.method == "POST" and not secrets.compare_digest(
                request.headers.get("X-CSRF", ""), session.get("csrf", "-")):
            fail(403, "Refresh the page and try again")
        return f(*a, **k)
    return wrap


def item(rel, meta):
    return {"path": rel, "name": rel.rsplit("/", 1)[-1], "folder": rel.rpartition("/")[0],
            "kind": meta["kind"], "w": meta["w"], "h": meta["h"], "date": meta["date"],
            "size": meta["size"], "dur": meta.get("dur"), "fav": rel in favorites.paths,
            "v": format(meta["mtime"] // 1_000_000 % 0xFFFFFFFF, "x")}  # cache-buster for thumbnails


def by_date(items):
    return sorted(items, key=lambda i: (i["date"], i["path"]), reverse=True)


@app.after_request
def headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "no-referrer"
    r.headers.setdefault("X-Frame-Options", "DENY")
    if r.mimetype == "text/html":
        r.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    if (r.mimetype == "application/json" and not r.direct_passthrough
            and "gzip" in request.headers.get("Accept-Encoding", "")
            and r.content_length and r.content_length > 2048):
        r.set_data(gzip.compress(r.get_data(), 5))
        r.headers["Content-Encoding"] = "gzip"
        r.headers["Vary"] = "Accept-Encoding"
    return r


@app.errorhandler(HTTPException)
def http_error(e):
    if e.response is not None:  # raised by fail() with a ready JSON response
        return e.response
    if request.path.startswith(("/api/", "/t/", "/m/", "/d/", "/tt/")):
        msg = {413: "That file is over 2 GB", 404: "Not found"}.get(e.code, e.description)
        return jsonify(error=msg), e.code
    return e


# ---------- auth ----------

@app.get("/api/session")
def get_session():
    ok = bool(session.get("ok"))
    return jsonify(authed=ok, csrf=session.get("csrf") if ok else None, configured=bool(auth["hash"]))


@app.post("/api/login")
def login():
    ip = request.remote_addr
    n, until = fails.get(ip, (0, 0))
    if until > time.time():
        fail(429, f"Too many tries. Wait {int(until - time.time()) // 60 + 1} min.")
    if auth["hash"] and check_password_hash(auth["hash"], str(body().get("key", ""))):
        fails.pop(ip, None)
        session.clear()
        session.update(ok=True, csrf=secrets.token_hex(16))
        session.permanent = True
        return jsonify(ok=True, csrf=session["csrf"])
    time.sleep(0.6)
    n += 1
    fails[ip] = (0, time.time() + LOCKOUT_SECONDS) if n >= LOCKOUT_TRIES else (n, 0)
    fail(401, "That key didn't work.")


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/lock")
def lock():  # old bookmark / plain link
    session.clear()
    return redirect("/login")


# ---------- browsing ----------

@app.get("/api/library")
@need_login
def get_library():
    items, _ = library.snapshot()
    return jsonify(items=by_date(item(r, m) for r, m in items.items() if not hidden.is_hidden(r)),
                   scanning=library.scanning)


@app.get("/api/albums")
@need_login
def get_album():
    rel = request.args.get("path", "").strip("/")
    folder = path_arg(rel)
    if not folder.is_dir():
        fail(404, "That album doesn't exist")
    items, folders = library.snapshot()
    prefix = rel + "/" if rel else ""
    inside = hidden.is_hidden(rel)  # browsing a hidden album: its contents are fair game
    secret = (lambda r: False) if inside else hidden.is_hidden  # hidden albums are listed only on the Hidden page
    subs = {f: {"count": 0, "cover": None, "date": ""} for f in folders
            if f and f.startswith(prefix) and "/" not in f[len(prefix):] and not secret(f)}
    direct = []
    for r, m in items.items():
        if not r.startswith(prefix) or secret(r):
            continue
        rest = r[len(prefix):]
        if "/" not in rest:
            direct.append(item(r, m))
            continue
        s = subs.get(prefix + rest.split("/", 1)[0])
        if s is not None:
            s["count"] += 1
            if m["date"] > s["date"]:
                s["date"], s["cover"] = m["date"], {"path": r, "kind": m["kind"]}
    albums = [{"path": f, "name": f.rsplit("/", 1)[-1], **v}
              for f, v in sorted(subs.items(), key=lambda kv: kv[0].lower())]
    parts = rel.split("/") if rel else []
    crumbs = [{"name": n, "path": "/".join(parts[:i + 1])} for i, n in enumerate(parts)]
    return jsonify(path=rel, name=parts[-1] if parts else "Albums", crumbs=crumbs,
                   albums=albums, items=by_date(direct), hidden=inside,
                   hiddenRoot=hidden.starts_at(rel))


@app.get("/api/folders")
@need_login
def get_folders():
    """All album paths. Hidden ones are included only while unlocked (so photos can be
    moved into them), and never for search (?search=1), like WhatsApp's locked chats."""
    _, folders = library.snapshot()
    ok = (lambda f: not hidden.is_hidden(f)) if request.args.get("search") else visible
    return jsonify(sorted((f for f in folders if ok(f)), key=str.lower))


@app.get("/api/info")
@need_login
def get_info():
    rel = request.args.get("path", "")
    p = path_arg(rel)
    k = kind(p)
    if not p.is_file() or not k:
        fail(404, "Not found")
    return jsonify(media.details(p, k))


# ---------- changing things ----------

@app.post("/api/upload")
@need_login
def upload():
    folder = path_arg(request.form.get("folder", ""))
    f = request.files.get("file")
    if not folder.is_dir() or not f or not f.filename:
        fail(400, "Nothing to upload")
    ext = Path(f.filename).suffix.lower()
    if ext not in IMAGES | VIDEOS:
        fail(400, "Not a photo or video")
    if shutil.disk_usage(ROOT).free < MIN_FREE:
        fail(507, "The Pi is almost out of space")
    dest = unique(folder, clean_name(Path(f.filename).stem), ext)
    tmp = folder / f".{dest.name}.{secrets.token_hex(4)}.part"
    try:
        f.save(tmp)
        if dest.exists():  # another upload took the name meanwhile
            dest = unique(folder, dest.stem, ext)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    library.invalidate()
    return jsonify(ok=True, path=rel_of(dest))


@app.post("/api/mkdir")
@need_login
def mkdir():
    b = body()
    parent = path_arg(b.get("folder", ""))
    name = clean_name(b.get("name", ""), fallback="")
    if not parent.is_dir() or not name:
        fail(400, "Enter an album name")
    target = parent / name
    if target.exists():
        fail(409, "An album with that name already exists")
    target.mkdir()
    library.invalidate()
    return jsonify(ok=True, path=rel_of(target))


@app.post("/api/delete")
@need_login
def delete():
    done, ids = [], []
    for rel in body().get("paths", [])[:5000]:
        try:
            if not isinstance(rel, str) or not visible(rel):
                continue
            ids.append(trash.put(rel))
            done.append(rel)
        except (BadPath, FileNotFoundError):
            pass
    favorites.drop(done)
    library.invalidate()
    return jsonify(ok=True, deleted=done, ids=ids)


@app.post("/api/move")
@need_login
def move():
    b = body()
    dest = path_arg(b.get("dest", ""))
    if not dest.is_dir():
        fail(400, "Pick an album to move to")
    moved = []
    for rel in b.get("paths", [])[:5000]:
        try:
            src = resolve(rel)
        except BadPath:
            continue
        if not visible(rel_of(src)) or not src.is_file() or src.parent == dest:
            continue
        target = unique(dest, src.stem, src.suffix)
        os.replace(src, target)
        favorites.moved(rel, rel_of(target))
        moved.append(rel_of(target))
    library.invalidate()
    return jsonify(ok=True, moved=moved)


@app.post("/api/rename")
@need_login
def rename():
    """Rename a photo/video (extension kept) or an album."""
    b = body()
    rel = b.get("path", "")
    src = path_arg(rel)
    if src == ROOT or not src.exists():
        fail(404, "Not found")
    name = clean_name(b.get("name", ""), fallback="")
    if src.is_file():
        name = clean_name(Path(name).stem if Path(name).suffix.lower() == src.suffix.lower() else name, "")
        if not name:
            fail(400, "Enter a name")
        target = src.with_name(name + src.suffix)
    else:
        if not name:
            fail(400, "Enter a name")
        target = src.with_name(name)
    if target == src:
        return jsonify(ok=True, path=rel)
    if target.exists():
        fail(409, "Something with that name is already there")
    old = rel_of(src)
    os.replace(src, target)
    favorites.moved(old, rel_of(target))
    hidden.moved(old, rel_of(target))
    library.invalidate()
    return jsonify(ok=True, path=rel_of(target))


@app.post("/api/rmdir")
@need_login
def rmdir():
    """Delete an album. Its photos and videos (sub-albums included) go to the trash one by
    one, so each can be restored to where it was; then the emptied folders are removed.
    Other files (documents etc.) are never deleted: their folders are kept."""
    p = path_arg(body().get("path", ""))
    if p == ROOT or not p.is_dir():
        fail(404, "Not found")
    rel = rel_of(p)
    items, _ = library.snapshot()
    inside = [r for r in items if r.startswith(rel + "/")]
    ids = []
    for r in inside:
        try:
            ids.append(trash.put(r))
        except (BadPath, FileNotFoundError):
            pass
    favorites.drop(inside)
    # remove folders bottom-up while they hold nothing but dot-files (macOS ._ leftovers)
    kept = False
    for d in sorted((x for x in p.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)) + [p]:
        if d.name.startswith(".") and d != p:
            continue
        if any(not c.name.startswith(".") for c in d.iterdir()):
            kept = True
            continue
        shutil.rmtree(d)
    if not p.exists():
        hidden.removed(rel)
    library.invalidate()
    return jsonify(ok=True, ids=ids, kept=kept and p.exists())


@app.post("/api/move-album")
@need_login
def move_album():
    """Move an album (with everything in it) into another album, or to the top level."""
    b = body()
    src = path_arg(b.get("path", ""))
    dest = path_arg(b.get("dest", ""))
    if src == ROOT or not src.is_dir():
        fail(404, "Not found")
    if not dest.is_dir():
        fail(400, "Pick an album to move it into")
    if dest == src or src in dest.parents:
        fail(400, "An album can't go inside itself")
    if src.parent == dest:
        return jsonify(ok=True, path=rel_of(src))
    target, n = dest / src.name, 1
    while target.exists():
        target = dest / f"{src.name}_{n}"
        n += 1
    old = rel_of(src)
    os.replace(src, target)
    favorites.moved(old, rel_of(target))
    hidden.moved(old, rel_of(target))
    library.invalidate()
    return jsonify(ok=True, path=rel_of(target))


@app.post("/api/favorite")
@need_login
def favorite():
    b = body()
    rels = [r for r in b.get("paths", [])[:5000] if isinstance(r, str)]
    favorites.set(rels, bool(b.get("on", True)))
    return jsonify(ok=True)


# ---------- trash ----------

@app.get("/api/trash")
@need_login
def get_trash():
    return jsonify([e for e in trash.list() if visible(e["from"])])


def trash_visible(tid):
    return any(e["id"] == tid for e in trash.list() if visible(e["from"]))


@app.post("/api/trash/restore")
@need_login
def restore():
    done = []
    for tid in body().get("ids", []):
        try:
            if not trash_visible(str(tid)):
                continue
            done.append(trash.restore(str(tid)))
        except (BadPath, FileNotFoundError):
            pass
    library.invalidate()
    return jsonify(ok=True, restored=done)


@app.post("/api/trash/delete")
@need_login
def purge():
    b = body()
    shown = {e["id"] for e in trash.list() if visible(e["from"])}
    trash.remove(list(shown) if b.get("all") else [str(t) for t in b.get("ids", []) if str(t) in shown])
    return jsonify(ok=True)


# ---------- hidden albums ----------

@app.get("/api/hidden")
@need_login
def get_hidden():
    """Status, plus the hidden albums themselves once the code has been entered."""
    if not unlocked():
        return jsonify(configured=hidden.configured, unlocked=False, albums=[])
    items, folders = library.snapshot()
    albums = []
    for f in sorted(hidden.folders, key=str.lower):
        if f not in folders:
            continue  # renamed elsewhere, or the drive isn't mounted
        inside = [(r, m) for r, m in items.items() if r.startswith(f + "/")]
        newest = max(inside, key=lambda rm: rm[1]["date"], default=None)
        albums.append({"path": f, "name": f.rsplit("/", 1)[-1], "count": len(inside),
                       "cover": {"path": newest[0], "kind": newest[1]["kind"]} if newest else None})
    return jsonify(configured=True, unlocked=True, albums=albums)


@app.post("/api/hidden/unlock")
@need_login
def unlock_hidden():
    """Called when a search is submitted. Answers 200 either way so a wrong guess looks
    like an ordinary search; checks are throttled per device to stop guessing."""
    code = str(body().get("code", "")).strip()
    ip = request.remote_addr
    now = time.time()
    recent = [t for t in code_checks.get(ip, []) if now - t < CODE_WINDOW]
    ok = False
    if hidden.configured and len(code) >= 4 and len(recent) < CODE_CHECKS:
        recent.append(now)
        ok = hidden.check(code)
    code_checks[ip] = recent
    if ok:
        session["hidden_until"] = now + HIDDEN_IDLE_SECONDS
    return jsonify(ok=ok)


@app.post("/api/hidden/lock")
@need_login
def lock_hidden():
    session.pop("hidden_until", None)
    return jsonify(ok=True)


@app.post("/api/hidden/code")
@need_login
def set_hidden_code():
    """Create the secret code, or change it (only while unlocked)."""
    code = str(body().get("code", "")).strip()
    if hidden.configured and not unlocked():
        fail(403, "Enter your current secret code first")
    if len(code) < 4:
        fail(400, "Use at least 4 characters")
    hidden.set_code(code)
    session["hidden_until"] = time.time() + HIDDEN_IDLE_SECONDS
    return jsonify(ok=True)


@app.post("/api/hidden/hide")
@need_login
def hide_album():
    if not hidden.configured or not unlocked():
        fail(403, "Enter your secret code first")
    p = path_arg(body().get("path", ""))
    if p == ROOT or not p.is_dir():
        fail(400, "Only albums can be hidden")
    hidden.hide(rel_of(p))
    return jsonify(ok=True)


@app.post("/api/hidden/unhide")
@need_login
def unhide_album():
    if not unlocked():
        fail(403, "Enter your secret code first")
    p = path_arg(body().get("path", ""))
    rel = rel_of(p)
    if not hidden.starts_at(rel):
        fail(400, "This album isn't hidden by itself. Unhide the album that contains it.")
    hidden.unhide(rel)
    return jsonify(ok=True)


# ---------- media ----------

def media_file(rel):
    p = path_arg(rel)
    k = kind(p)
    if not p.is_file() or not k:
        fail(404, "Not found")
    return p, k


@app.after_request
def no_cache_hidden(r):
    """Don't leave copies of hidden photos in the browser cache."""
    if request.path.startswith(("/t/", "/m/", "/d/")):
        rel = request.path.split("/", 2)[2].strip("/")  # request.path is already decoded
        if hidden.is_hidden(rel):
            r.headers["Cache-Control"] = "private, no-store"
    return r


@app.get("/t/<path:rel>")
@need_login
def thumb(rel):
    p, k = media_file(rel)
    try:
        return send_file(media.thumb(p, k), mimetype="image/jpeg", max_age=7 * 86400)
    except media.Unreadable:
        fail(404, "Can't read this file")


@app.get("/m/<path:rel>")
@need_login
def original(rel):
    """What the viewer shows: the file itself, or a JPEG copy for HEIC/TIFF/DNG."""
    p, k = media_file(rel)
    if p.suffix.lower() in CONVERT:
        try:
            return send_file(media.view(p), mimetype="image/jpeg", max_age=86400)
        except media.Unreadable:
            fail(404, "Can't read this file")
    return send_file(p, conditional=True, max_age=3600)


@app.get("/d/<path:rel>")
@need_login
def download(rel):
    p, _ = media_file(rel)
    return send_file(p, as_attachment=True, download_name=p.name, conditional=True)


@app.get("/tt/<tid>")
@need_login
def trash_thumb(tid):
    p = trash.file(tid) if trash_visible(tid) else None
    if not p or not kind(p):
        fail(404, "Not found")
    try:
        return send_file(media.thumb(p, kind(p)), mimetype="image/jpeg", max_age=86400)
    except media.Unreadable:
        fail(404, "Can't read this file")


# ---------- frontend ----------

@app.get("/g/")
@app.get("/g/<path:rel>")
def old_links(rel=""):  # bookmarks from the first version
    return redirect("/albums/" + quote(rel) if rel else "/albums")


@app.get("/")
@app.get("/<path:p>")
def spa(p=""):
    if p.startswith(("api/", "t/", "m/", "d/", "tt/")):
        abort(404)
    f = (DIST / p).resolve()
    if p and DIST in f.parents and f.is_file():
        immutable = p.startswith("assets/")
        r = send_file(f, max_age=31536000 if immutable else 0)
        if immutable:
            r.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return r
    index = DIST / "index.html"
    if not index.exists():
        return ("The app isn't built yet. Run: cd web && npm install && npm run build", 503,
                {"Content-Type": "text/plain"})
    r = send_file(index, max_age=0)
    r.headers["Cache-Control"] = "no-cache"
    return r
