# Changelog

Versions of the plugins in this repository.

## callout (formerly deauth-announcer)

### 0.5.0
- **English web UI**. The **spoken phrases stay Russian** (that's what the device
  says), now proper sentences (capitalized, with a period) and more varied.
- Name resolution prefers the **device name**: `hostname` → `Vendor-XXXX` →
  `Device-XXXX`, instead of just the vendor.

### 0.4.0
- The **"Test phrase"** button now shows the phrase **on the screen itself** (e-ink),
  not just in the browser. Duration via the `test_seconds` option.

### 0.3.0
- Renamed to **callout**; added a **"Test phrase"** button in the web UI.

### 0.2.0 (as deauth-announcer)
- Patches `voice.on_deauth` in memory: pwnagotchi says the name instead of the MAC.

### 0.1.0
- First version (a line on the e-ink).

## pwndex

### 0.5.0
- **Export passwords**: a button downloads all saved passwords as a `.txt` (SSID / MAC / vendor / password).
- Saving a password now **confirms in the UI** that the network was added to the whitelist
  ("saved ✓ · added to whitelist 🔒"); the auto-whitelist runs on every save.

### 0.4.0
- **English UI**.
- **Browse by brand**: clickable vendor chips (Xiaomi, TP-Link…), marketplace style,
  each with a per-brand count.
- Clearer **Download .pcap** button on caught entries.

### 0.3.0
- Caught networks get their **handshake (.pcap)** attached — downloadable from the web UI.
- **Vendor filter** in addition to search and filters.

### 0.2.0
- Networks with a password are auto-added to `main.whitelist` (don't attack your own).

### 0.1.0
- Network pokedex + password store + wpa-sec import.

## brain

### 0.3.0
- **English web UI + settings**. The **spoken lines stay Russian** (proper sentences
  with the channel, e.g. "Меняю тактику → канал 11.").
- `(A_I)` now shows **instead of the face** on a decision (configurable `face_mode`,
  shorter default hold).
- **Web Settings panel**: tweak display time and the reward amounts live; rewards are
  shown as a configurable **currency** (`$`). Settings persist in `/root/.brain/settings.json`.

### 0.2.0
- `(A_I)` shown instead of the face on a decision; lines rewritten.

### 0.1.0
- AI agent (bandit): learns by channel and steers scanning, `(A_I)` face, web stats.

## bootlogo

### 0.4.7
- Duration sliders: **show on screen** (2–10 s) and **hold the logo on boot** (3–30 s).

### 0.4.6
- The boot splash runs with pwnagotchi's **correct interpreter** (fixes "No module named pwnagotchi").

### 0.4.5
- Show-on-screen reverted to the event-based variant; the boot script writes a log; cleaner service timing.

### 0.4.3
- The display object is grabbed via UI hooks (`on_ui_setup`/`on_ui_update`) — fixes "display unavailable".

### 0.4.2
- **"Error 400" fix**: sends the CSRF token (pwnagotchi's web server has CSRFProtect on).

### 0.4.1
- More robust transport: `action` in the query string, the image as the raw body (no form parsing).

### 0.4.0
- All processing and preview **in the browser** (instant, no 400 on preview); a **"Show on screen"** button; RU/EN.

### 0.3.x
- Live preview without reboots, RU/EN toggle, in-browser photo compression.

### 0.2.0
- AJAX web UI: drag-and-drop, live preview, "as on e-ink" frame.

### 0.1.0
- First release: web photo uploader, fit to screen, dithering/effects, boot splash (systemd).
