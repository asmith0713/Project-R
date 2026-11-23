"""Reading photo/video metadata and making browser-friendly JPEGs."""
import hashlib, io, json, os, subprocess, threading
from datetime import datetime, timezone

from PIL import Image, ImageOps

from .config import CACHE, RAW, THUMB_SIDE, VIEW_SIDE

try:  # lets iPhone HEIC photos open
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

try:  # lets DNG (RAW) photos open
    import rawpy
except ImportError:
    rawpy = None

EXIF_IFD, GPS_IFD = 0x8769, 0x8825
ROTATED = {5, 6, 7, 8}  # EXIF orientations that swap width and height


class Unreadable(Exception):
    pass


# ---------- metadata ----------

def _exif_date(s):
    try:
        return datetime.strptime(str(s).strip()[:19], "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _image_meta(p):
    with Image.open(p) as im:
        w, h = im.size
        ex = im.getexif()
        sub = ex.get_ifd(EXIF_IFD)
        when = _exif_date(sub.get(36867) or sub.get(36868) or ex.get(306))
        if ex.get(274) in ROTATED:
            w, h = h, w
    if p.suffix.lower() in RAW and rawpy:
        with rawpy.imread(str(p)) as r:  # PIL sees the preview IFD; trust LibRaw for size
            w, h = r.sizes.width, r.sizes.height
            if r.sizes.flip in ROTATED:
                w, h = h, w
    return w, h, when, None


def _video_meta(p):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-print_format", "json",
         "-show_entries", "stream=width,height:stream_side_data=rotation:stream_tags=rotate"
         ":format=duration:format_tags=creation_time", str(p)],
        capture_output=True, text=True, timeout=30)
    data = json.loads(out.stdout or "{}")
    s = (data.get("streams") or [{}])[0]
    w, h = s.get("width") or 0, s.get("height") or 0
    rot = s.get("tags", {}).get("rotate") or next(
        (d.get("rotation") for d in s.get("side_data_list", []) if "rotation" in d), 0)
    if abs(int(float(rot or 0))) % 180 == 90:
        w, h = h, w
    fmt = data.get("format", {})
    when = None
    ct = fmt.get("tags", {}).get("creation_time")
    if ct:
        try:  # stored in UTC; show it in the Pi's local time like photo EXIF dates
            when = datetime.fromisoformat(ct.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    dur = float(fmt.get("duration") or 0) or None
    return w, h, when, dur


def read_meta(p, k, st):
    """Return the index entry for one file. Never raises: unreadable files still get
    listed (with their file date and a square placeholder shape)."""
    w = h = 0
    when = dur = None
    try:
        w, h, when, dur = (_image_meta if k == "image" else _video_meta)(p)
    except Exception:
        pass
    if not when or when.year < 1990:
        when = datetime.fromtimestamp(st.st_mtime)
    return {"kind": k, "w": w or 1, "h": h or 1, "date": when.isoformat(timespec="seconds"),
            "size": st.st_size, "mtime": st.st_mtime_ns, "dur": dur}


def details(p, k):
    """Extra info for the viewer's info panel (read on demand, not indexed)."""
    info = {}
    if k == "video":
        return info
    try:
        with Image.open(p) as im:
            ex = im.getexif()
            sub = ex.get_ifd(EXIF_IFD)
            gps = ex.get_ifd(GPS_IFD)
    except Exception:
        return info
    make, model = (ex.get(271) or "").strip(), (ex.get(272) or "").strip()
    if model:
        info["camera"] = model if model.startswith(make) else f"{make} {model}".strip()
    if sub.get(42036):
        info["lens"] = str(sub[42036]).strip()
    if sub.get(33437):
        info["aperture"] = f"ƒ/{float(sub[33437]):.1f}"
    if sub.get(33434):
        t = float(sub[33434])
        info["shutter"] = f"1/{round(1 / t)} s" if 0 < t < 1 else f"{t:g} s"
    if sub.get(34855):
        iso = sub[34855]
        info["iso"] = f"ISO {iso[0] if isinstance(iso, tuple) else iso}"
    if sub.get(37386):
        info["focal"] = f"{float(sub[37386]):.0f} mm"
    try:
        def deg(v, ref):
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return -d if ref in ("S", "W") else d
        if gps.get(2) and gps.get(4):
            info["gps"] = [round(deg(gps[2], gps.get(1)), 6), round(deg(gps[4], gps.get(3)), 6)]
    except (TypeError, ValueError, ZeroDivisionError, IndexError):
        pass
    return info


# ---------- JPEG renditions ----------

_locks, _locks_guard = {}, threading.Lock()
# A 48 MP HEIC needs ~150 MB to decode; cap parallel work so a burst of requests
# (grid scrolling + viewer preloading) can't exhaust the Pi's memory.
_slots = {"small": threading.BoundedSemaphore(3), "large": threading.BoundedSemaphore(2)}


def _lock(key):
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _open_raw(p):
    """The full-size JPEG preview embedded in a DNG (fast), else a real decode (slow)."""
    with rawpy.imread(str(p)) as r:
        flip = r.sizes.flip
        try:
            th = r.extract_thumb()
            if th.format == rawpy.ThumbFormat.JPEG:
                im = ImageOps.exif_transpose(Image.open(io.BytesIO(th.data)))
                im.load()
            else:
                im = Image.fromarray(th.data)
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            return Image.fromarray(r.postprocess(use_camera_wb=True, half_size=True))
    # Previews are usually stored unrotated; turn them if the shape disagrees with LibRaw.
    if flip in ROTATED and im.width > im.height:
        im = im.transpose(Image.Transpose.ROTATE_90 if flip == 5 else Image.Transpose.ROTATE_270)
    return im


def _render_image(p, side, out):
    if p.suffix.lower() in RAW and rawpy:
        im = _open_raw(p)
    else:
        with Image.open(p) as src:
            if src.format == "JPEG":
                src.draft("RGB", (side, side))  # decode at reduced scale: faster, less memory
            im = ImageOps.exif_transpose(src)  # returns a loaded copy, so src can close
    im.thumbnail((side, side), Image.Resampling.LANCZOS)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (24, 24, 27))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im.convert("RGB").save(out, "JPEG", quality=82 if side <= THUMB_SIDE else 88,
                           optimize=True, progressive=True)


def _render_video(p, side, out):
    for at in ("1", "0"):  # 1 s in avoids black first frames; fall back for very short clips
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", at, "-i", str(p), "-frames:v", "1",
             "-vf", f"scale='min({side},iw)':'min({side},ih)':force_original_aspect_ratio=decrease",
             "-q:v", "4", "-f", "image2", str(out)],
            capture_output=True, timeout=60)
        if r.returncode == 0 and out.exists() and out.stat().st_size:
            return
    raise Unreadable(p)


def rendition(p, k, side):
    """Path to a cached JPEG of `p` no bigger than `side` px. Cache key includes mtime,
    so edited/replaced files get fresh renditions automatically."""
    st = p.stat()
    key = hashlib.sha1(f"{p}|{st.st_mtime_ns}|{side}".encode()).hexdigest()
    out = CACHE / key[:2] / f"{key}.jpg"
    if out.exists():
        return out
    with _lock(key):
        if out.exists():
            return out
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with _slots["small" if side <= THUMB_SIDE else "large"]:
                (_render_image if k == "image" else _render_video)(p, side, tmp)
            os.replace(tmp, out)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise Unreadable(p) from e
    with _locks_guard:
        _locks.pop(key, None)
    return out


def thumb(p, k):
    return rendition(p, k, THUMB_SIDE)


def view(p):
    return rendition(p, "image", VIEW_SIDE)
