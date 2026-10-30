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
# The vslider plugin launches this with `systemd-run` (so stopping pwnagotchi
# does NOT kill this script) and, after pwnagotchi restarts, reads the live
# progress file below to replay the "growing number" animation on real counts.
#
#   sudo bash pwn-sync.sh            # manual run
#
# Progress for vslider is written to /root/.vslider/sync.json as we go:
#   {ts,state,result,total,up,already,sent_total,cur,net,names,cracked,finished,fin_ts}
#   state : start|search|connect|upload|done|error
#   result: ""|ok|no_profile|no_net|no_iface|error
#
set +e

HS_DIR=/home/pi/handshakes
PROFILES=/root/.pwndex/profiles.json
WPASEC="https://wpa-sec.stanev.org"
IFACE=wlan0
VDIR=/root/.vslider
SENT="$VDIR/sent.txt"               # basenames already uploaded (fast re-runs)
SYNC="$VDIR/sync.json"              # live progress for the vslider screen
CFG=/etc/pwnagotchi/config.toml

mkdir -p "$VDIR"; touch "$SENT"

# --- progress file -----------------------------------------------------------
TS=$(date +%s)
STATE=start; RESULT=""; TOTAL=0; UP=0; DONE0=0; CUR=""; NET=""; CRACKED=0
FIN=false; FINTS=0
NAMES=""                            # TAB-separated list of uploaded net names

emit(){                             # emit [state] [result]
    [ -n "$1" ] && STATE="$1"
    [ -n "$2" ] && RESULT="$2"
    V_TS="$TS" V_STATE="$STATE" V_RESULT="$RESULT" V_TOTAL="$TOTAL" V_UP="$UP" \
    V_DONE="$DONE0" V_CUR="$CUR" V_NET="$NET" V_CRACKED="$CRACKED" \
    V_FIN="$FIN" V_FINTS="$FINTS" V_NAMES="$NAMES" \
    python3 -I -c '
import json, os
def i(k):
    try: return int(os.environ.get(k, "0") or 0)
    except Exception: return 0
names = [n for n in (os.environ.get("V_NAMES", "") or "").split("\t") if n]
d = {"ts": i("V_TS"), "state": os.environ.get("V_STATE", ""),
     "result": os.environ.get("V_RESULT", ""), "total": i("V_TOTAL"),
     "up": i("V_UP"), "already": i("V_DONE"), "sent_total": i("V_DONE") + i("V_UP"),
     "cur": os.environ.get("V_CUR", ""), "net": os.environ.get("V_NET", ""),
     "names": names, "cracked": i("V_CRACKED"),
     "finished": os.environ.get("V_FIN", "false") == "true", "fin_ts": i("V_FINTS")}
open("/root/.vslider/sync.json.tmp", "w").write(json.dumps(d))
os.replace("/root/.vslider/sync.json.tmp", "/root/.vslider/sync.json")
' 2>/dev/null
}

finish(){                           # finish <result>
    RESULT="$1"; FIN=true; FINTS=$(date +%s); STATE=done
    [ "$RESULT" = "ok" ] || STATE=error
    emit
}

log(){ echo "[pwn-sync] $*"; }

# ALWAYS restore hunting, even if something fails midway.
restore(){
    log "restoring hunting..."
    pkill -f wpa_supplicant 2>/dev/null
    dhclient -r "$IFACE" 2>/dev/null
    ip addr flush dev "$IFACE" 2>/dev/null
    ip link set "$IFACE" down 2>/dev/null
    /usr/bin/monstart 2>/dev/null       # bring the monitor back
    systemctl start pwnagotchi
    log "pwnagotchi restarted."
}
trap restore EXIT

[ "$(id -u)" = "0" ] || { echo "run with sudo: sudo bash pwn-sync.sh"; exit 1; }

# count work up front so the screen can show the real total straight away
TOTAL=$(ls -1 "$HS_DIR"/*.pcap 2>/dev/null | wc -l)
DONE0=0
for p in "$HS_DIR"/*.pcap; do
    [ -f "$p" ] || continue
    grep -qxF "$(basename "$p")" "$SENT" && DONE0=$((DONE0+1))
done
emit start

KEY=$(grep -E '^[[:space:]]*main\.plugins\.wpa-sec\.api_key' "$CFG" | head -1 | grep -oE '[0-9a-fA-F]{20,}')
[ -z "$KEY" ] && { log "no wpa-sec api_key in config — aborting"; finish error; exit 1; }
[ -f "$PROFILES" ] || { log "no profiles ($PROFILES) — save a password in pwndex first"; finish no_profile; exit 1; }

# small head start so the frozen e-ink frame shows "Заливаю, жди"
sleep 3

log "stopping pwnagotchi to borrow the radio..."
emit search
systemctl stop pwnagotchi; sleep 2
/usr/bin/monstop 2>/dev/null
ip link set wlan0mon down 2>/dev/null
iw dev wlan0mon del 2>/dev/null
# make sure a managed wlan0 exists (monitor setup may leave only wlan0mon)
if ! iw dev "$IFACE" info >/dev/null 2>&1; then
    PHY=$(ls /sys/class/ieee80211/ 2>/dev/null | head -1); [ -z "$PHY" ] && PHY=phy0
    log "wlan0 missing -> creating a managed interface on $PHY"
    iw phy "$PHY" interface add "$IFACE" type managed 2>/dev/null
    sleep 1
fi
rfkill unblock wifi
ip link set "$IFACE" up 2>/dev/null; sleep 1
if ! iw dev "$IFACE" info >/dev/null 2>&1; then
    log "could not create a client interface on the radio — aborting (hunting restored)"
    finish no_iface                 # <- the honest "driver wall" result
    exit 1
fi
log "radio ready as $IFACE (client mode)"

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

ONLINE=""; CONNECTED_ANY=0
while IFS=$'\t' read -r ssid psk; do
    [ -z "$ssid" ] && continue
    log "trying profile: $ssid"
    NET="$ssid"; emit connect
    if try_connect "$ssid" "$psk"; then ONLINE="$ssid"; CONNECTED_ANY=1; break; fi
    ip -4 addr show "$IFACE" | grep -q "inet " && CONNECTED_ANY=1
    pkill -f wpa_supplicant 2>/dev/null; ip addr flush dev "$IFACE" 2>/dev/null
done < <(python3 -I -c "import json;d=json.load(open('$PROFILES'));[print(k+chr(9)+((v.get('pw','') if isinstance(v,dict) else str(v)))) for k,v in d.items()]" 2>/dev/null)

if [ -z "$ONLINE" ]; then
    if [ "$CONNECTED_ANY" = "1" ]; then
        log "connected to a profile but no internet — nothing uploaded"
        finish no_net
    else
        log "no profiled network in range — nothing to do"
        finish no_profile
    fi
    exit 0
fi
NET="$ONLINE"
log "online via: $ONLINE"

UP=0; FAIL=0
emit upload
for p in "$HS_DIR"/*.pcap; do
    [ -f "$p" ] || continue
    name=$(basename "$p")
    # pretty network name out of "<essid>_<bssid>.pcap"
    net=$(echo "$name" | sed -E 's/\.pcap$//; s/_[0-9A-Fa-f]{12}$//')
    CUR="$net"
    grep -qxF "$name" "$SENT" && continue        # already uploaded -> skip
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 40 -b "key=$KEY" -F "file=@$p" "$WPASEC" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "302" ]; then
        echo "$name" >> "$SENT"; UP=$((UP+1))
        NAMES="$NAMES$net"$'\t'
        emit upload
    else
        FAIL=$((FAIL+1)); [ "$FAIL" -ge 5 ] && { log "too many upload failures ($code), stopping"; break; }
    fi
done
CUR=""
log "uploaded $UP new handshake(s)"

# pull cracked passwords back (updates the potfile pwndex/vslider read)
if curl -s --max-time 40 -b "key=$KEY" "$WPASEC/?api&dl=1" -o /tmp/cracked.potfile 2>/dev/null && [ -s /tmp/cracked.potfile ]; then
    cp /tmp/cracked.potfile "$HS_DIR/wpa-sec.cracked.potfile"
    CRACKED=$(wc -l < /tmp/cracked.potfile)
    log "downloaded cracked list: $CRACKED line(s)"
fi

finish ok
# hunting is restored by the EXIT trap
