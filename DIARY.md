# Version Diary

A running log of what changed in the gallery, how it was done, and **why**. The git history shows *what* changed; this diary keeps the reasoning, so later changes don't undo decisions that were made on purpose.

Newest entries go at the top. Each entry has:
- **What:** the visible result
- **How:** the approach and key pieces
- **Why:** the reasons and trade-offs
- **Open:** anything left unfinished

---

## v2.4: Free remote access with Tailscale (2026-11-24, `471c7da`)

### What
- **Private access from anywhere:** `http://asmithpi:8080`, only for your own devices signed in to Tailscale.
- **Public link for office computers:** `https://your-pi.your-tailnet.ts.net` (Tailscale Funnel). It opens in any browser and still needs the secret key.
- Both cost ₹0, need no domain, and survive reboots.

### How
- Installed Tailscale from its official apt repo, signed in as host `asmithpi`, and enabled Funnel with `tailscale funnel --bg 8080`.
- Inspected the headers Funnel forwards. It sends `X-Forwarded-For` and `X-Forwarded-Proto: https` (plus `Tailscale-User-*` for tailnet users).
- `app.py`: waitress now uses `clear_untrusted_proxy_headers=False`. By default it stripped those headers, so the app saw neither HTTPS nor the visitor's address behind Funnel.
- `client_ip()` now uses only the **last** `X-Forwarded-For` entry and no longer reads `CF-Connecting-IP`.

### Why
- **Tailscale over a Cloudflare named tunnel:** the user asked for free or cheap (INR). A named tunnel needs a paid domain, while Tailscale is free and gives a permanent address.
- **Both private and public:** the private address keeps the gallery off the internet for everyday use on the phone. Funnel covers office PCs where the app can't be installed.
- **The last `X-Forwarded-For` entry:** Funnel forwards whatever headers the visitor sends. Reading `CF-Connecting-IP` or the first `X-Forwarded-For` entry let a guesser rotate fake addresses and never get locked out. The last entry is the one our own proxy added. A live test through Funnel with faked headers was still locked out after 5 tries.

### Privacy on office wifi (answered)
- **Personal device:** traffic is encrypted. The network can see only that you connected to `ts.net`, and how much data moved.
- **Office-managed PC:** company TLS inspection or monitoring software could see everything. Use a private window there, and rely on lock-on-close.
- Hidden albums are never cached by the browser.

### Open
- The public link exposes the sign-in page to the internet, and the 6-character key minimum is weak for that. Set a longer key.
- Uploads through Funnel weren't tested with very large files.
- To turn the public link off: `sudo tailscale funnel --https=443 off` (private access keeps working).

---

## v2.3: Works behind Cloudflare Tunnel (2026-11-24, `471c7da`)

### What
The gallery can be opened from outside the home through `cloudflared tunnel --url http://127.0.0.1:8080`. The first attempt used `--url localhost:80`, which failed: nothing listens on 80, and `localhost` resolved to `::1` while waitress listens on IPv4 only.

### How
- `client_ip()`: when a request comes from 127.0.0.1 or ::1 (cloudflared), take the visitor's address from `CF-Connecting-IP` / `X-Forwarded-For`. The login lockout and the hidden-code throttle use it.
- `SessionCookies`: marks the sign-in cookie `Secure`, and HSTS is sent, when `X-Forwarded-Proto: https` comes from localhost.
- The uploader explains Cloudflare's 413 (100 MB per request on free plans). The sign-in page no longer says "only works on your home wifi".

### Why
- **Per-visitor lockout:** through the tunnel every visitor looked like 127.0.0.1. One stranger's five wrong guesses would have locked out everyone for 5 minutes, and the hidden-code throttle would have been shared too.
- **Forwarded headers are trusted only from localhost:** otherwise anyone on the LAN could send a fake `CF-Connecting-IP` with every guess and never be locked out.
- **Secure only for HTTPS requests, not always on:** a `Secure` cookie would never be set on the plain-HTTP home address, breaking sign-in on wifi.

### Verified
With the test client: a stranger is locked out after 5 tries while another visitor through the tunnel still signs in, a spoofed header from a LAN address is ignored, the tunnel cookie is `Secure`, and the wifi cookie isn't and still works. The live service restarted and is healthy.

### Open
- The quick tunnel is temporary (random URL, stops with the terminal). A permanent setup would need a named tunnel (Cloudflare account) running as a systemd service.
- Now that the sign-in page is on the internet, the 6-character minimum key length is weak. Consider a longer key, or Cloudflare Access in front.

---

## v2.2: Locks when the tab or browser closes (2026-11-24, `471c7da`)

### What
- **What locks the gallery:**
  - closing its tab or the whole browser (about 8 s later)
  - 10 minutes without contact, for example a phone asleep or a browser killed without warning
  - 12 hours at most
- **What doesn't:** reloading, or closing one of several gallery tabs.
- Old v1 thumbnails (1,560 files, 92 MB) and two indexes left over from test servers were deleted from `.cache/`.

### How
- **Server-side sessions:** login creates a random `sid` stored in the cookie and in an in-memory `active` table (created / last seen / closing). `need_login` checks it through `session_alive()`. Lock and logout delete it, so a copied cookie stops working.
- **Goodbye beacon:** on `pagehide` the page sends `navigator.sendBeacon('/api/bye')`, which marks the sign-in as "closing". It ends after 8 s unless the page checks in through `/api/session` or `/api/ping`.
- **Other tabs:** a `BroadcastChannel` message makes them ping 1 s and 4 s later, which cancels the goodbye.
- **Heartbeat:** every 60 s, plus a ping when a tab becomes visible again and a re-check on bfcache restore.
- The cookie is now a browser-session cookie (`session.permanent` was removed).

### Why
- **Server-side state was required.** Flask's default session is a signed cookie the server can't revoke, so "locked" previously only meant "the browser forgot the cookie". Now the server decides.
- **A grace period instead of logging out on `pagehide`:** browsers fire the same event for closing, reloading and pull-to-refresh, and there's no reliable way to tell them apart. A reload checks back in within about a second, and a closed tab never does.
- **Not `sessionStorage`, and not only a session cookie:** Chrome's "continue where you left off" and mobile tab restore bring both back, so they wouldn't actually lock anything.
- **The idle backstop:** mobile browsers often send no event when swiped away or killed. Ten minutes keeps a long slideshow on a visible screen working (the heartbeat keeps it alive) while a forgotten phone locks soon.
- **Kept in memory, not on disk:** simpler, and a restart signing everyone out is acceptable, even desirable, for a private gallery.

### Verified
- In headless Chromium: a reload stays signed in, closing one of two tabs leaves the other signed in, closing the last tab locks it and reopening shows the sign-in screen, Lock is immediate, and a copied cookie fails after Lock.
- With the test client: an 11-minute idle gap gives 401, and so does a 13-hour-old sign-in.

### Open
- When a phone browser is killed, locking falls back to the 10-minute idle limit (there's no close event to catch).
- An open tab in the background keeps the sign-in alive, as intended, since the tab is still open.

---

## v2.1.1: Service waits for the pendrive (2026-11-24, `19151de`)

### What
The gallery no longer starts when the USB pendrive isn't mounted. It keeps retrying every 10 seconds and starts as soon as the drive is there.

### How
In `/etc/systemd/system/gallery.service` (the old version is backed up as `gallery.service.bak-2026-11-24`):
- `Wants=` and `After=mnt-pendrive.mount` pull in the fstab mount and order the start after it.
- `ExecStartPre=/usr/bin/mountpoint -q /mnt/pendrive` refuses to start unless the drive is really mounted.
- `Restart=on-failure` retries, now every 10 s instead of 5, to keep the logs quieter while the drive is missing. Each retry re-attempts the mount.

### Why
- fstab uses `nofail` (so the Pi still boots without the drive), and the old unit didn't care whether the drive was mounted. Without the drive, the gallery served the empty `/mnt/pendrive` folder on the SD card, and uploads were written there.
- **Why not `RequiresMountsFor=`:** with a hard dependency, a failed mount marks the start as a "dependency" failure, and systemd never retries those, so the gallery would stay down until someone restarted it. The `mountpoint` check makes it a normal failure that `Restart=` keeps retrying.

### Verified
- `systemd-analyze verify` passes, the live service restarted and is healthy, and the mount appears in its `After=`/`Wants=`.
- A temporary test unit with the same guard on a folder that isn't a mount was refused (exit 32) and kept being retried.

### Open
- If the drive is unplugged while the gallery is running, it isn't detected (the files just fail to load). A real-world unplug or replug test hasn't been done.

---

## v2.1: Hidden albums, search, full album menu (2026-11-24, `41ca19f`)

### What
- **Hidden albums**, modelled on WhatsApp's Chat Lock: an album can be hidden behind a secret code. It vanishes from Photos, Albums, Favorites, search, slideshows and Trash. Typing the code into the search box and pressing Enter reveals a **Hidden albums** page.
- **Search** by file name, album name, month or year.
- **Album ⋮ menu everywhere** (on every album cover and in the album header): Rename, **Move into album…** (folders inside folders), Hide/Unhide, **Delete** (now works for albums that still have photos, with Undo), and **Share** (shown as "Coming soon").

### How
- `Hidden` store in `gallery/store.py` (`.hidden.json`: a code hash plus hidden folder paths). It's kept up to date when albums are renamed, moved or deleted.
- **Enforced on the server.** `path_arg()` returns 404 for hidden paths unless the session is unlocked, and every list endpoint filters them out. A locked hidden album is indistinguishable from one that doesn't exist.
- Unlocking sets `session["hidden_until"]`, which slides 15 minutes with use and is cleared by "Hide again", Lock or logout.
- `POST /api/move-album` moves a whole folder and refuses to put it inside itself. `rmdir` now trashes each photo individually, so Undo and restore put every file back in its original sub-folder.
- Frontend: `SearchBox`, `Search` and `Hidden` views, plus `AlbumCard` and `lib/albumMenu.js`, so cards and headers share one menu.

### Why
- **Search box as the way in (not a visible "Hidden" button):** nobody browsing the gallery can tell that hidden albums exist. This matches the WhatsApp behaviour that was asked for.
- **A separate code from the login key:** the family shares the login key, and the hidden code is personal.
- **Server-side checks, not just hiding in the UI:** URLs, thumbnails, the move picker and Trash would otherwise leak hidden photos.
- **The search query is never put in the URL:** the code is typed there, and URLs end up in browser history and address-bar suggestions.
- **A wrong code returns 200 `{ok:false}`:** a failed guess looks exactly like a normal search. There's a throttle instead of a lockout (10 checks per 10 minutes per device), so ordinary searching never locks anyone out, while guessing a 4+ character code stays impractical.
- **Hidden photos never appear in the timeline, even when unlocked:** they're reachable only through the Hidden page, like locked chats living only in the locked folder.
- **Hidden media is sent with `Cache-Control: no-store`,** so no copies are left in the browser cache.
- **Only someone who knows the code can hide an album** (the first person creates it). Otherwise a family member could hide another person's album and lock them out.
- **Delete with contents trashes files one by one** (no folder-level trash), so restore works per file and other files like documents are never removed.

### Verified
- API tests: every route refuses hidden paths while locked (album, thumbnail, info, upload, move, rename, folder list, trash), unlock and throttle work, and hidden status follows a renamed album.
- Browser test on a phone-sized screen with a generated library: all 17 checks pass. Covers hiding from a card menu, the album disappearing, search showing nothing, a wrong code behaving like a search, the right code opening the Hidden page, the code never reaching the URL, "Hide again", moving an album into another, delete with contents, and Undo.

### Open
- Sharing albums (the menu item is a placeholder).
- Hidden albums are hidden from the web app only. Anyone with SSH or the physical drive can see the folders.
- The code-check throttle resets when the service restarts (same as the login lockout).

---

## v2.0: Svelte frontend, Flask JSON API (2026-11-24, `a4fd868`)

### Goal
Make the gallery look and feel like a modern gallery app (Google Photos-like), fit every screen we use daily (phone, tablet, laptop, TV), and add the management features that were missing.

### Decision: keep Python for the backend, rewrite only the frontend
- **What:** the server stays Flask (now a JSON API), and the pages are rebuilt in Svelte.
- **Why:**
  - About 700 of ~1,200 files on the pendrive are iPhone **HEIC**. `pillow-heif` decodes them in Python. Node's standard image library (`sharp`) can't decode HEIC without a custom libvips build, so switching languages would have put most of the library at risk.
  - The look-and-feel goal is all frontend work. Rewriting the backend would add nothing visible.
  - The v1 backend already had working path safety, login lockout, CSRF and uploads. Rewriting those invites new security bugs.
  - It keeps `.auth.json` (same password-hash format) and `app.py` as the entry point, so **the systemd unit didn't need any changes**.

### Decision: Svelte 5 + Vite for the frontend
- **Why:** it produces small bundles (about 40 KB of gzipped JS), which suits a Pi serving phones over wifi. Vite builds to static files that Flask serves, so no Node process runs in production. Node is only needed to build.
- Dependency versions are pinned exactly to releases at least 2 weeks old. At install time the newest Svelte (5.59.1) was 4 days old, so 5.57.3 was used.

### Layout: Google Photos-style timeline
- **What:** justified rows (each row fills the width and keeps each photo's real shape), grouped under day headers, with a year/month scrubber on the right.
- **How:** `web/src/lib/layout.js` computes absolute positions for every tile and header. `PhotoGrid.svelte` renders only the blocks near the screen (virtualization), so thousands of photos stay smooth.
- **Why the change after the first version:** the first version gave every day its own row, which left big empty gaps on days with one or two photos. Days that fit in one row are now **packed side by side**, which is what Google Photos and Immich do.
- **Why window scrolling (not an inner scroll box):** mobile browsers hide the address bar and handle momentum scrolling properly only for the page itself.

### Viewer
- **What:** swipe to page, swipe down to close, pinch, double-tap or scroll-wheel zoom, an info panel, slideshow, and keyboard shortcuts.
- **How:** custom pointer-event gestures in `Viewer.svelte`. The open photo is stored in the URL as `?photo=<path>`.
- **Why the URL:** Back (and Android's back gesture) then closes the viewer instead of leaving the site, and a refresh reopens the same photo.
- **Why the thumbnail shows first:** large HEICs need converting (up to ~2.5 s for 48 MP), so the cached thumbnail appears instantly and the full image fades in. Neighbouring photos are preloaded.

### New features and why
| Feature | Why / how |
|---|---|
| Favorites | Quick access to the best photos. Stored in `.favorites.json` and kept up to date when files are moved or renamed. |
| Trash (30 days) + Undo | Deleting from a phone is easy to do by accident. Files move to a hidden `.trash/` on the same drive, so it's an instant rename, not a copy. |
| Move / rename / albums | Organising used to require SSH. Albums are just folders, so rsync and the drive layout keep working. |
| Multi-select | Long-press on touch, hover checkbox or Shift-click on desktop, matching what people expect from phone gallery apps. |
| DNG (RAW) | 27 DNGs were hidden in v1. The embedded full-size JPEG preview (via `rawpy`) loads in 0.14 s, against 1.7 s for a full decode. |
| Video thumbnails | Real poster frames from `ffmpeg`. v1 made the browser load the start of every video in the grid. |
| Library index | Dates come from EXIF/ffprobe, not file times (exFAT copy times are unreliable). Cached in `.cache/library-<hash>.json` because a full scan takes ~60 s. Later scans only read new or changed files. |
| PWA manifest | "Add to Home Screen". There's **no service worker on purpose**: it needs HTTPS, and caching private photos on devices isn't wanted. |
| `app.py warm` | Pre-builds thumbnails after a big rsync so browsing is instant. |

### Problems found while testing, and fixes
1. **Viewer stayed black on real photos.** Several 48 MP HEIC conversions ran at once (viewer + preloads) and starved the server. Fixed with semaphores in `media.py` (3 small and 2 large jobs at a time) and reduced-size JPEG decoding (`draft`).
2. **Taps near a thumbnail's corner selected it instead of opening it.** The selection checkbox was invisible on phones but still clickable. It now accepts taps only when it's visible.
3. **Large uploads could exhaust RAM.** `/tmp` on Raspberry Pi OS (Debian 13) is RAM-backed, and waitress plus Flask buffer the upload body there twice, so a 2 GB video could fill memory. This was already true in v1. Temp files now go to `PHOTO_DIR/.tmp` on the pendrive. Verified with a 300 MB upload: 0 MB added to `/tmp`.
4. **Test and live servers overwrote each other's index.** The index file is now named per photo folder.
5. **Album covers stayed invisible.** A CSS specificity clash meant the fade-in class never won. Fixed in Albums, Trash and the grid.

### How it was verified
- Backend: Flask test client against the real library (read-only) and a temporary folder for every file-changing operation, including path traversal, hidden files, bad names and the CSRF check.
- Frontend: a headless Chromium (Playwright, kept outside the project) driving phone, tablet, landscape and desktop sizes, with real touch events for swipe, pinch and long-press. Visual checks used a **generated placeholder library**, not personal photos.

### Setup changes
- Installed with apt: `nodejs` (20.19), `npm`, `ffmpeg`. Installed in the venv: `rawpy`.
- New gitignored local files: `.favorites.json`, `web/node_modules/`, `web/dist/`.
- Deploy: `cd web && npm run build`, then `sudo systemctl restart gallery` (the restart is only needed for Python changes).

### Open
- ~~If the pendrive isn't mounted at boot, the service serves an empty folder and uploads land on the SD card.~~ Fixed in v2.1.1.
- ~~The old v1 thumbnail files (~93 MB) are still in `.cache/`.~~ Deleted in v2.2.
- Android can't install it as a full app without HTTPS. Options for later: Tailscale HTTPS, or a local certificate.
- The login lockout counter still resets on restart (same as v1).

---

## v1.0: Initial version (2026-11-08, `ce10948`)

### What
A single-file Flask app (`app.py`) for the Raspberry Pi: folder browsing as a grid, a full-screen viewer, HEIC support, a shuffle slideshow, uploads from the phone, and folder creation, all behind one secret key.

### How
- Flask + waitress. HTML, CSS and JS were inline strings rendered with `render_template_string`.
- Thumbnails and HEIC→JPEG copies cached in `.cache/`.
- Password hash plus session secret in `.auth.json`, created by `python3 app.py setpass`.
- Runs as `gallery.service` with `PHOTO_DIR=/mnt/pendrive` (a 58 GB exFAT USB drive).

### Why
- One file and few dependencies made it easy to copy to the Pi and understand.
- LAN-only with a shared key: the threat model is people at home, not the internet.

### Known limits that led to v2
- Plain folder grid with square crops, so photos lost their shape and there was no timeline.
- No delete, move, rename or favorites, and no RAW support or video thumbnails.
- `.gitignore` patterns (`./venv`) didn't match, so `.auth.json` could have been committed. Fixed before v2.
