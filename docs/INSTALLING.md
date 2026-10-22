# 📥 Installing a plugin on Pwnagotchi

Tested on the jayofelony image (Raspberry Pi Zero 2 W).

## 1. Copy the file to the device

Over SSH (over USB the device is usually at `10.0.0.2`):

```bash
# from your computer:
scp plugins/<name>/<name>.py pi@10.0.0.2:/tmp/

# on the device:
sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
sudo mv /tmp/<name>.py /usr/local/share/pwnagotchi/custom-plugins/
```

## 2. Enable it in config.toml

```bash
sudo nano /etc/pwnagotchi/config.toml
```

```toml
main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
main.plugins.<name>.enabled = true
# + plugin options, if any
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`.

## 3. Restart and check

```bash
sudo systemctl restart pwnagotchi
sudo journalctl -u pwnagotchi -f | grep -i <name>
```

Look for a `[<name>] loaded` line (or your own from `on_loaded`).

## 🧰 Troubleshooting

| Symptom | Cause / what to do |
|---|---|
| `plugin not found` | file isn't in `custom_plugins`, or filename ≠ name in the config |
| an element stays "stuck" on screen | `ui.remove_element(...)` not called in `on_unload` |
| `tail: cannot open ...potfile` | not an error — the results file doesn't exist yet, it'll appear |
| the plugin needs internet but there's none | `ping -c3 1.1.1.1`; on a single radio a Wi-Fi client + hunting are incompatible — you need USB/BT/a second adapter |
| element in the wrong place | tune `position=(x, y)` for your display (V2/V3/V4 differ) |

## 💾 Back up the config

Before editing:
```bash
sudo cp /etc/pwnagotchi/config.toml /etc/pwnagotchi/config.toml.bak
```
