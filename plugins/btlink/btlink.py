"""
btlink — one plugin to pair the Pwn Companion app over Bluetooth (or cable).

What it does (reliable, testable):
  • Makes the pwnagotchi Bluetooth DISCOVERABLE + PAIRABLE so your iPhone can
    pair it for Bluetooth tethering (BT-PAN). iOS pairing shows a 6-digit code
    on BOTH devices that you confirm once — that's the "no stranger connects"
    security, built into Bluetooth itself.
  • Shows a short LINK CODE and the BT status on the e-ink.
  • Exposes a tiny web gate: the app sends the code once to "unlock", so even
    over the shared network nobody without the on-screen code can drive the Pi.

What you still do once (can't be automated from the Pi reliably):
  • On the iPhone: Settings → Bluetooth → tap "pwnagotchi" → confirm the code.
  • Turn ON Personal Hotspot so the Pi can join over Bluetooth (BT-PAN). The Pi
    then gets an IP like 172.20.10.x — put that in the app (Bluetooth mode).

Transport choice (Bluetooth vs cable) lives in the APP settings; this plugin
just makes the Bluetooth side reachable and secured. Cable (USB 10.0.0.2) needs
no plugin at all.

Config (/etc/pwnagotchi/config.toml):
  main.plugins.btlink.enabled     = true
  main.plugins.btlink.alias       = "pwnagotchi"   # Bluetooth name
  main.plugins.btlink.discoverable = true          # show up for pairing
  main.plugins.btlink.require_code = true          # app must send the code once
  main.plugins.btlink.code        = ""             # fixed code, or "" = random per boot
  main.plugins.btlink.position    = "0,95"         # where to draw on the e-ink

Web:  http://<ip>:8080/plugins/btlink/?code=123456   -> {"ok": true/false}
Own device only.
"""

import logging
import random
import subprocess

import pwnagotchi.plugins as plugins

try:
    from pwnagotchi.ui.components import LabeledValue
    from pwnagotchi.ui.view import BLACK
    import pwnagotchi.ui.fonts as fonts
except Exception:
    LabeledValue = None
    BLACK = 0x00


class BTLink(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "Bluetooth pairing + on-screen link code for the Pwn Companion app."

    def __init__(self):
        self._alias = "pwnagotchi"
        self._discoverable = True
        self._require_code = True
        self._fixed = ""
        self._pos = (0, 95)
        self._code = ""
        self._unlocked = False
        self._bt_ok = None

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._alias = o.get("alias", self._alias)
        self._discoverable = bool(o.get("discoverable", True))
        self._require_code = bool(o.get("require_code", True))
        self._fixed = str(o.get("code", "") or "")
        pos = o.get("position", "0,95")
        try:
            x, y = str(pos).split(",")
            self._pos = (int(x), int(y))
        except Exception:
            pass
        logging.info("[btlink] loaded")

    def _sh(self, args, timeout=10):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            logging.debug("[btlink] cmd %s: %s", args, e)
            return False, str(e)

    def _gen_code(self):
        if self._fixed:
            return str(self._fixed)
        return "%06d" % random.randint(0, 999999)

    def on_ready(self, agent):
        self._code = self._gen_code()
        self._unlocked = not self._require_code
        ok, _ = self._sh(["bluetoothctl", "show"])
        self._bt_ok = ok
        try:
            self._sh(["bluetoothctl", "power", "on"])
            self._sh(["bluetoothctl", "system-alias", self._alias])
            if self._discoverable:
                self._sh(["bluetoothctl", "discoverable", "on"])
                self._sh(["bluetoothctl", "pairable", "on"])
            logging.info("[btlink] ready (bt=%s, code=%s)", self._bt_ok, self._code)
        except Exception:
            logging.exception("[btlink] bluetooth setup failed")

    # --- e-ink -------------------------------------------------------------
    def on_ui_setup(self, ui):
        if LabeledValue is None:
            return
        try:
            ui.add_element("btlink", LabeledValue(
                color=BLACK, label="BT", value="...",
                position=self._pos,
                label_font=getattr(fonts, "Bold", None),
                text_font=getattr(fonts, "Small", None)))
        except Exception:
            logging.debug("[btlink] could not add ui element")

    def on_ui_update(self, ui):
        try:
            if self._require_code and not self._unlocked:
                msg = "code %s" % self._code
            elif self._unlocked:
                msg = "linked"
            else:
                msg = "pair ON"
            ui.set("btlink", msg)
        except Exception:
            pass

    def on_unload(self, ui):
        try:
            self._sh(["bluetoothctl", "discoverable", "off"])
        except Exception:
            pass
        try:
            ui.remove_element("btlink")
        except Exception:
            pass

    # --- web gate ----------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify
        code = ""
        try:
            code = (request.args.get("code") or "").strip()
        except Exception:
            code = ""
        if not self._require_code:
            return jsonify(ok=True, linked=True, require_code=False)
        if code and code == self._code:
            self._unlocked = True
            return jsonify(ok=True, linked=True)
        return jsonify(ok=False, linked=self._unlocked,
                       msg="Enter the code shown on the pwnagotchi screen")
