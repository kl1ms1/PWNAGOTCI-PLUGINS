# 🤝 How to add a plugin

Conventions to keep the repository tidy.

## 1. Make a folder

```
plugins/<plugin_name>/
├── <plugin_name>.py       # code (filename = plugin name in config.toml)
├── <plugin_name>.toml     # example config
└── README.md              # what it does, options, a screenshot/photo
```

Easiest: `cp -r plugins/template plugins/<plugin_name>` and rename.

## 2. Code

- the class inherits from `pwnagotchi.plugins.Plugin`;
- fill in `__author__`, `__version__`, `__license__`, `__description__`;
- only take the hooks you need (the list is in the template);
- **always** remove your UI elements in `on_unload` (otherwise they stay stuck on screen);
- log with a `[name]` prefix so it's easy to grep:
  `sudo journalctl -u pwnagotchi -f | grep -i name`.

## 3. Names and style

- plugin name is `snake_case`, latin (it's also the key in `config.toml`);
- read options from `self.options.get("key", default)`;
- don't hardcode handshake paths — read them from `agent.config()`
  (`config['bettercap']['handshakes']`); the path differs per image
  (`/home/pi/handshakes` or `/root/handshakes`).

## 4. Test on the device

```bash
sudo cp plugins/<name>/<name>.py /usr/local/share/pwnagotchi/custom-plugins/
# enable it in /etc/pwnagotchi/config.toml, then:
sudo systemctl restart pwnagotchi
sudo journalctl -u pwnagotchi -f | grep -i <name>
```

## 5. Update the indexes

Add a row to the tables in [`README.md`](README.md) and [`plugins/README.md`](plugins/README.md),
and optionally move the idea in [`ROADMAP.md`](ROADMAP.md) from 💡 to ✅.

## ⚠️ Ethics

Plugins are for your own networks and authorized tests. We don't accept anything
built for mass attacks / surveilling other people without consent.
