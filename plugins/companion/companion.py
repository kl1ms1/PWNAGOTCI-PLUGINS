"""
companion — THE single plugin for the Pwn Companion app. Enable just this one:

    main.plugins.companion.enabled = true

It does everything the app needs, so you never touch plugins again — only the app
gets updated:
  • Bluetooth: powers the stack up, stays pairable (btmgmt) with a live pairing
    agent, auto-joins the phone's BT-PAN with a FIXED ip, shows status on e-ink.
  • BLE: launches the BLE GATT server (btlink_ble.py, system python) for the
    Flipper-style direct link — if that file + its packages are present.
  • JSON API over HTTP (for Wi-Fi / BT-PAN): status / pwndex (read+edit) / control.

Copy companion.py (and btlink_ble.py for BLE) to the custom-plugins folder.
Disable the old btlink plugin. Own device / your own networks only.
"""

import json
import logging
import os
import socket
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


class Companion(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "1.2.0"
    __license__ = "MIT"
    __description__ = "One plugin for the Pwn Companion app: Bluetooth + BLE + JSON API."

    def __init__(self):
        # --- bluetooth / PAN ---
        self._alias = "pwnagotchi"
        self._auto_pan = True
        self._phone_mac = ""
        self._pan_iface = "bnep0"
        self._pan_ip = ""
        self._static_ip = "172.20.10.6"
        self._disc = False
        self._pair = False
        self._passkey = ""
        self._passkey_at = 0.0
        self._btctl_proc = None
        self._ble_proc = None
        self._agent_started = False
        self._keep_started = False
        self._added = False
        self._label_added = False
        self._label_pos = (0, 83)
        self._f_small = None
        self._f_big = None
        # --- json api ---
        self._dex_f = "/root/.pwndex/dex.json"
        self._hs_dir = "/home/pi/handshakes"
        self._name = "pwnagotchi"
        self._shakes = 0
        self._agent = None
        self._ble_script = "/home/pi/btlink_ble.py"

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._alias = o.get("alias", self._alias)
        self._auto_pan = bool(o.get("auto_pan", True))
        self._phone_mac = str(o.get("phone_mac", "") or "").upper().strip()
        self._static_ip = o.get("static_ip", self._static_ip)
        self._dex_f = o.get("pwndex", self._dex_f)
        self._ble_script = o.get("ble_script", self._ble_script)
        pos = o.get("label_position", "0,83")
        try:
            x, y = str(pos).split(",")
            self._label_pos = (int(x), int(y))
        except Exception:
            pass
        logging.info("[companion] loaded")

    def on_ready(self, agent):
        self._agent = agent
        try:
            cfg = agent.config()
            self._name = cfg.get("main", {}).get("name") or socket.gethostname()
            self._hs_dir = cfg["bettercap"].get("handshakes", self._hs_dir)
        except Exception:
            self._name = socket.gethostname()
        try:
            self._sh(["rfkill", "unblock", "bluetooth"])
            self._sh(["systemctl", "start", "bluetooth"])
            self._sh(["hciconfig", "hci0", "up"])
            time.sleep(1)
            self._sh(["bluetoothctl", "power", "on"])
            self._sh(["bluetoothctl", "system-alias", self._alias])
            self._sh(["bluetoothctl", "discoverable", "on"])
            self._assert_pairable()
        except Exception:
            logging.exception("[companion] bt setup")
        self._start_agent()
        self._launch_ble()
        self._start_keepalive()

    # --- helpers -----------------------------------------------------------
    def _sh(self, args, timeout=12):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            logging.debug("[companion] cmd %s: %s", args, e)
            return False, str(e)

    def _assert_pairable(self):
        self._sh(["btmgmt", "pairable", "on"])
        self._sh(["btmgmt", "connectable", "on"])

    def _launch_ble(self):
        if self._ble_proc is not None and self._ble_proc.poll() is None:
            return
        if not os.path.exists(self._ble_script):
            logging.info("[companion] no BLE script at %s (skip BLE)", self._ble_script)
            return
        for py in ("/usr/bin/python3", "python3"):
            try:
                self._ble_proc = subprocess.Popen([py, self._ble_script],
                                                  stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.DEVNULL)
                logging.info("[companion] BLE server launched (%s)", py)
                return
            except Exception:
                continue

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
            threading.Thread(target=self._agent_loop, daemon=True).start()
        else:
            self._start_btctl_agent()

    def _start_btctl_agent(self):
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
            self._btctl_proc = p
            logging.info("[companion] persistent bluetoothctl agent up")
        except Exception:
            logging.exception("[companion] bluetoothctl agent failed")

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
            path = "/companion/agent"
            Agent(bus, path)
            mgr = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                                 "org.bluez.AgentManager1")
            mgr.RegisterAgent(path, "DisplayOnly")
            mgr.RequestDefaultAgent(path)
            logging.info("[companion] DisplayOnly pairing agent registered")
            GLib.MainLoop().run()
        except Exception:
            logging.exception("[companion] agent loop failed")

    def _on_passkey(self, code):
        self._passkey = code
        self._passkey_at = time.time()
        logging.info("[companion] pairing passkey: %s", code)

    # --- BT-PAN ------------------------------------------------------------
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
            self._passkey = ""
            return
        mac = self._phone_mac
        self._sh(["bluetoothctl", "trust", mac])
        self._sh(["bluetoothctl", "connect", mac], timeout=15)
        dev = "dev_" + mac.replace(":", "_")
        self._sh(["dbus-send", "--system", "--print-reply", "--dest=org.bluez",
                  "/org/bluez/hci0/" + dev, "org.bluez.Network1.Connect", "string:nap"],
                 timeout=20)
        time.sleep(3)
        ok, _ = self._sh(["ip", "link", "show", self._pan_iface])
        if ok:
            self._sh(["ip", "addr", "flush", "dev", self._pan_iface])
            self._sh(["ip", "addr", "add", self._static_ip + "/24", "dev", self._pan_iface])
            self._sh(["ip", "link", "set", self._pan_iface, "up"])
            ip = self._iface_ip()
            if ip:
                self._pan_ip = ip
                logging.info("[companion] PAN up (static): %s", ip)

    def _start_keepalive(self):
        if self._keep_started:
            return
        self._keep_started = True
        threading.Thread(target=self._keepalive_loop, daemon=True).start()

    def _keepalive_loop(self):
        while True:
            try:
                self._pan_ip = self._iface_ip()
                if not self._pan_ip:
                    self._assert_pairable()
                    self._ensure_pan()
                if self._btctl_proc is not None and self._btctl_proc.poll() is not None:
                    self._start_btctl_agent()
                self._launch_ble()           # relaunch BLE server if it died
                ok, out = self._sh(["bluetoothctl", "show"])
                self._disc = "Discoverable: yes" in out
                self._pair = "Pairable: yes" in out
            except Exception:
                logging.debug("[companion] keepalive tick failed")
            time.sleep(15)

    # --- e-ink -------------------------------------------------------------
    def on_ui_setup(self, ui):
        if LabeledValue is not None:
            try:
                ui.add_element("colabel", LabeledValue(
                    color=BLACK, label="", value="[x][x] no ip",
                    position=self._label_pos,
                    label_font=getattr(fonts, "Bold", None),
                    text_font=getattr(fonts, "Small", None)))
                self._label_added = True
            except Exception:
                logging.debug("[companion] could not add label")
        if _Widget is not object:
            try:
                ui.add_element("cowidget", _LinkWidget(self))
                self._added = True
            except Exception:
                logging.debug("[companion] could not add widget")

    def on_ui_update(self, ui):
        if self._label_added:
            try:
                ui.set("colabel", self._status_text())
            except Exception:
                pass
        if not self._added:
            return
        show = bool(self._passkey) and (time.time() - self._passkey_at < 40)
        if not show:
            return
        try:
            st = getattr(getattr(ui, "_state", None), "_state", None)
            if isinstance(st, dict) and "cowidget" in st:
                st["cowidget"] = st.pop("cowidget")
        except Exception:
            pass

    def _status_text(self):
        d = "O" if self._disc else "x"
        p = "O" if self._pair else "x"
        return "[%s][%s] %s" % (d, p, self._pan_ip if self._pan_ip else "no ip")

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
        for proc in (self._ble_proc,):
            try:
                if proc is not None:
                    proc.terminate()
            except Exception:
                pass
        try:
            self._sh(["bluetoothctl", "discoverable", "off"])
        except Exception:
            pass
        for el in ("cowidget", "colabel"):
            try:
                ui.remove_element(el)
            except Exception:
                pass

    # --- JSON API ----------------------------------------------------------
    def on_handshake(self, agent, filename, access_point, client_station):
        self._shakes += 1

    @staticmethod
    def _read_temp():
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            return None

    def _read_cpu(self):
        try:
            def snap():
                with open("/proc/stat") as f:
                    p = [int(x) for x in f.readline().split()[1:]]
                idle = p[3] + (p[4] if len(p) > 4 else 0)
                return sum(p), idle
            t0, i0 = snap(); time.sleep(0.1); t1, i1 = snap()
            dt, di = t1 - t0, i1 - i0
            return round(100.0 * (dt - di) / dt, 1) if dt > 0 else 0.0
        except Exception:
            return None

    @staticmethod
    def _read_mem():
        try:
            info = {}
            with open("/proc/meminfo") as f:
                for ln in f:
                    k, _, v = ln.partition(":")
                    info[k] = int(v.split()[0])
            tot = info.get("MemTotal", 0)
            av = info.get("MemAvailable", info.get("MemFree", 0))
            return round(100.0 * (tot - av) / tot, 1) if tot else None
        except Exception:
            return None

    @staticmethod
    def _read_uptime():
        try:
            with open("/proc/uptime") as f:
                return int(float(f.read().split()[0]))
        except Exception:
            return 0

    @staticmethod
    def _sd_free():
        try:
            st = os.statvfs("/")
            return round(st.f_bavail * st.f_frsize / (1024 ** 3), 1)
        except Exception:
            return None

    def _pcaps(self):
        try:
            return sum(1 for f in os.listdir(self._hs_dir) if f.endswith(".pcap"))
        except Exception:
            return 0

    def _dex(self):
        try:
            with open(self._dex_f, encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _save_dex(self, dex):
        try:
            tmp = self._dex_f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dex, f, ensure_ascii=False)
            os.replace(tmp, self._dex_f)
            return True
        except Exception:
            return False

    @staticmethod
    def _mode():
        return "manual" if os.path.exists("/root/.pwnagotchi-manual") else "auto"

    def _status(self):
        dex = self._dex()
        return {
            "name": self._name, "mode": self._mode(), "uptime": self._read_uptime(),
            "temp": self._read_temp(), "cpu": self._read_cpu(), "mem": self._read_mem(),
            "sd_free": self._sd_free(), "pcaps": self._pcaps(), "networks": len(dex),
            "cracked": sum(1 for e in dex.values() if e.get("pw")), "shakes": self._shakes,
            "bt": self._status_text(),
        }

    def _pwndex(self):
        out = []
        for mac, e in self._dex().items():
            out.append({"ssid": e.get("ssid") or "(hidden)", "mac": (mac or "").upper(),
                        "pw": e.get("pw") or "", "caught": bool(e.get("caught")),
                        "last": e.get("last") or 0, "pw_at": e.get("pw_at") or 0})
        out.sort(key=lambda x: (x["pw"] == "", x["ssid"].lower()))
        return out

    @staticmethod
    def _bg(args):
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def _control(self, cmd):
        if cmd == "reboot":
            return self._bg(["systemctl", "reboot"])
        if cmd == "shutdown":
            return self._bg(["systemctl", "poweroff"])
        if cmd == "restart":
            return self._bg(["systemctl", "restart", "pwnagotchi"])
        if cmd in ("manual", "auto"):
            flag = "/root/.pwnagotchi-manual"
            try:
                if cmd == "manual":
                    open(flag, "a").close()
                elif os.path.exists(flag):
                    os.remove(flag)
            except Exception:
                return False
            return self._bg(["systemctl", "restart", "pwnagotchi"])
        return False

    @staticmethod
    def _have_net():
        try:
            socket.setdefaulttimeout(3)
            socket.getaddrinfo("wpa-sec.stanev.org", 443)
            return True
        except Exception:
            return False

    def _upload_all(self):
        wp = plugins.loaded.get("wpa-sec")
        if not wp:
            return False, "wpa-sec plugin not loaded"
        if not getattr(wp, "ready", False):
            return False, "wpa-sec not ready (api_key?)"
        if self._agent is None:
            return False, "agent not ready"
        if not self._have_net():
            return False, "no internet"
        try:
            wp.on_internet_available(self._agent)
            return True, "wpa-sec upload + download triggered"
        except Exception as e:
            return False, str(e)

    def _pcap_list(self):
        try:
            return sorted(f for f in os.listdir(self._hs_dir) if f.endswith(".pcap"))
        except Exception:
            return []

    def on_webhook(self, path, request):
        from flask import jsonify, abort
        action = request.args.get("action", "")
        if action == "status":
            return jsonify(self._status())
        if action == "pwndex":
            return jsonify(self._pwndex())
        if action == "upload_all":
            ok, msg = self._upload_all()
            return jsonify(ok=ok, msg=msg)
        if action == "pcaps":
            return jsonify(self._pcap_list())
        if action == "pcap":
            from flask import send_file
            name = os.path.basename(request.args.get("name") or "")
            p = os.path.join(self._hs_dir, name)
            if name.endswith(".pcap") and os.path.isfile(p):
                return send_file(p, as_attachment=True)
            abort(404)
        if action == "plugins":
            out = []
            try:
                cfg = self._agent.config() if self._agent else {}
                pl = (cfg.get("main", {}) or {}).get("plugins", {}) or {}
                for name, v in pl.items():
                    en = bool(v.get("enabled")) if isinstance(v, dict) else False
                    out.append({"name": name, "enabled": en, "path": "/plugins/%s/" % name})
            except Exception:
                pass
            out.sort(key=lambda x: (not x["enabled"], x["name"]))
            return jsonify(out)
        if action == "exec":
            import base64
            raw = request.args.get("cmd") or ""
            try:
                cmd = base64.b64decode(raw).decode("utf-8", "ignore") if raw else ""
            except Exception:
                cmd = raw
            if not cmd.strip():
                return jsonify(ok=False, out="(empty)")
            try:
                r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                                   text=True, timeout=25)
                out = (r.stdout or "") + (r.stderr or "")
                return jsonify(ok=(r.returncode == 0), code=r.returncode, out=out[-4000:])
            except Exception as e:
                return jsonify(ok=False, out=str(e))
        if action == "set":
            mac = (request.args.get("mac") or "").upper()
            pw = request.args.get("pw") or ""
            dex = self._dex()
            key = next((k for k in dex if (k or "").upper() == mac), None)
            if key is None:
                return jsonify(ok=False, msg="not in catalog"), 404
            dex[key]["pw"] = pw
            dex[key]["pw_at"] = int(time.time())
            return jsonify(ok=self._save_dex(dex))
        if action == "control":
            cmd = request.args.get("cmd") or ""
            if cmd not in ("reboot", "shutdown", "restart", "manual", "auto"):
                return jsonify(ok=False, msg="bad cmd"), 400
            return jsonify(ok=self._control(cmd), cmd=cmd)
        abort(404)
