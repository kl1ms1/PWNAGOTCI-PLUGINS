# 🗂️ webshell

A tiny **web file manager + terminal** for your own pwnagotchi — browse the
filesystem, view/edit text files, download them, rename, delete, make folders,
and run shell commands, all from the web page. Like a little PC.

Open: `http://<ip>:8080/plugins/webshell/`

## ⚠️ Security — read this
This gives **ROOT** file access and a **ROOT** shell over the web (pwnagotchi
runs as root). **Your own device / authorized use only.**

Protect it with at least one of:
- an access password for this plugin: `main.plugins.webshell.password = "…"`
- and/or the pwnagotchi web auth: `ui.web.auth = true`.

With **no** password, anyone who can reach the web UI gets root. That's okay
over a direct USB link to your own PC, but **not** once the device broadcasts
its own Wi-Fi — set a password then.

## What it does
- **Files**: navigate folders, open text files in an editor, **Save**,
  **Download**, **Delete** (files and *empty* folders), **+ folder**.
- **Terminal**: type any command (e.g. `ls -la`, `cat`, `nano`-no, `df -h`,
  `rm -rf`, `systemctl restart pwnagotchi`). `cd` is remembered between commands.
  Each command times out after `timeout` seconds (default 30).

> Deleting a **non-empty folder** is intentionally blocked in the file manager —
> use the terminal (`rm -rf …`) for that, so it's a deliberate action.

## Options
| Key | Default | Description |
|---|---|---|
| `enabled` | — | turn it on |
| `password` | *(empty)* | access password for this plugin (empty = open) |
| `timeout` | `30` | command timeout, seconds |
| `start_dir` | `/root` | where the terminal starts |

> ⚠️ Your own device / authorized use only.
