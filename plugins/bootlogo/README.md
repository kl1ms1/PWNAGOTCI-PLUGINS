# 🖼️ bootlogo

A custom boot logo for Pwnagotchi with a **web uploader**: drop a photo in the
browser — the plugin fits it to your screen, converts it to black & white
(e-ink dithering) and can show the image **when the device powers on**.

## What it does
- Web UI with **drag-and-drop** photo upload.
- **All processing and preview happen in the browser** (instant, no round-trips to
  the device): live preview in an "as on e-ink" frame.
- Fit to screen: **contain / center-crop / stretch / center at native size**.
- Effects: **dithering** (Floyd–Steinberg) or **threshold**, **invert**,
  **brightness**, **contrast**, **rotation**.
- 👁 **"Show on screen"** — pushes the image to the e-ink **without a reboot**
  (the frame is handed to pwnagotchi's normal render thread, no races).
- 💾 **"Save as boot logo"** — only the small final PNG goes to the device.
- A **"Show on boot"** toggle (systemd service, timeout auto-tuned).
- **Duration sliders**: how long to hold the preview on screen (2–10 s) and how
  long to hold the logo on boot (3–30 s).
- **RU/EN language toggle** (remembered in the browser).
- Screen size is **auto-detected** (can be overridden in the config).

## Install
```bash
sudo cp bootlogo.py /usr/local/share/pwnagotchi/custom-plugins/
sudo nano /etc/pwnagotchi/config.toml   # add the lines from bootlogo.toml
sudo systemctl restart pwnagotchi
```

## How to use
1. Open `http://<ip>:8080/plugins/bootlogo/` (same login/password as the pwnagotchi web UI).
2. Upload a photo, tweak fit/effects, hit **"Process"** — watch the preview.
3. **"Save as boot logo"** — the image goes to `/root/pwnagotchi-bootlogo.png`.
4. **"Enable show on boot"** — once, so the logo appears at power-on.

## Show on boot — how it works
The button installs a oneshot service `pwnagotchi-bootlogo.service` with
`Before=pwnagotchi.service`: at boot it draws the saved PNG straight to the e-ink,
reusing pwnagotchi's display driver. The model is read from `ui.display.type` in
`config.toml` — it must be set there (usually done when the image is flashed).

## Options (config.toml)
| Key | Default | Description |
|---|---|---|
| `enabled` | — | turn the plugin on |
| `path` | `/root/pwnagotchi-bootlogo.png` | where to save the boot logo |
| `width` / `height` | auto | screen size if auto-detect fails |

## Troubleshooting
| Symptom | What to do |
|---|---|
| web page 404 | check `main.custom_plugins` and the filename `bootlogo.py` |
| preview looks "muddy" | switch dithering↔threshold, tweak threshold, brightness/contrast |
| nothing at boot | is `ui.display.type` set? `systemctl status pwnagotchi-bootlogo` |
| image upside down | pick a rotation in the web UI (the screen is often mounted at 180°) |
| wrong size | set `width`/`height` in the config for your panel |

## 🚑 If the device is slow to boot / screen freezes after "show on boot"
The boot service hung initializing the display. SSH in (sshd runs separately, even
if pwnagotchi didn't come up) and disable it:
```bash
sudo systemctl disable --now pwnagotchi-bootlogo.service
sudo systemctl restart pwnagotchi
```
The service has a hard timeout (20 s), so it can't block boot for long. The usual
cause is a wrong `ui.display.type` in the config: check it and re-save the logo.

> ⚠️ Your own devices only.
