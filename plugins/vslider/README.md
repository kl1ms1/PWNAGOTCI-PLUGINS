# 🎚️ vslider

A **virtual slider** for pwnagotchi (web UI) — a stand-in for the future hardware
3-position switch. You flip positions in the web page (opened like pwndex/brain).

Open: `http://<ip>:8080/plugins/vslider/`

## Positions
1. **Auto** — normal pwnagotchi hunting (resumes `wifi.recon`).
2. **Dashboard** — **fully pauses hunting** (`wifi.recon off`, like manual mode — nothing
   is searched, radio quiet, easy on battery/heat) and shows a **tabbed dashboard**
   whose tabs **auto-rotate**:
   - 🏆 **Охота** (5s) — hunt stats (hashes/min, total, session, temp, networks/with-password,
     caught/seen, top channel, nearby, streak, status) + a connection line + a QR placeholder.
   - 🖥 **Система** (15s) — temperature / CPU / memory with live sparklines + SD card.
   - 🎞 **Комикс** (5s) — a procedural 3-frame "comic of the day" (generated from state,
     no hand-drawn art).
   - 🔑 **Пароли** (10s = 2×5s) — **Cracked networks** (from wpa-sec 🟦 and pwndex 🟨) and
     **Nearby** (visible networks, with password first, "нет пароля" last).
   - ⭐ **№5** (5s) — reserved.
3. **???** — reserved.

The chosen position persists across restarts (`/root/.vslider/state.json`). Handshake
totals and the day streak are kept in `/root/.vslider/stats.json` (survive reboots —
important without a battery).

## Install
```bash
sudo cp vslider.py /usr/local/share/pwnagotchi/custom-plugins/
sudo nano /etc/pwnagotchi/config.toml   # main.plugins.vslider.enabled = true
sudo systemctl restart pwnagotchi
```

## Options
| Key | Default | Description |
|---|---|---|
| `enabled` | — | turn it on |
| `ap_ssid` / `ap_pass` | `pwn-ap` / `changeme` | shown on the connection line (and future QR) |
| `web` | `http://10.0.0.2:8080` | web UI link on the connection line |
| `pwndex` | `/root/.pwndex/dex.json` | pwndex catalog for the passwords tab |

## v1 notes
- Web-only. The e-ink carousel on the device comes later.
- The **Wi-Fi-join QR** and the real **Sync** upload (connect to your own network →
  wpa-sec) need the device to raise its own AP — that's the planned **Sync/position 3**,
  so the QR is a placeholder for now and the connection details are shown as text.
- Passwords are read from wpa-sec + pwndex — displayed for **your own networks /
  authorized tests only**.

> ⚠️ Your own networks / authorized tests only.
