#!/usr/bin/env python3
"""Private photo gallery for a Raspberry Pi.

  python3 app.py setpass        # choose your secret key (once)
  python3 app.py                # start the gallery (default port 8080)
  python3 app.py sethidden      # set or reset the secret code for hidden albums
  python3 app.py warm [--views] # pre-build the index and thumbnails (and viewer copies
                                # of HEIC/DNG/TIFF) so browsing is instant, e.g. after rsync

Put your photos (sub-folders are fine) in ./photos, or set PHOTO_DIR to
another folder, such as a mounted USB drive. The web app lives in web/ and
must be built once with `npm install && npm run build`.
"""
import getpass, json, secrets, sys

from werkzeug.security import generate_password_hash

from gallery.config import AUTH, DIST, PORT, ROOT


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


def set_hidden_code():
    from gallery.store import Hidden
    h = Hidden()
    print("Hidden albums open when this code is typed into the gallery's search box.")
    a = getpass.getpass("New secret code: ").strip()
    if len(a) < 4:
        sys.exit("Use at least 4 characters.")
    if a != getpass.getpass("Type it again: ").strip():
        sys.exit("The two entries didn't match.")
    h.set_code(a)
    print(f"Saved. {len(h.folders)} album(s) are hidden. Restart the gallery to apply.")


def warm(views=False):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from gallery import media
    from gallery.config import CONVERT
    from gallery.library import Library
    from gallery.paths import resolve

    t = time.time()
    lib = Library()
    lib.refresh(force=True)
    print(f"Indexed {len(lib.items)} items in {time.time() - t:.0f} s")
    jobs = [(rel, m["kind"], "thumb") for rel, m in lib.items.items()]
    if views:
        jobs += [(rel, "image", "view") for rel in lib.items if rel.rsplit(".", 1)[-1].lower() in
                 {e.lstrip(".") for e in CONVERT}]
    done = failed = 0

    def run(job):
        rel, k, what = job
        p = resolve(rel)
        media.thumb(p, k) if what == "thumb" else media.view(p)

    with ThreadPoolExecutor(3) as pool:
        for fut in [pool.submit(run, j) for j in jobs]:
            try:
                fut.result()
                done += 1
            except Exception:
                failed += 1
            if (done + failed) % 100 == 0:
                print(f"  {done + failed}/{len(jobs)}", flush=True)
    print(f"Done: {done} ready, {failed} unreadable, {time.time() - t:.0f} s total")


def serve():
    if not AUTH.exists():
        sys.exit("No secret key yet. Run:  python3 app.py setpass")
    if not (DIST / "index.html").exists():
        print("Warning: web/dist is missing. Build it: cd web && npm install && npm run build")
    ROOT.mkdir(exist_ok=True)
    # Upload bodies are spooled to temp files (by waitress, then again by Flask's form
    # parser). /tmp is RAM on Raspberry Pi OS, so a 2 GB video could exhaust memory;
    # spool on the photo drive instead (hidden folder, files are deleted as they close).
    import tempfile
    spool = ROOT / ".tmp"
    spool.mkdir(exist_ok=True)
    tempfile.tempdir = str(spool)
    from gallery.server import app, library
    library.warm()  # index new photos in the background so the first visit is quick
    print(f"Gallery running on port {PORT}, photos from {ROOT}")
    try:
        from waitress import serve as waitress_serve
        # clear_untrusted_proxy_headers=False: let X-Forwarded-* from a local proxy (Tailscale
        # Funnel, cloudflared) reach the app; server.client_ip()/via_https() only trust them
        # when the request really comes from 127.0.0.1.
        waitress_serve(app, host="0.0.0.0", port=PORT, threads=8,
                       max_request_body_size=2200 * 1024 * 1024,
                       clear_untrusted_proxy_headers=False)
    except ImportError:
        app.run(host="0.0.0.0", port=PORT, threaded=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setpass":
        set_passphrase()
    elif len(sys.argv) > 1 and sys.argv[1] == "sethidden":
        set_hidden_code()
    elif len(sys.argv) > 1 and sys.argv[1] == "warm":
        warm(views="--views" in sys.argv)
    else:
        serve()
