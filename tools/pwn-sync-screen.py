#!/usr/bin/env python3
"""
pwn-sync-screen.py — draws the LIVE upload progress on the e-ink WHILE pwnagotchi
is stopped (so you see the number grow during the real upload, not just after).

pwn-sync.sh launches this right after it stops pwnagotchi and kills it just
before restarting pwnagotchi. It reads /root/.vslider/sync.json (written live by
pwn-sync.sh) and redraws the Waveshare 2.13" V4 panel on every change.

It is fully optional and defensive: if the e-ink driver can't be found or the
panel can't be opened, it just exits quietly and the upload continues headless
(vslider still replays the final animation after pwnagotchi restarts).

Probe which driver your image has (run once on the device):
    python3 /home/pi/pwn-sync-screen.py --probe

Panel: Waveshare 2.13" V4, 250x122 landscape, rotation 180 (jayofelony image).
Own device / your own networks only.
"""

import json
import os
import signal
import sys
import time

SYNC = "/root/.vslider/sync.json"
ROTATE = 180                       # waveshare_4 on this build is mounted upside-down
# pwnagotchi lives in a venv on the jayofelony image; its driver + PIL are there,
# so re-exec into it if we were started with the system python.
VENV_PY = os.environ.get("PWN_VENV", "/home/pi/.pwn/bin/python3")
_RUN = True


def _ensure_venv():
    try:
        import pwnagotchi  # noqa: F401
        return
    except Exception:
        pass
    try:
        if os.path.exists(VENV_PY) and \
                os.path.realpath(sys.executable) != os.path.realpath(VENV_PY):
            os.execv(VENV_PY, [VENV_PY] + sys.argv)
    except Exception:
        pass


def _stop(*_a):
    global _RUN
    _RUN = False


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


# --- driver discovery --------------------------------------------------------
def load_epd():
    """Return (epd, driver_name). Tries the standalone lib first, then the
    paths pwnagotchi bundles the Waveshare V4 driver under."""
    attempts = []
    candidates = [
        # jayofelony image (confirmed path)
        ("pwnagotchi.ui.hw.libs.waveshare.epaper.v2in13_V4.epd2in13_V4", "EPD"),
        # other layouts / standalone lib, just in case
        ("waveshare_epd.epd2in13_V4", "EPD"),
        ("pwnagotchi.ui.hw.libs.waveshare.v4.epd2in13_V4", "EPD"),
        ("pwnagotchi.ui.hw.libs.waveshare.epd2in13_V4", "EPD"),
    ]
    for path, cls in candidates:
        try:
            mod = __import__(path, fromlist=[cls])
            epd = getattr(mod, cls)()
            return epd, path
        except Exception as e:                      # noqa: BLE001
            attempts.append("%s -> %s" % (path, e))
    raise RuntimeError("no Waveshare V4 EPD driver found:\n  " + "\n  ".join(attempts))


def _font(size):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _tw(drawer, text, font):
    try:
        return drawer.textlength(text, font=font)
    except Exception:
        try:
            b = font.getbbox(text)
            return b[2] - b[0]
        except Exception:
            return len(text) * 7


def _face(total, up):
    if up <= 0:
        return "(T_T)"
    pct = (up / total) if total else 1.0
    if pct < 0.34:
        return "(._.)"
    if pct < 0.67:
        return "(-_-)"
    if pct < 1.0:
        return "(^_^)"
    return "(^o^)"


def _result_face(result, up):
    if result == "ok":
        return "(^o^)"
    if result in ("no_profile", "no_iface"):
        return "(x_x)"
    if result in ("no_net", "offline"):
        return "(T_T)"
    return _face(1, up)


def _bignum(img, box, text, drawer):
    """Stretch a number to fill the box — the big 'liquid-glass' digits."""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    f = _font(64)
    tw = max(1, int(_tw(drawer, text, f)))
    try:
        asc, desc = f.getmetrics()
        th = max(1, asc + desc)
    except Exception:
        th = 48
    tmp = Image.new("1", (tw + 4, th + 2), 255)
    ImageDraw.Draw(tmp).text((2, 0), text, font=f, fill=0)
    m = 2
    tmp = tmp.resize((max(1, bw - 2 * m), max(1, bh - 2 * m)))
    img.paste(tmp, (x0 + m, y0 + m))


def _clip(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def render(W, H, s, history):
    """LEFT: two big stretched numbers (hs / up) that grow. RIGHT: a live status
    log in small English words, so you can see the current step on the panel."""
    from PIL import Image, ImageDraw
    img = Image.new("1", (W, H), 255)         # 1 = white
    d = ImageDraw.Draw(img)
    state = s.get("state", "")
    total = int(s.get("total") or 0)
    up = int(s.get("sent_total") or s.get("up") or 0)
    cur = s.get("cur") or ""
    finished = bool(s.get("finished"))

    f_small = _font(10)               # the status log — small so more fits
    f_hdr = _font(11)
    f_lbl = _font(12)

    # header
    d.rectangle((2, 2, W - 2, 14), fill=0)
    hdr = "wpa-sec sync"
    d.text(((W - _tw(d, hdr, f_hdr)) / 2, 2), hdr, font=f_hdr, fill=255)

    # LEFT: the numbers, shifted left; same big stretched "liquid" digits
    lx0, lx1 = 3, int(W * 0.46)
    d.text((lx0 + 2, 17), "hs", font=f_lbl, fill=0)
    _bignum(img, (lx0, 31, lx1, 61), str(total), d)
    d.text((lx0 + 2, 64), "up", font=f_lbl, fill=0)
    _bignum(img, (lx0, 78, lx1, H - 3), str(up), d)

    # RIGHT: the live status log (the same stages you saw in the terminal)
    rx0 = int(W * 0.49) + 2
    d.line((rx0 - 3, 16, rx0 - 3, H - 2), fill=0)
    lines = list(history)[-8:]
    if not finished and state == "upload":
        live = "up %d/%d" % (up, total)
        if cur:
            live += " " + cur
        lines = lines + [live]
        lines = lines[-8:]
    maxw = W - rx0 - 3
    y = 17
    n = len(lines)
    for i, ln in enumerate(lines):
        pref = "> " if i == n - 1 else "  "
        txt = pref + ln
        while _tw(d, txt, f_small) > maxw and len(txt) > 3:
            ln = ln[:-1]
            txt = pref + ln + "…"
        d.text((rx0, y), txt, font=f_small, fill=0)
        y += 13
        if y > H - 11:
            break

    if ROTATE:
        img = img.rotate(ROTATE)
    return img


def read_sync():
    try:
        with open(SYNC, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def main():
    probe = "--probe" in sys.argv
    _ensure_venv()                      # jump into pwnagotchi's venv if needed
    # the panel may still be releasing from pwnagotchi — retry the open a few times
    epd = name = None
    for _ in range(10):
        try:
            epd, name = load_epd()
            break
        except Exception as e:
            if probe:
                print("open failed:", e)
                return 2
            time.sleep(1)
    if epd is None:
        return 2
    if probe:
        print("driver OK:", name)
    inited = False
    for arg in ((), (0,)):               # V4 is init(); some drivers want init(0)
        try:
            epd.init(*arg)
            inited = True
            break
        except TypeError:
            continue
        except Exception as e:
            if probe:
                print("init failed:", e)
            return 2
    if not inited:
        if probe:
            print("init failed: no working init() signature")
        return 2
    # landscape dimensions (driver reports native portrait 122x250)
    W = max(getattr(epd, "width", 122), getattr(epd, "height", 250))
    H = min(getattr(epd, "width", 122), getattr(epd, "height", 250))

    def show(img, partial):
        try:
            buf = epd.getbuffer(img)
        except Exception:
            try:                          # driver wants the other orientation
                buf = epd.getbuffer(img.rotate(90, expand=True))
            except Exception:
                return
        for meth in (("displayPartial",) if partial else ()) + ("display",):
            fn = getattr(epd, meth, None)
            if fn:
                try:
                    fn(buf)
                    return
                except Exception:
                    continue

    if probe:
        hist = ["stopping pwnagotchi", "radio ready", "online: Xiaomi_67"]
        show(render(W, H, {"state": "upload", "total": 7, "up": 3,
                           "cur": "TestNet", "stage": "uploading"}, hist), False)
        print("drew a test frame (3/7) with a status log. Looks right? then it's wired.")
        try:
            epd.sleep()
        except Exception:
            pass
        return 0

    history = []

    def push(msg):
        if msg and (not history or history[-1] != msg):
            history.append(msg)
            del history[:-12]

    last_key = None
    base_done = False
    try:
        while _RUN:
            s = read_sync()
            push(s.get("stage") or s.get("state") or "")
            key = (s.get("stage"), s.get("state"),
                   s.get("sent_total") or s.get("up"),
                   s.get("cur"), s.get("finished"), s.get("result"))
            if key != last_key:
                img = render(W, H, s, history)
                show(img, base_done)          # full first, partial after
                base_done = True
                last_key = key
            if s.get("finished"):
                # hold the final frame until pwnagotchi restarts (we get killed)
                for _ in range(40):
                    if not _RUN:
                        break
                    time.sleep(0.25)
                break
            time.sleep(0.4)
    finally:
        try:
            epd.sleep()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
