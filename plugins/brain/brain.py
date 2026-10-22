"""
brain — ИИ-агент для pwnagotchi, который сам выбирает стратегию сканирования.

Это НЕ тяжёлый deep-RL (без PyTorch/модели). Это лёгкий онлайн-агент
(multi-armed bandit): он учится прямо на девайсе, на каких каналах больше улова,
и смещает сканирование туда (exploit), иногда проверяя другие (explore).

  • награда: on_handshake (большая) + цели/клиенты на канале (малая);
  • выбор: epsilon-greedy по «ценности» канала (EWMA), + периодический полный скан;
  • применяет через agent.run('wifi.recon.channel 1,6,11') — конфиг не переписывает;
  • лицо (A_I) и реплики на e-ink;
  • логи всех решений в /root/.brain/log.jsonl;
  • веб-стата: http://<ip>:8080/plugins/brain/

Это «кооперативное» смещение: pwnagotchi в своём цикле тоже трогает каналы,
поэтому агент переустанавливает выбор каждую эпоху. Лучше всего работает,
когда main.personality.channels пуст (по умолчанию).
"""

import json
import logging
import os
import random
import time

import pwnagotchi.plugins as plugins

HS_REWARD = 10.0          # награда за хендшейк на канале
TARGET_REWARD = 0.5       # награда за клиента/цель на канале
FACE = "(A_I)"            # «лицо» ИИ — показывается вместо обычного в момент решения

# {ch} подставляется выбранными каналами ("1·6·11"). Реплики — с AI/хакерским
# характером (без рыбацких клише).
PHRASES = {
    "decide": ["меняю тактику → {ch}", "перехожу на {ch}", "вектор смещён на {ch}",
               "приоритет: {ch}", "курс на {ch}", "захожу на {ch}",
               "сканирую плотнее {ch}", "перенастраиваю приём на {ch}",
               "пересчитал — цель {ch}", "смещаю фокус на {ch}"],
    "hot":    ["{ch} кормит — остаюсь", "жатва на {ch}", "{ch} в топе, качаю",
               "не ухожу с {ch}", "{ch} — золотая жила", "держу {ch}, тут улов"],
    "quiet":  ["собираю данные…", "слушаю эфир", "калибруюсь", "учусь на лету",
               "пока наблюдаю", "разведка эфира", "строю карту каналов"],
}


class Brain(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.2.0"
    __license__ = "MIT"
    __description__ = "ИИ-агент (bandit): учится и выбирает каналы сканирования."

    def __init__(self):
        self._dir = "/root/.brain"
        self._state_f = os.path.join(self._dir, "state.json")
        self._log = os.path.join(self._dir, "log.jsonl")
        self._ch = {}                 # ch -> {"value","n"}
        self._pool = list(range(1, 14))
        self._epoch_r = {}            # аккумулятор награды за эпоху
        self._decisions = 0
        self._last_reward = 0.0
        self._last_choice = []
        self._epochs = 0
        self._phrase = "собираю данные…"   # текущая реплика (для веб-статы)
        # показ на e-ink
        self._ui = None
        self._say_until = 0.0              # до какого времени держим «AI-момент»
        self._hold = 8                     # секунд держать лицо (A_I) + реплику
        # опции
        self._epsilon = 0.2
        self._top_k = 3
        self._full_every = 10
        self._warmup = 3
        self._alpha = 0.3
        self._mode = "face"               # face | corner | off
        self._pos = (0, 83)               # для режима corner
        self._enabled_steer = True

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        o = self.options or {}
        self._epsilon = float(o.get("epsilon", self._epsilon))
        self._top_k = int(o.get("top_k", self._top_k))
        self._full_every = int(o.get("full_scan_every", self._full_every))
        self._alpha = float(o.get("ewma_alpha", self._alpha))
        # режим показа ИИ: face (вместо лица, по умолч.), corner (угол), off
        self._mode = str(o.get("face_mode", "face")).lower()
        if o.get("show_face") is False:
            self._mode = "off"
        try:
            self._hold = int(o.get("say_seconds", self._hold))
        except Exception:
            pass
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
        logging.info("[brain] loaded (eps=%.2f, top_k=%d, pool=%s)",
                     self._epsilon, self._top_k, self._pool)

    def on_ready(self, agent):
        try:
            sc = getattr(agent, "_supported_channels", None)
            if sc:
                self._pool = [c for c in self._pool if c in sc] or list(sc)
        except Exception:
            pass
        # оптимистичная инициализация — чтобы каждый канал хоть раз попробовать
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

    # --- сбор награды ------------------------------------------------------
    def _reward(self, ch, amount):
        if ch:
            self._epoch_r[ch] = self._epoch_r.get(ch, 0.0) + amount

    def on_handshake(self, agent, filename, access_point, client_station):
        self._reward((access_point or {}).get("channel"), HS_REWARD)

    def on_wifi_update(self, agent, access_points):
        try:
            for ap in access_points or []:
                ch = ap.get("channel")
                clients = ap.get("clients") or []
                if ch:
                    self._reward(ch, TARGET_REWARD * (len(clients) or 0.2))
        except Exception:
            pass

    # --- мозг: раз в эпоху решаем, куда смотреть ---------------------------
    def on_epoch(self, agent, epoch, epoch_data):
        self._epochs += 1
        # 1) обновляем ценность каналов по собранной награде
        total_r = sum(self._epoch_r.values())
        self._last_reward = round(total_r, 2)
        for ch in self._pool:
            r = self._epoch_r.get(ch, 0.0)
            e = self._ch.setdefault(ch, {"value": 1.0, "n": 0})
            e["value"] = (1 - self._alpha) * e["value"] + self._alpha * r
            if r > 0:
                e["n"] += 1
        self._epoch_r = {}

        # прогрев: пока мало данных — не вмешиваемся и лицо не трогаем
        if self._epochs <= self._warmup:
            self._phrase = random.choice(PHRASES["quiet"])
            return

        # 2) выбираем каналы
        chosen = self._choose()
        self._last_choice = chosen
        self._decisions += 1

        # 3) применяем (не переписывая конфиг)
        if self._enabled_steer and chosen:
            try:
                agent.run("wifi.recon.channel %s" % ",".join(str(c) for c in chosen))
            except Exception:
                logging.debug("[brain] set channels failed")

        # 4) реплика + «AI-момент» на экране + лог
        best = max(self._ch.get(c, {"value": 0})["value"] for c in chosen) if chosen else 0
        self._set_phrase("hot" if best > HS_REWARD * 0.3 else "decide")
        self._announce()          # лицо (A_I) + речь на e-ink на пару секунд
        self._logline(chosen)
        if self._decisions % 5 == 0:
            self._save()

    def _choose(self):
        # полный скан периодически — освежить картину
        if self._full_every and self._epochs % self._full_every == 0:
            return list(self._pool)
        ranked = sorted(self._pool,
                        key=lambda c: self._ch.get(c, {"value": 0})["value"],
                        reverse=True)
        chosen = ranked[:max(1, self._top_k)]
        # explore: с вероятностью epsilon докинуть случайный новый канал
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
        """Открыть «AI-момент»: на _hold секунд показать (A_I) вместо лица + речь."""
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
        """Нарисовать текущий AI-момент: лицо (A_I) + реплику в строке речи."""
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
            # держим лицо (A_I) + реплику, пока активен «AI-момент»;
            # по истечении окна — отдаём экран обратно pwnagotchi.
            if time.time() < self._say_until:
                try:
                    self._paint(ui)
                except Exception:
                    pass

    # --- web ---------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method != "GET":
            abort(405)
        if request.args.get("action") == "data":
            chans = [{"ch": c,
                      "value": round(self._ch.get(c, {"value": 0})["value"], 2),
                      "n": self._ch.get(c, {"n": 0})["n"]} for c in self._pool]
            return jsonify(ok=True, channels=chans,
                           decisions=self._decisions, epochs=self._epochs,
                           last_reward=self._last_reward, epsilon=self._epsilon,
                           choice=self._last_choice, phrase=self._phrase)
        if path in (None, "", "/"):
            return _PAGE
        abort(404)


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>brain</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;--fg:#e6edf3;--acc:#1f6feb;--ok:#238636}
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
.ch .v{width:40px;text-align:right;font-size:.8rem}
.ch.sel .lbl{color:#7ee2a0;font-weight:700}
.muted{color:var(--mut);font-size:.78rem;text-align:center;margin-top:14px}
</style></head><body><div class="wrap">
<h1>🧠 brain</h1>
<div class="phrase" id="phrase">(A_I)</div>
<div class="stats" id="stats"></div>
<div id="chans"></div>
<div class="muted">ценность канала = сколько улова он приносил · учится онлайн 🫡</div>
</div>
<script>
const BASE="/plugins/brain/";
async function load(){
  try{const j=await (await fetch(BASE+"?action=data",{credentials:"same-origin"})).json();
    document.getElementById("phrase").textContent="(A_I) "+(j.phrase||"");
    document.getElementById("stats").innerHTML=
      tile(j.decisions,"решений")+tile(j.epochs,"эпох")+tile(j.last_reward,"награда")+tile(j.epsilon,"ε");
    const sel=new Set(j.choice||[]);
    const max=Math.max(1,...j.channels.map(c=>c.value));
    document.getElementById("chans").innerHTML=j.channels.map(c=>{
      const w=Math.max(2,Math.round(c.value/max*100));
      return '<div class="ch'+(sel.has(c.ch)?' sel':'')+'"><div class="lbl">ch '+c.ch+'</div>'
        +'<div class="bar"><div style="width:'+w+'%"></div></div><div class="v">'+c.value+'</div></div>';
    }).join("");
  }catch(e){}
}
function tile(v,l){return '<div class="stat"><b>'+(v==null?0:v)+'</b> '+l+'</div>';}
load(); setInterval(load,4000);
</script></body></html>"""
