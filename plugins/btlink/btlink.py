"""
btlink — pwnagotchi raises ITS OWN secured Wi-Fi hotspot for the Companion app.

The phone joins the pwnagotchi's Wi-Fi by typing the password that is shown
FULL-SCREEN on the e-ink (so nobody without the password can connect). Then the
app reaches the device at the hotspot IP (default 192.168.50.1).

Why Wi-Fi and not Bluetooth: an iPhone cannot join a Raspberry Pi's Bluetooth
network (iOS doesn't allow it), so "phone connects to the Pi + password" is only
possible over Wi-Fi.

⚠️ ONE radio: while the hotspot is up, hunting is PAUSED. Enable this plugin when
you want to use the app; disable it to hunt. (A physical switch can automate this
later.)

Config (/etc/pwnagotchi/config.toml):
  main.plugins.btlink.enabled = true
  main.plugins.btlink.ap_ssid = "pwn-Ki213"    # Wi-Fi name
  main.plugins.btlink.ap_pass = ""             # fixed pass, or "" = generated once
  main.plugins.btlink.ap_ip   = "192.168.50.1" # app connects here
  main.plugins.btlink.channel = 6

Needs hostapd + dnsmasq on the device (usually present). Own device only.
"""

import logging
import os
import random
import string
import subprocess
import time

import pwnagotchi.plugins as plugins

try:
    from pwnagotchi.ui.components import Widget as _Widget
    import pwnagotchi.ui.fonts as fonts
except Exception:
    _Widget = object
    fonts = None


class _APWidget(_Widget):
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
    __version__ = "0.3.0"
    __license__ = "MIT"
    __description__ = "pwnagotchi's own secured Wi-Fi hotspot for the Companion app (full-screen password)."

    def __init__(self):
        self._ssid = "pwnagotchi"
        self._pass = ""
        self._ip = "192.168.50.1"
        self._channel = 6
        self._iface = "wlan0"
        self._dir = "/root/.btlink"
        self._hostapd_conf = "/tmp/btlink_hostapd.conf"
        self._dnsmasq_conf = "/tmp/btlink_dnsmasq.conf"
        self._procs = []
        self._up = False
        self._added = False
        self._f_small = None
        self._f_big = None

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._ssid = o.get("ap_ssid", "pwnagotchi")
        self._pass = str(o.get("ap_pass", "") or "")
        self._ip = o.get("ap_ip", self._ip)
        self._iface = o.get("ap_iface", self._iface)
        try:
            self._channel = int(o.get("channel", 6))
        except Exception:
            self._channel = 6
        os.makedirs(self._dir, exist_ok=True)
        if not self._pass:
            self._pass = self._load_or_make_pass()
        logging.info("[btlink] loaded (ssid=%s)", self._ssid)

    def _load_or_make_pass(self):
        pf = os.path.join(self._dir, "pass.txt")
        try:
            with open(pf) as f:
                p = f.read().strip()
                if len(p) >= 8:
                    return p
        except Exception:
            pass
        # readable 8-char password (no ambiguous chars)
        alpha = "abcdefghijkmnpqrstuvwxyz23456789"
        p = "".join(random.choice(alpha) for _ in range(8))
        try:
            with open(pf, "w") as f:
                f.write(p)
        except Exception:
            pass
        return p

    def _sh(self, args, timeout=10):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0
        except Exception as e:
            logging.debug("[btlink] cmd %s: %s", args, e)
            return False

    def on_ready(self, agent):
        self._raise_ap()

    # --- the hotspot -------------------------------------------------------
    def _raise_ap(self):
        if self._up:
            return
        if len(self._pass) < 8:
            logging.warning("[btlink] password <8 chars — not raising AP")
            return
        try:
            self._sh(["/usr/bin/monstop"])
            self._sh(["rfkill", "unblock", "wifi"])
            self._sh(["ip", "link", "set", self._iface, "down"])
            self._sh(["ip", "addr", "flush", "dev", self._iface])
            self._sh(["ip", "addr", "add", self._ip + "/24", "dev", self._iface])
            self._sh(["ip", "link", "set", self._iface, "up"])
            net = self._ip.rsplit(".", 1)[0]
            with open(self._hostapd_conf, "w") as f:
                f.write("interface=%s\ndriver=nl80211\nssid=%s\nhw_mode=g\nchannel=%d\n"
                        "auth_algs=1\nwpa=2\nwpa_passphrase=%s\nwpa_key_mgmt=WPA-PSK\n"
                        "rsn_pairwise=CCMP\nignore_broadcast_ssid=0\n"
                        % (self._iface, self._ssid, self._channel, self._pass))
            with open(self._dnsmasq_conf, "w") as f:
                f.write("interface=%s\nbind-interfaces\nexcept-interface=lo\n"
                        "dhcp-range=%s.10,%s.100,255.255.255.0,12h\n"
                        "dhcp-option=3,%s\ndhcp-option=6,%s\nno-resolv\nport=0\n"
                        % (self._iface, net, net, self._ip, self._ip))
            hp = subprocess.Popen(["hostapd", self._hostapd_conf],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            dm = subprocess.Popen(["dnsmasq", "-C", self._dnsmasq_conf, "-k"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._procs = [hp, dm]
            self._up = True
            logging.info("[btlink] hotspot up: %s @ %s", self._ssid, self._ip)
        except Exception:
            logging.exception("[btlink] raise AP failed")
            self._ap_down()

    def _ap_down(self):
        for p in self._procs:
            try:
                p.terminate()
            except Exception:
                pass
        self._procs = []
        self._sh(["pkill", "-f", self._hostapd_conf])
        self._sh(["pkill", "-f", self._dnsmasq_conf])
        self._sh(["ip", "addr", "flush", "dev", self._iface])
        self._sh(["ip", "link", "set", self._iface, "down"])
        self._sh(["/usr/bin/monstart"])
        self._up = False

    # --- full-screen password on the e-ink ---------------------------------
    def on_ui_setup(self, ui):
        if _Widget is object:
            return
        try:
            ui.add_element("btlink", _APWidget(self))
            self._added = True
        except Exception:
            logging.debug("[btlink] could not add widget")

    def on_ui_update(self, ui):
        if not self._added:
            return
        try:
            st = getattr(getattr(ui, "_state", None), "_state", None)
            if isinstance(st, dict) and "btlink" in st:
                st["btlink"] = st.pop("btlink")     # draw last (on top)
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
        self._fonts()
        if self._f_small is None:
            return
        try:
            W, H = canvas.size
        except Exception:
            W, H = 250, 122
        drawer.rectangle((0, 0, W, H), fill=0xFF)
        # header: Wi-Fi name
        drawer.rectangle((0, 0, W, 16), fill=0x00)
        top = "WiFi: %s" % self._ssid
        drawer.text(((W - self._tw(drawer, top, self._f_small)) / 2, 2), top,
                    font=self._f_small, fill=0xFF)
        # label
        lbl = "пароль / password"
        drawer.text(((W - self._tw(drawer, lbl, self._f_small)) / 2, 22), lbl,
                    font=self._f_small, fill=0x00)
        # the password, as big as fits (fall back to small if too wide)
        ff = self._f_big
        if ff is None or self._tw(drawer, self._pass, ff) > W - 16:
            ff = self._f_small
        pw_w = self._tw(drawer, self._pass, ff)
        drawer.text(((W - pw_w) / 2, 44), self._pass, font=ff, fill=0x00)
        # footer: where to point the app
        foot = "app: %s:8080" % self._ip if self._up else "AP down — see log"
        drawer.rectangle((0, H - 16, W, H), fill=0x00)
        drawer.text(((W - self._tw(drawer, foot, self._f_small)) / 2, H - 15), foot,
                    font=self._f_small, fill=0xFF)

    def on_unload(self, ui):
        try:
            self._ap_down()
        except Exception:
            pass
        try:
            ui.remove_element("btlink")
        except Exception:
            pass
