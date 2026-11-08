#!/usr/bin/env python3
"""Private photo gallery for a Raspberry Pi.

  python3 app.py setpass   # choose your secret key (once)
  python3 app.py           # start the gallery (default port 8080)

Put your photos (sub-folders are fine) in ./photos, or set PHOTO_DIR to
another folder, such as a mounted SSD.
"""
import getpass, hashlib, json, os, secrets, shutil, sys, time
from functools import wraps
from pathlib import Path
from urllib.parse import quote

from flask import (Flask, abort, jsonify, redirect, render_template_string,
                   request, send_file, session)
from PIL import Image, ImageOps
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:  # lets iPhone HEIC photos open
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

BASE = Path(__file__).parent.resolve()
ROOT = Path(os.environ.get("PHOTO_DIR", BASE / "photos")).resolve()
CACHE = BASE / ".cache"
AUTH = BASE / ".auth.json"
PORT = int(os.environ.get("PORT", 8080))
IMAGES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff"}
VIDEOS = {".mp4", ".mov", ".m4v", ".webm"}
CONVERT = {".heic", ".heif", ".tif", ".tiff"}  # browsers can't show these as-is

auth = json.loads(AUTH.read_text()) if AUTH.exists() else {"hash": "", "secret": "unset"}
app = Flask(__name__)
app.secret_key = auth["secret"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                  PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
                  MAX_CONTENT_LENGTH=2 * 1024 ** 3)  # biggest single upload: 2 GB
fails = {}  # ip -> (wrong tries, locked until)


def set_passphrase():
    a = getpass.getpass("Choose your secret key: ")
    if len(a) < 6:
        sys.exit("Use at least 6 characters.")
    if a != getpass.getpass("Type it again: "):
        sys.exit("The two entries didn't match.")
    AUTH.write_text(json.dumps({"hash": generate_password_hash(a),
                                "secret": secrets.token_hex(32)}))
    AUTH.chmod(0o600)
    print("Saved. Start the gallery with: python3 app.py")


def need_login(f):
    @wraps(f)
    def wrap(*a, **k):
        if not session.get("ok"):
            return redirect("/login")
        return f(*a, **k)
    return wrap


@app.after_request
def headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "no-referrer"
    return r


def safe(rel):
    p = (ROOT / rel).resolve()
    if p != ROOT and ROOT not in p.parents:
        abort(404)
    if any(s.startswith(".") for s in p.relative_to(ROOT).parts):
        abort(404)
    return p


def kind(p):
    e = p.suffix.lower()
    return "image" if e in IMAGES else "video" if e in VIDEOS else None


def listing(folder, deep=False):
    files = folder.rglob("*") if deep else folder.iterdir()
    out = []
    for p in sorted(files, key=lambda x: str(x).lower()):
        rel = p.relative_to(ROOT)
        if not p.is_file() or any(s.startswith(".") for s in rel.parts) or not kind(p):
            continue
        u = quote(rel.as_posix())
        out.append({"kind": kind(p), "src": "/m/" + u, "thumb": "/t/" + u, "name": p.name})
    return out


def jpeg(p, side):
    st = p.stat()
    key = hashlib.sha1(f"{p}|{st.st_mtime_ns}|{side}".encode()).hexdigest()
    out = CACHE / (key + ".jpg")
    if not out.exists():
        CACHE.mkdir(exist_ok=True)
        try:
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((side, side))
                im.convert("RGB").save(out, "JPEG", quality=84)
        except Exception:
            abort(404)
    return out


@app.route("/")
def home():
    return redirect("/g/")


@app.route("/login", methods=["GET", "POST"])
def login():
    ip, error = request.remote_addr, ""
    if request.method == "POST":
        n, until = fails.get(ip, (0, 0))
        if until > time.time():
            error = "Too many tries. Wait a few minutes."
        elif check_password_hash(auth["hash"], request.form.get("key", "")):
            fails.pop(ip, None)
            session.clear()
            session["ok"] = True
            session["csrf"] = secrets.token_hex(16)
            session.permanent = True
            return redirect("/g/")
        else:
            time.sleep(0.6)
            n += 1
            fails[ip] = (0, time.time() + 300) if n >= 5 else (n, 0)
            error = "That key didn't work."
    return render_template_string(LOGIN, css=CSS, error=error)


@app.route("/lock")
def lock():
    session.clear()
    return redirect("/login")


@app.route("/g/")
@app.route("/g/<path:rel>")
@need_login
def browse(rel=""):
    folder = safe(rel)
    if not folder.is_dir():
        abort(404)
    parts = Path(rel).parts
    crumbs = [("Gallery", "/g/")] + [
        (n, "/g/" + quote("/".join(parts[:i + 1]))) for i, n in enumerate(parts)]
    dirs = [(d.name, "/g/" + quote(d.relative_to(ROOT).as_posix()))
            for d in sorted(folder.iterdir(), key=lambda x: x.name.lower())
            if d.is_dir() and not d.name.startswith(".")]
    return render_template_string(PAGE, css=CSS, crumbs=crumbs, dirs=dirs,
                                  items=listing(folder), api="/api/list/" + quote(rel),
                                  csrf=session.setdefault("csrf", secrets.token_hex(16)), rel=rel)


@app.route("/api/list/")
@app.route("/api/list/<path:rel>")
@need_login
def api_list(rel=""):
    folder = safe(rel)
    if not folder.is_dir():
        abort(404)
    return jsonify(listing(folder, deep=True))


def check_csrf():
    if not secrets.compare_digest(request.headers.get("X-CSRF", ""), session.get("csrf", "none")):
        abort(403)


@app.route("/upload", methods=["POST"])
@need_login
def upload():
    check_csrf()
    folder = safe(request.form.get("folder", ""))
    f = request.files.get("file")
    if not folder.is_dir() or not f or not f.filename:
        abort(400)
    ext = Path(f.filename).suffix.lower()
    if ext not in IMAGES | VIDEOS:
        return jsonify(error="Not a photo or video"), 400
    if shutil.disk_usage(ROOT).free < 500 * 1024 * 1024:
        return jsonify(error="The Pi is almost out of space"), 507
    stem = secure_filename(Path(f.filename).stem) or "photo"
    dest, n = folder / (stem + ext), 1
    while dest.exists():  # never overwrite an existing photo
        dest = folder / f"{stem}_{n}{ext}"
        n += 1
    tmp = folder / f".{dest.name}.part"
    f.save(tmp)
    os.replace(tmp, dest)
    return jsonify(ok=True, name=dest.name)


@app.route("/mkdir", methods=["POST"])
@need_login
def mkdir():
    check_csrf()
    parent = safe(request.form.get("folder", ""))
    name = secure_filename(request.form.get("name", "").strip())
    if not parent.is_dir() or not name:
        return jsonify(error="Enter a folder name"), 400
    (parent / name).mkdir(exist_ok=True)
    return jsonify(ok=True)


@app.route("/t/<path:rel>")
@need_login
def thumb(rel):
    p = safe(rel)
    if not p.is_file() or p.suffix.lower() not in IMAGES:
        abort(404)
    return send_file(jpeg(p, 480), max_age=86400)


@app.route("/m/<path:rel>")
@need_login
def media(rel):
    p = safe(rel)
    if not p.is_file() or not kind(p):
        abort(404)
    if p.suffix.lower() in CONVERT:
        return send_file(jpeg(p, 2400))
    return send_file(p, conditional=True)


CSS = """
:root{--bg:#1b1d24;--surface:#252833;--line:#363a49;--text:#ebe8e3;--muted:#9a9ca9;--accent:#aebcf0;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.btn{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:.45rem .9rem;cursor:pointer;text-decoration:none;display:inline-block}
.btn:hover{border-color:var(--accent)}
.primary{background:var(--accent);color:#14161f;border-color:var(--accent);font-weight:600}
.center{min-height:100vh;display:grid;place-items:center}
.login{width:min(320px,88vw);display:grid;gap:.75rem}
.login input{font:inherit;padding:.6rem .8rem;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--text)}
.err{margin:0;color:#f0a5a5}
header{display:flex;flex-wrap:wrap;gap:.75rem;justify-content:space-between;align-items:center;padding:1rem clamp(1rem,3vw,2rem);border-bottom:1px solid var(--line)}
.crumbs{font:1.35rem Georgia,"Times New Roman",serif;display:flex;flex-wrap:wrap;gap:.4rem}
.crumbs a{text-decoration:none}.crumbs a:hover{text-decoration:underline}.crumbs span{color:var(--muted)}
.actions{display:flex;gap:.5rem}
main{padding:1rem clamp(1rem,3vw,2rem) 3rem}
.folders{list-style:none;margin:0 0 1.25rem;padding:0;display:flex;flex-wrap:wrap;gap:.5rem}
.folders a{display:block;padding:.4rem .9rem;border:1px solid var(--line);border-radius:999px;text-decoration:none}
.folders a:hover{border-color:var(--accent)}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px}
.tile{position:relative;aspect-ratio:1;padding:0;border:0;background:var(--surface);cursor:pointer;overflow:hidden;border-radius:4px}
.tile img,.tile video{width:100%;height:100%;object-fit:cover;display:block}
.badge{position:absolute;left:6px;bottom:6px;background:#000a;color:#fff;font-size:.75rem;padding:.1rem .5rem;border-radius:999px}
.empty{color:var(--muted)}
#lb{position:fixed;inset:0;background:#0c0d11;z-index:10}
#lb[hidden]{display:none}
#stage{position:absolute;inset:0 0 56px 0;display:grid;place-items:center}
#stage img,#stage video{max-width:100%;max-height:100%}
.nav{position:absolute;top:50%;transform:translateY(-50%);font-size:2.2rem;line-height:1;color:var(--text);background:#0008;border:0;border-radius:8px;padding:.5rem .9rem;cursor:pointer}
.nav.l{left:.5rem}.nav.r{right:.5rem}
.bar{position:absolute;left:0;right:0;bottom:0;height:56px;display:flex;gap:.75rem;align-items:center;justify-content:center;border-top:1px solid var(--line)}
#count{color:var(--muted);min-width:5rem;text-align:center}
"""

LOGIN = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Sign in</title><style>{{ css|safe }}</style></head>
<body class="center"><form method="post" class="login">
<label for="key">Secret key</label>
<input id="key" name="key" type="password" autocomplete="off" autofocus required>
<button class="btn primary">Open</button>
{% if error %}<p class="err" role="alert">{{ error }}</p>{% endif %}
</form></body></html>"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Gallery</title><style>{{ css|safe }}</style></head><body>
<header>
<nav class="crumbs" aria-label="Folder">{% for n,u in crumbs %}<a href="{{ u }}">{{ n }}</a>{% if not loop.last %}<span>/</span>{% endif %}{% endfor %}</nav>
<div class="actions"><label class="btn" for="files">Upload</label><input id="files" type="file" accept="image/*,video/*,.heic,.heif" multiple hidden><button id="newdir" class="btn">New folder</button><button id="shuffle" class="btn">Shuffle slideshow</button><a class="btn" href="/lock">Lock</a></div>
</header>
<main>
{% if dirs %}<ul class="folders">{% for n,u in dirs %}<li><a href="{{ u }}">{{ n }}</a></li>{% endfor %}</ul>{% endif %}
<p id="status" class="empty" role="status"></p>
<div id="grid"></div>
{% if not items and not dirs %}<p class="empty">Nothing here yet. Copy photos into the photos folder on the Pi.</p>{% endif %}
</main>
<div id="lb" hidden role="dialog" aria-modal="true" aria-label="Viewer">
<div id="stage"></div>
<button id="prev" class="nav l" aria-label="Previous">&lsaquo;</button>
<button id="nextb" class="nav r" aria-label="Next">&rsaquo;</button>
<div class="bar"><span id="count"></span><button id="play" class="btn">Play</button><button id="close" class="btn">Close</button></div>
</div>
<script>
const here={{ items|tojson }}, API={{ api|tojson }}, CSRF={{ csrf|tojson }}, REL={{ rel|tojson }};
const $=id=>document.getElementById(id);
let list=[],idx=0,timer=null;
here.forEach((it,i)=>{
  const b=document.createElement('button');b.className='tile';b.setAttribute('aria-label','Open '+it.name);
  if(it.kind==='video'){
    b.innerHTML='<video preload="metadata" muted playsinline></video><span class="badge">Video</span>';
    b.firstChild.src=it.src+'#t=0.1';
  }else{
    const im=document.createElement('img');im.loading='lazy';im.alt='';im.src=it.thumb;b.append(im);
  }
  b.onclick=()=>openLb(here,i,false);$('grid').append(b);
});
function show(){
  const it=list[idx],st=$('stage');st.replaceChildren();let el;
  if(it.kind==='video'){el=document.createElement('video');el.controls=true;el.autoplay=true;el.playsInline=true;el.src=it.src;el.onended=()=>{if(timer)step(1)};}
  else{el=document.createElement('img');el.alt='';el.src=it.src;}
  st.append(el);$('count').textContent=(idx+1)+' / '+list.length;
}
function step(d){idx=(idx+d+list.length)%list.length;show();}
function setPlay(on){
  clearInterval(timer);timer=null;
  if(on)timer=setInterval(()=>{const v=$('stage').firstChild;if(!(v&&v.tagName==='VIDEO'))step(1);},6000);
  $('play').textContent=on?'Pause':'Play';
}
function openLb(l,i,play){list=l;idx=i;$('lb').hidden=false;document.body.style.overflow='hidden';show();setPlay(play);}
function closeLb(){setPlay(false);$('lb').hidden=true;$('stage').replaceChildren();document.body.style.overflow='';}
$('prev').onclick=()=>step(-1);$('nextb').onclick=()=>step(1);$('close').onclick=closeLb;
$('play').onclick=()=>setPlay(!timer);
document.addEventListener('keydown',e=>{
  if($('lb').hidden)return;
  if(e.key==='ArrowRight')step(1);else if(e.key==='ArrowLeft')step(-1);
  else if(e.key==='Escape')closeLb();else if(e.key===' '&&e.target.tagName!=='BUTTON'){e.preventDefault();setPlay(!timer);}
});
let x0=null;$('lb').addEventListener('touchstart',e=>{x0=e.touches[0].clientX},{passive:true});
$('lb').addEventListener('touchend',e=>{if(x0===null)return;const dx=e.changedTouches[0].clientX-x0;if(Math.abs(dx)>60)step(dx<0?1:-1);x0=null;});
let cur=0,tot=0;
const status=t=>{$('status').textContent=t;};
function up(file){return new Promise(res=>{
  const x=new XMLHttpRequest(),fd=new FormData();
  fd.append('folder',REL);fd.append('file',file);
  x.open('POST','/upload');x.setRequestHeader('X-CSRF',CSRF);
  x.upload.onprogress=e=>{if(e.lengthComputable)status('Uploading '+cur+' of '+tot+': '+Math.round(e.loaded/e.total*100)+'%');};
  x.onload=()=>{let m='';try{m=JSON.parse(x.responseText).error||'';}catch(_){}res(x.status===200?'':(m||'Upload failed ('+x.status+')'));};
  x.onerror=()=>res('Connection lost');
  x.send(fd);
});}
$('files').onchange=async e=>{
  const fs=[...e.target.files];tot=fs.length;let ok=0;const bad=[];
  for(cur=1;cur<=tot;cur++){const m=await up(fs[cur-1]);if(m)bad.push(fs[cur-1].name+' ('+m+')');else ok++;}
  e.target.value='';
  status(ok+' uploaded'+(bad.length?'. Failed: '+bad.join(', '):'.'));
  if(ok)setTimeout(()=>location.reload(),bad.length?4000:900);
};
$('newdir').onclick=async()=>{
  const n=prompt('Folder name');if(!n)return;
  const r=await fetch('/mkdir',{method:'POST',headers:{'X-CSRF':CSRF},body:new URLSearchParams({folder:REL,name:n})});
  if(r.ok)location.reload();else status('Could not create that folder.');
};
$('shuffle').onclick=async()=>{
  const r=await fetch(API+'?deep=1');if(!r.ok)return;
  const all=await r.json();if(!all.length)return;
  for(let i=all.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[all[i],all[j]]=[all[j],all[i]];}
  openLb(all,0,true);
};
</script></body></html>"""


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setpass":
        set_passphrase()
    elif not AUTH.exists():
        sys.exit("No secret key yet. Run:  python3 app.py setpass")
    else:
        ROOT.mkdir(exist_ok=True)
        print(f"Gallery running on port {PORT}")
        try:
            from waitress import serve
            serve(app, host="0.0.0.0", port=PORT, threads=8,
                  max_request_body_size=2200 * 1024 * 1024)
        except ImportError:
            app.run(host="0.0.0.0", port=PORT, threaded=True)
