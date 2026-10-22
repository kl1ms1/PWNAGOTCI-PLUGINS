# 📖 Tutorial: installing a plugin over SSH

Step by step, for beginners. Using **bootlogo** as the example, but **every plugin in
this repo installs exactly the same way** — only the filename and the config lines change.

> You need: pwnagotchi powered on and connected to your computer over USB. Over USB the
> device is usually reachable at **10.0.0.2** (user `pi`, default password `raspberry`).

---

## Step 1. Connect over SSH

**Windows / Mac / Linux** — in a terminal (on Windows, PowerShell):
```bash
ssh pi@10.0.0.2
```
The first time it asks "Are you sure…?" → type `yes`. Enter the password (it isn't shown — that's normal).

**From a phone** — an app like *Termius* (iOS/Android): new host `10.0.0.2`, user `pi`.

---

## Step 2. Back up the config (just in case)
```bash
sudo cp /etc/pwnagotchi/config.toml /etc/pwnagotchi/config.toml.bak
```

---

## Step 3. Get the plugin onto the device

If the device has internet — download it straight from the repo:
```bash
sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
sudo wget -O /usr/local/share/pwnagotchi/custom-plugins/bootlogo.py \
  https://raw.githubusercontent.com/kl1ms1/PWNAGOTCI-PLUGINS/main/plugins/bootlogo/bootlogo.py
```

**No internet on the device?** Then download the file on your computer and copy it over
with `scp` (run this **on your computer**, not inside the SSH session):
```bash
scp bootlogo.py pi@10.0.0.2:/tmp/
# then back in the device's SSH session:
sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
sudo mv /tmp/bootlogo.py /usr/local/share/pwnagotchi/custom-plugins/
```

---

## Step 4. Enable the plugin in the config
```bash
sudo nano /etc/pwnagotchi/config.toml
```
Add the lines (for bootlogo):
```toml
main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
main.plugins.bootlogo.enabled = true
main.plugins.bootlogo.path = "/root/pwnagotchi-bootlogo.png"
```
Save: **Ctrl+O**, **Enter**, exit: **Ctrl+X**.

> `main.custom_plugins` only needs to be set once — for all custom plugins.

---

## Step 5. Restart pwnagotchi
```bash
sudo systemctl restart pwnagotchi
```

---

## Step 6. Check that the plugin came up
```bash
sudo journalctl -u pwnagotchi -f | grep -i bootlogo
```
Look for a line like `[bootlogo] loaded`. Exit the log with **Ctrl+C**.

---

## Step 7. Open the plugin's web UI
In a browser on your computer/phone:
```
http://10.0.0.2:8080/plugins/bootlogo/
```
Login/password — same as the pwnagotchi web UI (default `changeme` / `changeme` if you
haven't changed it). Then: upload a photo → tweak the settings → **"Save as boot logo"**.

---

## 🧰 If something's wrong

| Symptom | What to do |
|---|---|
| `ssh: connect ... timed out` | the device isn't at 10.0.0.2 — check the USB connection / address |
| `Permission denied` when copying | add `sudo` before the command |
| web page 404 | check `main.custom_plugins` and that the file is named `bootlogo.py` |
| `plugin not found` in the log | filename ≠ name in the config (`bootlogo.py` ↔ `main.plugins.bootlogo`) |
| config broke | roll back: `sudo cp /etc/pwnagotchi/config.toml.bak /etc/pwnagotchi/config.toml` |

---

## ♻️ Update a plugin later
Just re-download the fresh file (Step 3) over the old one and restart (Step 5).

> ⚠️ Your own devices only.
