# Version Diary

A running log of what changed in the gallery, how it was done, and **why**. The git history shows *what* changed; this diary keeps the reasoning, so later changes don't undo decisions that were made on purpose.

Newest entries go at the top. Each entry has:
- **What:** the visible result
- **How:** the approach and key pieces
- **Why:** the reasons and trade-offs
- **Open:** anything left unfinished

---

## v2.1: Hidden albums, search, full album menu (2026-11-24, uncommitted)

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
- If the pendrive isn't mounted at boot, the service serves an empty folder and uploads land on the SD card (`nofail` in fstab, and no `RequiresMountsFor=` in the unit). It's a one-line fix in the unit that hasn't been applied yet.
- The old v1 thumbnail files (~93 MB) are still in `.cache/` and unused. They're safe to delete.
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
