"""
vslider — a VIRTUAL slider for pwnagotchi (web UI), a stand-in for the future
hardware 3-position switch.

You flip between 3 positions in the web page (opened like pwndex/brain):

  1. Auto      — normal hunting (resumes wifi recon).
  2. Dashboard — PAUSES hunting (wifi.recon off) and shows live mini-charts:
                 temperature / CPU / memory (sparklines) + uptime.
  3. ???       — reserved ("coming soon"); we'll decide what it does later.

Open: http://<ip>:8080/plugins/vslider/

v1 is web-only. The e-ink carousel and the real Sync upload (connect to your own
network -> wpa-sec) come later.
"""

import json
import logging
import os
import time
from collections import deque

import pwnagotchi.plugins as plugins

HIST = 60   # how many samples to keep per metric (sparkline length)

POS_AUTO = 1
POS_DASH = 2
POS_X = 3


class Vslider(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "Virtual 3-position slider: Auto / Dashboard / reserved (web UI)."

    def __init__(self):
        self._dir = "/root/.vslider"
        self._state_f = os.path.join(self._dir, "state.json")
        self._pos = POS_AUTO
        self._agent = None
        self._cpu_prev = None
        self._hist = {"temp": deque(maxlen=HIST),
                      "cpu": deque(maxlen=HIST),
                      "mem": deque(maxlen=HIST)}
        self._last = {"temp": 0, "cpu": 0, "mem": 0, "uptime": 0}

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        self._load()
        logging.info("[vslider] loaded (position=%d)", self._pos)

    def on_ready(self, agent):
        self._agent = agent
        self._apply()

    def on_epoch(self, agent, epoch, epoch_data):
        self._agent = agent
        self._sample()
        # keep hunting paused while on the Dashboard (pwnagotchi may re-enable it)
        if self._pos == POS_DASH:
            self._run("wifi.recon off")

    # --- state -------------------------------------------------------------
    def _load(self):
        try:
            with open(self._state_f, encoding="utf-8") as f:
                self._pos = int(json.load(f).get("pos", POS_AUTO))
        except Exception:
            self._pos = POS_AUTO

    def _save(self):
        try:
            tmp = self._state_f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"pos": self._pos}, f)
            os.replace(tmp, self._state_f)
        except Exception:
            pass

    def _run(self, cmd):
        if self._agent is None:
            return
        try:
            self._agent.run(cmd)
        except Exception:
            logging.debug("[vslider] run failed: %s", cmd)

    def _apply(self):
        """Apply the current position's side effect."""
        if self._pos == POS_AUTO:
            self._run("wifi.recon on")      # resume hunting
        elif self._pos == POS_DASH:
            self._run("wifi.recon off")     # pause hunting
        # POS_X: nothing yet

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
                dt = total - self._cpu_prev[0]
                di = idle - self._cpu_prev[1]
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

    def _sample(self):
        t = self._read_temp()
        c = self._read_cpu()
        m = self._read_mem()
        u = self._read_uptime()
        self._hist["temp"].append(t)
        self._hist["cpu"].append(c)
        self._hist["mem"].append(m)
        self._last = {"temp": t, "cpu": c, "mem": m, "uptime": u}

    # --- web ---------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method == "GET":
            if request.args.get("action") == "data":
                # sample once on demand too, so the page isn't empty before the first epoch
                if not self._hist["temp"]:
                    self._sample()
                return jsonify(ok=True, pos=self._pos,
                               last=self._last,
                               hist={k: list(v) for k, v in self._hist.items()})
            if path in (None, "", "/"):
                return self._page()
            abort(404)

        # POST
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
            self._save()
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
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;--fg:#e6edf3;--acc:#1f6feb;--ok:#238636;--warn:#d29922}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px;line-height:1.4}
.wrap{max-width:640px;margin:0 auto}h1{font-size:1.3rem;margin:.2em 0}
.sub{color:var(--mut);font-size:.82rem;margin-bottom:14px}
.slider{display:flex;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:6px;gap:6px;position:relative}
.pos{flex:1;text-align:center;padding:14px 8px;border-radius:10px;cursor:pointer;user-select:none;font-weight:600;transition:.15s}
.pos small{display:block;font-weight:400;color:var(--mut);font-size:.72rem;margin-top:3px}
.pos.on{color:#fff}
.pos.on small{color:#dbe7ff}
.pos.on[data-p="1"]{background:var(--ok)}
.pos.on[data-p="2"]{background:var(--acc)}
.pos.on[data-p="3"]{background:#6e40c9}
.panel{margin-top:16px}
.status{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;text-align:center}
.status .big{font-size:1.1rem;font-weight:600}
.status .hint{color:var(--mut);font-size:.82rem;margin-top:4px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.mcard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.mcard .lbl{color:var(--mut);font-size:.78rem}
.mcard .val{font-size:1.5rem;font-weight:700;margin:2px 0}
.mcard .unit{font-size:.9rem;color:var(--mut);font-weight:400}
.spark{width:100%;height:38px;display:block}
.carousel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;text-align:center;cursor:pointer}
.slidelbl{color:var(--mut);font-size:.9rem}
.slideval{font-size:2.4rem;font-weight:800;margin:6px 0}
.slideval .unit{font-size:1.1rem;color:var(--mut);font-weight:400}
.carousel .spark{height:54px;margin-top:6px}
.dots{display:flex;gap:7px;justify-content:center;margin-top:14px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--line);transition:.2s}
.dot.on{background:var(--acc);transform:scale(1.25)}
.carhint{color:var(--mut);font-size:.72rem;margin-top:8px}
.muted{color:var(--mut);font-size:.78rem;text-align:center;margin-top:16px}
</style></head><body><div class="wrap">
<h1>🎚️ vslider</h1>
<div class="sub">Virtual slider · v1 (web) · flip a position below</div>

<div class="slider" id="slider">
  <div class="pos" data-p="1">Auto<small>охота идёт</small></div>
  <div class="pos" data-p="2">Dashboard<small>пауза + инфа</small></div>
  <div class="pos" data-p="3">???<small>скоро</small></div>
</div>

<div class="panel" id="panel"></div>
<div class="muted">pwnagotchi · your own networks only 🫡</div>
</div>
<script>
const BASE="/plugins/vslider/", CSRF="__CSRF__";
const $=s=>document.querySelector(s);
let POS=1, DATA=null, carIdx=0, carTimer=null;

// Position 2 is a CAROUSEL — these slides auto-rotate every 5s (tap to flip).
const SLIDES=[
  {k:"temp", lbl:"🌡 Температура", unit:"°C", color:"#f0883e", lo:null, hi:null},
  {k:"cpu",  lbl:"⚙️ CPU",        unit:"%",  color:"#1f6feb", lo:0, hi:100},
  {k:"mem",  lbl:"🧠 Память",      unit:"%",  color:"#2ea043", lo:0, hi:100},
  {k:"up",   lbl:"⏱ Аптайм",      unit:"",   color:"#8b949e"},
];

function spark(arr, color, lo, hi){
  arr=arr||[]; const W=200,H=54,n=arr.length;
  if(n<2) return '<svg class="spark" viewBox="0 0 '+W+' '+H+'"></svg>';
  if(lo==null){lo=Math.min(...arr); hi=Math.max(...arr);}
  if(hi<=lo)hi=lo+1;
  const pts=arr.map((v,i)=>{
    const x=i/(n-1)*W, y=H-2-((v-lo)/(hi-lo))*(H-4);
    return x.toFixed(1)+','+y.toFixed(1);}).join(' ');
  return '<svg class="spark" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'
    +'<polyline fill="none" stroke="'+color+'" stroke-width="2" points="'+pts+'"/></svg>';
}
function fmtUptime(s){s=s||0;const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);
  if(d)return d+"д "+h+"ч";if(h)return h+"ч "+m+"м";return m+"м";}

function slideHtml(i){
  const s=SLIDES[i], L=(DATA&&DATA.last)||{}, h=(DATA&&DATA.hist)||{};
  let val, spk="";
  if(s.k==="up"){ val=fmtUptime(L.uptime); }
  else{ val=(L[s.k]||0)+'<span class="unit"> '+s.unit+'</span>'; spk=spark(h[s.k],s.color,s.lo,s.hi); }
  const dots=SLIDES.map((_,j)=>'<span class="dot'+(j===i?' on':'')+'"></span>').join('');
  return '<div class="slidelbl">'+s.lbl+'</div><div class="slideval">'+val+'</div>'+spk
    +'<div class="dots">'+dots+'</div>'
    +'<div class="carhint">меняется каждые 5 сек · нажми, чтобы листнуть</div>';
}
function restartCar(){
  clearInterval(carTimer); carTimer=null;
  if(POS===2) carTimer=setInterval(()=>{carIdx=(carIdx+1)%SLIDES.length; renderPanel();},5000);
}
function renderPanel(){
  if(!DATA){$("#panel").innerHTML="";return;}
  if(POS===1){
    $("#panel").innerHTML='<div class="status"><div class="big">🟢 Auto — охота идёт</div>'
      +'<div class="hint">pwnagotchi сканирует и ловит рукопожатия как обычно.</div></div>';
  }else if(POS===2){
    $("#panel").innerHTML='<div class="status" style="margin-bottom:10px"><div class="big">⏸ Dashboard — охота на паузе</div></div>'
      +'<div class="carousel" id="car">'+slideHtml(carIdx%SLIDES.length)+'</div>';
    const car=$("#car");
    if(car) car.onclick=()=>{carIdx=(carIdx+1)%SLIDES.length; renderPanel(); restartCar();};
  }else{
    $("#panel").innerHTML='<div class="status"><div class="big">🟣 ??? — скоро</div>'
      +'<div class="hint">Эту позицию придумаем вместе.</div></div>';
  }
}
function paintSlider(){
  document.querySelectorAll(".pos").forEach(p=>p.classList.toggle("on", +p.dataset.p===POS));
}
async function load(){
  try{const j=await (await fetch(BASE+"?action=data",{credentials:"same-origin"})).json();
    if(!j.ok)return; DATA=j;
    if(j.pos!==POS){POS=j.pos; carIdx=0; restartCar();}
    paintSlider(); renderPanel();}
  catch(e){}
}
async function setpos(p){
  POS=p; carIdx=0; restartCar(); paintSlider(); renderPanel();
  try{await fetch(BASE+"?action=setpos",{method:"POST",credentials:"same-origin",
    headers:{"X-CSRFToken":CSRF,"Content-Type":"application/json"},body:JSON.stringify({pos:p})});}
  catch(e){}
  load();
}
document.querySelectorAll(".pos").forEach(p=>p.addEventListener("click",()=>setpos(+p.dataset.p)));
load(); setInterval(load,3000);
</script></body></html>"""
