# 🎮 pwndex

A "pokedex" of networks for Pwnagotchi — **web UI only**: a catalog of every
network the device has seen and caught, with search, **seen/caught** status and a
**password store**.

Open: `http://<ip>:8080/plugins/pwndex/`

## What it does
- **Network catalog**: SSID, vendor, MAC, encryption, channel, last seen.
- **Seen / Caught** like a pokedex: 👁 just seen vs 🏆 handshake captured.
- **Search** by SSID / vendor / MAC (instant) + filters (all / caught / with
  password / seen only).
- **Browse by brand**: clickable vendor chips (Xiaomi, TP-Link, Apple…), like a
  marketplace — each shows how many networks that brand has.
- **Passwords**: type them in manually OR pull them from `wpa-sec.cracked.potfile`
  (the "↻ Refresh from wpa-sec" button); peek at them later. Plus per-network notes.
- **Export passwords**: the "⬇ Export passwords (.txt)" button downloads all saved
  passwords as a text file (SSID / MAC / vendor / password).
- **Download .pcap**: for caught networks, grab the captured handshake file right
  from the entry.
- **Auto-whitelist**: the moment you save a password for a network (your own), it's
  auto-added to `main.whitelist` so pwnagotchi won't attack it — the UI confirms with
  "saved ✓ · added to whitelist 🔒".
- Stats on top: total / caught / brands / passwords.

## Install
```bash
sudo cp pwndex.py /usr/local/share/pwnagotchi/custom-plugins/
sudo nano /etc/pwnagotchi/config.toml   # add the lines from pwndex.toml (custom_plugins once!)
sudo systemctl restart pwnagotchi
```
Step by step — [../../docs/TUTORIAL-SSH.md](../../docs/TUTORIAL-SSH.md).

## Options (config.toml)
| Key | Default | Description |
|---|---|---|
| `enabled` | — | turn the plugin on |
| `catalog_seen` | `true` | catalog all visible networks, not just caught ones |
| `auto_whitelist` | `true` | networks with a password → whitelist (don't attack) |
| `handshakes` | auto | wpa-sec handshakes/potfile folder |

## Where it's stored
`/root/.pwndex/dex.json` — the catalog and passwords (in plain text).

> ⚠️ Passwords sit in plain text on the card and are shown in the web UI (which is
> behind Basic auth). Your own networks / authorized tests only.
