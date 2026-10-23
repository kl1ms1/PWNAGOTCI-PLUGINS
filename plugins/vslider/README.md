# 🎚️ vslider

A **virtual slider** for pwnagotchi (web UI) — a stand-in for the future hardware
3-position switch. You flip positions in the web page (opened like pwndex/brain).

Open: `http://<ip>:8080/plugins/vslider/`

## Positions
1. **Auto** — normal hunting (resumes `wifi.recon`).
2. **Dashboard** — **pauses hunting** (`wifi.recon off`) and shows a **carousel** of
   mini-charts that **rotates every 5 seconds** (tap to flip): temperature, CPU,
   memory (sparklines) and uptime.
3. **???** — reserved; we'll decide what it does (ideas: Sync upload to wpa-sec,
   disguise mode, e-ink carousel).

The chosen position persists across restarts (`/root/.vslider/state.json`).

## Install
```bash
sudo cp vslider.py /usr/local/share/pwnagotchi/custom-plugins/
sudo nano /etc/pwnagotchi/config.toml   # main.plugins.vslider.enabled = true
sudo systemctl restart pwnagotchi
```

## v1 scope
Web-only. The e-ink carousel on the device and the real Sync (connect to your own
network → upload to wpa-sec) come next. Metrics are sampled each epoch into a short
rolling history for the sparklines.

> ⚠️ Pausing uses bettercap's `wifi.recon off/on` at runtime — it doesn't touch your
> config. Your own networks / authorized tests only.
