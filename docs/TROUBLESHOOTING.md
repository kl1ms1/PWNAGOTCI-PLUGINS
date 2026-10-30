# 🛠️ Troubleshooting (hard-won fixes)

Real problems hit on a **Raspberry Pi Zero 2 W + Waveshare 2.13" V4**, jayofelony
image (pwnagotchi 2.9.5.x), and what actually fixed them. Edit `config.toml`
**over SSH** — see the warning about Webcfg at the bottom.

---

## 1. `APS 0` / "sees no networks" / hammers one AP / no handshakes

**Symptoms**
- Screen shows `CH *   APS 0` for minutes even with lots of Wi-Fi around.
- Or it announces "connecting to X / Y" but stays stuck and captures nothing.
- `PWND` doesn't grow.

**Root cause** — the Wi-Fi chip is **crashing and resetting**, not a power or
plugin problem. Check the kernel log:
```bash
dmesg | grep -i brcmf
```
If you see this, the firmware crashed and the whole chip re-initialised:
```
ieee80211 phy0: brcmf_fil_cmd_data: bus is down. we have nothing to do.
ieee80211 phy0: brcmf_net_mon_stop: BRCMF_C_SET_MONITOR error (-5)
```
The trigger: the log also shows
`brcmf_c_process_clm_blob: no clm_blob available … limited channels`. The
internal **BCM43430** has no full channel/regulatory table, so when something
hops it to a channel the firmware dislikes (12/13/14, or whatever the
**auto-tune** plugin picked), the firmware dies.

**Fix** — stop the channel hopping onto bad channels:
1. **Disable `auto-tune`** (it changes channels dynamically → lands on a bad one).
2. **Lock Wi-Fi to the safe, common 2.4 GHz channels** `1, 6, 11`.
3. **Attack gentler** (also reduces current spikes and stops fixating on one AP).

Add/update these in `/etc/pwnagotchi/config.toml`:
```toml
main.plugins.auto-tune.enabled = false
personality.channels = [1, 6, 11]
personality.max_interactions = 1
personality.throttle_a = 0.5
personality.throttle_d = 0.9
personality.ap_ttl = 60
personality.sta_ttl = 120
personality.recon_time = 20
personality.min_recon_time = 5
```
Then **full reboot** (`sudo reboot`) and let it hunt. Verify:
```bash
uptime
dmesg | grep -c "bus is down"
```
**One** `bus is down` (a one-off at ~65 s during bettercap's monitor init, which
self-recovers) and the count **not growing** over 15+ min = fixed. `APS` and
`PWND` should start climbing.

> ⚠️ `personality.channels` may be written as a **multi-line array** in the
> config. Replace the whole block with the single line above — don't leave
> orphaned `1,` / `6` / `]` lines, or the TOML won't parse.

**If `bus is down` keeps growing even on `[1, 6, 11]`** — it's the internal
BCM43430's known monitor-mode flakiness. The bulletproof fix is a cheap **USB
Wi-Fi adapter with an Atheros AR9271** (rock-solid monitor + injection out of
the box). Hunt through the dongle, leave the internal chip for Bluetooth/tether.

---

## 2. Validate the config before every restart

After any edit, make sure it still parses (Python 3.11+ has `tomllib` built in):
```bash
python3 -c "import tomllib;tomllib.load(open('/etc/pwnagotchi/config.toml','rb'));print('✅ OK')"
```
If it errors — **don't restart**. Restore the backup you made first:
```bash
cp /etc/pwnagotchi/config.toml /etc/pwnagotchi/config.toml.bak.$(date +%s)  # before editing
sudo cp "$(ls -t /etc/pwnagotchi/config.toml.bak.* | head -1)" /etc/pwnagotchi/config.toml  # to roll back
```

---

## 3. "CSRF session token is missing" in the web UI

Happens when you restart pwnagotchi while an **old browser tab** is open — the
web session key changed, the tab's cookie is stale. Fix: hard-refresh the page
(**Ctrl+F5**) or reopen `http://10.0.0.2:8080` fresh, then click. Make sure
cookies aren't blocked.

---

## 4. ⚠️ Do NOT use Webcfg "Save"

The web **Webcfg** editor has wiped a working `config.toml` (Error 500) more than
once here. **Edit `config.toml` over SSH**, keep backups, and if it ever gets
nuked, restore a clean one with [`tools/pwn-restore.sh`](../tools/pwn-restore.sh).

---

## 5. After a reflash: monitor sees nothing

The brcmfmac monitor sometimes comes up without capturing after a fresh flash.
Usually fixed by:
```bash
sudo rfkill unblock wifi
sudo reboot
```
If `APS` is still 0 after a couple of minutes, work through section 1.
