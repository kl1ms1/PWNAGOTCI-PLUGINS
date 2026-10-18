"""
bootlogo — кастомное бут-лого для Pwnagotchi.

Что умеет:
  • Веб-морда прямо в разделе плагинов (http://<ip>:8080/plugins/bootlogo/):
      - загрузил фото → плагин сам подгоняет под твой экран и переводит в ч/б (дизеринг под e-ink);
      - режимы подгона: растянуть / вписать / обрезать по центру / по центру без масштаба;
      - эффекты: дизеринг (Floyd–Steinberg) или порог, инверсия, яркость, контраст, поворот;
      - живое превью увеличенным «пикселями»;
      - кнопка «Сохранить как бут-лого».
  • Кнопка «Включить показ при загрузке» — ставит systemd-сервис, который рисует картинку
    на e-ink ДО старта pwnagotchi (т.е. сразу при включении).

Размер экрана определяется автоматически (по рендеру UI). Если не определился —
задаётся опциями width/height в config.toml.
"""

import io
import logging
import os
import shutil
import subprocess

import pwnagotchi.plugins as plugins

# --- встроенные ресурсы для установки автозапуска --------------------------
# Размеры большинства распространённых панелей (fallback, если авто-детект не сработал).
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
ExecStart=/usr/bin/python3 {script}
RemainAfterExit=no

[Install]
WantedBy=multi-user.target
"""

# Скрипт, который рисует лого на e-ink до старта pwnagotchi.
# {type} подставляется при установке как fallback, если его нет в config.toml.
_BOOT_SCRIPT = '''#!/usr/bin/env python3
"""Рисует бут-лого на e-ink до старта pwnagotchi (ставится плагином bootlogo)."""
import os, logging

CONFIG = "/etc/pwnagotchi/config.toml"
LOGO = "{logo}"
FALLBACK_TYPE = "{type}"

def _load_cfg():
    try:
        with open(CONFIG, "rb") as f:
            import tomllib
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
    __version__ = "0.1.0"
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
        # последние применённые параметры обработки (для перерисовки формы)
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
        # авто-детект размера экрана и типа дисплея
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
        img = ImageOps.exif_transpose(img)  # учесть ориентацию с телефона

        # подложка под прозрачность
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
            out = g.convert("1")  # Floyd–Steinberg
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

    def _handle_process(self, request):
        # новый файл?
        up = request.files.get("image") if request.files else None
        if up and up.filename:
            up.save(self._orig)
        self._read_params(request.form)
        if not os.path.exists(self._orig):
            return self._render(message="⚠️ Сначала загрузи изображение")
        out = self._process(self._orig)
        out.save(self._preview)
        return self._render(message="🔄 Превью обновлено")

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
            return True, "✅ Автозапуск включён (сервис pwnagotchi-bootlogo)"
        except Exception as e:
            logging.exception("[bootlogo] install service failed")
            return False, "⚠️ Не удалось поставить сервис: %s" % e

    # --- web UI ------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import send_file, abort
        try:
            if path == "preview.png":
                if os.path.exists(self._preview):
                    return send_file(self._preview, mimetype="image/png")
                abort(404)
            if request.method == "POST":
                action = request.form.get("action", "process")
                if action == "save":
                    self._save_boot_logo()
                    return self._render(message="✅ Сохранено как бут-лого")
                if action == "install":
                    _, msg = self._install_service()
                    return self._render(message=msg)
                return self._handle_process(request)
            return self._render()
        except Exception as e:
            logging.exception("[bootlogo] webhook error")
            return self._render(message="⚠️ Ошибка: %s" % e)

    def _render(self, message=""):
        p = self._p
        has_prev = os.path.exists(self._preview)
        has_logo = os.path.exists(self._logo)
        scale = max(1, min(4, 800 // max(1, self._w)))
        sel = lambda cur, val: "selected" if cur == val else ""
        chk = "checked" if p["invert"] else ""
        prev_block = ""
        if has_prev:
            prev_block = (
                '<div class="card"><h3>Превью ({w}×{h})</h3>'
                '<img class="prev" src="/plugins/bootlogo/preview.png?x={rnd}" '
                'style="width:{pw}px"/>'
                '<form method="POST"><input type="hidden" name="action" value="save">'
                '<button class="ok">💾 Сохранить как бут-лого</button></form>'
                '</div>'
            ).format(w=self._w, h=self._h, rnd=os.urandom(3).hex(),
                     pw=self._w * scale)
        logo_note = "есть ✅" if has_logo else "ещё нет"
        msg_block = ('<div class="card msg">%s</div>' % message) if message else ""
        return _PAGE.format(
            msg_block=msg_block, w=self._w, h=self._h, logo=self._logo,
            logo_note=logo_note,
            c_str=sel(p["fit"], "stretch"), c_con=sel(p["fit"], "contain"),
            c_cov=sel(p["fit"], "cover"), c_cen=sel(p["fit"], "center"),
            d_fl=sel(p["dither"], "floyd"), d_no=sel(p["dither"], "none"),
            thr=p["threshold"], br=p["brightness"], ct=p["contrast"],
            r0=sel(str(p["rotate"]), "0"), r90=sel(str(p["rotate"]), "90"),
            r180=sel(str(p["rotate"]), "180"), r270=sel(str(p["rotate"]), "270"),
            inv=chk, preview=prev_block,
        )


_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bootlogo</title><style>
:root{{color-scheme:dark}}
body{{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:16px}}
h2{{margin:.2em 0}} h3{{margin:.4em 0}}
.wrap{{max-width:720px;margin:0 auto}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:16px;margin:12px 0}}
label{{display:block;margin:8px 0 4px;font-size:.9em;color:#9da7b3}}
select,input[type=range],input[type=file]{{width:100%}}
.row{{display:flex;gap:12px;flex-wrap:wrap}} .row>div{{flex:1;min-width:140px}}
button{{background:#238636;color:#fff;border:0;border-radius:8px;padding:10px 16px;font-size:1em;cursor:pointer;margin-top:10px}}
button.ok{{background:#1f6feb}} button.ghost{{background:#30363d}}
.prev{{image-rendering:pixelated;border:1px solid #30363d;background:#fff;margin:8px 0;max-width:100%}}
.msg{{background:#1f2937;border-left:3px solid #1f6feb;padding:8px 12px;border-radius:6px}}
.muted{{color:#7d8590;font-size:.85em}}
</style></head><body><div class="wrap">
<h2>🐾 bootlogo</h2>
<p class="muted">Экран: <b>{w}×{h}</b> · Бут-лого: {logo_note} · <code>{logo}</code></p>
{msg_block}
<div class="card"><h3>1. Картинка и эффекты</h3>
<form method="POST" enctype="multipart/form-data">
<input type="hidden" name="action" value="process">
<label>Файл изображения (jpg/png)</label>
<input type="file" name="image" accept="image/*">
<div class="row">
<div><label>Подгон под экран</label><select name="fit">
<option value="contain" {c_con}>Вписать (с полями)</option>
<option value="cover" {c_cov}>Обрезать по центру</option>
<option value="stretch" {c_str}>Растянуть</option>
<option value="center" {c_cen}>По центру (без масштаба)</option>
</select></div>
<div><label>Перевод в ч/б</label><select name="dither">
<option value="floyd" {d_fl}>Дизеринг (Floyd–Steinberg)</option>
<option value="none" {d_no}>Порог (чёткое ч/б)</option>
</select></div>
<div><label>Поворот</label><select name="rotate">
<option value="0" {r0}>0°</option><option value="90" {r90}>90°</option>
<option value="180" {r180}>180°</option><option value="270" {r270}>270°</option>
</select></div>
</div>
<label>Порог ч/б (для режима «Порог»): <span>{thr}</span></label>
<input type="range" name="threshold" min="0" max="255" value="{thr}">
<label>Яркость: {br}</label>
<input type="range" name="brightness" min="0.3" max="2.0" step="0.05" value="{br}">
<label>Контраст: {ct}</label>
<input type="range" name="contrast" min="0.3" max="2.5" step="0.05" value="{ct}">
<label><input type="checkbox" name="invert" {inv}> Инверсия (негатив)</label>
<button>🔄 Обработать / обновить превью</button>
</form></div>
{preview}
<div class="card"><h3>3. Показ при включении</h3>
<p class="muted">Ставит systemd-сервис, который рисует бут-лого на e-ink сразу при загрузке, до старта pwnagotchi.</p>
<form method="POST"><input type="hidden" name="action" value="install">
<button class="ghost">⚙️ Включить показ при загрузке</button></form>
</div>
<p class="muted">bootlogo · только для своих устройств 🫡</p>
</div></body></html>"""
