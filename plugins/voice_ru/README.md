# 🇷🇺 voice_ru

Makes pwnagotchi **speak Russian** — every phrase it says on the e-ink (starting,
excited, sad, deauth, handshakes, the session summary, the tweet, everything).

## How it works
pwnagotchi runs every phrase through one translator (`self._(text)`). This plugin
swaps that translator for a **Russian dictionary** — so one dict covers all ~25
phrase methods, and no method is reimplemented. It patches it **in memory**, so
**pwnagotchi updates don't wipe it** (unlike editing `voice.py` on disk).

Unknown phrases (e.g. ones a future update adds) fall back to English until the
dict is extended — nothing breaks.

> If **callout** is also enabled, callout still overrides the *deauth* phrase
> (device name instead of MAC) on top of this.

## Install (recommended — the plugin)
```bash
sudo cp voice_ru.py /usr/local/share/pwnagotchi/custom-plugins/
sudo nano /etc/pwnagotchi/config.toml   # main.plugins.voice_ru.enabled = true
sudo systemctl restart pwnagotchi
```

## Alternative — replace the core file
If you'd rather replace pwnagotchi's own `voice.py` (⚠️ an update can overwrite it):
```bash
# back up first
sudo cp /home/pi/.pwn/lib/python3.11/site-packages/pwnagotchi/voice.py ~/voice.py.bak
# then copy the translated file over it
sudo cp voice.ru.py /home/pi/.pwn/lib/python3.11/site-packages/pwnagotchi/voice.py
sudo systemctl restart pwnagotchi
```
`voice.ru.py` in this folder is the full translated core file.

## Note on the font
Your Waveshare renders Cyrillic fine (seen in testing). If a different build shows
"□□□" squares instead of Russian, the e-ink font lacks Cyrillic glyphs — then you'd
need a Cyrillic-capable font, or keep English.

> ⚠️ Your own devices only.
