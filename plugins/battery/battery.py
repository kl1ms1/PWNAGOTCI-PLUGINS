"""
battery — iPhone-style battery indicator for pwnagotchi + UPS Lite.

Reads the UPS Lite fuel gauge (MAX17040, I2C 0x36) and draws a small battery
icon with the percentage in the corner of the e-ink (moving `uptime` aside to
make room). When you plug in USB it detects charging — by voltage / a rising
charge level, NO soldering needed (variant A) — and plays a full-screen
"⚡ USB подключён" animation for a few seconds.

Config (/etc/pwnagotchi/config.toml):
  main.plugins.battery.enabled      = true
  main.plugins.battery.i2c_bus      = 1        # Pi I2C bus
  main.plugins.battery.address      = 0x36     # MAX17040 (UPS Lite)
  main.plugins.battery.charge_volts = 4.15     # >= this volts => treat as charging
  main.plugins.battery.anim_seconds = 4        # full-screen "plugged in" animation
  main.plugins.battery.x            = 0        # icon top-left X (0 = auto, top-right)
  main.plugins.battery.y            = 0        # icon top-left Y
  main.plugins.battery.uptime_shift = 46       # move `uptime` this many px left
  main.plugins.battery.low_pct      = 15       # blink when below this

Own device only.
"""

import logging
import time
from collections import deque

import pwnagotchi.plugins as plugins

try:
    from pwnagotchi.ui.components import Widget as _Widget
except Exception:
    _Widget = object


class _BatWidget(_Widget):
    """Full-canvas widget: the plugin decides what to draw (corner icon or
    the full-screen charging animation)."""

    def __init__(self, plugin):
        try:
            super().__init__((0, 0))
        except Exception:
            pass
        self.xy = (0, 0)
        self._p = plugin

    def draw(self, canvas, drawer):
        try:
            self._p._draw(canvas, drawer)
        except Exception:
            pass


class Battery(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "iPhone-style battery % + icon (UPS Lite / MAX17040) with a charging animation."

    def __init__(self):
        self._bus = None
        self._i2c_bus = 1
        self._addr = 0x36
        self._charge_volts = 4.15
        self._anim_seconds = 4
        self._x = 0
        self._y = 0
        self._uptime_shift = 46
        self._low_pct = 15
        # live state
        self._pct = None
        self._volts = None
        self._charging = False
        self._hist = deque(maxlen=12)     # (t, pct) for the rising-charge check
        self._last_read = 0.0
        self._anim_until = 0.0            # full-screen animation deadline
        self._was_charging = False
        self._added = False
        # fonts (resolved on first draw)
        self._f_small = None
        self._f_big = None

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._i2c_bus = int(o.get("i2c_bus", self._i2c_bus))
        self._addr = int(o.get("address", self._addr))
        self._charge_volts = float(o.get("charge_volts", self._charge_volts))
        self._anim_seconds = int(o.get("anim_seconds", self._anim_seconds))
        self._x = int(o.get("x", 0))
        self._y = int(o.get("y", 0))
        self._uptime_shift = int(o.get("uptime_shift", self._uptime_shift))
        self._low_pct = int(o.get("low_pct", self._low_pct))
        logging.info("[battery] loaded (i2c bus %d, addr 0x%02x)", self._i2c_bus, self._addr)

    # --- fuel gauge (MAX17040 on UPS Lite) --------------------------------
    def _open_bus(self):
        if self._bus is not None:
            return self._bus
        for mod in ("smbus2", "smbus"):
            try:
                m = __import__(mod)
                self._bus = m.SMBus(self._i2c_bus)
                return self._bus
            except Exception:
                continue
        return None

    def _read_word_swapped(self, reg):
        bus = self._open_bus()
        if bus is None:
            return None
        try:
            import struct
            raw = bus.read_word_data(self._addr, reg)
            return struct.unpack("<H", struct.pack(">H", raw))[0]
        except Exception:
            return None

    def _read_voltage(self):
        w = self._read_word_swapped(0x02)      # VCELL
        if w is None:
            return None
        return round(w * 1.25 / 1000.0 / 16.0, 3)

    def _read_capacity(self):
        w = self._read_word_swapped(0x04)      # SOC
        if w is None:
            return None
        return max(0.0, min(100.0, round(w / 256.0, 1)))

    def _sample(self):
        """Read the gauge (throttled) and update charging state (variant A)."""
        now = time.time()
        if now - self._last_read < 5 and self._pct is not None:
            return
        self._last_read = now
        v = self._read_voltage()
        c = self._read_capacity()
        if c is None and v is None:
            return                              # no HAT / no I2C — stay blank
        if c is not None:
            self._pct = c
            self._hist.append((now, c))
        if v is not None:
            self._volts = v
        # charging if the voltage is high OR the charge level is clearly rising
        rising = False
        if len(self._hist) >= 3:
            old = self._hist[0][1]
            rising = (self._pct - old) >= 1.0
        charging = (self._volts is not None and self._volts >= self._charge_volts) or rising
        # rising edge -> kick off the full-screen "plugged in" animation
        if charging and not self._was_charging:
            self._anim_until = now + self._anim_seconds
        self._was_charging = charging
        self._charging = charging

    # --- UI ----------------------------------------------------------------
    def on_ui_setup(self, ui):
        try:
            ui.add_element("bat", _BatWidget(self))
            self._added = True
        except Exception:
            logging.debug("[battery] could not add widget")
        # move `uptime` to the left to free the top-right corner for the icon
        try:
            st = getattr(getattr(ui, "_state", None), "_state", None)
            el = st.get("uptime") if isinstance(st, dict) else None
            if el is not None and getattr(el, "xy", None) and self._uptime_shift:
                x, y = el.xy
                el.xy = (max(0, x - self._uptime_shift), y)
        except Exception:
            pass

    def on_ui_update(self, ui):
        if not self._added:
            return
        self._sample()
        # while the charging animation runs, make sure our widget draws LAST
        if time.time() < self._anim_until:
            try:
                st = getattr(getattr(ui, "_state", None), "_state", None)
                if isinstance(st, dict) and "bat" in st:
                    st["bat"] = st.pop("bat")
            except Exception:
                pass

    def on_unload(self, ui):
        try:
            ui.remove_element("bat")
        except Exception:
            pass
        try:
            if self._bus is not None:
                self._bus.close()
        except Exception:
            pass

    # --- drawing -----------------------------------------------------------
    def _fonts(self):
        if self._f_small is not None:
            return
        try:
            import pwnagotchi.ui.fonts as fonts
            self._f_small = getattr(fonts, "Small", None)
            self._f_big = (getattr(fonts, "Huge", None)
                           or getattr(fonts, "Bold", None) or self._f_small)
        except Exception:
            pass

    @staticmethod
    def _tw(drawer, text, font):
        try:
            return drawer.textlength(text, font=font)
        except Exception:
            try:
                b = font.getbbox(text)
                return b[2] - b[0]
            except Exception:
                return len(text) * 6

    def _draw(self, canvas, drawer):
        self._fonts()
        if self._f_small is None:
            return
        try:
            W, H = canvas.size
        except Exception:
            W, H = 250, 122
        if time.time() < self._anim_until:
            self._draw_charge_anim(canvas, drawer, W, H)
        else:
            self._draw_corner(drawer, W, H)

    # small iPhone-style icon + % in the corner
    def _draw_corner(self, drawer, W, H):
        if self._pct is None:
            return
        pct = int(round(self._pct))
        bw, bh = 22, 11
        x = self._x if self._x else (W - bw - 5)
        y = self._y if self._y else 1
        # % text to the left of the icon
        txt = "%d%%" % pct
        tw = self._tw(drawer, txt, self._f_small)
        drawer.text((x - tw - 3, y), txt, font=self._f_small, fill=0x00)
        self._bat_shape(drawer, x, y, bw, bh, pct, self._charging)

    def _bat_shape(self, drawer, x, y, bw, bh, pct, charging):
        # body + nub (iPhone look)
        drawer.rectangle((x, y, x + bw, y + bh), outline=0x00, fill=0xFF)
        drawer.rectangle((x + bw + 1, y + 3, x + bw + 2, y + bh - 3), fill=0x00)
        # low battery blinks (skip the fill on odd seconds)
        if pct <= self._low_pct and int(time.time()) % 2 == 0 and not charging:
            return
        fillw = int((bw - 3) * max(0, min(100, pct)) / 100.0)
        if fillw > 0:
            drawer.rectangle((x + 2, y + 2, x + 2 + fillw, y + bh - 2), fill=0x00)
        if charging:
            self._bolt(drawer, x + bw / 2 - 2, y + 1, bh)

    @staticmethod
    def _bolt(drawer, cx, cy, h):
        # tiny lightning, drawn inverted so it reads on the dark fill
        pts = [(cx + 2, cy), (cx - 2, cy + h / 2 + 1), (cx, cy + h / 2 + 1),
               (cx - 1, cy + h), (cx + 3, cy + h / 2 - 1), (cx + 1, cy + h / 2 - 1)]
        try:
            drawer.polygon(pts, fill=0xFF, outline=0x00)
        except Exception:
            pass

    # full-screen "⚡ USB подключён" animation on plug-in
    def _draw_charge_anim(self, canvas, drawer, W, H):
        drawer.rectangle((0, 0, W, H), fill=0xFF)         # cover the normal UI
        pct = int(round(self._pct or 0))
        # big battery, centered, filling up with the animation frame
        bw, bh = 120, 54
        x = (W - bw) / 2
        y = 20
        drawer.rounded_rectangle((x, y, x + bw, y + bh), radius=8,
                                 outline=0x00, fill=0xFF, width=3)
        drawer.rectangle((x + bw + 3, y + bh / 2 - 9, x + bw + 10, y + bh / 2 + 9), fill=0x00)
        # animated fill sweeps up to the real %
        frame = int((time.time() * 3) % 11) / 10.0          # 0..1 loop
        shown = min(pct / 100.0, frame) if frame > 0 else 0
        fw = int((bw - 10) * shown)
        if fw > 0:
            drawer.rounded_rectangle((x + 5, y + 5, x + 5 + fw, y + bh - 5), radius=5, fill=0x00)
        # lightning badge
        self._bolt(drawer, x + bw / 2, y + 10, bh - 20)
        # text
        t1 = "USB подключён"
        drawer.text(((W - self._tw(drawer, t1, self._f_big)) / 2, y + bh + 8),
                    t1, font=self._f_big, fill=0x00)
        t2 = "Зарядка пошла  %d%%" % pct
        drawer.text(((W - self._tw(drawer, t2, self._f_small)) / 2, H - 16),
                    t2, font=self._f_small, fill=0x00)
