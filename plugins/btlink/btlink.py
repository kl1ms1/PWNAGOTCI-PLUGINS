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
    from pwnagotchi.ui.components import Widget as _Widget, LabeledValue
    from pwnagotchi.ui.view import BLACK
    import pwnagotchi.ui.fonts as fonts
except Exception:
    _Widget = object
    LabeledValue = None
    BLACK = 0x00
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
        self._static_ip = "172.20.10.6"   # fixed IP on the phone's BT-PAN
        self._gw = "172.20.10.1"
        self._disc = False
        self._pair = False
        self._passkey = ""            # shown full-screen while pairing
        self._passkey_at = 0.0
        self._added = False
        self._label_added = False
        self._label_pos = (0, 83)     # "BT: nick" line, above the cracked-pw line
        self._agent_started = False
        self._keep_started = False
        self._btctl_proc = None       # persistent bluetoothctl agent process
        self._f_small = None
        self._f_big = None

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._alias = o.get("alias", self._alias)
        self._auto_pan = bool(o.get("auto_pan", True))
        self._phone_mac = str(o.get("phone_mac", "") or "").upper().strip()
        self._pan_iface = o.get("pan_iface", self._pan_iface)
        self._static_ip = o.get("static_ip", self._static_ip)
        pos = o.get("label_position", "0,83")
        try:
            x, y = str(pos).split(",")
            self._label_pos = (int(x), int(y))
        except Exception:
            pass
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
            # pwnagotchi images often ship Bluetooth OFF — bring the stack up first
            self._sh(["rfkill", "unblock", "bluetooth"])
            self._sh(["systemctl", "start", "bluetooth"])
            self._sh(["hciconfig", "hci0", "up"])
            time.sleep(1)
            self._sh(["bluetoothctl", "power", "on"])
            self._sh(["bluetoothctl", "system-alias", self._alias])
            self._sh(["bluetoothctl", "discoverable", "on"])
            self._sh(["bluetoothctl", "pairable", "on"])
            self._sh(["bluetoothctl", "discoverable-timeout", "0"])
            self._assert_pairable()          # btmgmt — the real pairable fix
            ok, out = self._sh(["bluetoothctl", "show"])
            logging.info("[btlink] bt up? %s", "Powered: yes" in out)
        except Exception:
            logging.exception("[btlink] bt setup")
        self._start_agent()
        self._start_keepalive()

    def _start_keepalive(self):
        if self._keep_started:
            return
        self._keep_started = True
        threading.Thread(target=self._keepalive_loop, daemon=True).start()

    def _keepalive_loop(self):
        """Runs in a thread (not on_epoch), so it works the SAME in auto AND
        manual mode: keep the pairing agent alive + Pairable on, and join PAN."""
        while True:
            try:
                self._pan_ip = self._iface_ip()
                if not self._pan_ip:
                    self._assert_pairable()                # keep Pairable on (btmgmt)
                    self._ensure_pan()
                if self._btctl_proc is not None and self._btctl_proc.poll() is not None:
                    self._start_btctl_agent()              # agent died -> relaunch
                ok, out = self._sh(["bluetoothctl", "show"])
                self._disc = "Discoverable: yes" in out
                self._pair = "Pairable: yes" in out
            except Exception:
                logging.debug("[btlink] keepalive tick failed")
            time.sleep(15)

    # --- pairing agent -----------------------------------------------------
    def _start_agent(self):
        if self._agent_started:
            return
        self._agent_started = True
        try:
            import gi  # noqa: F401
            has_gi = True
        except Exception:
            has_gi = False
        if has_gi:
            # D-Bus DisplayOnly agent -> passkey shown on the e-ink
            threading.Thread(target=self._agent_loop, daemon=True).start()
        else:
            # reliable fallback: a PERSISTENT bluetoothctl agent (code-free,
            # 'just works' pairing) — a one-shot agent would exit and leave the
            # device un-pairable, which is exactly the bug we hit.
            self._start_btctl_agent()

    def _assert_pairable(self):
        """btmgmt sets the Pairable flag reliably (bluetoothctl didn't on this
        device). This is what finally let the iPhone pair."""
        self._sh(["btmgmt", "pairable", "on"])
        self._sh(["btmgmt", "connectable", "on"])

    def _start_btctl_agent(self):
        import subprocess
        try:
            if self._btctl_proc is not None and self._btctl_proc.poll() is None:
                return
            p = subprocess.Popen(["bluetoothctl"], stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 text=True)
            for c in ("power on", "pairable on", "discoverable on",
                      "discoverable-timeout 0", "agent NoInputNoOutput", "default-agent"):
                p.stdin.write(c + "\n")
            p.stdin.flush()
            self._btctl_proc = p          # KEEP the process alive -> agent stays up
            logging.info("[btlink] persistent bluetoothctl agent (NoInputNoOutput) up")
        except Exception:
            logging.exception("[btlink] bluetoothctl agent failed")

    def _agent_loop(self):
        import dbus
        import dbus.service
        import dbus.mainloop.glib
        from gi.repository import GLib

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

    def _status_text(self):
        """Compact live status for the e-ink: [discoverable][pairable] + IP.
        O = on, x = off; then the fixed PAN IP (or 'no ip' until linked)."""
        d = "O" if self._disc else "x"
        p = "O" if self._pair else "x"
        return "[%s][%s] %s" % (d, p, self._pan_ip if self._pan_ip else "no ip")

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
        # assign a FIXED ip on bnep0 so the app always uses the same address
        ok, _ = self._sh(["ip", "link", "show", self._pan_iface])
        if ok:
            self._sh(["ip", "addr", "flush", "dev", self._pan_iface])
            self._sh(["ip", "addr", "add", self._static_ip + "/24", "dev", self._pan_iface])
            self._sh(["ip", "link", "set", self._pan_iface, "up"])
            ip = self._iface_ip()
            if ip:
                self._pan_ip = ip
                logging.info("[btlink] PAN up (static): %s", ip)

    # --- e-ink -------------------------------------------------------------
    def on_ui_setup(self, ui):
        # small persistent "BT: nick" line (above the cracked-password line)
        if LabeledValue is not None:
            try:
                ui.add_element("btlabel", LabeledValue(
                    color=BLACK, label="", value="[x][x] no ip",
                    position=self._label_pos,
                    label_font=getattr(fonts, "Bold", None),
                    text_font=getattr(fonts, "Small", None)))
                self._label_added = True
            except Exception:
                logging.debug("[btlink] could not add label")
        # full-screen passkey takeover (only while pairing)
        if _Widget is not object:
            try:
                ui.add_element("btlink", _LinkWidget(self))
                self._added = True
            except Exception:
                logging.debug("[btlink] could not add widget")

    def on_ui_update(self, ui):
        # keep the small "BT:" line current (nick, or the IP once linked)
        if self._label_added:
            try:
                ui.set("btlabel", self._status_text())
            except Exception:
                pass
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
        try:
            ui.remove_element("btlabel")
        except Exception:
            pass
