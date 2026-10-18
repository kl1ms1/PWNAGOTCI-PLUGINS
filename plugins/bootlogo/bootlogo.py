"""
bootlogo — кастомное бут-лого для Pwnagotchi.

Веб-морда (http://<ip>:8080/plugins/bootlogo/):
  • перетащи/выбери фото → живое превью в рамке «как на e-ink» (без перезагрузок);
  • подгон: вписать / обрезать / растянуть / по центру;
  • эффекты: дизеринг (Floyd–Steinberg) или порог, инверсия, яркость, контраст, поворот;
  • «Сохранить как бут-лого» и «Показ при загрузке» (вкл/выкл systemd-сервиса,
    который рисует лого на e-ink сразу при включении, с жёстким таймаутом).

Размер экрана определяется автоматически (по рендеру UI); можно задать width/height
в config.toml.
"""

import logging
import os
import shutil
import subprocess

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
    __version__ = "0.2.0"
    __license__ = "MIT"
    __description__ = "Кастомное бут-лого с веб-загрузчиком и авто-обработкой под e-ink."

    def __init__(self):
        self._w = 250
        self._h = 122
        self._display_type = ""
        self._dir = "/root/.bootlogo"
        self._orig = os.path.join(self._dir, "original")
        self._preview = os.path.join(self._dir, "preview.png")
        self._logo = "/root/pwnagotchi-bootlogo.png"
        self._p = dict(fit="contain", dither="floyd", threshold=128,
                       brightness=1.0, contrast=1.0, rotate=0, invert=False)

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
            im = agent.view().image()
            if im is not None and im.size[0] > 0:
                self._w, self._h = im.size
        except Exception:
            pass
        logging.info("[bootlogo] ready (display=%s, %dx%d)",
                     self._display_type, self._w, self._h)

    # --- обработка изображения --------------------------------------------
    def _process(self, src_path):
        from PIL import Image, ImageOps, ImageEnhance
        W, H = self._w, self._h
        p = self._p

        img = Image.open(src_path)
        img = ImageOps.exif_transpose(img)

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img)
        img = img.convert("L")

        rot = int(p["rotate"]) % 360
        if rot:
            img = img.rotate(-rot, expand=True, fillcolor=255)

        if float(p["brightness"]) != 1.0:
            img = ImageEnhance.Brightness(img).enhance(float(p["brightness"]))
        if float(p["contrast"]) != 1.0:
            img = ImageEnhance.Contrast(img).enhance(float(p["contrast"]))
        if p["invert"]:
            img = ImageOps.invert(img)

        fit = p["fit"]
        if fit == "stretch":
            g = img.resize((W, H), Image.LANCZOS)
        elif fit == "cover":
            g = ImageOps.fit(img, (W, H), method=Image.LANCZOS, centering=(0.5, 0.5))
        elif fit == "center":
            g = Image.new("L", (W, H), 255)
            left = max(0, (img.width - W) // 2)
            top = max(0, (img.height - H) // 2)
            crop = img.crop((left, top, left + min(W, img.width),
                             top + min(H, img.height)))
            g.paste(crop, ((W - crop.width) // 2, (H - crop.height) // 2))
        else:  # contain
            im2 = img.copy()
            im2.thumbnail((W, H), Image.LANCZOS)
            g = Image.new("L", (W, H), 255)
            g.paste(im2, ((W - im2.width) // 2, (H - im2.height) // 2))

        if p["dither"] == "none":
            thr = int(p["threshold"])
            out = g.point(lambda v: 255 if v >= thr else 0, mode="1")
        else:
            out = g.convert("1")
        return out

    def _read_params(self, form):
        def f(name, default, cast):
            try:
                return cast(form.get(name, default))
            except Exception:
                return default
        self._p = dict(
            fit=form.get("fit", "contain"),
            dither=form.get("dither", "floyd"),
            threshold=f("threshold", 128, int),
            brightness=f("brightness", 1.0, float),
            contrast=f("contrast", 1.0, float),
            rotate=f("rotate", 0, int),
            invert=(form.get("invert") in ("on", "1", "true", "True")),
        )

    # --- действия ----------------------------------------------------------
    def _save_boot_logo(self):
        if not os.path.exists(self._preview):
            raise RuntimeError("нет превью — сначала обработай картинку")
        shutil.copyfile(self._preview, self._logo)

    def _install_service(self):
        try:
            script = _BOOT_SCRIPT.format(logo=self._logo,
                                         type=self._display_type or "")
            with open(_BOOT_SCRIPT_PATH, "w") as fh:
                fh.write(script)
            os.chmod(_BOOT_SCRIPT_PATH, 0o755)
            with open(_SERVICE_PATH, "w") as fh:
                fh.write(_SERVICE_UNIT.format(script=_BOOT_SCRIPT_PATH))
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "pwnagotchi-bootlogo.service"],
                           check=True)
            return True, "Показ при загрузке включён"
        except Exception as e:
            logging.exception("[bootlogo] install service failed")
            return False, "Не удалось включить: %s" % e

    def _uninstall_service(self):
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

    def _service_enabled(self):
        return os.path.exists(_SERVICE_PATH)

    # --- web API -----------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import send_file, jsonify, abort
        try:
            if request.method == "GET":
                if path in (None, "", "/"):
                    return self._page()
                if path == "preview.png" and os.path.exists(self._preview):
                    return send_file(self._preview, mimetype="image/png")
                if path == "current.png" and os.path.exists(self._logo):
                    return send_file(self._logo, mimetype="image/png")
                abort(404)

            action = (path or "").strip("/")
            if action == "process":
                up = request.files.get("image") if request.files else None
                if up and up.filename:
                    up.save(self._orig)
                self._read_params(request.form)
                if not os.path.exists(self._orig):
                    return jsonify(ok=False, msg="Сначала загрузи изображение"), 400
                self._process(self._orig).save(self._preview)
                return jsonify(ok=True, w=self._w, h=self._h)
            if action == "save":
                self._save_boot_logo()
                return jsonify(ok=True, msg="Сохранено как бут-лого ✅")
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
        return (_APP_HTML
                .replace("__W__", str(self._w))
                .replace("__H__", str(self._h))
                .replace("__SVC__", "1" if self._service_enabled() else "0")
                .replace("__DISP__", self._display_type or "—"))


_APP_HTML = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bootlogo</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;
--fg:#e6edf3;--acc:#1f6feb;--ok:#238636}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);
margin:0;padding:16px;line-height:1.4}
.wrap{max-width:560px;margin:0 auto}
h1{font-size:1.3rem;margin:.2em 0}
.sub{color:var(--mut);font-size:.85rem;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}
.drop{border:2px dashed var(--line);border-radius:12px;padding:22px;text-align:center;
color:var(--mut);cursor:pointer;transition:.15s}
.drop:hover,.drop.hot{border-color:var(--acc);color:var(--fg);background:#0b1b33}
.stage{display:flex;justify-content:center;margin:4px 0 2px}
.frame{background:#c9ccd1;border-radius:14px;padding:12px;box-shadow:0 6px 18px #0008;max-width:100%}
.screen{background:#fff;border-radius:4px;overflow:hidden;aspect-ratio:__W__/__H__;
width:min(420px,78vw)}
.screen img{width:100%;height:100%;display:block;image-rendering:pixelated}
.ph{display:flex;align-items:center;justify-content:center;height:100%;color:#9aa0a6;font-size:.85rem}
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
pointer-events:none;max-width:90vw}
.toast.show{opacity:1}
.spin{display:inline-block;width:14px;height:14px;border:2px solid #ffffff55;border-top-color:#fff;
border-radius:50%;animation:s .7s linear infinite;vertical-align:-2px;margin-right:6px}
@keyframes s{to{transform:rotate(360deg)}}
.muted{color:var(--mut);font-size:.78rem;margin-top:10px;text-align:center}
</style></head><body><div class="wrap">
<h1>🐾 bootlogo</h1>
<div class="sub">Экран <b>__W__×__H__</b> · дисплей <code>__DISP__</code></div>

<div class="card">
  <div id="drop" class="drop">📷 Перетащи фото сюда или нажми, чтобы выбрать</div>
  <input id="file" type="file" accept="image/*" hidden>
  <div class="stage"><div class="frame"><div class="screen">
    <img id="prev" alt="" style="display:none">
    <div id="ph" class="ph">превью появится здесь</div>
  </div></div></div>
  <div class="dim" id="dim">предпросмотр как на e-ink</div>
</div>

<div class="card" id="controls" style="opacity:.5;pointer-events:none">
  <label>Подгон под экран</label>
  <div class="seg" data-k="fit">
    <button data-v="contain" class="on">Вписать</button>
    <button data-v="cover">Обрезать</button>
    <button data-v="stretch">Растянуть</button>
    <button data-v="center">По центру</button>
  </div>
  <label>Перевод в ч/б</label>
  <div class="seg" data-k="dither">
    <button data-v="floyd" class="on">Дизеринг</button>
    <button data-v="none">Порог</button>
  </div>
  <label>Поворот</label>
  <div class="seg" data-k="rotate">
    <button data-v="0" class="on">0°</button><button data-v="90">90°</button>
    <button data-v="180">180°</button><button data-v="270">270°</button>
  </div>
  <div class="row">
    <div><label>Яркость <span class="val" id="vbr">1.0</span></label>
      <input id="brightness" type="range" min="0.3" max="2.0" step="0.05" value="1.0"></div>
    <div><label>Контраст <span class="val" id="vct">1.0</span></label>
      <input id="contrast" type="range" min="0.3" max="2.5" step="0.05" value="1.0"></div>
  </div>
  <label>Порог ч/б (для режима «Порог») <span class="val" id="vth">128</span></label>
  <input id="threshold" type="range" min="0" max="255" value="128">
  <div class="switch"><input id="invert" type="checkbox"><label style="margin:0">Инверсия (негатив)</label></div>
</div>

<div class="card">
  <div class="actions">
    <button class="btn save" id="bSave" disabled>💾 Сохранить как бут-лого</button>
  </div>
  <div class="actions" style="margin-top:10px">
    <button class="btn ghost" id="bInstall"></button>
  </div>
  <div class="muted">Сохранение не трогает экран. «Показ при загрузке» рисует лого при включении (с таймаутом 20 c).</div>
</div>
<div class="muted">bootlogo · только для своих устройств 🫡</div>
</div>

<div id="toast" class="toast"></div>
<script>
const BASE="/plugins/bootlogo/";
let hasFile=false, svc=(__SVC__===1), busy=false, t=null;
const P={fit:"contain",dither:"floyd",rotate:"0",brightness:"1.0",contrast:"1.0",threshold:"128",invert:"0"};
const $=id=>document.getElementById(id);

function toast(m){const e=$("toast");e.textContent=m;e.classList.add("show");
  clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove("show"),2600);}
function svcLabel(){$("bInstall").textContent=svc?"🧹 Выключить показ при загрузке":"⚙️ Включить показ при загрузке";}

// сегментные кнопки
document.querySelectorAll(".seg").forEach(seg=>{
  seg.addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;
    seg.querySelectorAll("button").forEach(x=>x.classList.remove("on"));
    b.classList.add("on");P[seg.dataset.k]=b.dataset.v;process();});
});
// ползунки
[["brightness","vbr"],["contrast","vct"],["threshold","vth"]].forEach(([id,lab])=>{
  $(id).addEventListener("input",()=>{P[id]=$(id).value;$(lab).textContent=$(id).value;debounce();});
});
$("invert").addEventListener("change",()=>{P.invert=$("invert").checked?"1":"0";process();});

// загрузка файла
$("drop").addEventListener("click",()=>$("file").click());
$("file").addEventListener("change",()=>{if($("file").files[0])process($("file").files[0]);});
["dragover","dragenter"].forEach(ev=>$("drop").addEventListener(ev,e=>{e.preventDefault();$("drop").classList.add("hot");}));
["dragleave","drop"].forEach(ev=>$("drop").addEventListener(ev,e=>{e.preventDefault();$("drop").classList.remove("hot");}));
$("drop").addEventListener("drop",e=>{const f=e.dataTransfer.files[0];if(f)process(f);});

function debounce(){clearTimeout(t);t=setTimeout(()=>process(),250);}

async function process(file){
  if(!hasFile && !file) return;
  if(busy){debounce();return;}
  busy=true;
  const fd=new FormData();
  if(file) fd.append("image",file);
  for(const k in P) fd.append(k,P[k]);
  try{
    const r=await fetch(BASE+"process",{method:"POST",body:fd});
    const j=await r.json();
    if(!j.ok){toast(j.msg||"Ошибка");busy=false;return;}
    hasFile=true;
    $("controls").style.opacity=1;$("controls").style.pointerEvents="auto";
    $("bSave").disabled=false;
    $("ph").style.display="none";
    const img=$("prev");img.style.display="block";
    img.src=BASE+"preview.png?ts="+Date.now();
    $("dim").textContent="обработано "+j.w+"×"+j.h+" · 1-бит";
  }catch(e){toast("Сеть недоступна");}
  busy=false;
}

async function act(ep){
  try{const r=await fetch(BASE+ep,{method:"POST"});const j=await r.json();
    toast(j.msg||(j.ok?"Готово":"Ошибка"));return j;}
  catch(e){toast("Сеть недоступна");return{ok:false};}
}
$("bSave").addEventListener("click",async()=>{if($("bSave").disabled)return;await act("save");});
$("bInstall").addEventListener("click",async()=>{
  const j=await act(svc?"uninstall":"install");if(j.ok){svc=!svc;svcLabel();}});

svcLabel();
</script></body></html>"""
