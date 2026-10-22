#!/usr/bin/env python3
"""
Reference boot script: draws the boot logo on the e-ink before pwnagotchi starts.

Normally the plugin's web UI installs it (the "Enable show on boot" button).
This file is for manual install/editing. The display model is read from config.toml
(ui.display.type), so it must be set there.

Manual install:
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
        logging.getLogger().error("bootlogo: ui.display.type not set in config.toml")
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
