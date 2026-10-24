"""
vslider — a VIRTUAL slider for pwnagotchi (web UI), stand-in for the future
hardware 3-position switch.

Positions:
  1. Auto      — normal pwnagotchi hunting (resumes wifi recon).
  2. Dashboard — FULLY pauses hunting (wifi.recon off — like manual mode, nothing
                 is searched, radio quiet) and shows a tabbed dashboard:
                   • Охота   — hunt stats + connection info (+ QR placeholder)
                   • Система — temp / CPU / memory / SD, live graphs
                   • Комикс  — a procedural 3-frame "comic of the day"
                   • Пароли  — Cracked networks (wpa-sec + pwndex) + nearby
                   • №5      — reserved
                 Tabs auto-rotate (Охота 5s · Система 15s · Комикс 5s ·
                 Пароли 10s(2×5s) · №5 5s). Values refresh live.
  3. ???       — reserved.

Open: http://<ip>:8080/plugins/vslider/

v1 is web-only. The real Wi-Fi-join QR and Sync upload come with the AP/Sync
feature (position 3). Your own networks / authorized tests only.
"""

import json
import logging
import os
import time
from collections import deque

import pwnagotchi.plugins as plugins

POS_AUTO, POS_DASH, POS_X = 1, 2, 3
HIST = 60


class Vslider(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.2.0"
    __license__ = "MIT"
    __description__ = "Virtual slider: Auto / tabbed Dashboard / reserved (web UI)."

    def __init__(self):
        self._dir = "/root/.vslider"
        self._state_f = os.path.join(self._dir, "state.json")
        self._stats_f = os.path.join(self._dir, "stats.json")
        self._pos = POS_AUTO
        self._agent = None
        self._cpu_prev = None
        self._hist = {"temp": deque(maxlen=HIST), "cpu": deque(maxlen=HIST),
                      "mem": deque(maxlen=HIST)}
        self._hist_t = deque(maxlen=HIST)   # timestamp per sample (for the time axis)
        self._nearby = []                 # current scan: [{ssid,mac,ch,rssi}]
        self._hs_total = 0                # all-time handshakes (persisted)
        self._hs_session = 0
        self._hs_times = deque(maxlen=500)  # timestamps for rate
        self._streak = 0
        self._last_day = ""
        # paths (resolved on ready)
        self._dex_f = "/root/.pwndex/dex.json"
        self._hs_dir = "/home/pi/handshakes"
        self._potfile = os.path.join(self._hs_dir, "wpa-sec.cracked.potfile")
        self._conn = {"ssid": "pwn-ap", "pass": "changeme", "web": ""}

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        o = self.options or {}
        self._conn["ssid"] = o.get("ap_ssid", self._conn["ssid"])
        self._conn["pass"] = o.get("ap_pass", self._conn["pass"])
        self._conn["web"] = o.get("web", self._conn["web"])
        self._dex_f = o.get("pwndex", self._dex_f)
        self._load_state()
        self._load_stats()
        logging.info("[vslider] loaded (pos=%d, hs_total=%d)", self._pos, self._hs_total)

    def on_ready(self, agent):
        self._agent = agent
        try:
            cfg = agent.config()
            self._hs_dir = cfg["bettercap"].get("handshakes", self._hs_dir)
            self._potfile = os.path.join(self._hs_dir, "wpa-sec.cracked.potfile")
            if not self._conn["web"]:
                self._conn["web"] = "http://10.0.0.2:8080"
        except Exception:
            pass
        self._apply()

    def on_epoch(self, agent, epoch, epoch_data):
        self._agent = agent
        self._sample_sys()
        if self._pos == POS_DASH:
            self._run("wifi.recon off")   # keep hunting fully paused

    def on_handshake(self, agent, filename, access_point, client_station):
        self._hs_total += 1
        self._hs_session += 1
        now = int(time.time())
        self._hs_times.append(now)
        self._bump_streak(now)
        self._save_stats()

    def on_wifi_update(self, agent, access_points):
        try:
            near = []
            for ap in access_points or []:
                mac = (ap.get("mac") or ap.get("bssid") or "").upper()
                near.append({"ssid": ap.get("hostname") or ap.get("essid") or ap.get("ssid") or "",
                             "mac": mac, "ch": ap.get("channel") or 0,
                             "rssi": ap.get("rssi") or -99})
            self._nearby = near
        except Exception:
            pass

    # --- position ----------------------------------------------------------
    def _run(self, cmd):
        if self._agent is None:
            return
        try:
            self._agent.run(cmd)
        except Exception:
            logging.debug("[vslider] run failed: %s", cmd)

    def _apply(self):
        if self._pos == POS_AUTO:
            self._run("wifi.recon on")
        elif self._pos == POS_DASH:
            self._run("wifi.recon off")

    # --- persistence -------------------------------------------------------
    def _load_state(self):
        try:
            with open(self._state_f, encoding="utf-8") as f:
                self._pos = int(json.load(f).get("pos", POS_AUTO))
        except Exception:
            self._pos = POS_AUTO

    def _save_state(self):
        try:
            with open(self._state_f + ".tmp", "w", encoding="utf-8") as f:
                json.dump({"pos": self._pos}, f)
            os.replace(self._state_f + ".tmp", self._state_f)
        except Exception:
            pass

    def _load_stats(self):
        try:
            with open(self._stats_f, encoding="utf-8") as f:
                d = json.load(f)
            self._hs_total = int(d.get("hs_total", 0))
            self._streak = int(d.get("streak", 0))
            self._last_day = d.get("last_day", "")
        except Exception:
            pass

    def _save_stats(self):
        try:
            with open(self._stats_f + ".tmp", "w", encoding="utf-8") as f:
                json.dump({"hs_total": self._hs_total, "streak": self._streak,
                           "last_day": self._last_day}, f)
            os.replace(self._stats_f + ".tmp", self._stats_f)
        except Exception:
            pass

    def _bump_streak(self, now):
        day = time.strftime("%Y-%m-%d", time.localtime(now))
        if day == self._last_day:
            return
        # new active day: if it's the very next day keep streak, else reset to 1
        yday = time.strftime("%Y-%m-%d", time.localtime(now - 86400))
        self._streak = self._streak + 1 if self._last_day == yday else 1
        self._last_day = day

    # --- metrics -----------------------------------------------------------
    def _read_temp(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            return 0.0

    def _read_cpu(self):
        try:
            with open("/proc/stat") as f:
                parts = [int(x) for x in f.readline().split()[1:]]
            idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
            total = sum(parts)
            pct = 0.0
            if self._cpu_prev:
                dt, di = total - self._cpu_prev[0], idle - self._cpu_prev[1]
                pct = 100.0 * (dt - di) / dt if dt > 0 else 0.0
            self._cpu_prev = (total, idle)
            return round(max(0.0, min(100.0, pct)), 1)
        except Exception:
            return 0.0

    def _read_mem(self):
        try:
            info = {}
            with open("/proc/meminfo") as f:
                for ln in f:
                    k, _, v = ln.partition(":")
                    info[k] = int(v.split()[0])
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            return round(100.0 * (total - avail) / total, 1) if total else 0.0
        except Exception:
            return 0.0

    def _read_uptime(self):
        try:
            with open("/proc/uptime") as f:
                return int(float(f.read().split()[0]))
        except Exception:
            return 0

    def _read_sd(self):
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used_pct = round(100.0 * (total - free) / total, 1) if total else 0.0
            free_gb = round(free / (1024 ** 3), 1)
            return used_pct, free_gb
        except Exception:
            return 0.0, 0.0

    def _read_load(self):
        try:
            with open("/proc/loadavg") as f:
                return round(float(f.read().split()[0]), 2)
        except Exception:
            return 0.0

    def _read_freq(self):
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
                return int(int(f.read().strip()) / 1000)   # MHz
        except Exception:
            return 0

    def _read_throttled(self):
        try:
            import subprocess
            out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                                  text=True, timeout=3).stdout
            val = int(out.strip().split("=")[1], 16)
            if val == 0:
                return "OK"
            flags = []
            if val & 0x1:
                flags.append("undervolt")
            if val & 0x4:
                flags.append("throttle")
            if val & 0x50000:
                flags.append("было")
            return ",".join(flags) or "⚠"
        except Exception:
            return "н/д"

    @staticmethod
    def _port_open(port):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False
        finally:
            s.close()

    def _read_ip(self):
        try:
            import subprocess
            out = subprocess.run(["hostname", "-I"], capture_output=True,
                                 text=True, timeout=3).stdout.split()
            return out[0] if out else "—"
        except Exception:
            return "—"

    def _pcap_count(self):
        try:
            return sum(1 for f in os.listdir(self._hs_dir) if f.endswith(".pcap"))
        except Exception:
            return 0

    def _sample_sys(self):
        self._hist["temp"].append(self._read_temp())
        self._hist["cpu"].append(self._read_cpu())
        self._hist["mem"].append(self._read_mem())
        self._hist_t.append(int(time.time()))

    # --- pwndex / wpa-sec --------------------------------------------------
    def _read_dex(self):
        try:
            with open(self._dex_f, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _potfile_ssids(self):
        """Set of (ssid_lower, mac_upper) that appear in the wpa-sec potfile."""
        ssids, macs = set(), set()
        try:
            with open(self._potfile, encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    for sep in ("*", ":"):
                        if sep in ln:
                            p = ln.strip().split(sep)
                            if len(p) >= 4:
                                m = p[0].replace(":", "").replace("-", "").lower()
                                if len(m) == 12:
                                    macs.add(":".join(m[i:i+2] for i in range(0, 12, 2)).upper())
                                try:
                                    ssids.add(bytes.fromhex(p[2]).decode("utf-8", "ignore").lower())
                                except Exception:
                                    ssids.add(p[2].lower())
                            break
        except Exception:
            pass
        return ssids, macs

    def _src_of(self, e, pot_ssids, pot_macs):
        mac = (e.get("mac") or "").upper()
        ssid = (e.get("ssid") or "").lower()
        if mac in pot_macs or (ssid and ssid in pot_ssids):
            return "wpa"
        return "pdx"

    def _cracked(self, dex, pot_ssids, pot_macs):
        items = [e for e in dex.values() if e.get("pw")]
        items.sort(key=lambda e: e.get("last", 0), reverse=True)   # newest first
        out = []
        for e in items[:50]:
            out.append({"ssid": e.get("ssid") or "(hidden)", "pw": e.get("pw"),
                        "src": self._src_of(e, pot_ssids, pot_macs)})
        return out

    def _nearby_list(self, dex, pot_ssids, pot_macs):
        by_mac = {(k or "").upper(): v for k, v in dex.items()}
        withpw, nopw = [], []
        seen = set()
        for ap in self._nearby:
            mac = ap["mac"]
            if not mac or mac in seen:
                continue
            seen.add(mac)
            e = by_mac.get(mac)
            name = ap["ssid"] or (e.get("ssid") if e else "") or "(hidden)"
            if e and e.get("pw"):
                withpw.append({"ssid": name, "pw": e["pw"],
                               "src": self._src_of(e, pot_ssids, pot_macs), "rssi": ap["rssi"]})
            else:
                nopw.append({"ssid": name, "pw": "", "src": "non", "rssi": ap["rssi"]})
        withpw.sort(key=lambda x: x["rssi"], reverse=True)
        nopw.sort(key=lambda x: x["rssi"], reverse=True)
        return withpw + nopw[:30]

    # --- data assembly -----------------------------------------------------
    def _hunt(self, dex):
        now = int(time.time())
        per_min = sum(1 for t in self._hs_times if t >= now - 60)
        with_pw = sum(1 for e in dex.values() if e.get("pw"))
        total_nets = len(dex)
        caught = sum(1 for e in dex.values() if e.get("caught"))
        ch = {}
        for ap in self._nearby:
            if ap["ch"]:
                ch[ap["ch"]] = ch.get(ap["ch"], 0) + 1
        top_ch = max(ch, key=ch.get) if ch else "-"
        return {"total": self._hs_total, "session": self._hs_session, "per_min": per_min,
                "temp": self._read_temp(), "nets_total": total_nets, "nets_pw": with_pw,
                "caught": caught, "seen": total_nets, "top_ch": top_ch,
                "nearby": len(self._nearby), "streak": self._streak,
                "status": "на охоте" if self._pos == POS_AUTO else "на паузе"}

    def _sys(self):
        used, free = self._read_sd()
        return {"temp": self._read_temp(), "cpu": self._read_cpu(), "mem": self._read_mem(),
                "sd_used": used, "sd_free": free, "uptime": self._read_uptime(),
                "load": self._read_load(), "freq": self._read_freq(),
                "throttled": self._read_throttled(), "ip": self._read_ip(),
                "pcaps": self._pcap_count(), "nearby": len(self._nearby),
                "bettercap": self._port_open(8081), "pwngrid": self._port_open(8666),
                "span": round((time.time() - self._hist_t[0]) / 60.0, 1) if self._hist_t else 0,
                "h": {k: list(v) for k, v in self._hist.items()}}

    def _comic(self, hunt):
        """3 procedural frames based on state (no hand-drawn art)."""
        hot = hunt["per_min"] > 0
        hour = int(time.strftime("%H"))
        morning = 5 <= hour < 11
        night = hour >= 23 or hour < 5
        if night:
            return [{"f": "(-_-) zzz", "c": "ночь, сплю…"},
                    {"f": "(._.)", "c": "кто там?"},
                    {"f": "(-_-) zzz", "c": "ладно, дальше спать"}]
        if hot:
            return [{"f": "(•‿•)", "c": "утро! эфир спит" if morning else "слушаю эфир"},
                    {"f": "(⌐■_■)", "c": "о, добыча!"},
                    {"f": "(♥‿♥)", "c": "+%d рукопожатий!" % hunt["per_min"]}]
        return [{"f": "(•‿•)", "c": "доброе утро!" if morning else "на дежурстве"},
                {"f": "(・_・)", "c": "ищу цели…"},
                {"f": "(ー_ー)", "c": "тихо сегодня"}]

    # --- web ---------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method == "GET":
            if request.args.get("action") == "data":
                dex = self._read_dex()
                pot_ssids, pot_macs = self._potfile_ssids()
                hunt = self._hunt(dex)
                return jsonify(ok=True, pos=self._pos, hunt=hunt, sys=self._sys(),
                               cracked=self._cracked(dex, pot_ssids, pot_macs),
                               nearby=self._nearby_list(dex, pot_ssids, pot_macs),
                               comic=self._comic(hunt), conn=self._conn)
            if path in (None, "", "/"):
                return self._page()
            abort(404)
        body = {}
        try:
            raw = request.get_data(as_text=True)
            if raw:
                body = json.loads(raw)
        except Exception:
            body = {}
        if request.args.get("action") == "setpos":
            try:
                pos = int(body.get("pos"))
            except Exception:
                return jsonify(ok=False, msg="bad pos"), 400
            if pos not in (POS_AUTO, POS_DASH, POS_X):
                return jsonify(ok=False, msg="bad pos"), 400
            self._pos = pos
            self._apply()
            self._save_state()
            return jsonify(ok=True, pos=self._pos)
        abort(404)

    def _page(self):
        token = ""
        try:
            from flask_wtf.csrf import generate_csrf
            token = generate_csrf()
        except Exception:
            token = ""
        return _PAGE.replace("__CSRF__", token)


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vslider</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;--fg:#e6edf3;--acc:#1f6feb;--ok:#238636;--gold:#d29922;--pur:#6e40c9}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:14px;line-height:1.4}
.wrap{max-width:460px;margin:0 auto}h1{font-size:1.25rem;margin:.2em 0}
.sub{color:var(--mut);font-size:.8rem;margin-bottom:12px}
.slider{display:flex;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:6px;gap:6px}
.pos{flex:1;text-align:center;padding:12px 6px;border-radius:10px;cursor:pointer;font-weight:600;transition:.15s;font-size:.9rem}
.pos small{display:block;font-weight:400;color:var(--mut);font-size:.68rem;margin-top:3px}
.pos.on{color:#fff}.pos.on small{color:#dbe7ff}
.pos.on[data-p="1"]{background:var(--ok)}.pos.on[data-p="2"]{background:var(--acc)}.pos.on[data-p="3"]{background:var(--pur)}
.panel{margin-top:14px}
.status{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;text-align:center}
.status .big{font-size:1.05rem;font-weight:600}.status .hint{color:var(--mut);font-size:.82rem;margin-top:4px}
.win{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.tabs{display:flex;background:#0b0f14;border-bottom:1px solid var(--line)}
.tb{flex:1;text-align:center;padding:9px 2px;font-size:11px;color:var(--mut);border-right:1px solid #22262d;white-space:nowrap}
.tb:last-child{border-right:0}.tb.on{background:var(--card);color:#fff;font-weight:700;box-shadow:inset 0 -3px 0 var(--acc)}
.bd{padding:13px;min-height:220px}
.row{display:flex;gap:12px}
.qr{width:104px;height:104px;background:#223;border:1px dashed #456;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#8aa;font-size:10px;text-align:center;padding:6px}
.qrcap{font-size:9px;color:var(--mut);text-align:center;margin-top:4px}
.ul{margin-top:4px}
.u,.s{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;border-bottom:1px dashed #22262d}
.u .k,.s .k{color:var(--mut)}.u .v,.s .v{font-weight:700}
.right{flex:1}.s.fun .k{color:var(--gold)}
.conn{margin-top:9px;font-size:10px;color:#79b8ff;text-align:center;background:#0b0f14;border:1px solid #22262d;border-radius:7px;padding:5px 8px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.q{background:#0b0f14;border:1px solid var(--line);border-radius:11px;padding:11px}
.q .ql{color:var(--mut);font-size:12px;display:flex;justify-content:space-between;align-items:baseline}
.q .qv{font-weight:800;font-size:18px}.q .qv small{font-size:11px;color:var(--mut);font-weight:400}
.qsub{font-size:11px;color:var(--mut);margin-top:8px}
.xax{display:flex;justify-content:space-between;font-size:9px;color:var(--mut);margin-top:3px}
.spk{width:100%;height:38px;display:block;margin-top:6px}
.frames{display:flex;gap:8px}
.frame{flex:1;background:#0b0f14;border:1px solid var(--line);border-radius:11px;padding:12px 6px;text-align:center}
.face{font-size:20px;font-weight:700}.cap{color:#c9d1d9;font-size:11px;margin-top:8px;min-height:30px}
.ttl{text-align:center;font-size:15px;font-weight:800;margin-bottom:8px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:2px 14px}
.e{display:flex;align-items:center;font-size:11.5px;padding:2.5px 0;border-bottom:1px dashed #1c2128}
.e .n{color:var(--mut);width:20px;flex:0 0 20px}
.src{width:8px;height:8px;border-radius:2px;flex:0 0 8px;margin-right:5px}
.wpa{background:var(--acc)}.pdx{background:var(--gold)}.non{background:#30363d}
.e .ssid{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:78px}
.e .dash{color:var(--mut);margin:0 4px}.e .p{font-family:ui-monospace,monospace;color:#7ee2a0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.e .no{color:var(--mut);font-style:italic}
.legend{display:flex;gap:12px;justify-content:center;font-size:10px;color:var(--mut);margin-top:9px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.subdots{display:flex;gap:6px;justify-content:center;margin-top:9px}
.sd2{width:28px;height:4px;border-radius:3px;background:#30363d}.sd2.on{background:var(--gold)}
.muted{color:var(--mut);font-size:.76rem;text-align:center;margin-top:12px}
</style></head><body><div class="wrap">
<h1>🎚️ vslider</h1><div class="sub">виртуальный слайдер · v1 (web)</div>
<div class="slider" id="slider">
  <div class="pos" data-p="1">Auto<small>охота идёт</small></div>
  <div class="pos" data-p="2">Dashboard<small>пауза + инфа</small></div>
  <div class="pos" data-p="3">???<small>скоро</small></div>
</div>
<div class="panel" id="panel"></div>
<div class="muted">pwnagotchi · только свои сети / авторизованный тест 🫡</div>
</div>
<script>
const BASE="/plugins/vslider/", CSRF="__CSRF__";
const $=s=>document.querySelector(s);
let POS=1, D=null, tabIdx=0, pwSub=0, sysSub=0, tabTimer=null, subTimer=null;
const TABS=[
  {id:"hunt",lbl:"🏆 Охота",dur:5000},
  {id:"sys", lbl:"🖥 Система",dur:15000},
  {id:"comic",lbl:"🎞 Комикс",dur:5000},
  {id:"pw",  lbl:"🔑 Пароли",dur:10000},
  {id:"x5",  lbl:"⭐ №5",dur:5000},
];
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function spark(a,col,lo,hi){a=a||[];const W=200,H=38,n=a.length;
  if(n<2)return '<svg class="spk" viewBox="0 0 '+W+' '+H+'"></svg>';
  if(lo==null){lo=Math.min(...a);hi=Math.max(...a);}if(hi<=lo)hi=lo+1;
  const p=a.map((v,i)=>(i/(n-1)*W).toFixed(1)+','+(H-2-((v-lo)/(hi-lo))*(H-4)).toFixed(1)).join(' ');
  return '<svg class="spk" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none"><polyline fill="none" stroke="'+col+'" stroke-width="2" points="'+p+'"/></svg>';}
function upt(s){s=s||0;const d=(s/86400)|0,h=(s%86400/3600)|0,m=(s%3600/60)|0;return d?d+"д "+h+"ч":h?h+"ч "+m+"м":m+"м";}

function tabsBar(act){return '<div class="tabs">'+TABS.map(t=>'<div class="tb'+(t.id===act?' on':'')+'">'+t.lbl+'</div>').join('')+'</div>';}
function pwRows(list,withNo){
  const n=list.length, half=Math.ceil(n/2);
  function cell(e,i){
    const inner = (e.pw||!withNo)?'<span class="dash">-</span><span class="p">'+esc(e.pw)+'</span>'
      :'<span class="dash">-</span><span class="no">нет пароля</span>';
    return '<div class="e"><span class="n">'+(i+1)+'.</span><span class="src '+e.src+'"></span>'
      +'<span class="ssid">'+esc(e.ssid)+'</span>'+inner+'</div>';
  }
  let L="",R="";
  list.forEach((e,i)=>{(i<half?L+=cell(e,i):R+=cell(e,i));});
  return '<div class="cols"><div>'+L+'</div><div>'+R+'</div></div>';
}
function renderTab(){
  if(!D)return "";
  const t=TABS[tabIdx].id;
  if(t==="hunt"){const h=D.hunt,c=D.conn||{};
    return '<div class="row"><div><div class="qr">QR Wi-Fi<br>(с Sync)</div><div class="qrcap">скан → коннект</div>'
      +'<div class="ul"><div class="u"><span class="k">Хеш/мин</span><span class="v">'+h.per_min+'</span></div>'
      +'<div class="u"><span class="k">Всего</span><span class="v">'+h.total+'</span></div>'
      +'<div class="u"><span class="k">За сессию</span><span class="v">'+h.session+'</span></div></div></div>'
      +'<div class="right"><div class="s"><span class="k">Температура</span><span class="v">'+h.temp+' °C</span></div>'
      +'<div class="s"><span class="k">Сетей / с паролем</span><span class="v">'+h.nets_total+' | '+h.nets_pw+'</span></div>'
      +'<div class="s"><span class="k">Поймано / видел</span><span class="v">'+h.caught+' / '+h.seen+'</span></div>'
      +'<div class="s"><span class="k">Топ-канал</span><span class="v">'+h.top_ch+'</span></div>'
      +'<div class="s"><span class="k">Сетей рядом</span><span class="v">'+h.nearby+'</span></div>'
      +'<div class="s fun"><span class="k">🔥 Стрик</span><span class="v">'+h.streak+' дн</span></div>'
      +'<div class="s fun"><span class="k">😎 Статус</span><span class="v">'+esc(h.status)+'</span></div></div></div>'
      +'<div class="conn">📡 Wi-Fi: '+esc(c.ssid)+' · pass: '+esc(c.pass)+' · веб: '+esc((c.web||"").replace("http://",""))+'</div>';
  }
  if(t==="sys"){const s=D.sys,h=s.h||{};
    const tile=(lbl,val,extra)=>'<div class="q"><div class="ql">'+lbl+'<span class="qv">'+val+'</span></div>'+(extra||'')+'</div>';
    let g,cap="";
    if(sysSub===0){
      const ax='<div class="xax"><span>−'+(s.span||0)+'м</span><span>сейчас</span></div>';
      g=tile('🌡 Темп.',s.temp+'<small>°C</small>',spark(h.temp,"#f0883e",null,null)+ax)
       +tile('⚙️ CPU',s.cpu+'<small>%</small>',spark(h.cpu,"#1f6feb",0,100)+ax)
       +tile('🧠 Память',s.mem+'<small>%</small>',spark(h.mem,"#2ea043",0,100)+ax)
       +tile('💾 SD',s.sd_used+'<small>%</small>','<div class="qsub">своб. '+s.sd_free+' ГБ</div>');
      cap='<div class="muted" style="margin-top:6px">графики за последние ~'+(s.span||0)+' мин · ось: раньше → сейчас</div>';
    }else if(sysSub===1){
      const tc=(s.throttled==="OK")?'#3fb950':(s.throttled==="н/д"?'#8b949e':'#f0883e');
      g=tile('📊 Нагрузка',s.load,'')
       +tile('⚡ Частота',s.freq+'<small>МГц</small>','<div class="qsub">троттл: <b style="color:'+tc+'">'+esc(s.throttled)+'</b></div>')
       +tile('⏱ Аптайм',upt(s.uptime),'')
       +tile('📶 Сетей рядом',s.nearby,'');
    }else{
      const dot=ok=>'<span style="color:'+(ok?'#3fb950':'#f85149')+'">●</span> '+(ok?'жив':'нет');
      g=tile('🛰 bettercap',dot(s.bettercap),'')
       +tile('🛰 pwngrid',dot(s.pwngrid),'')
       +tile('🌐 IP','<span style="font-size:13px">'+esc(s.ip)+'</span>','')
       +tile('📥 .pcap',s.pcaps,'');
    }
    const dots=[0,1,2].map(i=>'<span class="sd2'+(i===sysSub?' on':'')+'"></span>').join('');
    return '<div class="grid">'+g+'</div>'+cap+'<div class="subdots">'+dots+'</div>';
  }
  if(t==="comic"){const fr=D.comic||[];
    return '<div class="frames">'+fr.map(f=>'<div class="frame"><div class="face">'+esc(f.f)+'</div><div class="cap">'+esc(f.c)+'</div></div>').join('')+'</div>'
      +'<div class="muted" style="margin-top:12px">комикс дня · генерится из состояния</div>';
  }
  if(t==="pw"){
    if(pwSub===0){
      return '<div class="ttl">Cracked networks</div>'+pwRows(D.cracked||[],false)
        +'<div class="legend"><span><i class="wpa"></i>wpa-sec</span><span><i class="pdx"></i>pwndex</span></div>'
        +'<div class="subdots"><span class="sd2 on"></span><span class="sd2"></span></div>';
    }
    return '<div class="ttl">Nearby</div>'+pwRows(D.nearby||[],true)
      +'<div class="legend"><span><i class="wpa"></i>wpa-sec</span><span><i class="pdx"></i>pwndex</span><span><i class="non"></i>нет пароля</span></div>'
      +'<div class="subdots"><span class="sd2"></span><span class="sd2 on"></span></div>';
  }
  return '<div class="status"><div class="big">⭐ №5 — скоро</div><div class="hint">придумаем вместе</div></div>';
}
function renderPanel(){
  if(!D){$("#panel").innerHTML="";return;}
  if(POS===1){$("#panel").innerHTML='<div class="status"><div class="big">🟢 Auto — охота идёт</div><div class="hint">pwnagotchi сканирует и ловит как обычно.</div></div>';return;}
  if(POS===3){$("#panel").innerHTML='<div class="status"><div class="big">🟣 ??? — скоро</div><div class="hint">придумаем (Sync / Quiet / Disguise…)</div></div>';return;}
  $("#panel").innerHTML='<div class="win">'+tabsBar(TABS[tabIdx].id)+'<div class="bd">'+renderTab()+'</div></div>';
}
function schedTab(){
  clearTimeout(tabTimer);clearInterval(subTimer);subTimer=null;
  if(POS!==2)return;
  const t=TABS[tabIdx];
  if(t.id==="pw"){pwSub=0;subTimer=setInterval(()=>{pwSub=(pwSub+1)%2;renderPanel();},5000);}
  if(t.id==="sys"){sysSub=0;subTimer=setInterval(()=>{sysSub=(sysSub+1)%3;renderPanel();},5000);}
  tabTimer=setTimeout(()=>{tabIdx=(tabIdx+1)%TABS.length;renderPanel();schedTab();},t.dur);
}
function paintSlider(){document.querySelectorAll(".pos").forEach(p=>p.classList.toggle("on",+p.dataset.p===POS));}
async function load(){
  try{const j=await (await fetch(BASE+"?action=data",{credentials:"same-origin"})).json();
    if(!j.ok)return;D=j;if(j.pos!==POS){POS=j.pos;tabIdx=0;pwSub=0;sysSub=0;schedTab();}paintSlider();renderPanel();}
  catch(e){}
}
async function setpos(p){POS=p;tabIdx=0;pwSub=0;sysSub=0;schedTab();paintSlider();renderPanel();
  try{await fetch(BASE+"?action=setpos",{method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":CSRF,"Content-Type":"application/json"},body:JSON.stringify({pos:p})});}catch(e){}
  load();}
document.querySelectorAll(".pos").forEach(p=>p.addEventListener("click",()=>setpos(+p.dataset.p)));
load(); setInterval(load,1000);
</script></body></html>"""
