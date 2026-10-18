#!/usr/bin/env python3
"""
Референс boot-скрипта: рисует бут-лого на e-ink до старта pwnagotchi.

Обычно его ставит сама веб-морда плагина (кнопка «Включить показ при загрузке»).
Этот файл — для ручной установки/правки. Модель дисплея берётся из config.toml
(ui.display.type), поэтому она должна быть там прописана.

Ручная установка:
    sudo cp boot_logo_show.py /usr/local/bin/pwnagotchi-bootlogo.py
    sudo chmod +x /usr/local/bin/pwnagotchi-bootlogo.py
    sudo cp pwnagotchi-bootlogo.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable pwnagotchi-bootlogo.service
"""
import os
import logging

CONFIG = "/etc/pwnagotchi/config.toml"
LOGO = "/root/pwnagotchi-bootlogo.png"


def _load_cfg():
    try:
        import tomllib
        with open(CONFIG, "rb") as f:
            return tomllib.load(f)
    except Exception:
        try:
            import toml
            return toml.load(CONFIG)
        except Exception:
            return {}


def main():
    if not os.path.exists(LOGO):
        return
    cfg = _load_cfg()
    disp = cfg.setdefault("ui", {}).setdefault("display", {})
    if not disp.get("type"):
        logging.getLogger().error("bootlogo: ui.display.type не задан в config.toml")
        return
    disp.setdefault("enabled", True)
    disp.setdefault("rotation", 180)
    disp.setdefault("color", "black")

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
