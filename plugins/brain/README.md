# 🧠 brain

An AI agent that **picks its own scanning strategy**: it learns which channels pay
off the most and steers scanning there. No PyTorch, no trained model — it's a
lightweight **online agent (multi-armed bandit)** that learns right on the device.

## How it works (in short)
Each channel is a "slot machine arm". The agent scores a **reward** per channel:
- 🏆 captured handshake → big reward for that channel;
- 📶 clients/targets on a channel → small reward.

Once per epoch it updates each channel's **value** (a moving average) and picks
where to look next: **mostly the best ones** (exploit) + **sometimes a random new
one** (explore, probability `epsilon`) + a periodic **full scan** (refresh the
picture). The choice is applied with `agent.run('wifi.recon.channel 1,6,11')` —
**your config is never rewritten**.

On screen, on a decision, the big face turns into **`(A_I)`** and the speech line
shows a line with the channel (e.g. "Switching tactics to ch 11."), then the normal
face comes back. All decisions are logged to `/root/.brain/log.jsonl` (your whole
strategy history). Web stats + live settings: `http://<ip>:8080/plugins/brain/`.

Rewards are shown as a configurable **currency** (default `$`), so each channel's
value reads like how much it "earned".

## Install
```bash
sudo cp brain.py /usr/local/share/pwnagotchi/custom-plugins/
sudo nano /etc/pwnagotchi/config.toml   # lines from brain.toml (custom_plugins once!)
sudo systemctl restart pwnagotchi
```

## Options
| Key | Default | Description |
|---|---|---|
| `enabled` | — | turn it on |
| `epsilon` | `0.2` | share of exploring new channels |
| `top_k` | `3` | how many of the best channels to keep in focus |
| `full_scan_every` | `10` | full scan of all channels every N epochs |
| `face_mode` | `"face"` | `face` (instead of the face), `corner`, or `off` |
| `say_seconds` | `5` | how long to hold the "AI moment" on screen |
| `hs_reward` | `10` | reward per captured handshake |
| `target_reward` | `0.5` | reward per client/target on a channel |
| `currency` | `"$"` | currency symbol for the web page |
| `position` | `"0,83"` | line position (corner mode) |
| `channels` | auto | limit the channel pool (e.g. `[1,6,11]`) |

`say_seconds`, `hs_reward`, `target_reward` and `currency` can also be changed
live from the **⚙️ Settings** panel on the web page (saved to
`/root/.brain/settings.json`, survives restarts without touching config.toml).

## Honest notes
- This is a **cooperative nudge**, not a hard takeover: pwnagotchi also touches
  channels in its own loop, so the agent **re-applies** its choice every epoch.
  Works best when `main.personality.channels` is empty (default).
- The first few epochs are **warmup** (gathering data), no interference.

> ⚠️ Your own networks / authorized tests only.
