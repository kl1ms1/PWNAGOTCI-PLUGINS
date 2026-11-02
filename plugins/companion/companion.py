"""
companion — a small JSON API on the pwnagotchi so the Pwn Companion app can show
live info, browse/edit the pwndex catalog, and control the device.

All actions are GET (so no CSRF token is needed from the app):

  GET /plugins/companion/?action=status
      -> {name, mode, uptime, temp, cpu, mem, sd_free, pcaps, networks,
          cracked, shakes}
  GET /plugins/companion/?action=pwndex
      -> [{ssid, mac, pw, caught, last, pw_at}, ...]  (your network catalog)
  GET /plugins/companion/?action=set&mac=AA:..&pw=secret
      -> {ok} : set/replace the password for a catalogued network
  GET /plugins/companion/?action=control&cmd=reboot|shutdown|restart|manual|auto
      -> {ok} : device control

Config:
  main.plugins.companion.enabled = true
  main.plugins.companion.pwndex  = "/root/.pwndex/dex.json"

Own device / your own networks only.
"""

import json
import logging
import os
import socket
import subprocess
import time

import pwnagotchi.plugins as plugins


class Companion(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "JSON API for the Pwn Companion app (status, pwndex, control)."

    def __init__(self):
        self._dex_f = "/root/.pwndex/dex.json"
        self._hs_dir = "/home/pi/handshakes"
        self._name = "pwnagotchi"
        self._shakes = 0
        self._cpu_prev = None

    def on_loaded(self):
        o = self.options or {}
        self._dex_f = o.get("pwndex", self._dex_f)
        logging.info("[companion] loaded")

    def on_ready(self, agent):
        try:
            cfg = agent.config()
            self._name = cfg.get("main", {}).get("name") or socket.gethostname()
            self._hs_dir = cfg["bettercap"].get("handshakes", self._hs_dir)
        except Exception:
            self._name = socket.gethostname()

    def on_handshake(self, agent, filename, access_point, client_station):
        self._shakes += 1

    # --- metrics -----------------------------------------------------------
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
            t0, i0 = snap()
            time.sleep(0.1)
            t1, i1 = snap()
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
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            return round(100.0 * (total - avail) / total, 1) if total else None
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
            logging.exception("[companion] save dex")
            return False

    @staticmethod
    def _mode():
        # pwnagotchi uses a flag file for manual mode
        return "manual" if os.path.exists("/root/.pwnagotchi-manual") else "auto"

    def _status(self):
        dex = self._dex()
        cracked = sum(1 for e in dex.values() if e.get("pw"))
        return {
            "name": self._name, "mode": self._mode(),
            "uptime": self._read_uptime(), "temp": self._read_temp(),
            "cpu": self._read_cpu(), "mem": self._read_mem(),
            "sd_free": self._sd_free(), "pcaps": self._pcaps(),
            "networks": len(dex), "cracked": cracked, "shakes": self._shakes,
        }

    def _pwndex(self):
        out = []
        for mac, e in self._dex().items():
            out.append({
                "ssid": e.get("ssid") or "(hidden)", "mac": (mac or "").upper(),
                "pw": e.get("pw") or "", "caught": bool(e.get("caught")),
                "last": e.get("last") or 0, "pw_at": e.get("pw_at") or 0,
            })
        out.sort(key=lambda x: (x["pw"] == "", x["ssid"].lower()))
        return out

    # --- control -----------------------------------------------------------
    @staticmethod
    def _sh(args):
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def _control(self, cmd):
        if cmd == "reboot":
            return self._sh(["systemctl", "reboot"])
        if cmd == "shutdown":
            return self._sh(["systemctl", "poweroff"])
        if cmd == "restart":
            return self._sh(["systemctl", "restart", "pwnagotchi"])
        if cmd in ("manual", "auto"):
            flag = "/root/.pwnagotchi-manual"
            try:
                if cmd == "manual":
                    open(flag, "a").close()
                elif os.path.exists(flag):
                    os.remove(flag)
            except Exception:
                return False
            return self._sh(["systemctl", "restart", "pwnagotchi"])
        return False

    # --- web ---------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        action = request.args.get("action", "")
        if action == "status":
            return jsonify(self._status())
        if action == "pwndex":
            return jsonify(self._pwndex())
        if action == "set":
            mac = (request.args.get("mac") or "").upper()
            pw = request.args.get("pw") or ""
            dex = self._dex()
            key = next((k for k in dex if (k or "").upper() == mac), None)
            if key is None:
                return jsonify(ok=False, msg="network not in catalog"), 404
            dex[key]["pw"] = pw
            dex[key]["pw_at"] = int(time.time())
            return jsonify(ok=self._save_dex(dex))
        if action == "control":
            cmd = request.args.get("cmd") or ""
            if cmd not in ("reboot", "shutdown", "restart", "manual", "auto"):
                return jsonify(ok=False, msg="bad cmd"), 400
            return jsonify(ok=self._control(cmd), cmd=cmd)
        abort(404)
