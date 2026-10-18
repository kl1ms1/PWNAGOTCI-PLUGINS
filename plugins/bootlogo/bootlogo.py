"""
bootlogo — кастомное бут-лого для Pwnagotchi.

Веб-морда (http://<ip>:8080/plugins/bootlogo/):
  • перетащи/выбери фото — вся обработка и превью идут ПРЯМО В БРАУЗЕРЕ (мгновенно,
    без запросов к девайсу): подгон (вписать/обрезать/растянуть/по центру), дизеринг
    (Floyd–Steinberg) или порог, инверсия, яркость, контраст, поворот;
  • 👁 «Показать на экране» — выводит картинку на e-ink на ~4 c без перезагрузки;
  • 💾 «Сохранить как бут-лого» — на девайс уходит только маленький финальный PNG;
  • переключатель «Показ при загрузке» (systemd-сервис с таймаутом);
  • переключатель языка RU/EN.

Размер экрана определяется автоматически (по рендеру UI); можно задать width/height.
"""

import io
import logging
import os
import threading
import time

import pwnagotchi.plugins as plugins

_KNOWN_SIZES = {
    "waveshare_1": (250, 122), "waveshare_2": (250, 122),
    "waveshare_3": (250, 122), "waveshare_4": (250, 122),
    "waveshare2in13d": (212, 104), "adafruit2in13_v3": (250, 122),
    "waveshare2in7": (264, 176), "waveshare2in7_v2": (264, 176),
    "waveshare2in9": (296, 128), "waveshare2in9_v2": (296, 128),
    "waveshare1in54": (200, 200), "waveshare1in54_v2": (200, 200),
}

_SERVICE_PATH = "/etc/systemd/system/pwnagotchi-bootlogo.service"
_BOOT_SCRIPT_PATH = "/usr/local/bin/pwnagotchi-bootlogo.py"

_SERVICE_UNIT = """[Unit]
Description=Pwnagotchi boot logo
DefaultDependencies=no
After=local-fs.target
Before=pwnagotchi.service

[Service]
Type=oneshot
# жёсткий таймаут: если показ лого завис, он не должен держать загрузку pwnagotchi
TimeoutStartSec=30
ExecStart=/usr/bin/timeout 20 /usr/bin/python3 {script}
RemainAfterExit=no
SuccessExitStatus=0 124

[Install]
WantedBy=multi-user.target
"""

_BOOT_SCRIPT = '''#!/usr/bin/env python3
"""Рисует бут-лого на e-ink до старта pwnagotchi (ставится плагином bootlogo)."""
import os, logging

CONFIG = "/etc/pwnagotchi/config.toml"
LOGO = "{logo}"
FALLBACK_TYPE = "{type}"

def _load_cfg():
    try:
        import tomllib
        with open(CONFIG, "rb") as f:
            return tomllib.load(f)
    except Exception:
        try:
            import toml as _t
            return _t.load(CONFIG)
        except Exception:
            return {{}}

def main():
    if not os.path.exists(LOGO):
        return
    cfg = _load_cfg()
    disp = cfg.setdefault("ui", {{}}).setdefault("display", {{}})
    if not disp.get("type"):
        disp["type"] = FALLBACK_TYPE
    disp.setdefault("enabled", True)
    disp.setdefault("rotation", 180)
    disp.setdefault("color", "black")
    if not disp.get("type"):
        return
    from PIL import Image
    from pwnagotchi.ui import hw
    impl = hw.display_for(cfg)
    impl.initialize()
    img = Image.open(LOGO).convert("1")
    rot = int(disp.get("rotation", 0) or 0)
    if rot:
        img = img.rotate(rot)
    impl.render(img)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.basicConfig()
        logging.getLogger().error("bootlogo boot script: %s", e)
'''


class Bootlogo(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.4.3"
    __license__ = "MIT"
    __description__ = "Кастомное бут-лого: обработка в браузере, показ на экране, бут-сплэш."

    def __init__(self):
        self._w = 250
        self._h = 122
        self._display_type = ""
        self._view = None
        self._dir = "/root/.bootlogo"
        self._preview = os.path.join(self._dir, "preview.png")
        self._logo = "/root/pwnagotchi-bootlogo.png"

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._logo = o.get("path", self._logo)
        if o.get("width"):
            self._w = int(o["width"])
        if o.get("height"):
            self._h = int(o["height"])
        os.makedirs(self._dir, exist_ok=True)
        logging.info("[bootlogo] loaded (target %dx%d, logo=%s)",
                     self._w, self._h, self._logo)

    def on_ready(self, agent):
        try:
            cfg = agent.config()
            self._display_type = cfg["ui"]["display"].get("type", "") or ""
            if (not self.options or not self.options.get("width")) \
                    and self._display_type in _KNOWN_SIZES:
                self._w, self._h = _KNOWN_SIZES[self._display_type]
        except Exception:
            pass
        try:
            v = agent.view()           # не на всех сборках есть — ловим ещё и в UI-хуках
            if v is not None:
                self._capture_view(v)
        except Exception:
            pass
        logging.info("[bootlogo] ready (display=%s, %dx%d)",
                     self._display_type, self._w, self._h)

    # pwnagotchi сам передаёт сюда объект дисплея (View/Display) — самый надёжный способ
    def on_ui_setup(self, ui):
        self._capture_view(ui)

    def on_ui_update(self, ui):
        if self._view is None:
            self._capture_view(ui)

    def _capture_view(self, ui):
        self._view = ui
        # размер берём из UI только если его не задали в конфиге
        if self.options and (self.options.get("width") or self.options.get("height")):
            return
        try:
            im = ui.image()
            if im is not None and im.size[0] > 0:
                self._w, self._h = im.size
        except Exception:
            pass

    # --- картинка ----------------------------------------------------------
    def _to_logo(self, b64):
        """base64 (PNG из браузера, уже ч/б) -> PIL '1' точного размера экрана."""
        import base64
        from PIL import Image
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
        if img.size != (self._w, self._h):
            img = img.resize((self._w, self._h))
        # порог, а не дизеринг: картинка уже ч/б, сохраняем как есть
        return img.point(lambda v: 255 if v >= 128 else 0, mode="1")

    def _show_on_device(self, path, seconds=4):
        """Показать картинку на e-ink, отдав её в штатный рендер-поток pwnagotchi."""
        ui = self._view
        if ui is None:
            return False, "Дисплей недоступен"
        impl = getattr(ui, "_implementation", None)
        ev = getattr(ui, "_canvas_next_event", None)
        lock = getattr(ui, "_lock", None)
        if impl is None or ev is None or lock is None:
            return False, "Дисплей не поддерживает предпоказ"
        from PIL import Image
        img = Image.open(path).convert("1")
        rot = int(getattr(ui, "_rotation", 0) or 0)
        disp = img if rot == 0 else img.rotate(rot)

        def run():
            try:
                with lock:
                    ui._frozen = True            # остановить штатные апдейты UI
                ui._canvas_next = disp           # отдаём наш кадр
                ev.set()                         # будим единственный рендер-поток
                time.sleep(max(1, min(10, seconds)))
            except Exception:
                logging.exception("[bootlogo] on-device preview failed")
            finally:
                try:
                    ui._frozen = False           # гарантированно разморозить
                except Exception:
                    pass
                try:
                    ui.update(force=True)        # вернуть обычный экран
                except Exception:
                    pass

        threading.Thread(target=run, name="bootlogo-ondevice", daemon=True).start()
        return True, "Показываю на экране ~%d c" % seconds

    # --- бут-сервис --------------------------------------------------------
    def _service_enabled(self):
        return os.path.exists(_SERVICE_PATH)

    def _install_service(self):
        import subprocess
        try:
            script = _BOOT_SCRIPT.format(logo=self._logo, type=self._display_type or "")
            with open(_BOOT_SCRIPT_PATH, "w") as fh:
                fh.write(script)
            os.chmod(_BOOT_SCRIPT_PATH, 0o755)
            with open(_SERVICE_PATH, "w") as fh:
                fh.write(_SERVICE_UNIT.format(script=_BOOT_SCRIPT_PATH))
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "pwnagotchi-bootlogo.service"], check=True)
            return True, "Показ при загрузке включён"
        except Exception as e:
            logging.exception("[bootlogo] install service failed")
            return False, "Не удалось включить: %s" % e

    def _uninstall_service(self):
        import subprocess
        try:
            subprocess.run(["systemctl", "disable", "--now",
                            "pwnagotchi-bootlogo.service"], check=False)
            for pth in (_SERVICE_PATH, _BOOT_SCRIPT_PATH):
                if os.path.exists(pth):
                    os.remove(pth)
            subprocess.run(["systemctl", "daemon-reload"], check=False)
            return True, "Показ при загрузке выключен"
        except Exception as e:
            logging.exception("[bootlogo] uninstall service failed")
            return False, "Не удалось выключить: %s" % e

    # --- web API -----------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import send_file, jsonify, abort
        try:
            if request.method == "GET":
                if path in (None, "", "/"):
                    return self._page()
                if path == "current.png" and os.path.exists(self._logo):
                    return send_file(self._logo, mimetype="image/png")
                if path == "preview.png" and os.path.exists(self._preview):
                    return send_file(self._preview, mimetype="image/png")
                abort(404)

            # Надёжно, без разбора формы (некоторые сборки pwnagotchi её не парсят):
            # action — из query-строки или под-адреса; картинка — из сырого тела.
            action = request.args.get("action") or (path or "").strip("/")
            try:
                body = request.get_data(as_text=True) or ""
            except Exception:
                body = ""
            b64 = body if body.strip().startswith("data:") else ""
            if not action and request.form:          # запасной путь (форма)
                action = request.form.get("action", "")
            if not b64 and request.form:
                b64 = request.form.get("logo_b64", "")

            if action == "save":
                if not b64:
                    return jsonify(ok=False, msg="Нет картинки"), 400
                self._to_logo(b64).save(self._logo)
                return jsonify(ok=True, msg="Сохранено как бут-лого ✅")

            if action == "ondevice":
                if b64:
                    self._to_logo(b64).save(self._preview)
                    src = self._preview
                elif os.path.exists(self._logo):
                    src = self._logo
                else:
                    return jsonify(ok=False, msg="Нет картинки"), 400
                ok, msg = self._show_on_device(src, 4)
                return jsonify(ok=ok, msg=msg)

            if action == "install":
                ok, msg = self._install_service()
                return jsonify(ok=ok, msg=msg)
            if action == "uninstall":
                ok, msg = self._uninstall_service()
                return jsonify(ok=ok, msg=msg)
            abort(404)
        except Exception as e:
            logging.exception("[bootlogo] webhook error")
            from flask import jsonify
            return jsonify(ok=False, msg=str(e)), 500

    def _page(self):
        # у веб-сервера pwnagotchi включён CSRFProtect — без токена POST = 400.
        # Генерим токен и вшиваем в страницу; клиент шлёт его заголовком X-CSRFToken.
        token = ""
        try:
            from flask_wtf.csrf import generate_csrf
            token = generate_csrf()
        except Exception:
            token = ""
        return (_APP_HTML
                .replace("__W__", str(self._w))
                .replace("__H__", str(self._h))
                .replace("__SVC__", "1" if self._service_enabled() else "0")
                .replace("__DISP__", self._display_type or "—")
                .replace("__CSRF__", token))


_APP_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bootlogo</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;
--fg:#e6edf3;--acc:#1f6feb;--ok:#238636}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);
margin:0;padding:16px;line-height:1.4}
.wrap{max-width:560px;margin:0 auto}
.top{display:flex;align-items:center;justify-content:space-between}
h1{font-size:1.3rem;margin:.2em 0}
.lang{background:#21262d;color:var(--fg);border:1px solid var(--line);border-radius:8px;
padding:6px 12px;font-size:.8rem;cursor:pointer}
.sub{color:var(--mut);font-size:.85rem;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}
.drop{border:2px dashed var(--line);border-radius:12px;padding:22px;text-align:center;
color:var(--mut);cursor:pointer;transition:.15s}
.drop:hover,.drop.hot{border-color:var(--acc);color:var(--fg);background:#0b1b33}
.stage{display:flex;justify-content:center;margin:4px 0 2px}
.frame{background:#c9ccd1;border-radius:14px;padding:12px;box-shadow:0 6px 18px #0008;max-width:100%}
.screen{background:#fff;border-radius:4px;overflow:hidden;aspect-ratio:__W__/__H__;width:min(420px,78vw)}
.screen canvas{width:100%;height:100%;display:block;image-rendering:pixelated}
.ph{display:flex;align-items:center;justify-content:center;height:100%;color:#9aa0a6;font-size:.85rem;text-align:center;padding:8px}
.dim{text-align:center;color:var(--mut);font-size:.8rem;margin-top:6px}
label{display:block;font-size:.82rem;color:var(--mut);margin:10px 0 4px}
.seg{display:flex;gap:6px;flex-wrap:wrap}
.seg button{flex:1;min-width:64px;background:#21262d;color:var(--fg);border:1px solid var(--line);
border-radius:9px;padding:8px 6px;font-size:.82rem;cursor:pointer}
.seg button.on{background:var(--acc);border-color:var(--acc)}
input[type=range]{width:100%;accent-color:var(--acc)}
.row{display:flex;gap:14px}.row>div{flex:1}
.val{color:var(--fg)}
.switch{display:flex;align-items:center;gap:10px;margin-top:12px}
.switch input{width:38px;height:22px;accent-color:var(--acc)}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:4px}
.btn{flex:1;min-width:150px;border:0;border-radius:10px;padding:12px;font-size:.95rem;
cursor:pointer;color:#fff;background:var(--acc)}
.btn.save{background:var(--ok)}.btn.ghost{background:#30363d}.btn:disabled{opacity:.5;cursor:default}
.toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:#21262d;
border:1px solid var(--line);padding:10px 16px;border-radius:10px;opacity:0;transition:.25s;
pointer-events:none;max-width:90vw;text-align:center}
.toast.show{opacity:1}
.muted{color:var(--mut);font-size:.78rem;margin-top:10px;text-align:center}
</style></head><body><div class="wrap">
<div class="top"><h1>🐾 bootlogo</h1><button class="lang" id="langBtn"></button></div>
<div class="sub" id="sub"></div>

<div class="card">
  <div id="drop" class="drop"></div>
  <input id="file" type="file" accept="image/*" hidden>
  <div class="stage"><div class="frame"><div class="screen">
    <canvas id="cv" style="display:none"></canvas>
    <div id="ph" class="ph"></div>
  </div></div></div>
  <div class="dim" id="dim"></div>
</div>

<div class="card" id="controls" style="opacity:.5;pointer-events:none">
  <label id="lFit"></label>
  <div class="seg" data-k="fit">
    <button data-v="contain" class="on"></button><button data-v="cover"></button>
    <button data-v="stretch"></button><button data-v="center"></button>
  </div>
  <label id="lBw"></label>
  <div class="seg" data-k="dither">
    <button data-v="floyd" class="on"></button><button data-v="none"></button>
  </div>
  <label id="lRot"></label>
  <div class="seg" data-k="rotate">
    <button data-v="0" class="on">0°</button><button data-v="90">90°</button>
    <button data-v="180">180°</button><button data-v="270">270°</button>
  </div>
  <div class="row">
    <div><label><span id="lBr"></span> <span class="val" id="vbr">1.0</span></label>
      <input id="brightness" type="range" min="0.3" max="2.0" step="0.05" value="1.0"></div>
    <div><label><span id="lCt"></span> <span class="val" id="vct">1.0</span></label>
      <input id="contrast" type="range" min="0.3" max="2.5" step="0.05" value="1.0"></div>
  </div>
  <label><span id="lTh"></span> <span class="val" id="vth">128</span></label>
  <input id="threshold" type="range" min="0" max="255" value="128">
  <div class="switch"><input id="invert" type="checkbox"><label style="margin:0" id="lInv"></label></div>
</div>

<div class="card">
  <div class="actions">
    <button class="btn save" id="bSave" disabled></button>
    <button class="btn" id="bDev" disabled></button>
  </div>
  <div class="actions" style="margin-top:10px"><button class="btn ghost" id="bInstall"></button></div>
  <div class="muted" id="note"></div>
</div>
<div class="muted" id="footer"></div>
</div>

<div id="toast" class="toast"></div>
<script>
const BASE="/plugins/bootlogo/";
const SCRW=__W__, SCRH=__H__, DISP="__DISP__", CSRF="__CSRF__";
let svc=(__SVC__===1), srcImg=null, lang="ru", devCooldown=false;
const P={fit:"contain",dither:"floyd",rotate:"0",brightness:"1.0",contrast:"1.0",threshold:"128",invert:"0"};
const $=id=>document.getElementById(id);
const cv=$("cv"); cv.width=SCRW; cv.height=SCRH;

const I18N={
 ru:{lang:"EN",subScreen:"Экран",subDisplay:"дисплей",
  drop:"📷 Перетащи фото сюда или нажми, чтобы выбрать",
  ph:"превью появится здесь",dimDef:"предпросмотр как на e-ink",dimDone:"готово",
  lFit:"Подгон под экран",contain:"Вписать",cover:"Обрезать",stretch:"Растянуть",center:"По центру",
  lBw:"Перевод в ч/б",floyd:"Дизеринг",none:"Порог",lRot:"Поворот",
  lBr:"Яркость",lCt:"Контраст",lTh:"Порог ч/б (для «Порога»)",lInv:"Инверсия (негатив)",
  save:"💾 Сохранить как бут-лого",dev:"👁 Показать на экране",
  svcOn:"⚙️ Включить показ при загрузке",svcOff:"🧹 Выключить показ при загрузке",
  note:"Обработка идёт в браузере. «Показать на экране» выводит картинку на e-ink на ~4 c без перезагрузки.",
  footer:"bootlogo · только для своих устройств 🫡",
  net:"Сеть недоступна",err:"Ошибка",noimg:"Сначала загрузи фото"},
 en:{lang:"RU",subScreen:"Screen",subDisplay:"display",
  drop:"📷 Drop a photo here or tap to choose",
  ph:"preview will appear here",dimDef:"e-ink preview",dimDone:"ready",
  lFit:"Fit to screen",contain:"Fit",cover:"Crop",stretch:"Stretch",center:"Center",
  lBw:"Black & white",floyd:"Dithering",none:"Threshold",lRot:"Rotate",
  lBr:"Brightness",lCt:"Contrast",lTh:"B/W threshold (for «Threshold»)",lInv:"Invert (negative)",
  save:"💾 Save as boot logo",dev:"👁 Show on screen",
  svcOn:"⚙️ Enable boot splash",svcOff:"🧹 Disable boot splash",
  note:"Processing runs in your browser. «Show on screen» draws it on the e-ink for ~4s, no reboot.",
  footer:"bootlogo · for your own devices only 🫡",
  net:"Network unavailable",err:"Error",noimg:"Load a photo first"}
};
try{lang=localStorage.getItem("bl_lang")||"ru";}catch(e){}
function D(){return I18N[lang];}

function applyLang(){
  const d=D();
  $("langBtn").textContent=d.lang;
  $("sub").innerHTML=d.subScreen+" <b>"+SCRW+"×"+SCRH+"</b> · "+d.subDisplay+" <code>"+DISP+"</code>";
  $("drop").textContent=d.drop; if(!srcImg)$("ph").textContent=d.ph;
  $("dim").textContent=srcImg?(d.dimDone+" · "+SCRW+"×"+SCRH+" · 1-bit"):d.dimDef;
  $("lFit").textContent=d.lFit; $("lBw").textContent=d.lBw; $("lRot").textContent=d.lRot;
  $("lBr").textContent=d.lBr; $("lCt").textContent=d.lCt; $("lTh").textContent=d.lTh; $("lInv").textContent=d.lInv;
  document.querySelector('[data-k=fit]').querySelectorAll('button').forEach(b=>b.textContent=d[b.dataset.v]);
  document.querySelector('[data-k=dither]').querySelectorAll('button').forEach(b=>b.textContent=d[b.dataset.v]);
  $("bSave").textContent=d.save; $("bDev").textContent=d.dev;
  $("note").textContent=d.note; $("footer").textContent=d.footer;
  svcLabel();
}
$("langBtn").addEventListener("click",()=>{lang=(lang==="ru")?"en":"ru";
  try{localStorage.setItem("bl_lang",lang);}catch(e){} applyLang();});

function toast(m){const e=$("toast");e.textContent=m;e.classList.add("show");
  clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove("show"),2600);}
function svcLabel(){$("bInstall").textContent=svc?D().svcOff:D().svcOn;}

// ---- выбор файла ----
$("drop").addEventListener("click",()=>$("file").click());
$("file").addEventListener("change",()=>{if($("file").files[0])pick($("file").files[0]);});
["dragover","dragenter"].forEach(ev=>$("drop").addEventListener(ev,e=>{e.preventDefault();$("drop").classList.add("hot");}));
["dragleave","drop"].forEach(ev=>$("drop").addEventListener(ev,e=>{e.preventDefault();$("drop").classList.remove("hot");}));
$("drop").addEventListener("drop",e=>{const f=e.dataTransfer.files[0];if(f)pick(f);});

function pick(file){
  const url=URL.createObjectURL(file), im=new Image();
  im.onload=()=>{URL.revokeObjectURL(url);srcImg=im;
    $("controls").style.opacity=1;$("controls").style.pointerEvents="auto";
    $("bSave").disabled=false;$("bDev").disabled=false;
    $("ph").style.display="none";cv.style.display="block";render();};
  im.onerror=()=>{URL.revokeObjectURL(url);toast(D().err+" (формат?)");};
  im.src=url;
}

// ---- обработка целиком в браузере ----
function floyd(id,useFS,thr){
  const w=id.width,h=id.height,d=id.data,g=new Float32Array(w*h);
  for(let i=0;i<w*h;i++)g[i]=0.299*d[i*4]+0.587*d[i*4+1]+0.114*d[i*4+2];
  if(useFS){
    for(let y=0;y<h;y++)for(let x=0;x<w;x++){
      const i=y*w+x,old=g[i],nw=old<128?0:255,err=old-nw;g[i]=nw;
      if(x+1<w)g[i+1]+=err*7/16;
      if(y+1<h){if(x>0)g[i+w-1]+=err*3/16;g[i+w]+=err*5/16;if(x+1<w)g[i+w+1]+=err*1/16;}
    }
  }else{for(let i=0;i<w*h;i++)g[i]=g[i]>=thr?255:0;}
  for(let i=0;i<w*h;i++){const v=g[i]<=0?0:(g[i]>=255?255:g[i]);d[i*4]=d[i*4+1]=d[i*4+2]=v;d[i*4+3]=255;}
}
function render(){
  if(!srcImg)return;
  const W=SCRW,H=SCRH; let sw=srcImg.naturalWidth,sh=srcImg.naturalHeight,src=srcImg;
  const rot=parseInt(P.rotate)||0;
  if(rot){const t=document.createElement("canvas");
    if(rot===90||rot===270){t.width=sh;t.height=sw;}else{t.width=sw;t.height=sh;}
    const tc=t.getContext("2d");tc.translate(t.width/2,t.height/2);tc.rotate(rot*Math.PI/180);
    tc.drawImage(srcImg,-sw/2,-sh/2);src=t;sw=t.width;sh=t.height;}
  const ctx=cv.getContext("2d",{willReadFrequently:true});
  ctx.filter="none";ctx.fillStyle="#fff";ctx.fillRect(0,0,W,H);
  ctx.filter="brightness("+P.brightness+") contrast("+P.contrast+")"+(P.invert==="1"?" invert(1)":"");
  const fit=P.fit;
  if(fit==="stretch"){ctx.drawImage(src,0,0,W,H);}
  else if(fit==="cover"){const s=Math.max(W/sw,H/sh),dw=sw*s,dh=sh*s;ctx.drawImage(src,(W-dw)/2,(H-dh)/2,dw,dh);}
  else if(fit==="center"){ctx.drawImage(src,(W-sw)/2,(H-sh)/2);}
  else{const s=Math.min(W/sw,H/sh),dw=sw*s,dh=sh*s;ctx.drawImage(src,(W-dw)/2,(H-dh)/2,dw,dh);}
  ctx.filter="none";
  const id=ctx.getImageData(0,0,W,H);floyd(id,P.dither!=="none",parseInt(P.threshold)||128);
  ctx.putImageData(id,0,0);
  $("dim").textContent=D().dimDone+" · "+W+"×"+H+" · 1-bit";
}

// ---- контролы -> мгновенный пере-рендер ----
document.querySelectorAll(".seg").forEach(seg=>{
  seg.addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;
    seg.querySelectorAll("button").forEach(x=>x.classList.remove("on"));
    b.classList.add("on");P[seg.dataset.k]=b.dataset.v;render();});
});
[["brightness","vbr"],["contrast","vct"],["threshold","vth"]].forEach(([id,lab])=>{
  $(id).addEventListener("input",()=>{P[id]=$(id).value;$(lab).textContent=$(id).value;render();});
});
$("invert").addEventListener("change",()=>{P.invert=$("invert").checked?"1":"0";render();});

// ---- отправка на девайс ----
// action — в query, картинку шлём сырым телом (не формой) — так надёжнее всего
async function post(action,withImage){
  const opt={method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":CSRF}};
  if(withImage){opt.body=cv.toDataURL("image/png");
    opt.headers["Content-Type"]="text/plain;charset=UTF-8";}
  try{const r=await fetch(BASE+"?action="+action,opt);
    let j=null;try{j=await r.json();}catch(e){}
    if(!r.ok||!j){toast(D().err+" "+r.status);return null;}return j;}
  catch(e){toast(D().net);return null;}
}

$("bSave").addEventListener("click",async()=>{if($("bSave").disabled)return;
  const j=await post("save",true);if(j)toast(j.msg||"OK");});

$("bDev").addEventListener("click",async()=>{
  if($("bDev").disabled||devCooldown)return;
  if(!srcImg){toast(D().noimg);return;}
  devCooldown=true;$("bDev").disabled=true;
  const j=await post("ondevice",true);if(j)toast(j.msg||"OK");
  setTimeout(()=>{devCooldown=false;$("bDev").disabled=false;},5000);
});

$("bInstall").addEventListener("click",async()=>{
  const j=await post(svc?"uninstall":"install",false);if(j&&j.ok){svc=!svc;svcLabel();}
  if(j)toast(j.msg||"OK");});

applyLang();
</script></body></html>"""
