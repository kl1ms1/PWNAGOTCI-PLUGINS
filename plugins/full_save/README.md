# 💾 full_save

One good handshake per network — stop re-attacking networks you've already
fully captured, and tidy away duplicate `.pcap` files. Safely.

For each network it checks (with a built-in EAPOL parser, the same 4-way
messages Wireshark/aircrack look for) whether a **crackable** handshake already
exists — an AP message (M1/M3) together with a client MIC message (M2/M4), or a
**PMKID**. Then:

- **crackable** → the network goes into the whitelist (pwnagotchi stops
  deauthing it), and the *extra* `.pcap` duplicates of that same network are
  tidied away;
- **not crackable yet** → nothing is touched, it keeps capturing.

## 🛡️ Safety (why it can't nuke your system)

This plugin is built to be incapable of touching anything it shouldn't. Every
file it moves/deletes must pass ALL of these:

- it is a **regular `.pcap` file** (never a directory),
- it is **not a symlink**,
- it lives **directly inside the handshakes directory** (verified via
  `realpath`, so `..`/symlink escapes are rejected).

By default it **MOVES** duplicates into `<handshakes>/_full_save_trash/`
(recoverable) — it does **not** delete. Only `hard_delete = true` actually
removes files, and even then only ones that pass every check above. When
anything is uncertain, it does nothing. The whitelist is kept in the plugin's
own file (`/root/.full_save/done.json`) and applied at runtime — **config.toml
is never edited**.

The safety logic ships with a test suite (`tests/test_full_save.py`) that
verifies it leaves outside files, symlinks and nested folders untouched.

## Options
| Key | Default | Description |
|---|---|---|
| `enabled` | — | turn it on |
| `handshakes` | `/home/pi/handshakes` | capture folder (match `bettercap.handshakes`) |
| `whitelist_done` | `true` | add fully-captured nets to the whitelist |
| `hard_delete` | `false` | `false` = move dupes to trash; `true` = really delete |
| `trash_dir` | `<handshakes>/_full_save_trash` | where moved dupes go |

Web status: `http://<ip>:8080/plugins/full_save/`

> ⚠️ Your own networks / authorized tests only.
