"""
deauth-announcer — pwnagotchi говорит ИМЯ устройства вместо MAC.

Вместо родного "Kickbanning A4:83:E7:11:22:33" он скажет "кикаю Apple".
Работает подменой метода voice.Voice.on_deauth В ПАМЯТИ (сам voice.py не трогаем,
поэтому обновления pwnagotchi это не стирают). Никаких лишних строк на экране —
меняется та самая фраза, что он и так произносит.

Бонус: лог в /root/.deauth/log.txt + список последних в веб-морде
(http://<ip>:8080/plugins/deauth-announcer/, только чтение).
"""

import logging
import os
import random
import time

import pwnagotchi.plugins as plugins

# Фразы по умолчанию (RU). {name} подставляется вместо MAC. Меняются в config.toml.
DEFAULT_PHRASES = [
    "глушу {name}",
    "кикаю {name}",
    "отключаю {name}",
    "вырубаю {name}",
    "{name} — без WiFi!",
]


def _nice_name(sta):
    """Имя клиента: hostname -> vendor -> dev-XXXX -> устройство."""
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


class DeauthAnnouncer(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.2.0"
    __license__ = "MIT"
    __description__ = "pwnagotchi говорит имя устройства вместо MAC при деауте."

    def __init__(self):
        self._dir = "/root/.deauth"
        self._log = os.path.join(self._dir, "log.txt")
        self._phrases = DEFAULT_PHRASES
        self._recent = []
        self._patched = False

    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        o = self.options or {}
        if o.get("phrases"):
            self._phrases = list(o.get("phrases"))
        self._patch_voice()
        logging.info("[deauth-announcer] loaded (patched=%s)", self._patched)

    # --- подмена родной фразы деаута --------------------------------------
    def _patch_voice(self):
        try:
            import pwnagotchi.voice as voice
            if not hasattr(voice.Voice, "_da_orig_on_deauth"):
                voice.Voice._da_orig_on_deauth = voice.Voice.on_deauth
            plugin = self

            def _patched(vself, sta):
                try:
                    name = _nice_name(sta)
                    return random.choice(plugin._phrases).format(name=name)
                except Exception:
                    return voice.Voice._da_orig_on_deauth(vself, sta)

            voice.Voice.on_deauth = _patched
            self._patched = True
        except Exception:
            logging.exception("[deauth-announcer] не смог подменить voice.on_deauth")
            self._patched = False

    def on_unload(self, ui):
        # вернуть родной метод
        try:
            import pwnagotchi.voice as voice
            if hasattr(voice.Voice, "_da_orig_on_deauth"):
                voice.Voice.on_deauth = voice.Voice._da_orig_on_deauth
        except Exception:
            pass

    # --- лог + история для веб-морды --------------------------------------
    def on_deauthentication(self, agent, access_point, client_station):
        try:
            who = _nice_name(client_station)
            ap = access_point or {}
            net = ap.get("hostname") or ap.get("essid") or "сеть"
            self._recent.insert(0, {
                "t": int(time.time()), "who": who, "net": net,
                "cmac": (client_station or {}).get("mac", ""),
            })
            self._recent = self._recent[:100]
            try:
                with open(self._log, "a", encoding="utf-8") as f:
                    f.write("%s %s ▸ %s\n" %
                            (time.strftime("%Y-%m-%d %H:%M:%S"), who, net))
            except Exception:
                pass
        except Exception:
            logging.exception("[deauth-announcer] on_deauth")

    # --- web (только чтение) ----------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method != "GET":
            abort(405)
        if request.args.get("action") == "data":
            return jsonify(ok=True, items=self._recent, patched=self._patched)
        if path in (None, "", "/"):
            return _PAGE
        abort(404)


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>deauth-announcer</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;--fg:#e6edf3}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px}
.wrap{max-width:560px;margin:0 auto}h1{font-size:1.3rem}
.sub{color:var(--mut);font-size:.8rem;margin-bottom:10px}
.row{background:var(--card);border:1px solid var(--line);border-left:3px solid #f85149;
border-radius:10px;padding:9px 12px;margin:7px 0;display:flex;justify-content:space-between;gap:8px}
.who{font-weight:600}.net{color:var(--mut);font-size:.85rem}
.age{color:var(--mut);font-size:.78rem;white-space:nowrap}
.empty{color:var(--mut);text-align:center;padding:30px 0}
.muted{color:var(--mut);font-size:.78rem;text-align:center;margin-top:14px}
</style></head><body><div class="wrap">
<h1>📢 deauth-announcer</h1>
<div class="sub" id="sub"></div>
<div id="list"><div class="empty">загрузка…</div></div>
<div class="muted">pwnagotchi говорит имя вместо MAC · только свои сети 🫡</div>
</div>
<script>
const BASE="/plugins/deauth-announcer/";
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function age(t){const d=Date.now()/1000-t;if(d<60)return Math.round(d)+"с";
  if(d<3600)return Math.round(d/60)+"м";return Math.round(d/3600)+"ч";}
async function load(){
  try{const j=await (await fetch(BASE+"?action=data",{credentials:"same-origin"})).json();
    document.getElementById("sub").textContent = j.patched ? "фраза деаута подменена ✓" : "⚠ подмена не применилась";
    const it=j.items||[];
    document.getElementById("list").innerHTML = it.length
      ? it.map(e=>'<div class="row"><div><div class="who">'+esc(e.who)
          +'</div><div class="net">▸ '+esc(e.net)+'</div></div><div class="age">'+age(e.t)+'</div></div>').join("")
      : '<div class="empty">пока никого не глушили</div>';
  }catch(e){}
}
load(); setInterval(load,5000);
</script></body></html>"""
