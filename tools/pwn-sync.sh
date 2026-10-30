#!/usr/bin/env bash
#
# pwn-sync.sh — "field sync" over Wi-Fi, no phone / PC / Bluetooth needed.
#
# Connects to one of your saved pwndex profiles, UPLOADS all handshakes to
# wpa-sec, DOWNLOADS the cracked results, then restores hunting.
#
# Why a script (not the plugin): the device has ONE radio and can't hunt
# (monitor mode) and be a Wi-Fi client at the same time. So we fully stop
# pwnagotchi, borrow the radio, sync, and restart it. This is the exact recipe
# proven to work on this device (associates, gets an IP, reaches the internet).
#
#   sudo bash pwn-sync.sh
#
# Tip: run it on a schedule, e.g. every 3h, with cron:
#   sudo crontab -e   ->   0 */3 * * * /bin/bash /home/pi/pwn-sync.sh >> /var/log/pwn-sync.log 2>&1
#
set +e

HS_DIR=/home/pi/handshakes
PROFILES=/root/.pwndex/profiles.json
WPASEC="https://wpa-sec.stanev.org"
IFACE=wlan0
SENT=/root/.vslider/sent.txt          # basenames already uploaded (so re-runs are fast)
CFG=/etc/pwnagotchi/config.toml

log(){ echo "[pwn-sync] $*"; }

# ALWAYS restore hunting, even if something fails midway.
restore(){
    log "restoring hunting..."
    pkill -f wpa_supplicant 2>/dev/null
    dhclient -r "$IFACE" 2>/dev/null
    ip addr flush dev "$IFACE" 2>/dev/null
    ip link set "$IFACE" down 2>/dev/null
    systemctl start pwnagotchi
    log "pwnagotchi restarted."
}
trap restore EXIT

[ "$(id -u)" = "0" ] || { echo "run with sudo: sudo bash pwn-sync.sh"; exit 1; }

KEY=$(grep -E '^[[:space:]]*main\.plugins\.wpa-sec\.api_key' "$CFG" | head -1 | grep -oE '[0-9a-fA-F]{20,}')
[ -z "$KEY" ] && { log "no wpa-sec api_key in config — aborting"; exit 1; }
[ -f "$PROFILES" ] || { log "no profiles ($PROFILES) — save a password in pwndex first"; exit 1; }
mkdir -p "$(dirname "$SENT")"; touch "$SENT"

log "stopping pwnagotchi to borrow the radio..."
systemctl stop pwnagotchi; sleep 2
ip link set wlan0mon down 2>/dev/null
iw dev wlan0mon del 2>/dev/null
rfkill unblock wifi
ip link set "$IFACE" up; sleep 1

try_connect(){
    local ssid="$1" psk="$2"
    cat > /tmp/sync_wpa.conf <<EOF
ctrl_interface=/run/wpa_supplicant
network={
    ssid="$ssid"
    psk="$psk"
}
EOF
    pkill -f wpa_supplicant 2>/dev/null; sleep 1
    wpa_supplicant -B -i "$IFACE" -D nl80211 -c /tmp/sync_wpa.conf >/dev/null 2>&1
    sleep 9
    dhclient -1 "$IFACE" >/dev/null 2>&1
    ip -4 addr show "$IFACE" | grep -q "inet " || return 1
    ping -c1 -W3 8.8.8.8 >/dev/null 2>&1
}

ONLINE=""
while IFS=$'\t' read -r ssid psk; do
    [ -z "$ssid" ] && continue
    log "trying profile: $ssid"
    if try_connect "$ssid" "$psk"; then ONLINE="$ssid"; break; fi
    pkill -f wpa_supplicant 2>/dev/null; ip addr flush dev "$IFACE" 2>/dev/null
done < <(python3 -c "import json;d=json.load(open('$PROFILES'));[print(k+chr(9)+((v.get('pw','') if isinstance(v,dict) else str(v)))) for k,v in d.items()]" 2>/dev/null)

[ -z "$ONLINE" ] && { log "no profiled network with internet in range — nothing to do"; exit 0; }
log "online via: $ONLINE"

UP=0; FAIL=0
for p in "$HS_DIR"/*.pcap; do
    [ -f "$p" ] || continue
    name=$(basename "$p")
    grep -qxF "$name" "$SENT" && continue        # already uploaded -> skip
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 40 -b "key=$KEY" -F "file=@$p" "$WPASEC" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "302" ]; then
        echo "$name" >> "$SENT"; UP=$((UP+1))
    else
        FAIL=$((FAIL+1)); [ "$FAIL" -ge 5 ] && { log "too many upload failures ($code), stopping"; break; }
    fi
done
log "uploaded $UP new handshake(s)"

# pull cracked passwords back (updates the potfile pwndex/vslider read)
if curl -s --max-time 40 -b "key=$KEY" "$WPASEC/?api&dl=1" -o /tmp/cracked.potfile 2>/dev/null && [ -s /tmp/cracked.potfile ]; then
    cp /tmp/cracked.potfile "$HS_DIR/wpa-sec.cracked.potfile"
    log "downloaded cracked list: $(wc -l < /tmp/cracked.potfile) line(s)"
fi
# hunting is restored by the EXIT trap
