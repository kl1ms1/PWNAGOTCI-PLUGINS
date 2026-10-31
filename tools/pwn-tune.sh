#!/usr/bin/env bash
#
# pwn-tune.sh — SAFELY tune pwnagotchi's hunting so it stops hammering one AP:
# forget an access point ~1 min after it goes quiet, and don't keep poking the
# same target forever. Makes a backup, edits only specific scalar keys, then
# VALIDATES the TOML and auto-restores the backup if anything is off.
#
#   sudo bash pwn-tune.sh          # apply the anti-hammer settings
#   sudo bash pwn-tune.sh --show   # just show the current related values
#
# After applying:  sudo systemctl restart pwnagotchi
#
CFG=/etc/pwnagotchi/config.toml
PY=/home/pi/.pwn/bin/python3; [ -x "$PY" ] || PY=python3

[ "$(id -u)" = "0" ] || { echo "run with sudo: sudo bash pwn-tune.sh"; exit 1; }
[ -f "$CFG" ] || { echo "no $CFG"; exit 1; }

if [ "$1" = "--show" ]; then
    echo "current hunting-related keys:"
    grep -nE 'auto-tune|personality\.(ap_ttl|sta_ttl|max_interactions|recon_time|channels)' "$CFG" \
        || echo "  (none set — defaults in use)"
    exit 0
fi

BK="$CFG.bak.$(date +%s)"
cp "$CFG" "$BK"
echo "backup saved: $BK"

"$PY" - "$CFG" <<'PY'
import re, sys
cfg = sys.argv[1]
# forget quiet APs/stations after 60s; stop poking the same target after 2 tries
want = {
    "main.plugins.auto-tune.enabled": "false",   # keep auto-tune OFF (it fought us)
    "personality.ap_ttl": "60",
    "personality.sta_ttl": "60",
    "personality.max_interactions": "2",
}
lines = open(cfg, encoding="utf-8").read().splitlines()

def set_key(lines, key, val):
    pat = re.compile(r'^\s*' + re.escape(key) + r'\s*=')
    for i, l in enumerate(lines):
        if pat.match(l):
            lines[i] = "%s = %s" % (key, val)
            return True
    return False

# dotted root keys are safe to place at the very TOP (before any [table]); never
# append at EOF, which could land inside a table section.
insert_at = 0
for i, l in enumerate(lines):
    if l.strip().startswith("[") and l.strip().endswith("]"):
        break
    insert_at = i + 1
missing = []
for k, v in want.items():
    if not set_key(lines, k, v):
        missing.append("%s = %s" % (k, v))
if missing:
    lines[insert_at:insert_at] = missing
open(cfg, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("set:", ", ".join(want.keys()))
PY

if "$PY" -c "import tomllib; tomllib.load(open('$CFG','rb'))" 2>/dev/null; then
    echo "config is valid TOML ✓"
    echo "applied. now:  sudo systemctl restart pwnagotchi"
else
    echo "config became INVALID -> restoring backup"
    cp "$BK" "$CFG"
    exit 1
fi
