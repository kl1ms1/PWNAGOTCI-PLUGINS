"""
btlink — pair the phone to pwnagotchi over Bluetooth like a speaker.

When the iPhone starts pairing, pwnagotchi shows a PASSKEY FULL-SCREEN on the
e-ink; iOS asks you to type that code ("Enter the code shown on ..."). After
pairing, btlink joins the phone's Bluetooth Personal Hotspot (BT-PAN) so the
Companion app can reach the device over Bluetooth.

How it works:
  • a BlueZ pairing agent with "DisplayOnly" capability -> pwnagotchi displays
    the passkey, the phone enters it (needs python3-gi + python3-dbus; if they
    are missing it falls back to code-free "just works" pairing and logs it).
  • after pairing it dials the phone's BT-PAN with dbus-send (always available),
    runs dhclient on bnep0 and shows the obtained IP on the e-ink.

Config (/etc/pwnagotchi/config.toml):
  main.plugins.btlink.enabled = true
  main.plugins.btlink.alias    = "pwnagotchi"   # Bluetooth name
  main.plugins.btlink.auto_pan = true
  main.plugins.btlink.phone_mac = ""            # auto-detected if empty

iPhone: Settings -> Bluetooth -> tap it -> enter the code shown -> turn on
Personal Hotspot. Then the app connects to the IP shown on the e-ink.
Own device only.
"""

import logging
import os
import subprocess
import threading
import time

import pwnagotchi.plugins as plugins

try:
    from pwnagotchi.ui.components import Widget as _Widget
    import pwnagotchi.ui.fonts as fonts
except Exception:
    _Widget = object
    fonts = None


class _LinkWidget(_Widget):
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


class BTLink(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.4.0"
    __license__ = "MIT"
    __description__ = "Bluetooth pairing (passkey on screen) + PAN tether for the Companion app."

    def __init__(self):
        self._alias = "pwnagotchi"
        self._auto_pan = True
        self._phone_mac = ""
        self._pan_iface = "bnep0"
        self._pan_ip = ""
        self._passkey = ""            # shown full-screen while pairing
        self._passkey_at = 0.0
        self._last_pan = 0.0
        self._added = False
        self._agent_started = False
        self._f_small = None
        self._f_big = None

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._alias = o.get("alias", self._alias)
        self._auto_pan = bool(o.get("auto_pan", True))
        self._phone_mac = str(o.get("phone_mac", "") or "").upper().strip()
        self._pan_iface = o.get("pan_iface", self._pan_iface)
        logging.info("[btlink] loaded")

    def _sh(self, args, timeout=12):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            logging.debug("[btlink] cmd %s: %s", args, e)
            return False, str(e)

    def on_ready(self, agent):
        try:
            self._sh(["bluetoothctl", "power", "on"])
            self._sh(["bluetoothctl", "system-alias", self._alias])
            self._sh(["bluetoothctl", "discoverable", "on"])
            self._sh(["bluetoothctl", "pairable", "on"])
            self._sh(["bluetoothctl", "discoverable-timeout", "0"])
        except Exception:
            logging.exception("[btlink] bt setup")
        self._start_agent()

    # --- BlueZ pairing agent: DisplayOnly -> show passkey on the e-ink -----
    def _start_agent(self):
        if self._agent_started:
            return
        self._agent_started = True
        t = threading.Thread(target=self._agent_loop, daemon=True)
        t.start()

    def _agent_loop(self):
        try:
            import dbus
            import dbus.service
            import dbus.mainloop.glib
            from gi.repository import GLib
        except Exception as e:
            logging.warning("[btlink] no python dbus/gi (%s) -> code-free pairing. "
                            "Install python3-gi python3-dbus for the on-screen code.", e)
            # fall back: a capability-less agent via bluetoothctl (just works)
            self._sh(["bluetoothctl", "agent", "NoInputNoOutput"])
            self._sh(["bluetoothctl", "default-agent"])
            return

        plugin = self

        class Agent(dbus.service.Object):
            @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
            def Release(self): pass

            @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
            def AuthorizeService(self, device, uuid): return

            @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
            def DisplayPasskey(self, device, passkey, entered):
                plugin._on_passkey("%06u" % int(passkey))

            @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
            def DisplayPinCode(self, device, pincode):
                plugin._on_passkey(str(pincode))

            @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
            def RequestAuthorization(self, device): return

            @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
            def Cancel(self):
                plugin._passkey = ""

        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            bus = dbus.SystemBus()
            path = "/btlink/agent"
            Agent(bus, path)
            mgr = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                                 "org.bluez.AgentManager1")
            mgr.RegisterAgent(path, "DisplayOnly")
            mgr.RequestDefaultAgent(path)
            logging.info("[btlink] DisplayOnly pairing agent registered")
            GLib.MainLoop().run()
        except Exception:
            logging.exception("[btlink] agent loop failed")

    def _on_passkey(self, code):
        self._passkey = code
        self._passkey_at = time.time()
        logging.info("[btlink] pairing passkey: %s", code)

    # --- BT-PAN: join the phone's hotspot ----------------------------------
    def _iface_ip(self):
        ok, out = self._sh(["ip", "-4", "addr", "show", self._pan_iface])
        if not ok:
            return ""
        for tok in out.split():
            if tok.count(".") == 3 and "/" in tok:
                return tok.split("/")[0]
        return ""

    def _auto_mac(self):
        for args in (["devices", "Connected"], ["paired-devices"], ["devices", "Paired"]):
            ok, out = self._sh(["bluetoothctl"] + args)
            if not ok:
                continue
            for line in out.splitlines():
                p = line.split()
                if len(p) >= 2 and p[0] == "Device":
                    return p[1].upper()
        return ""

    def _ensure_pan(self):
        if not self._auto_pan:
            return
        if not self._phone_mac:
            self._phone_mac = self._auto_mac()
            if not self._phone_mac:
                return
        if self._iface_ip():
            self._pan_ip = self._iface_ip()
            self._passkey = ""                 # paired & linked -> drop the code
            return
        mac = self._phone_mac
        self._sh(["bluetoothctl", "trust", mac])
        self._sh(["bluetoothctl", "connect", mac], timeout=15)
        dev = "dev_" + mac.replace(":", "_")
        self._sh(["dbus-send", "--system", "--print-reply", "--dest=org.bluez",
                  "/org/bluez/hci0/" + dev, "org.bluez.Network1.Connect", "string:nap"],
                 timeout=20)
        time.sleep(3)
        self._sh(["dhclient", "-1", self._pan_iface], timeout=25)
        ip = self._iface_ip()
        if ip:
            self._pan_ip = ip
            logging.info("[btlink] PAN up: %s", ip)

    def on_epoch(self, agent, epoch, epoch_data):
        now = time.time()
        if now - self._last_pan < 20:
            return
        self._last_pan = now
        try:
            self._ensure_pan()
        except Exception:
            logging.exception("[btlink] ensure_pan")

    # --- full-screen e-ink -------------------------------------------------
    def on_ui_setup(self, ui):
        if _Widget is object:
            return
        try:
            ui.add_element("btlink", _LinkWidget(self))
            self._added = True
        except Exception:
            logging.debug("[btlink] could not add widget")

    def on_ui_update(self, ui):
        if not self._added:
            return
        # only take over the whole screen while a passkey is being shown
        show = bool(self._passkey) and (time.time() - self._passkey_at < 40)
        if not show:
            return
        try:
            st = getattr(getattr(ui, "_state", None), "_state", None)
            if isinstance(st, dict) and "btlink" in st:
                st["btlink"] = st.pop("btlink")       # draw last (on top)
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
                return len(text) * 8

    def _fonts(self):
        if self._f_small is not None or fonts is None:
            return
        self._f_small = getattr(fonts, "Small", None)
        self._f_big = (getattr(fonts, "Huge", None)
                       or getattr(fonts, "Bold", None) or self._f_small)

    def _draw(self, canvas, drawer):
        if not self._passkey or (time.time() - self._passkey_at >= 40):
            return
        self._fonts()
        if self._f_small is None:
            return
        try:
            W, H = canvas.size
        except Exception:
            W, H = 250, 122
        drawer.rectangle((0, 0, W, H), fill=0xFF)
        drawer.rectangle((0, 0, W, 16), fill=0x00)
        t = "Bluetooth — код на айфоне"
        drawer.text(((W - self._tw(drawer, t, self._f_small)) / 2, 2), t,
                    font=self._f_small, fill=0xFF)
        ff = self._f_big
        if ff is None or self._tw(drawer, self._passkey, ff) > W - 10:
            ff = self._f_small
        drawer.text(((W - self._tw(drawer, self._passkey, ff)) / 2, 44),
                    self._passkey, font=ff, fill=0x00)
        b = "введи этот код на телефоне"
        drawer.text(((W - self._tw(drawer, b, self._f_small)) / 2, H - 16), b,
                    font=self._f_small, fill=0x00)

    def on_unload(self, ui):
        try:
            self._sh(["bluetoothctl", "discoverable", "off"])
        except Exception:
            pass
        try:
            ui.remove_element("btlink")
        except Exception:
            pass
