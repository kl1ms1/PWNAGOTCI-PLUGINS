# 📢 callout

pwnagotchi calls out the deauth victim **by name**, not by MAC.
(Formerly `deauth-announcer`.)

- Before: `Kickbanning A4:83:E7:11:22:33!`
- After: `Кикаю Ivan-PC.`

The web UI is in English, but **what the device says** (the spoken phrases) stays in
Russian by default — set your own via the `phrases` option.

It patches `voice.Voice.on_deauth` **in memory** — the `voice.py` file is left
untouched, so pwnagotchi updates don't wipe it. There is no extra line on screen —
it changes the **very phrase** pwnagotchi already speaks.

Name resolution prefers the **device name**: `hostname` → `Vendor-XXXX`
(vendor + last 4 of the MAC) → `Device-XXXX`. The goal is to always show a
device-looking name, not just the company.

## Web UI
`http://<ip>:8080/plugins/callout/`
- **🧪 Test phrase** — shows what it would say **right on the e-ink**, without
  waiting for a real deauth (held for a few seconds).
- A list of recent targets by name + log `/root/.callout/log.txt`.

## Install
```bash
sudo cp callout.py /usr/local/share/pwnagotchi/custom-plugins/
# if you installed the old deauth-announcer, remove it so it doesn't double up:
sudo rm -f /usr/local/share/pwnagotchi/custom-plugins/deauth_announcer.py
sudo nano /etc/pwnagotchi/config.toml   # main.plugins.callout.enabled = true
sudo systemctl restart pwnagotchi
```

## Options
| Key | Default | Description |
|---|---|---|
| `enabled` | — | turn it on |
| `phrases` | RU set | your own phrases, `{name}` = device name |
| `test_seconds` | `6` | how long the test phrase stays on screen |

> ⚠️ Your own networks / authorized tests only.
