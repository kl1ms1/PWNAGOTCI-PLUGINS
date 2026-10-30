# Changelog

Versions of the plugins in this repository.

## callout (formerly deauth-announcer)

### 0.6.0
- **Announces the target NETWORK, not the client.** It used to say the client's
  vendor ("Xiaomi"/"Apple"); now it names the Wi-Fi it's attacking
  ("Атакую RT-GPON-3868."). The current network is learned from
  `on_association`/`on_deauthentication` (which carry the AP). The client is kept
  as a small secondary line in the web list.

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

### 0.6.4
- The list order is now **configurable** via a dropdown: "no-password first",
  "with-password first", or "as-is" (caught-first / by name). Choice is
  remembered in the browser. (Server sort is neutral again.)

### 0.6.3
- Saving a password now also writes a **Wi-Fi profile** (SSID → password) to
  `/root/.pwndex/profiles.json`, for the upcoming auto-connect / upload flow.
  All profiles are equal (no priority stored).

### 0.6.2
- Networks **without a password are now listed first** (at the top), so it's
  obvious which ones still need a password; ones with a password sort below.

### 0.6.1
- Records **when a password was saved** (`pw_at`) — used by vslider to sort the
  Cracked list newest-first and show the age.

### 0.6.0
- A **"💾 .pcap" button right on each caught network** (next to the badge) — saves the
  handshake file without expanding the entry.
- **Removed** the "Browse by brand" vendor chips (search still matches the vendor).

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

## battery

### 0.1.0
- First version. Reads the **UPS Lite** fuel gauge (MAX17040, I2C `0x36`) and
  draws an **iPhone-style battery icon + %** in the top-right corner, shifting
  the `uptime` label left to make room. Detects charging **without soldering**
  (variant A — by cell voltage ≥ `charge_volts` or a rising charge level) and
  plays a **full-screen "⚡ USB подключён"** animation on plug-in. Degrades
  cleanly to blank when no HAT / no I2C is present. All positions and the
  charge threshold are configurable.

## webshell

### 0.1.1
- Added a **"+ file"** button in the file manager (create a new file, then edit
  and save it). Creating files already worked from the terminal (`touch`,
  `echo > file`) — now it's one click in the folders view too.

### 0.1.0
- First version: a **web file manager + root terminal** for your own device —
  browse/view/edit/download/delete files, make folders, and run shell commands
  (with `cd` remembered). Optional per-plugin `password`; recursive folder
  deletes are left to the terminal on purpose. ⚠️ ROOT access — own device only.

## full_save

### 0.1.0
- First version. Detects a **crackable** handshake per network (EAPOL M1/M3 +
  M2/M4, or PMKID) with a built-in parser; whitelists fully-captured networks so
  pwnagotchi stops re-attacking them, and tidies duplicate `.pcap` files. Safe by
  design: only touches regular `.pcap` files directly inside the handshakes dir,
  rejects symlinks and anything outside, and **moves to a trash folder** instead
  of deleting (unless `hard_delete = true`). Ships a safety test suite.

## vslider

### 0.6.2
- **Upload flow runs once, not in a loop.** On pos 2 it used to re-run the whole
  search → upload → "Я загрузил" sequence every epoch; now it runs once, stays on
  the "Я загрузил, молодец!" result screen, and only runs again when you leave
  pos 2 and come back. (No-profile/error states still retry.)

### 0.6.1
- **Redesigned the Wi-Fi flow screen.** Two columns: on the **left** a big face
  + caption, on the **right** two **huge, stretched "liquid-glass" numbers** —
  top = total **хэши** (handshakes), bottom = **залито** (uploaded). The uploaded
  number **counts up live** as each handshake is sent (real wpa-sec POSTs in live
  mode; a visual count-up in dry-run). The "done" face is now the **sunglasses**
  `(⌐■_■)` with "Я загрузил, я молодец!".
- The profile flow still only runs **in Dashboard (pos 2) with `ap_mode`**, and
  only matches networks that are **currently visible AND saved in pwndex** (it
  picks the single strongest one — it does not cycle through all your profiles).
- **Upload won't hang.** It now sends only handshakes **not uploaded before**
  (remembered in `/root/.vslider/uploaded.json`), so re-entering pos 2 is instant
  instead of re-POSTing everything, and it stops after a **180 s budget** (the
  rest go next time). «залито» is the real **cumulative** count sent to wpa-sec.
  Networking logic (connect over the right ports + upload) is covered by a stubbed
  test suite; the real radio still has to be tried on the device.

### 0.6.0
- **Wi-Fi access-point flow on Dashboard (pos 2), EXPERIMENTAL.** On entering pos 2
  (with `ap_mode`) it runs a full-screen flow: 🔍 search your saved **profiles**
  among nearby networks → if none, a sad face + "закину в другой раз" → if found,
  connect to the strongest one, **upload handshakes to wpa-sec**, show
  "хендшейков X / залито Y", then raise the device's **own AP** (hostapd+dnsmasq).
  Leaving pos 2 (or any failure) auto-restores hunting.
- **Safe by default:** `ap_live=false` is a **dry-run** — it shows the whole flow
  and detects your profiled networks, but changes NO networking. Set
  `ap_live=true` (hostapd + wpa-sec key required) to go live. All profiles are
  equal; the nearest/strongest is chosen.

### 0.5.3
- More **trend graphs** on the e-ink System page (sub-page 2): sparklines for
  Load, Nearby networks and Hash/min, sampled over time (not just temp/CPU/RAM).

### 0.5.2
- The e-ink dashboard now always **starts on the Hunt tab** when you switch to
  Dashboard (pos 2), instead of resuming mid-rotation.

### 0.5.1
- E-ink tabs now have **sub-pages** that rotate every 5 s, matching the web:
  **System** = 3 pages (graphs → load/freq/uptime/near → bettercap/pwngrid/.pcap/IP,
  = 15 s) and **Keys** = 2 pages (cracked → nearby, = 10 s), with little page dots.

### 0.5.0
- **Full web-style dashboard on the e-ink** (Dashboard / pos 2): a real
  full-screen takeover drawn by a custom widget — rounded tab bar at the top
  (Hunt · Sys · Comic · Keys · #5, auto-rotating), rounded cards, live
  **sparkline graphs** (temp/CPU/RAM), a Wi-Fi-join **QR** placeholder, and lots
  of stats. **English**, temperature to one decimal. Each tab draws its own data.
- Covers the normal pwnagotchi UI cleanly (no overlap) while in Dashboard, and
  restores the normal screen in Auto.

### 0.4.1
- **Full dashboard ON the e-ink** in Dashboard mode — the device screen now shows
  the live data (bettercap/pwngrid status, IP, .pcap count, nearby, handshakes,
  cracked passwords, temp/CPU/mem), like the web, instead of just a "paused"
  message. The face is cleared to make room; data refreshes ~every 5s.
- The **switch animation** now plays in the status line (knob sliding
  `[#··]→[·#·]→[··#]`), so nothing overlaps the top clock/uptime.

### 0.4.0
- First e-ink output + **reliable recon resume**: recon state is tracked and
  re-asserted each epoch, so switching Dashboard → Auto always turns hunting back
  on (fixes "on position 1 it doesn't see networks"), without spamming bettercap.

### 0.3.1
- **Passwords tab fixes:** the **Cracked** list is now sorted **newest-saved first**
  (by when the password was added) and shows a small **age** (сейчас/1ч/1д) per row.
- **Nearby** now also shows your **own/whitelisted networks** (uses the *unfiltered*
  AP list, which pwnagotchi otherwise hides from plugins) — marked with 🏠.

### 0.3.0
- **Switch animation.** Changing position now pops a little 3-section slider at the
  **top-center**; the knob **glides** from the old position to the new one (with a
  soft overshoot) and recolors to match (green/blue/purple). Plays on your own
  clicks and when the position changes elsewhere. Web only — on the e-ink it'll just
  snap (the screen is too slow for a smooth glide).

### 0.2.0
- Position 2 reworked into a **tabbed dashboard** that **fully pauses hunting** and
  **auto-rotates tabs**: 🏆 Охота (stats + connection + QR placeholder) · 🖥 Система
  (temp/CPU/mem graphs + SD) · 🎞 Комикс (procedural 3-frame) · 🔑 Пароли (Cracked
  networks from wpa-sec/pwndex + Nearby) · ⭐ №5 (reserved).
- Per-tab durations (Система 15s, Пароли 10s, others 5s); live data.
- Handshake totals + day streak persisted to survive reboots (no battery needed).

### 0.1.0
- First version of the **virtual slider** (web): 3 positions — **Auto** (hunt),
  **Dashboard** (pauses hunting + a carousel of temp/CPU/memory/uptime mini-charts
  that rotates every 5s, tap to flip), and a reserved **???** position. Position
  persists across restarts.

## voice_ru

### 1.0.0
- pwnagotchi now **speaks Russian**: every phrase translated via an in-memory swap of
  the `self._` translator (one dict, all ~25 methods), so updates don't wipe it.
  Ships with the full translated core file `voice.ru.py` as an alternative.

## brain

### 0.3.1
- **Settings save is now verified**: after writing `settings.json` it reads the
  file back, and the web shows "saved ✓" only on a real, persisted write (else
  "error") — so "saved" can't lie. Opening the ⚙️ panel now also fills the inputs
  with the current saved values.

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
