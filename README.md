# 🐾 pwnagotchi-plugins

A collection of custom plugins for [Pwnagotchi](https://pwnagotchi.org/)
(tested on the **jayofelony** image, Raspberry Pi Zero 2 W).

Not "yet another uploader" — things nobody really has yet:
gestures, GPS-less geo profiles, personality, self-diagnostics and pretty reports.

> ⚠️ **Lawful use only.** Everything here is for learning and working with **your own**
> networks, or networks you have explicit written permission to test. Capturing other
> people's handshakes and cracking other people's passwords without consent is illegal.

---

## 📂 Repository layout

```
pwnagotchi-plugins/
├── README.md              ← you are here
├── ROADMAP.md             ← idea bank + flagship features
├── CONTRIBUTING.md        ← how to add a new plugin (conventions)
├── docs/
│   ├── TUTORIAL-SSH.md    ← step-by-step beginner tutorial over SSH
│   └── INSTALLING.md      ← how to install any plugin on the device
└── plugins/
    ├── README.md          ← index of ready plugins
    └── template/          ← skeleton to start a new plugin
        ├── example_plugin.py
        └── example_plugin.toml
```

## 🚀 Quick start

1. Copy the plugin's `.py` into the custom-plugins folder on the device:
   ```bash
   sudo cp my_plugin.py /usr/local/share/pwnagotchi/custom-plugins/
   ```
2. Set the path and enable the plugin in `/etc/pwnagotchi/config.toml`:
   ```toml
   main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
   main.plugins.my_plugin.enabled = true
   ```
3. Restart: `sudo systemctl restart pwnagotchi`.

📖 New to this? Full step-by-step tutorial: [`docs/TUTORIAL-SSH.md`](docs/TUTORIAL-SSH.md).
Short version with troubleshooting — [`docs/INSTALLING.md`](docs/INSTALLING.md).

## 🧩 Plugins

| Plugin | Version | Status | What it does |
|--------|--------|--------|--------------|
| [bootlogo](plugins/bootlogo/) | 0.4.7 | ✅ | Custom boot logo: photo in the browser → auto-fit for e-ink → show on screen and at power-on |
| [pwndex](plugins/pwndex/) | 0.6.1 | ✅ | Network "pokedex": catalog, search, passwords (save + export, timestamped), save .pcap per catch; your networks → whitelist |
| [callout](plugins/callout/) | 0.6.0 | ✅ | pwnagotchi calls out the target **network** by name instead of MAC (+ test button shows it on screen) |
| [brain](plugins/brain/) | 0.3.0 | ✅ | AI agent (bandit): learns and picks scanning channels; on a decision the face turns into `(A_I)` and speaks |
| [voice_ru](plugins/voice_ru/) | 1.0.0 | ✅ | pwnagotchi speaks Russian — all phrases translated in memory (updates don't wipe it) |
| [full_save](plugins/full_save/) | 0.1.0 | ✅ | One good handshake per network: whitelist fully-captured nets, tidy duplicate .pcaps (safe — moves to trash, never leaves the handshakes dir) |
| [vslider](plugins/vslider/) | 0.5.0 | 🏗️ | Virtual 3-position slider (web + **e-ink**) with a switch animation: Auto / tabbed Dashboard (pauses hunting; Охота·Система·Комикс·Пароли·№5, auto-rotating) / reserved |

Version history — in [`CHANGELOG.md`](CHANGELOG.md). Tags/releases — on the repo's **Releases** tab.

## 💡 Ideas

The idea bank and flagship features are in [`ROADMAP.md`](ROADMAP.md).
Want to add yours — just append it there.

## 🤝 Contributing

How to shape a new plugin — [`CONTRIBUTING.md`](CONTRIBUTING.md).
A starter skeleton lives in [`plugins/template/`](plugins/template/).
