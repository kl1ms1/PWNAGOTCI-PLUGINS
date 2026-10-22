"""
brain — an AI agent for pwnagotchi that picks its own scanning strategy.

This is NOT heavy deep-RL (no PyTorch/model). It's a lightweight online agent
(multi-armed bandit): it learns on-device which channels pay off the most and
steers scanning there (exploit), occasionally probing others (explore).

  • reward: on_handshake (big) + targets/clients on a channel (small);
  • choice: epsilon-greedy over each channel's "value" (EWMA) + periodic full scan;
  • applies it via agent.run('wifi.recon.channel 1,6,11') — never rewrites config;
  • face (A_I) and short lines on the e-ink (takes over the face when it decides);
  • logs every decision to /root/.brain/log.jsonl;
  • web stats + settings: http://<ip>:8080/plugins/brain/

Rewards are shown as a configurable currency (default "$"), so the per-channel
value reads like how much each channel "earned". Display time and the reward
amounts are tweakable right from the web page (saved to /root/.brain/settings.json,
so it survives restarts without touching config.toml).
"""

import json
import logging
import os
import random
import time

import pwnagotchi.plugins as plugins

FACE = "(A_I)"            # the AI "face" — shown instead of the normal one on a decision

# What the device SAYS on the e-ink stays in Russian (only the web UI is English).
# {ch} is replaced with the chosen channels ("1·6·11"). Proper sentences:
# capitalized, with a period.
PHRASES = {
    "decide": ["Меняю тактику → канал {ch}.", "Перехожу на {ch}.",
               "Новый вектор: {ch}.", "Приоритет — {ch}.",
               "Перенастраиваюсь на {ch}.", "Беру на прицел {ch}.",
               "Пересчитал — цель {ch}.", "Смещаю фокус на {ch}."],
    "hot":    ["Канал {ch} кормит — остаюсь.", "Жатва на {ch}.",
               "{ch} в топе, качаю.", "Не ухожу с {ch}.",
               "{ch} — золотая жила.", "Держу {ch}, тут улов."],
    "quiet":  ["Собираю данные…", "Слушаю эфир.", "Калибруюсь…",
               "Учусь на лету.", "Разведка эфира.", "Строю карту каналов."],
}


class Brain(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.3.0"
    __license__ = "MIT"
    __description__ = "AI agent (bandit): learns and picks scanning channels."

    def __init__(self):
        self._dir = "/root/.brain"
        self._state_f = os.path.join(self._dir, "state.json")
        self._settings_f = os.path.join(self._dir, "settings.json")
        self._log = os.path.join(self._dir, "log.jsonl")
        self._ch = {}                 # ch -> {"value","n"}
        self._pool = list(range(1, 14))
        self._epoch_r = {}            # reward accumulator for the epoch
        self._decisions = 0
        self._last_reward = 0.0
        self._last_choice = []
        self._epochs = 0
        self._phrase = "Собираю данные…"   # current spoken line (RU; shown in the web too)
        # e-ink show
        self._ui = None
        self._say_until = 0.0         # until when to hold the "AI moment"
        # --- tweakable settings (web + config) ---
        self._hold = 5                # seconds to hold face (A_I) + line
        self._hs_reward = 10.0        # reward/price per handshake
        self._target_reward = 0.5     # reward/price per client/target
        self._currency = "$"          # currency symbol for the web
        # --- fixed-ish options ---
        self._epsilon = 0.2
        self._top_k = 3
        self._full_every = 10
        self._warmup = 3
        self._alpha = 0.3
        self._mode = "face"           # face | corner | off
        self._pos = (0, 83)           # for corner mode
        self._enabled_steer = True

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        o = self.options or {}
        self._epsilon = float(o.get("epsilon", self._epsilon))
        self._top_k = int(o.get("top_k", self._top_k))
        self._full_every = int(o.get("full_scan_every", self._full_every))
        self._alpha = float(o.get("ewma_alpha", self._alpha))
        self._mode = str(o.get("face_mode", "face")).lower()
        if o.get("show_face") is False:
            self._mode = "off"
        # tweakable defaults from config
        self._hold = int(o.get("say_seconds", self._hold))
        self._hs_reward = float(o.get("hs_reward", self._hs_reward))
        self._target_reward = float(o.get("target_reward", self._target_reward))
        self._currency = str(o.get("currency", self._currency))[:3]
        if o.get("channels"):
            try:
                self._pool = [int(c) for c in o.get("channels")]
            except Exception:
                pass
        if o.get("position"):
            try:
                x, y = str(o["position"]).split(",")
                self._pos = (int(x), int(y))
            except Exception:
                pass
        self._load()
        self._load_settings()         # web-saved settings win over config
        logging.info("[brain] loaded (eps=%.2f, top_k=%d, hold=%ds, pool=%s)",
                     self._epsilon, self._top_k, self._hold, self._pool)

    def on_ready(self, agent):
        try:
            sc = getattr(agent, "_supported_channels", None)
            if sc:
                self._pool = [c for c in self._pool if c in sc] or list(sc)
        except Exception:
            pass
        # optimistic init — so every channel gets tried at least once
        for c in self._pool:
            self._ch.setdefault(c, {"value": 1.0, "n": 0})

    def on_unload(self, ui):
        self._save()
        try:
            if self._mode == "corner":
                with ui._lock:
                    ui.remove_element("brain")
        except Exception:
            pass

    # --- storage -----------------------------------------------------------
    def _load(self):
        try:
            with open(self._state_f, encoding="utf-8") as f:
                d = json.load(f)
            self._ch = {int(k): v for k, v in d.get("ch", {}).items()}
            self._decisions = d.get("decisions", 0)
        except Exception:
            self._ch = {}

    def _save(self):
        try:
            tmp = self._state_f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"ch": self._ch, "decisions": self._decisions}, f)
            os.replace(tmp, self._state_f)
        except Exception:
            pass

    def _load_settings(self):
        try:
            with open(self._settings_f, encoding="utf-8") as f:
                s = json.load(f)
            self._hold = int(s.get("hold", self._hold))
            self._hs_reward = float(s.get("hs_reward", self._hs_reward))
            self._target_reward = float(s.get("target_reward", self._target_reward))
            self._currency = str(s.get("currency", self._currency))[:3]
        except Exception:
            pass

    def _save_settings(self):
        try:
            tmp = self._settings_f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"hold": self._hold, "hs_reward": self._hs_reward,
                           "target_reward": self._target_reward,
                           "currency": self._currency}, f)
            os.replace(tmp, self._settings_f)
        except Exception:
            logging.exception("[brain] save settings failed")

    # --- reward collection -------------------------------------------------
    def _reward(self, ch, amount):
        if ch:
            self._epoch_r[ch] = self._epoch_r.get(ch, 0.0) + amount

    def on_handshake(self, agent, filename, access_point, client_station):
        self._reward((access_point or {}).get("channel"), self._hs_reward)

    def on_wifi_update(self, agent, access_points):
        try:
            for ap in access_points or []:
                ch = ap.get("channel")
                clients = ap.get("clients") or []
                if ch:
                    self._reward(ch, self._target_reward * (len(clients) or 0.2))
        except Exception:
            pass

    # --- the brain: once per epoch decide where to look --------------------
    def on_epoch(self, agent, epoch, epoch_data):
        self._epochs += 1
        # 1) update channel values from the reward collected
        total_r = sum(self._epoch_r.values())
        self._last_reward = round(total_r, 2)
        for ch in self._pool:
            r = self._epoch_r.get(ch, 0.0)
            e = self._ch.setdefault(ch, {"value": 1.0, "n": 0})
            e["value"] = (1 - self._alpha) * e["value"] + self._alpha * r
            if r > 0:
                e["n"] += 1
        self._epoch_r = {}

        # warmup: not enough data yet — don't interfere, don't touch the face
        if self._epochs <= self._warmup:
            self._phrase = random.choice(PHRASES["quiet"])
            return

        # 2) pick channels
        chosen = self._choose()
        self._last_choice = chosen
        self._decisions += 1

        # 3) apply (without rewriting config)
        if self._enabled_steer and chosen:
            try:
                agent.run("wifi.recon.channel %s" % ",".join(str(c) for c in chosen))
            except Exception:
                logging.debug("[brain] set channels failed")

        # 4) line + "AI moment" on the e-ink + log
        best = max(self._ch.get(c, {"value": 0})["value"] for c in chosen) if chosen else 0
        self._set_phrase("hot" if best > self._hs_reward * 0.3 else "decide")
        self._announce()
        self._logline(chosen)
        if self._decisions % 5 == 0:
            self._save()

    def _choose(self):
        # full scan periodically — refresh the picture
        if self._full_every and self._epochs % self._full_every == 0:
            return list(self._pool)
        ranked = sorted(self._pool,
                        key=lambda c: self._ch.get(c, {"value": 0})["value"],
                        reverse=True)
        chosen = ranked[:max(1, self._top_k)]
        # explore: with probability epsilon add a random new channel
        if random.random() < self._epsilon:
            rest = [c for c in self._pool if c not in chosen]
            if rest:
                chosen.append(random.choice(rest))
        return sorted(set(chosen))

    def _logline(self, chosen):
        try:
            rec = {"t": int(time.time()), "epoch": self._epochs,
                   "chosen": chosen, "reward": self._last_reward,
                   "values": {c: round(self._ch.get(c, {"value": 0})["value"], 2)
                              for c in self._pool}}
            with open(self._log, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # --- e-ink -------------------------------------------------------------
    def _set_phrase(self, kind):
        ch = "·".join(str(c) for c in self._last_choice) if self._last_choice else "…"
        self._phrase = random.choice(PHRASES.get(kind, PHRASES["decide"])).format(ch=ch)

    def _announce(self):
        """Open an "AI moment": show (A_I) instead of the face + the line for _hold s."""
        if self._mode == "off":
            return
        self._say_until = time.time() + self._hold
        if self._ui is not None:
            try:
                self._paint(self._ui)
                self._ui.update(force=True)
            except Exception:
                logging.debug("[brain] announce failed")

    def _paint(self, ui):
        """Draw the current AI moment: face (A_I) + the line in the speech slot."""
        ui.set("face", FACE)
        ui.set("status", self._phrase)

    def on_ui_setup(self, ui):
        self._ui = ui
        if self._mode == "corner":
            try:
                import pwnagotchi.ui.fonts as fonts
                from pwnagotchi.ui.components import Text
                from pwnagotchi.ui.view import BLACK
                font = getattr(fonts, "Small", None) or fonts.Medium
                ui.add_element("brain", Text(value=FACE, position=self._pos,
                                             font=font, color=BLACK))
            except Exception:
                logging.exception("[brain] ui setup")

    def on_ui_update(self, ui):
        self._ui = ui
        if self._mode == "corner":
            try:
                ui.set("brain", "%s %s" % (FACE, self._phrase))
            except Exception:
                pass
            return
        if self._mode == "face":
            # hold face (A_I) + the line while the "AI moment" is active;
            # once the window ends, hand the screen back to pwnagotchi.
            if time.time() < self._say_until:
                try:
                    self._paint(ui)
                except Exception:
                    pass

    # --- web ---------------------------------------------------------------
    def _settings(self):
        return {"hold": self._hold, "hs_reward": self._hs_reward,
                "target_reward": self._target_reward, "currency": self._currency}

    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method == "GET":
            if request.args.get("action") == "data":
                chans = [{"ch": c,
                          "value": round(self._ch.get(c, {"value": 0})["value"], 2),
                          "n": self._ch.get(c, {"n": 0})["n"]} for c in self._pool]
                return jsonify(ok=True, channels=chans,
                               decisions=self._decisions, epochs=self._epochs,
                               last_reward=self._last_reward, epsilon=self._epsilon,
                               choice=self._last_choice, phrase=self._phrase,
                               settings=self._settings())
            if path in (None, "", "/"):
                return self._page()
            abort(404)

        # POST — body JSON (bypassing form parsing), CSRF checked by the server
        body = {}
        try:
            raw = request.get_data(as_text=True)
            if raw:
                body = json.loads(raw)
        except Exception:
            body = {}

        if request.args.get("action") == "save":
            try:
                if "hold" in body:
                    self._hold = max(1, min(60, int(float(body["hold"]))))
                if "hs_reward" in body:
                    self._hs_reward = max(0.0, min(1000.0, float(body["hs_reward"])))
                if "target_reward" in body:
                    self._target_reward = max(0.0, min(1000.0, float(body["target_reward"])))
                if "currency" in body:
                    self._currency = (str(body["currency"]) or "$")[:3]
            except Exception:
                return jsonify(ok=False, msg="bad values"), 400
            self._save_settings()
            return jsonify(ok=True, settings=self._settings())
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
<title>brain</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;--fg:#e6edf3;--acc:#1f6feb;--ok:#238636}
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px}
.wrap{max-width:560px;margin:0 auto}h1{font-size:1.3rem;margin:.2em 0}
.phrase{color:#9ad1ff;font-size:.95rem;margin:2px 0 12px}
.stats{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:.82rem}
.stat b{font-size:1.1rem}
.ch{display:flex;align-items:center;gap:8px;margin:5px 0}
.ch .lbl{width:52px;color:var(--mut);font-size:.82rem}
.bar{flex:1;height:14px;background:#0b0f14;border:1px solid var(--line);border-radius:7px;overflow:hidden}
.bar>div{height:100%;background:linear-gradient(90deg,#1f6feb,#238636)}
.ch .v{width:62px;text-align:right;font-size:.8rem}
.ch.sel .lbl{color:#7ee2a0;font-weight:700}
details{margin-top:16px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px 12px}
summary{cursor:pointer;padding:8px 0;font-weight:600}
.set{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:8px 0}
.set label{color:var(--mut);font-size:.85rem}
.set input{width:120px;background:#0b0f14;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:.9rem}
.savebtn{background:var(--ok);color:#fff;border:0;border-radius:9px;padding:9px 16px;cursor:pointer;margin:6px 0 10px}
.muted{color:var(--mut);font-size:.78rem;text-align:center;margin-top:14px}
</style></head><body><div class="wrap">
<h1>🧠 brain</h1>
<div class="phrase" id="phrase">(A_I)</div>
<div class="stats" id="stats"></div>
<div id="chans"></div>
<details id="cfg"><summary>⚙️ Settings</summary>
  <div class="set"><label>Show time on screen (sec)</label><input type="number" id="s_hold" min="1" max="60" step="1"></div>
  <div class="set"><label>Reward per handshake</label><input type="number" id="s_hs" min="0" max="1000" step="0.5"></div>
  <div class="set"><label>Reward per target</label><input type="number" id="s_tg" min="0" max="1000" step="0.1"></div>
  <div class="set"><label>Currency symbol</label><input type="text" id="s_cur" maxlength="3"></div>
  <button class="savebtn" id="save">💾 Save</button>
  <span id="saved" style="color:#7ee2a0;font-size:.85rem"></span>
</details>
<div class="muted">a channel's value = how much it earned · learns online 🫡</div>
</div>
<script>
const BASE="/plugins/brain/", CSRF="__CSRF__";
const $=s=>document.querySelector(s);
let CUR="$";
async function load(){
  try{const j=await (await fetch(BASE+"?action=data",{credentials:"same-origin"})).json();
    CUR=(j.settings&&j.settings.currency)||"$";
    $("#phrase").textContent="(A_I) "+(j.phrase||"");
    $("#stats").innerHTML=
      tile(j.decisions,"decisions")+tile(j.epochs,"epochs")
      +tile(CUR+j.last_reward,"last reward")+tile(j.epsilon,"ε");
    const sel=new Set(j.choice||[]);
    const max=Math.max(1,...j.channels.map(c=>c.value));
    $("#chans").innerHTML=j.channels.map(c=>{
      const w=Math.max(2,Math.round(c.value/max*100));
      return '<div class="ch'+(sel.has(c.ch)?' sel':'')+'"><div class="lbl">ch '+c.ch+'</div>'
        +'<div class="bar"><div style="width:'+w+'%"></div></div><div class="v">'+CUR+c.value+'</div></div>';
    }).join("");
    if(!$("#cfg").open){const s=j.settings||{};
      $("#s_hold").value=s.hold; $("#s_hs").value=s.hs_reward;
      $("#s_tg").value=s.target_reward; $("#s_cur").value=s.currency;}
  }catch(e){}
}
function tile(v,l){return '<div class="stat"><b>'+(v==null?0:v)+'</b> '+l+'</div>';}
$("#save").addEventListener("click",async()=>{
  const body={hold:+$("#s_hold").value, hs_reward:+$("#s_hs").value,
    target_reward:+$("#s_tg").value, currency:$("#s_cur").value||"$"};
  $("#saved").textContent="…";
  try{const j=await (await fetch(BASE+"?action=save",{method:"POST",credentials:"same-origin",
    headers:{"X-CSRFToken":CSRF,"Content-Type":"application/json"},body:JSON.stringify(body)})).json();
    $("#saved").textContent=j.ok?"saved ✓":"error";}
  catch(e){$("#saved").textContent="error";}
  setTimeout(()=>$("#saved").textContent="",1500);
});
load(); setInterval(load,4000);
</script></body></html>"""
