# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A private photo/video gallery that runs on a Raspberry Pi on a home LAN, behind one shared secret key. It has two parts:

- a **Python/Flask backend** (`app.py` + `gallery/`): JSON API, auth, thumbnails and format conversion, file management
- a **Svelte 5 + Vite frontend** (`web/`), built to static files in `web/dist/` that Flask serves

It was migrated from a single-file Flask app with inline templates (commit `ce10948`). The backend stayed in Python on purpose: most of the library is iPhone HEIC, which `pillow-heif` handles and Node's `sharp` can't decode without a custom build. DNG uses `rawpy`, and videos use `ffmpeg`/`ffprobe`.

`README.md` is end-user setup docs written for a non-technical reader; keep that plain tone if you edit it.

## Commands

```
# backend
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python3 app.py setpass             # create .auth.json (password hash + Flask session secret)
python3 app.py                     # serve API + web/dist on 0.0.0.0:8080 via waitress
python3 app.py warm [--views]      # pre-build index + thumbnails (+ viewer JPEGs for HEIC/DNG/TIFF)

# frontend (Node 20, from apt)
cd web && npm install
npm run build                      # -> web/dist, required before the backend can serve the UI
npm run dev                        # hot-reload UI on :5173, proxies API/media to BACKEND (default :8080)
```

There is no unit-test suite or linter. `npm run build` must finish with no Svelte warnings. Verify behaviour against a throwaway library rather than the real photos:

```
GALLERY_AUTH=/tmp/x/auth.json GALLERY_FAVORITES=/tmp/x/fav.json PHOTO_DIR=/tmp/x/lib PORT=8091 python3 app.py
```

`GALLERY_AUTH` and `GALLERY_FAVORITES` exist so a test server never touches the real key or favorites. The library index is keyed by `PHOTO_DIR`, so test servers can share `.cache/` safely. In the Flask test client you can skip login with `with c.session_transaction() as s: s["ok"]=True; s["csrf"]="x"` and send `X-CSRF: x` on POSTs.

## Backend architecture (`gallery/`)

- `config.py`: everything configurable (env: `PHOTO_DIR`, `PORT`, `GALLERY_AUTH`, `GALLERY_FAVORITES`), file-type sets (`IMAGES`, `VIDEOS`, `RAW`, `CONVERT`) and limits.
- `paths.py`: `resolve(rel)` is the **only** way to turn a client path into a filesystem path. It rejects escapes from `ROOT` and any dot-prefixed segment, which hides `.trash/`, macOS `._*` sidecars (the pendrive has many) and `.part` upload temp files. `clean_name()` sanitizes new file/album names but keeps spaces, emoji and apostrophes, unlike `secure_filename`.
- `library.py`: an in-memory index of every media file (`kind, w, h, date, size, mtime, dur`), persisted to `.cache/library-<hash(ROOT)>.json`. `refresh()` re-walks the tree (stat only, about 10 ms) at most every 10 s and reads EXIF/ffprobe only for new or changed files. A full first scan of about 1,200 files takes about 60 s, so `serve()` starts it in a background thread. Call `library.invalidate()` after any file change. Displayed sizes already account for EXIF orientation and video rotation. Dates come from EXIF `DateTimeOriginal`, then video `creation_time` (UTC converted to local), then file mtime.
- `media.py`: metadata readers and cached JPEG renditions in `.cache/<2 hex>/<sha1(path|mtime|side)>.jpg`. Sizes are 640 px for thumbnails and 2560 px for viewer copies of HEIC/TIFF/DNG. DNG uses the full-size embedded JPEG preview, rotated per LibRaw `flip`. Video posters are an ffmpeg frame at 1 s. Concurrency is capped with semaphores (3 small, 2 large) because a 48 MP HEIC needs about 150 MB to decode.
- `store.py`: `Favorites` (JSON set of paths; `moved()` rewrites paths when files or albums move or get renamed) and `Trash` (files moved to `ROOT/.trash/<id>/name` plus `manifest.json` with the original path, auto-purged after 30 days).
- `server.py`: the Flask app. The `@need_login` decorator checks the session and the CSRF header (`X-CSRF` must equal `session["csrf"]`) on every POST except `/api/login`. `fail(status, msg)` aborts with a JSON `{error}` that the frontend shows directly to the user, so write messages for the end user.

### API surface

| Route | Purpose |
|---|---|
| `GET /api/session`, `POST /api/login`, `POST /api/logout` | auth (per-IP lockout: 5 tries, then 5 min; resets on restart) |
| `GET /api/library` | every item, newest first (`path, name, folder, kind, w, h, date, size, dur, fav, v`) |
| `GET /api/albums?path=` | sub-albums (count + newest cover, recursive) and direct items of one folder |
| `GET /api/folders`, `GET /api/info?path=` | all folder paths (move picker); EXIF details for the info panel |
| `POST /api/upload` (multipart `folder`,`file`), `/api/mkdir`, `/api/rename`, `/api/move`, `/api/delete`, `/api/rmdir`, `/api/favorite` | changes; delete goes to trash and returns `ids` so the UI can offer Undo; `rmdir` only deletes empty albums |
| `GET /api/trash`, `POST /api/trash/restore`, `POST /api/trash/delete` | trash |
| `GET /t/<path>`, `/m/<path>`, `/d/<path>`, `/tt/<id>` | thumbnail, viewer file (original or converted JPEG), download original, trash thumbnail |
| `GET /g/<path>` | redirects old v1 bookmarks to `/albums/<path>` |
| anything else | `web/dist` asset or `index.html` (SPA fallback; hashed `assets/` are cached immutably) |

`v` on items is an mtime-derived cache-buster appended to `/t/` and `/m/` URLs.

## Frontend architecture (`web/src/`)

- No router library. `lib/router.svelte.js` uses `history`, and the open photo lives in `?photo=<path>`. Opening the viewer pushes a history entry, so Back or Android's back gesture closes it, and moving between photos replaces that entry.
- `lib/state.svelte.js` holds global `$state` (`app.library`, `app.context`, `app.slideshow`, `app.dialog`, toasts), the `favs` and `selection` `SvelteSet`s, and **every action that changes files**. After a change it calls `changed()`, which bumps `app.version` (open views re-fetch) and reloads the library.
- Each view sets `app.context` to the items it shows. `App.svelte` renders one global `Viewer` over `app.slideshow?.items ?? app.context`. `ask({kind:'confirm'|'prompt'|'album'})` returns a promise and is rendered by `Dialog.svelte`.
- `lib/layout.js` `justify()` produces absolutely positioned blocks: justified rows, day headers, and small days packed side by side. `PhotoGrid.svelte` renders only blocks near the viewport (window scroll) and owns selection (long-press on touch, hover checkbox or Ctrl/Shift-click on desktop) and the timeline scrubber.
- `Viewer.svelte` handles its own pointer gestures: swipe to page, swipe down to close, pinch, double-tap and wheel zoom with pan clamping. It keeps the thumbnail visible until the full image loads, and preloads neighbours.
- Layout breakpoint: at 900 px and up there's a sidebar; below that there's a bottom tab bar, with `--nav-offset` on `:root` so fixed elements clear it. Safe-area insets are respected. Light and dark follow the system setting via CSS variables in `app.css`.
- PWA: `public/manifest.webmanifest` plus Apple meta tags. There's deliberately **no service worker**: it would need HTTPS, and caching private photos on devices is unwanted. Over plain-HTTP LAN, iOS "Add to Home Screen" runs standalone, but Android only creates a shortcut.
- npm dependency versions are pinned exactly. Pick releases that are at least 2 weeks old.

## Production deployment (this Pi)

The app runs as the systemd unit `/etc/systemd/system/gallery.service` (enabled at boot):

```
[Service]
User=asmithreddy
WorkingDirectory=/home/asmithreddy/projects/youDontWannaSeeThis/private-gallery
Environment="PHOTO_DIR=/mnt/pendrive"
ExecStart=/home/asmithreddy/projects/youDontWannaSeeThis/private-gallery/venv/bin/python app.py
Restart=on-failure
RestartSec=5s
```

- It runs straight from this working copy, so a deploy is `cd web && npm run build`, then `sudo systemctl restart gallery`. Frontend-only changes need just the build, because `index.html` is served `no-cache`. Logs: `journalctl -u gallery -f`.
- **Photos are on a USB pendrive**: `/dev/sda1` (exFAT, 58 GB) at `/mnt/pendrive`, mounted from `/etc/fstab` with `uid=1000,gid=1000,umask=000,nofail`. exFAT has no Unix permissions or symlinks and treats names case-insensitively. Upload free-space checks measure the pendrive, and `.trash/` lives on it too.
- `.auth.json`, `.favorites.json` and `.cache/` stay on the SD card in this directory.
- Because of `nofail` and the missing `RequiresMountsFor=/mnt/pendrive`, if the drive isn't mounted at boot the service serves the empty mountpoint and uploads land on the SD card.
- Node 20, ffmpeg and `rawpy` are installed. Rebuild `web/dist` on the Pi after changing anything in `web/`.

## Repo notes

- Gitignored runtime and local data: `venv/`, `.cache/`, `.auth.json`, `.favorites.json`, `photos/`, `web/node_modules/`, `web/dist/`. Never commit them. If `PHOTO_DIR` points inside the repo under another name, add it to `.gitignore` too.
