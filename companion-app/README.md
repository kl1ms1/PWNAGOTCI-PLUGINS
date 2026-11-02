# 📱 Pwn Companion (iOS) — Milestone 1

A Flipper-style companion app for pwnagotchi. **Milestone 1** is a thin vertical
slice: connect to the device and show its live e-ink screen. We build it in the
cloud (GitHub Actions, macOS) into an **unsigned IPA** you sideload on a
**jailbroken** iPhone — no Mac needed.

> ⚠️ Own device / your own networks only.

## What M1 does
- **Dash** tab: live pwnagotchi screen (face + status) from `http://<ip>:8080/ui`,
  connection indicator, manual refresh.
- **Settings** tab: host / port / web login + password (basic auth).
- WiFi / Events / Control tabs are placeholders (M2–M3).

## Build it (no Mac needed)
1. On GitHub: **Actions** tab → **"Build iOS app (unsigned IPA)"** → **Run workflow**.
   (It also runs automatically when files under `companion-app/` change.)
2. When it's green, open the run → **Artifacts** → download
   **`PwnCompanion-unsigned-ipa`** → unzip to get `PwnCompanion-unsigned.ipa`.

## Install it (jailbroken iPhone)
- **TrollStore**: open the `.ipa` in Filza/Files → "Open in TrollStore" → Install.
- or **Sideloadly/AltStore** (non-jailbroken works too, but re-sign every 7 days).

## Use it
1. Open the app → **Settings** → set how you reach the device:
   - **USB**: `10.0.0.2` : `8080`
   - **Bluetooth (BT-PAN)** or **Wi-Fi**: the device's IP on that network
   - login/password = `ui.web.username` / `ui.web.password` from `config.toml`
     (default `changeme` / `changeme`).
2. Go to **Dash** → you should see the live pwnagotchi face. ✅

## How it's built
- SwiftUI, iOS 16+. `project.yml` → Xcode project via **XcodeGen** (in CI).
- `.github/workflows/ios-build.yml` runs `xcodebuild` with signing OFF and zips
  the `.app` into a `Payload/` IPA.

## Roadmap
- **M2:** Control (Manual/Auto, reconnect, reboot) · Events (WebSocket) · WiFi list.
- **M3:** 🔥 Upload handshakes via the phone's internet/VPN (a Pi plugin serves
  `.pcap` over HTTP; the app pulls them and POSTs to wpa-sec).
- **M4:** Files, GPS map of catches, themes, custom face/logo upload.
