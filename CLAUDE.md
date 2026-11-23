# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A private photo/video gallery that runs on a Raspberry Pi on a home LAN, behind one shared secret key. It has two parts:

- a **Python/Flask backend** (`app.py` + `gallery/`): JSON API, auth, thumbnails and format conversion, file management
- a **Svelte 5 + Vite frontend** (`web/`), built to static files in `web/dist/` that Flask serves

It was migrated from a single-file Flask app with inline templates (commit `ce10948`). The backend stayed in Python on purpose: most of the library is iPhone HEIC, which `pillow-heif` handles and Node's `sharp` can't decode without a custom build. DNG uses `rawpy`, and videos use `ffmpeg`/`ffprobe`.

`README.md` is end-user setup docs written for a non-technical reader; keep that plain tone if you edit it.

`DIARY.md` is the version diary: what changed, how, and **why**, newest first. Read it before reversing a design decision. After any meaningful change (feature, fix, dependency or deployment change), add or extend an entry with What / How / Why / Open, and link the commit hash.

## Commands

```
# backend
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python3 app.py setpass             # create .auth.json (password hash + Flask session secret)
python3 app.py                     # serve API + web/dist on 0.0.0.0:8080 via waitress
python3 app.py warm [--views]      # pre-build index + thumbnails (+ viewer JPEGs for HEIC/DNG/TIFF)
python3 app.py sethidden           # set/reset the hidden-albums secret code

# frontend (Node 20, from apt)
cd web && npm install
npm run build                      # -> web/dist, required before the backend can serve the UI
npm run dev                        # hot-reload UI on :5173, proxies API/media to BACKEND (default :8080)
```

There is no unit-test suite or linter. `npm run build` must finish with no Svelte warnings. Verify behaviour against a throwaway library rather than the real photos:

```
GALLERY_AUTH=/tmp/x/auth.json GALLERY_FAVORITES=/tmp/x/fav.json GALLERY_HIDDEN=/tmp/x/hidden.json PHOTO_DIR=/tmp/x/lib PORT=8091 python3 app.py
```

`GALLERY_AUTH`, `GALLERY_FAVORITES` and `GALLERY_HIDDEN` exist so a test server never touches the real key or favorites. The library index is keyed by `PHOTO_DIR`, so test servers can share `.cache/` safely. In the Flask test client you can skip login with `with c.session_transaction() as s: s["ok"]=True; s["csrf"]="x"` and send `X-CSRF: x` on POSTs.

## Backend architecture (`gallery/`)

- `config.py`: everything configurable (env: `PHOTO_DIR`, `PORT`, `GALLERY_AUTH`, `GALLERY_FAVORITES`), file-type sets (`IMAGES`, `VIDEOS`, `RAW`, `CONVERT`) and limits.
- `paths.py`: `resolve(rel)` is the **only** way to turn a client path into a filesystem path. It rejects escapes from `ROOT` and any dot-prefixed segment, which hides `.trash/`, macOS `._*` sidecars (the pendrive has many) and `.part` upload temp files. `clean_name()` sanitizes new file/album names but keeps spaces, emoji and apostrophes, unlike `secure_filename`.
- `library.py`: an in-memory index of every media file (`kind, w, h, date, size, mtime, dur`), persisted to `.cache/library-<hash(ROOT)>.json`. `refresh()` re-walks the tree (stat only, about 10 ms) at most every 10 s and reads EXIF/ffprobe only for new or changed files. A full first scan of about 1,200 files takes about 60 s, so `serve()` starts it in a background thread. Call `library.invalidate()` after any file change. Displayed sizes already account for EXIF orientation and video rotation. Dates come from EXIF `DateTimeOriginal`, then video `creation_time` (UTC converted to local), then file mtime.
- `media.py`: metadata readers and cached JPEG renditions in `.cache/<2 hex>/<sha1(path|mtime|side)>.jpg`. Sizes are 640 px for thumbnails and 2560 px for viewer copies of HEIC/TIFF/DNG. DNG uses the full-size embedded JPEG preview, rotated per LibRaw `flip`. Video posters are an ffmpeg frame at 1 s. Concurrency is capped with semaphores (3 small, 2 large) because a 48 MP HEIC needs about 150 MB to decode.
- `store.py`: `Favorites` (JSON set of paths; `moved()` rewrites paths when files or albums move or get renamed) and `Trash` (files moved to `ROOT/.trash/<id>/name` plus `manifest.json` with the original path, auto-purged after 30 days).
- `store.py` also has `Hidden`: a secret-code hash plus a list of hidden folder paths in `.hidden.json` (`GALLERY_HIDDEN`). A folder hides everything under it. Like `Favorites`, it is updated by album rename, move and delete (`moved()`/`removed()`), and it's never pruned automatically, because an unmounted drive would make every folder look deleted.
- `server.py`: the Flask app. The `@need_login` decorator checks the session and the CSRF header (`X-CSRF` must equal `session["csrf"]`) on every POST except `/api/login`. `fail(status, msg)` aborts with a JSON `{error}` that the frontend shows directly to the user, so write messages for the end user.
- **Sign-ins are server-side and revocable.** Login stores a random `sid` in the cookie and in the in-memory `active` dict. `need_login` calls `session_alive()`, which ends a sign-in after `SESSION_HOURS`, after `IDLE_SECONDS` (10 min) without any request, or `CLOSE_GRACE` (8 s) after a `/api/bye` unless `/api/session` or `/api/ping` revives it first (a reload does this). The cookie itself is a browser-session cookie. Restarting the service signs everyone out. On the frontend side, `web/src/lib/presence.js` sends the beacon on `pagehide`, uses a `BroadcastChannel` so other open tabs ping and cancel the goodbye, sends a heartbeat every 60 s, and re-checks on bfcache `pageshow`.
- **Behind a tunnel or reverse proxy:** `client_ip()` uses the **last** `X-Forwarded-For` entry (the one our own proxy appended), and **only** when the request comes from 127.0.0.1 or ::1. Earlier entries, and headers like `CF-Connecting-IP`, can be written by the visitor (Funnel passes them through), and LAN clients could fake any of them. Both cases were verified as spoofing attempts that still got locked out. Use `client_ip()` for anything keyed per visitor. `SessionCookies.get_cookie_secure()` marks the cookie `Secure` (and HSTS is sent) only when `X-Forwarded-Proto: https` arrives from localhost, because the plain-HTTP LAN address must keep working. Run the tunnel with `cloudflared tunnel --url http://127.0.0.1:8080` (waitress listens on IPv4 only, and `localhost` can resolve to ::1). Cloudflare caps request bodies at 100 MB, and the uploader explains a 413.
- **Hidden albums are enforced server-side.** `path_arg()` returns 404 for any hidden path unless `unlocked()`. `unlocked()` checks the session's `hidden_until`, which slides by 15 minutes on each use and is cleared by lock or logout. List endpoints filter separately:
  - `/api/library` never includes hidden items, even when unlocked, so they never reach the timeline, Favorites or search.
  - `/api/albums` leaves out hidden sub-albums unless you're browsing inside a hidden album.
  - `/api/folders` includes hidden albums only when unlocked, and never with `?search=1`.
  - Trash entries are filtered by their original path.
  - Hidden media is sent with `Cache-Control: no-store`.

  Any new endpoint that lists or touches files must follow the same rules.

### API surface

| Route | Purpose |
|---|---|
| `GET /api/session`, `POST /api/login`, `POST /api/logout` | auth (per-IP lockout: 5 tries, then 5 min; resets on restart) |
| `GET /api/ping`, `POST /api/bye` | presence: heartbeat, and the goodbye beacon sent on tab close (CSRF goes in the form body because beacons can't set headers) |
| `GET /api/library` | every item, newest first (`path, name, folder, kind, w, h, date, size, dur, fav, v`) |
| `GET /api/albums?path=` | sub-albums (count + newest cover, recursive) and direct items of one folder |
| `GET /api/folders`, `GET /api/info?path=` | all folder paths (move picker); EXIF details for the info panel |
| `POST /api/upload` (multipart `folder`,`file`), `/api/mkdir`, `/api/rename`, `/api/move`, `/api/delete`, `/api/rmdir`, `/api/favorite` | changes. `delete` and `rmdir` return trash `ids` so the UI can offer Undo. `rmdir` sends each media file inside to trash (so each restores to its old path), then removes folders that are left with only dot-files. Folders holding other files are kept. |
| `GET /api/trash`, `POST /api/trash/restore`, `POST /api/trash/delete` | trash |
| `POST /api/move-album` | move a folder into another folder (refuses to move it into itself; adds a `_1` suffix on name clashes) |
| `GET /api/hidden`, `POST /api/hidden/unlock` / `lock` / `code` / `hide` / `unhide` | hidden albums. `unlock` always answers 200 `{ok}` (a wrong code looks like a normal search), allows 10 checks per IP per 10 minutes, and needs codes of at least 4 characters |
| `GET /t/<path>`, `/m/<path>`, `/d/<path>`, `/tt/<id>` | thumbnail, viewer file (original or converted JPEG), download original, trash thumbnail |
| `GET /g/<path>` | redirects old v1 bookmarks to `/albums/<path>` |
| anything else | `web/dist` asset or `index.html` (SPA fallback; hashed `assets/` are cached immutably) |

`v` on items is an mtime-derived cache-buster appended to `/t/` and `/m/` URLs.

## Frontend architecture (`web/src/`)

- No router library. `lib/router.svelte.js` uses `history`, and the open photo lives in `?photo=<path>`. Opening the viewer pushes a history entry, so Back or Android's back gesture closes it, and moving between photos replaces that entry.
- `lib/state.svelte.js` holds global `$state` (`app.library`, `app.context`, `app.slideshow`, `app.dialog`, toasts), the `favs` and `selection` `SvelteSet`s, and **every action that changes files**. After a change it calls `changed()`, which bumps `app.version` (open views re-fetch) and reloads the library.
- Each view sets `app.context` to the items it shows. `App.svelte` renders one global `Viewer` over `app.slideshow?.items ?? app.context`. `ask({kind:'confirm'|'prompt'|'album'})` returns a promise and is rendered by `Dialog.svelte`.
- Search: `SearchBox.svelte` sits in the top bar (on phones it's an icon that expands). The query is kept in `app.search` and **deliberately not in the URL**, because the secret code is typed there and would otherwise end up in browser history. Pressing Enter calls `tryUnlock()`, and success navigates to `/hidden`. Results are filtered client-side from the library plus `/api/folders?search=1`.
- Album ⋮ menus all come from `lib/albumMenu.js` (rename, move, hide/unhide, share placeholder, delete) and are used by `AlbumCard.svelte` and the album page header. `Menu.svelte` flips left or up to stay on screen and supports `disabled` items with a hint.
- `lib/layout.js` `justify()` produces absolutely positioned blocks: justified rows, day headers, and small days packed side by side. `PhotoGrid.svelte` renders only blocks near the viewport (window scroll) and owns selection (long-press on touch, hover checkbox or Ctrl/Shift-click on desktop) and the timeline scrubber.
- `Viewer.svelte` handles its own pointer gestures: swipe to page, swipe down to close, pinch, double-tap and wheel zoom with pan clamping. It keeps the thumbnail visible until the full image loads, and preloads neighbours.
- Layout breakpoint: at 900 px and up there's a sidebar; below that there's a bottom tab bar, with `--nav-offset` on `:root` so fixed elements clear it. Safe-area insets are respected. Light and dark follow the system setting via CSS variables in `app.css`.
- PWA: `public/manifest.webmanifest` plus Apple meta tags. There's deliberately **no service worker**: it would need HTTPS, and caching private photos on devices is unwanted. Over plain-HTTP LAN, iOS "Add to Home Screen" runs standalone, but Android only creates a shortcut.
- npm dependency versions are pinned exactly. Pick releases that are at least 2 weeks old.

## Production deployment (this Pi)

The app runs as the systemd unit `/etc/systemd/system/gallery.service` (enabled at boot). The previous version is backed up as `gallery.service.bak-2026-11-24`.

```
[Unit]
After=network-online.target mnt-pendrive.mount
Wants=network-online.target mnt-pendrive.mount

[Service]
User=asmithreddy
WorkingDirectory=/home/asmithreddy/projects/youDontWannaSeeThis/private-gallery
Environment="PHOTO_DIR=/mnt/pendrive"
ExecStartPre=/usr/bin/mountpoint -q /mnt/pendrive
ExecStart=/home/asmithreddy/projects/youDontWannaSeeThis/private-gallery/venv/bin/python app.py
Restart=on-failure
RestartSec=10s
```

- It runs straight from this working copy, so a deploy is `cd web && npm run build`, then `sudo systemctl restart gallery`. Frontend-only changes need just the build, because `index.html` is served `no-cache`. Logs: `journalctl -u gallery -f`.
- **Photos are on a USB pendrive**: `/dev/sda1` (exFAT, 58 GB) at `/mnt/pendrive`, mounted from `/etc/fstab` with `uid=1000,gid=1000,umask=000,nofail`. exFAT has no Unix permissions or symlinks and treats names case-insensitively. Upload free-space checks measure the pendrive, and `.trash/` lives on it too.
- `.auth.json`, `.favorites.json` and `.cache/` stay on the SD card in this directory.
- **Mount guard:** fstab mounts the drive with `nofail`, so boot continues without it. The unit pulls in `mnt-pendrive.mount`, and `ExecStartPre=mountpoint -q` refuses to start while it isn't mounted. `Restart=on-failure` retries every 10 s, and each retry re-attempts the mount, so the gallery comes up by itself when the drive appears and never serves the empty SD-card mountpoint. Don't replace this with `RequiresMountsFor=`/`Requires=`: a failed mount then counts as a dependency failure, which systemd never retries.
- **Remote access: Tailscale** (apt repo `pkgs.tailscale.com`, `tailscaled` enabled). The Pi is `asmithpi` / `100.109.208.96` on the tailnet, so `http://asmithpi:8080` is private access for signed-in devices. **Funnel** publishes `https://your-pi.your-tailnet.ts.net` → `http://127.0.0.1:8080`; the setting is saved by `tailscaled` and survives reboots (`sudo tailscale funnel status`). Funnel and serve send `X-Forwarded-For`/`X-Forwarded-Proto` (and `Tailscale-User-*` headers for tailnet users, which the app ignores). waitress therefore runs with `clear_untrusted_proxy_headers=False`, because by default it strips those headers.
- Node 20, ffmpeg, `rawpy` and Tailscale are installed. Rebuild `web/dist` on the Pi after changing anything in `web/`.

## Repo notes

- Gitignored runtime and local data: `venv/`, `.cache/`, `.auth.json`, `.favorites.json`, `.hidden.json`, `photos/`, `web/node_modules/`, `web/dist/`. Never commit them. If `PHOTO_DIR` points inside the repo under another name, add it to `.gitignore` too.
