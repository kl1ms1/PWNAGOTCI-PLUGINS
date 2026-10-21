"""
deauth-announcer — показывает, КОГО глушит pwnagotchi, по имени/вендору,
а не по голому MAC. «глушу: Apple ▸ MyWiFi» вместо «deauth A4:83:E7:...».

Пишет на e-ink строку + ведёт лог + отдаёт список в веб-морде
(http://<ip>:8080/plugins/deauth-announcer/).
"""

import logging
import os
import random
import time

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import Text
from pwnagotchi.ui.view import BLACK

VERBS = ["глушу", "кикаю", "отключаю", "вырубаю"]


class DeauthAnnouncer(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "Объявляет цель деаута по имени/вендору, а не по MAC."

    def __init__(self):
        self._dir = "/root/.deauth"
        self._log = os.path.join(self._dir, "log.txt")
        self._last = ""
        self._pos = (0, 95)
        self._show_ui = True
        self._recent = []

    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        o = self.options or {}
        if o.get("position"):
            try:
                x, y = str(o["position"]).split(",")
                self._pos = (int(x), int(y))
            except Exception:
                pass
        if o.get("show_ui") is not None:
            self._show_ui = bool(o.get("show_ui"))
        logging.info("[deauth-announcer] loaded")

    # --- e-ink ------------------------------------------------------------
    def on_ui_setup(self, ui):
        if not self._show_ui:
            return
        try:
            font = getattr(fonts, "Small", None) or fonts.Medium
            ui.add_element("deauth", Text(value="", position=self._pos,
                                          font=font, color=BLACK))
        except Exception:
            logging.exception("[deauth-announcer] ui setup")

    def on_ui_update(self, ui):
        if self._show_ui and self._last:
            try:
                ui.set("deauth", self._last)
            except Exception:
                pass

    def on_unload(self, ui):
        try:
            with ui._lock:
                ui.remove_element("deauth")
        except Exception:
            pass

    # --- имя вместо MAC ---------------------------------------------------
    @staticmethod
    def _name(sta, ap):
        sta = sta or {}
        for k in ("hostname", "name"):
            v = sta.get(k)
            if v and v not in ("", "?"):
                return v
        v = sta.get("vendor") or sta.get("manufacturer")
        if v:
            return v
        mac = (sta.get("mac") or "").replace(":", "")
        if len(mac) >= 4:
            return "dev-" + mac[-4:].upper()
        return "устройство"

    def on_deauthentication(self, agent, access_point, client_station):
        try:
            who = self._name(client_station, access_point)
            ap = access_point or {}
            net = ap.get("hostname") or ap.get("essid") or "сеть"
            msg = "%s: %s ▸ %s" % (random.choice(VERBS), who, net)
            self._last = msg
            self._recent.insert(0, {
                "t": int(time.time()), "who": who, "net": net,
                "cmac": (client_station or {}).get("mac", ""),
                "amac": ap.get("mac", ""),
            })
            self._recent = self._recent[:100]
            try:
                with open(self._log, "a", encoding="utf-8") as f:
                    f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
            except Exception:
                pass
            logging.info("[deauth-announcer] %s", msg)
        except Exception:
            logging.exception("[deauth-announcer] on_deauth")

    # --- web (только чтение, без POST → без CSRF) -------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method != "GET":
            abort(405)
        if request.args.get("action") == "data":
            return jsonify(ok=True, items=self._recent)
        if path in (None, "", "/"):
            return _PAGE
        abort(404)


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>deauth-announcer</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;--fg:#e6edf3}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px}
.wrap{max-width:560px;margin:0 auto}h1{font-size:1.3rem}
.row{background:var(--card);border:1px solid var(--line);border-left:3px solid #f85149;
border-radius:10px;padding:9px 12px;margin:7px 0;display:flex;justify-content:space-between;gap:8px}
.who{font-weight:600}.net{color:var(--mut);font-size:.85rem}
.age{color:var(--mut);font-size:.78rem;white-space:nowrap}
.empty{color:var(--mut);text-align:center;padding:30px 0}
.muted{color:var(--mut);font-size:.78rem;text-align:center;margin-top:14px}
</style></head><body><div class="wrap">
<h1>📢 deauth-announcer</h1>
<div id="list"><div class="empty">загрузка…</div></div>
<div class="muted">кого глушил — по имени · только свои сети 🫡</div>
</div>
<script>
const BASE="/plugins/deauth-announcer/";
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function age(t){const d=Date.now()/1000-t;if(d<60)return Math.round(d)+"с";
  if(d<3600)return Math.round(d/60)+"м";return Math.round(d/3600)+"ч";}
async function load(){
  try{const j=await (await fetch(BASE+"?action=data",{credentials:"same-origin"})).json();
    const it=j.items||[];
    document.getElementById("list").innerHTML = it.length
      ? it.map(e=>'<div class="row"><div><div class="who">'+esc(e.who)
          +'</div><div class="net">▸ '+esc(e.net)+'</div></div><div class="age">'+age(e.t)+'</div></div>').join("")
      : '<div class="empty">пока никого не глушили</div>';
  }catch(e){}
}
load(); setInterval(load,5000);
</script></body></html>"""
