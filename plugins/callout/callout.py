"""
callout — pwnagotchi calls out the deauth victim by NAME instead of its MAC.

Instead of "Kickbanning A4:83:E7:11:22:33" it says "Kicking Ivan-PC off."
It patches voice.Voice.on_deauth IN MEMORY (the voice.py file is left untouched,
so pwnagotchi updates don't wipe it). There is no extra line on screen — it
changes the very phrase pwnagotchi already speaks.

Web UI (http://<ip>:8080/plugins/callout/): a "Test phrase" button (shows what it
would say right on the e-ink, without waiting for a real deauth) plus a list of
recent targets by name. Log: /root/.callout/log.txt.
"""

import logging
import os
import random
import time

import pwnagotchi.plugins as plugins

# Phrases are proper sentences: capitalized, with a period, and varied.
# {name} is the device name.
DEFAULT_PHRASES = [
    "Kicking {name} off.",
    "Jamming {name}.",
    "Deauthing {name}.",
    "Dropping {name} now.",
    "No WiFi for {name}.",
    "{name} is out.",
    "Booting {name} off the air.",
    "Bye-bye, {name}.",
    "Pressing F for {name}.",
    "Cutting {name} loose.",
]

# Demo clients for the Test button (mix of names and vendors).
FAKE = [
    {"hostname": "Ivan-PC"}, {"hostname": "Galaxy-S21"}, {"vendor": "Apple"},
    {"vendor": "Xiaomi", "mac": "a4:50:46:9f:4f:2a"}, {"vendor": "TP-Link"},
    {"mac": "aa:bb:cc:11:22:33"},
]


def _nice_name(sta):
    """Device name: hostname first; else vendor+MAC tail; else Device-XXXX.

    The goal is to always show a device-looking NAME (even an ugly one) rather
    than just the vendor/company.
    """
    sta = sta or {}
    for k in ("hostname", "name"):
        v = sta.get(k)
        if v and v not in ("", "?"):
            return v
    mac = (sta.get("mac") or "").replace(":", "").replace("-", "").upper()
    tail = mac[-4:] if len(mac) >= 4 else ""
    vendor = sta.get("vendor") or sta.get("manufacturer")
    if vendor:
        vendor = vendor.split()[0]
        return "%s-%s" % (vendor, tail) if tail else vendor
    if tail:
        return "Device-" + tail
    return "device"


class Callout(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.5.0"
    __license__ = "MIT"
    __description__ = "pwnagotchi calls out the deauth victim by name, not MAC."

    def __init__(self):
        self._dir = "/root/.callout"
        self._log = os.path.join(self._dir, "log.txt")
        self._phrases = DEFAULT_PHRASES
        self._recent = []
        self._patched = False
        # showing the phrase on the e-ink itself
        self._ui = None
        self._say_text = ""        # what the device is "saying" for the test
        self._say_until = 0.0      # until when to hold it on screen
        self._hold = 6             # seconds to hold the test phrase on screen

    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        o = self.options or {}
        if o.get("phrases"):
            self._phrases = list(o.get("phrases"))
        try:
            self._hold = int(o.get("test_seconds", self._hold))
        except Exception:
            pass
        self._patch_voice()
        logging.info("[callout] loaded (patched=%s)", self._patched)

    # --- replace the native deauth phrase ---------------------------------
    def _patch_voice(self):
        try:
            import pwnagotchi.voice as voice
            if not hasattr(voice.Voice, "_callout_orig"):
                voice.Voice._callout_orig = voice.Voice.on_deauth
            plugin = self

            def _patched(vself, sta):
                try:
                    return random.choice(plugin._phrases).format(name=_nice_name(sta))
                except Exception:
                    return voice.Voice._callout_orig(vself, sta)

            voice.Voice.on_deauth = _patched
            self._patched = True
        except Exception:
            logging.exception("[callout] could not patch voice.on_deauth")
            self._patched = False

    def on_unload(self, ui):
        try:
            import pwnagotchi.voice as voice
            if hasattr(voice.Voice, "_callout_orig"):
                voice.Voice.on_deauth = voice.Voice._callout_orig
        except Exception:
            pass

    # --- log + history ----------------------------------------------------
    def _record(self, who, net):
        self._recent.insert(0, {"t": int(time.time()), "who": who, "net": net})
        self._recent = self._recent[:100]
        try:
            with open(self._log, "a", encoding="utf-8") as f:
                f.write("%s %s -> %s\n" %
                        (time.strftime("%Y-%m-%d %H:%M:%S"), who, net))
        except Exception:
            pass

    def on_deauthentication(self, agent, access_point, client_station):
        try:
            who = _nice_name(client_station)
            ap = access_point or {}
            self._record(who, ap.get("hostname") or ap.get("essid") or "network")
        except Exception:
            logging.exception("[callout] on_deauth")

    # --- show the phrase on the e-ink -------------------------------------
    # Grab the display (view) via UI hooks — more reliable than agent.view().
    def on_ui_setup(self, ui):
        self._ui = ui

    def on_ui_update(self, ui):
        self._ui = ui
        # while a test is active, keep the phrase in the speech line so
        # pwnagotchi doesn't immediately overwrite it with its own text.
        if self._say_text and time.time() < self._say_until:
            try:
                ui.set("status", self._say_text)
                import pwnagotchi.ui.faces as faces
                face = getattr(faces, "ANGRY", None) or getattr(faces, "INTENSE", None)
                if face:
                    ui.set("face", face)
            except Exception:
                pass
        elif self._say_text and time.time() >= self._say_until:
            self._say_text = ""   # show window ended

    def _say_on_screen(self, text):
        """Show the phrase on the screen itself (like a real deauth)."""
        self._say_text = text
        self._say_until = time.time() + self._hold
        if self._ui is not None:
            try:
                self._ui.set("status", text)
                import pwnagotchi.ui.faces as faces
                face = getattr(faces, "ANGRY", None) or getattr(faces, "INTENSE", None)
                if face:
                    self._ui.set("face", face)
                self._ui.update(force=True)
            except Exception:
                logging.debug("[callout] could not draw on screen")

    # --- web --------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method != "GET":
            abort(405)
        act = request.args.get("action")
        if act == "data":
            return jsonify(ok=True, items=self._recent, patched=self._patched)
        if act == "test":
            sta = random.choice(FAKE)
            sample = random.choice(self._phrases).format(name=_nice_name(sta))
            self._record("TEST: " + _nice_name(sta), "demo")
            self._say_on_screen(sample)   # show it right on the e-ink
            return jsonify(ok=True, sample=sample, shown=self._ui is not None)
        if path in (None, "", "/"):
            return _PAGE
        abort(404)


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>callout</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;--fg:#e6edf3;--acc:#1f6feb}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px}
.wrap{max-width:560px;margin:0 auto}h1{font-size:1.3rem}
.sub{color:var(--mut);font-size:.8rem;margin-bottom:10px}
.bar{display:flex;gap:10px;align-items:center;margin-bottom:12px}
.btn{background:var(--acc);color:#fff;border:0;border-radius:9px;padding:10px 16px;cursor:pointer}
.sample{color:#9ad1ff;font-size:.95rem}
.row{background:var(--card);border:1px solid var(--line);border-left:3px solid #f85149;
border-radius:10px;padding:9px 12px;margin:7px 0;display:flex;justify-content:space-between;gap:8px}
.who{font-weight:600}.net{color:var(--mut);font-size:.85rem}
.age{color:var(--mut);font-size:.78rem;white-space:nowrap}
.empty{color:var(--mut);text-align:center;padding:30px 0}
.muted{color:var(--mut);font-size:.78rem;text-align:center;margin-top:14px}
</style></head><body><div class="wrap">
<h1>📢 callout</h1>
<div class="sub" id="sub"></div>
<div class="bar"><button class="btn" id="test">🧪 Test phrase</button><span class="sample" id="sample"></span></div>
<div id="list"><div class="empty">loading…</div></div>
<div class="muted">pwnagotchi says the name instead of the MAC · your networks only 🫡</div>
</div>
<script>
const BASE="/plugins/callout/";
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function age(t){const d=Date.now()/1000-t;if(d<60)return Math.round(d)+"s";
  if(d<3600)return Math.round(d/60)+"m";return Math.round(d/3600)+"h";}
async function load(){
  try{const j=await (await fetch(BASE+"?action=data",{credentials:"same-origin"})).json();
    document.getElementById("sub").textContent=j.patched?"deauth phrase replaced ✓":"⚠ patch not applied";
    const it=j.items||[];
    document.getElementById("list").innerHTML = it.length
      ? it.map(e=>'<div class="row"><div><div class="who">'+esc(e.who)
          +'</div><div class="net">▸ '+esc(e.net)+'</div></div><div class="age">'+age(e.t)+'</div></div>').join("")
      : '<div class="empty">nobody jammed yet — hit “Test”</div>';
  }catch(e){}
}
document.getElementById("test").addEventListener("click",async()=>{
  try{const j=await (await fetch(BASE+"?action=test",{credentials:"same-origin"})).json();
    document.getElementById("sample").textContent=(j.shown?"on screen ▸ ":"it will say: ")+(j.sample||"");}catch(e){}
  load();
});
load(); setInterval(load,5000);
</script></body></html>"""
