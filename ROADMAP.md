# 🗺️ ROADMAP — idea bank

Ideas for plugins. Both the usual ones and the ones **nobody has really done** (marked 🌟).
Statuses: 💡 idea · 🏗️ in progress · ✅ done · 🔧 needs hardware

---

## ✅ Done

- ✅ **bootlogo** — custom boot logo: upload a photo in the browser, process it for
  e-ink (dithering/effects), show on screen without a reboot, boot splash with a
  configurable duration. See [plugins/bootlogo](plugins/bootlogo/).
- ✅ **pwndex** — network "pokedex": web catalog of APs (SSID/vendor/MAC), search,
  browse by brand, seen/caught, password store (manual + auto from wpa-sec), .pcap
  download. See [plugins/pwndex](plugins/pwndex/).
- ✅ **callout** — pwnagotchi calls out the deauth victim by name instead of MAC
  (patches voice in memory, test button, log, web). Formerly deauth-announcer.
  See [plugins/callout](plugins/callout/).
- ✅ **pwndex → whitelist** — networks you give a password to (yours) are auto-added
  to `main.whitelist` at runtime, so pwnagotchi won't attack them.

## 🏗️ In progress / next (our wishlist)

- ✅ **brain** — AI agent (bandit): learns by channel and steers scanning, `(A_I)`
  face, lines, logs, web stats + settings. v1 done. See [plugins/brain](plugins/brain/).
  Next (layers): channel dwell time, deauth aggressiveness, targeting.
- 🏗️ **slider** — the One-Touch Sync flagship: a 3-position **hardware switch**
  (Hunt / Sync / Disguise). Sync = pause hunting → connect to your own network →
  upload to wpa-sec → access the native web UI. The 3rd position is a hidden mode
  with a combo lock. Order: **3rd** (waiting for hardware ~the 25th).
- ✅ **voice_ru** — all of pwnagotchi's phrases translated to Russian, applied in memory
  so updates don't wipe it. Done. See [plugins/voice_ru](plugins/voice_ru/).

## ⭐ Flagship: One-Touch Sync ("the Slider Exorcist")

> The author's idea. A gesture on the pwnagotchi itself = magic: swipe — and it
> ships everything at once.

A physical gesture (slider/touch/button/accelerometer) → instant upload of all the
"loot" over the best available channel (USB/BT/Wi-Fi), with optional encryption and
a status on the e-ink. Gestures (draft): swipe — "upload all", long press — day
summary, reverse swipe — quiet mode.

---

## 🧠 Smart behavior

- 🌟 **Zones** — geo profiles **without GPS**: position by the "fingerprint" of
  visible BSSIDs; at home → sleeps, in the field → active, own network nearby → safe-mode.
- 🌟 **Target Memory ("Been here")** — cross-session memory of collected APs: doesn't
  hammer old ones, highlights only fresh targets.
- 🌟 **Stealth Score** — rates how "noisy" the device is on the air and advises it to be quieter.
- 🌟 **Smart Channels** — learns which channels/times yield more, and shifts channel priority itself.
- 🌟 **Quiet Hours** — a schedule + geofence where the device is guaranteed to stay silent (listen only).
- 🌟 **Adaptive Recon** — aggressiveness adapts to context: low battery/home → quieter,
  many targets → more active.
- 💡 **Auto-channel-lock** — when steadily hunting one AP, holds its channel longer.
- 💡 **Dwell Detector** — figures out you're standing still (the set of networks isn't
  changing) and switches to a "deep" mode on the current targets.

## 🎭 Personality and "life"

- 🌟 **Mood Engine** — mood from epoch stats: euphoria on a catch, boredom/sleep in
  silence, its own faces and phrases, "sleep" at night on a schedule.
- 🌟 **Nemesis** — remembers neighboring pwnagotchis (peer events), gives them names,
  keeps a "rivalry" and relationships journal.
- 🌟 **Tamagotchi-needs** — "hunger/tiredness": no handshakes for a while → sad; new APs = "food".
- 🌟 **Comic Diary** — once a day draws a 3-panel mini-comic on the e-ink about the day's adventures.
- 💡 **Diary** — a text diary in Markdown: what it saw, who it caught, where it went.
- 💡 **Name Evolution** — the device's name/avatar grows with level and achievements.
- 💡 **Dream Mode** — at night shows "dreams" (abstract animation from the day's stats).

## 🎮 Gamification

- ✅ **Pwndex** — done! Web catalog of APs + search + seen/caught + passwords. [plugins/pwndex](plugins/pwndex/)
- 🌟 **Streaks & Goals** — daily goals, day streaks, best hour, a progress bar on screen.
- 💡 **Achievements** — badges: "first 100 handshakes", "night hunter", "5 in a minute".
- 💡 **XP / Levels** — levels and leveling up.
- 💡 **Leaderboard** — sync stats with friends over MQTT/HTTP, who's ahead.
- 💡 **Daily Quest** — "catch a network on channel 11", "meet another pwnagotchi", etc.

## 📊 Data, reports, dashboards

- 🌟 **Pwn Postcard** — auto-generate a shareable retro PNG postcard: map + stats + mood.
- 🌟 **Password Weakness Stats** — **educational** analytics: how weak the passwords
  around you are (length/patterns) — aggregated and anonymous, without revealing specifics.
- 💡 **Grafana/Prometheus exporter** — metrics (hs/hour, uptime, pace, battery) in nice graphs.
- 💡 **Web Gallery** — a local page with a gallery of catches, filters, a map.
- 💡 **Session Replay** — "rewind" the day: a timeline of events in the web UI.
- 💡 **CSV/JSON export** — export stats for your own charts.

## 🔌 Integrations and connectivity

- 💡 **Telegram/Discord Bot** — push "handshake caught + geotag", a digest, `/stats`, `/selfie` commands.
- 💡 **Mastodon/Matrix poster** — auto-post a "trophy" to your channel.
- 💡 **MQTT bridge** — publishes events to Home Assistant / your broker.
- 💡 **Webhook out** — hits your URL on every event (for your own automations).
- 🌟 **Companion widget** — a light PWA companion page (charts/map) auto-updating over BLE/USB.

## 🔋 Hardware, power, screen

- 🌟 **Battery Brain** 🔧 — UPS-Lite over I²C: percent on screen, aggressiveness adapts
  to charge, auto-shutdown, discharge log.
- 🌟 **Vitals** — a health score: SD wear estimate, temperature history, battery cycles,
  uptime; warns ahead of time.
- 🌟 **Aura** 🔧 — a WS2812 LED ring: "breathes" when idle, pulses on a handshake, color = mood.
- 💡 **E-Ink Themes** — a set of skins/faces, switching by time of day.
- 💡 **Button Control** 🔧 — a GPIO button: next mode/screen/reboot Wi-Fi.
- 💡 **Thermal Watchdog** — watches the Zero 2's throttling, warns.
- 💡 **Brightness/Refresh saver** — fewer full e-ink refreshes, to spare the panel.

## 🛡️ Device security and privacy

- 🌟 **Watchdog / Dead-man** 🔧 — accelerometer + geofence: taken out of the "safe" zone
  with no connection → lock/wipe the loot (anti-theft).
- 🌟 **Panic Wipe** — a gesture/command: instantly encrypt/wipe all the loot.
- 🌟 **Encrypted Loot** — handshakes are encrypted on the card right away, decrypted only on your server.
- 💡 **Auto-backup to cloud** — an encrypted backup of handshakes/config to a NAS/S3 when internet appears.
- 💡 **Known-networks filter** — an ignore list of your/neighbors' networks (work only on your own gear).
- 💡 **Home-safe mode** — automatically a purely passive mode at home.

## 🔊 Audio

- 🌟 **Chiptune** 🔧 — short 8-bit tunes on a PWM buzzer for each event.
- 💡 **TTS Voice** 🔧 — voice events (espeak/piper): "got a handshake!", a morning greeting.
- 💡 **Soundpacks** — swappable sound sets (retro, sci-fi, animals).

## 🗺️ Geo and maps

- 💡 **WiGLE-style Map** 🔧 — your own map of outings (needs a GPS module).
- 🌟 **Zone Map (no GPS)** — a heatmap of "areas" by BSSID clusters, without satellites.
- 💡 **Return Home** — hints the direction home by familiar networks fading/growing.

## 🎨 Unusual / art

- 🌟 **Screensaver Gallery** — rotates pixel art / your pictures when idle (built on bootlogo).
- 🌟 **Generative Face** — the device's "face" is generated procedurally and mutates over time.
- 💡 **Weather Mood** — pulls weather (when there's internet) and changes the face/behavior.
- 💡 **Matrix Rain / BSOD prank** — screen pranks on a gesture.

## 🧰 Utilities / QoL

- 🌟 **Config Doctor** — checks config.toml for duplicate keys/typos (the thing that
  once crashed us!) and shows a clear error in the web UI.
- 🌟 **Crash Catcher** — catches the cause of "silent" reboots (persistent log + a summary
  of the last crash).
- 💡 **Loot Organizer** — auto-sort `.pcap` by folder/date/geo, dedup.
- 💡 **Plugin Manager UI** — enable/disable/update plugins from the web UI, nicely.
- 💡 **OTA Updater** — update plugins from this repository with one button.
- 💡 **Backup/Restore config** — save/roll back config.toml from the web UI.

---

## ✍️ How to add your own idea

Append a line to the right section: `💡 **Name** — one sentence`. Taken into work →
change the icon to 🏗️ and create a folder in `plugins/`. Done → ✅ and a row in
[plugins/README.md](plugins/README.md).
