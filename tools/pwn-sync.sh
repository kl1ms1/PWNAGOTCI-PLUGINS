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
SCRIPT_DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo /home/pi)
SCREEN="$SCRIPT_DIR/pwn-sync-screen.py"   # LIVE e-ink while pwnagotchi is down
[ -f "$SCREEN" ] || SCREEN=/home/pi/pwn-sync-screen.py
PWN_PY=/home/pi/.pwn/bin/python3          # pwnagotchi's venv (has the EPD driver)
[ -x "$PWN_PY" ] || PWN_PY=python3
SCREEN_PID=""

mkdir -p "$VDIR"; touch "$SENT"

# --- progress file -----------------------------------------------------------
TS=$(date +%s)
STATE=start; RESULT=""; TOTAL=0; UP=0; DONE0=0; CUR=""; NET=""; CRACKED=0
FIN=false; FINTS=0
NAMES=""                            # TAB-separated list of uploaded net names
STAGE="start"                       # short human status for the live screen

emit(){                             # emit [state] [stage]
    [ -n "$1" ] && STATE="$1"
    [ -n "$2" ] && STAGE="$2"
    V_TS="$TS" V_STATE="$STATE" V_RESULT="$RESULT" V_TOTAL="$TOTAL" V_UP="$UP" \
    V_DONE="$DONE0" V_CUR="$CUR" V_NET="$NET" V_CRACKED="$CRACKED" \
    V_FIN="$FIN" V_FINTS="$FINTS" V_NAMES="$NAMES" V_STAGE="$STAGE" \
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
     "names": names, "cracked": i("V_CRACKED"), "stage": os.environ.get("V_STAGE", ""),
     "finished": os.environ.get("V_FIN", "false") == "true", "fin_ts": i("V_FINTS")}
open("/root/.vslider/sync.json.tmp", "w").write(json.dumps(d))
os.replace("/root/.vslider/sync.json.tmp", "/root/.vslider/sync.json")
' 2>/dev/null
}

finish(){                           # finish <result>
    RESULT="$1"; FIN=true; FINTS=$(date +%s); STATE=done
    case "$RESULT" in
        ok)         STAGE="done: sent $UP" ;;
        no_profile) STAGE="no known wifi nearby"; STATE=error ;;
        no_net)     STAGE="connected, no internet"; STATE=error ;;
        no_iface)   STAGE="no radio iface"; STATE=error ;;
        *)          STAGE="error"; STATE=error ;;
    esac
    emit
}

log(){ echo "[pwn-sync] $*"; }

# ALWAYS restore hunting, even if something fails midway.
restore(){
    log "restoring hunting..."
    [ -n "$SCREEN_PID" ] && kill "$SCREEN_PID" 2>/dev/null   # drop the live e-ink
    pkill -f pwn-sync-screen.py 2>/dev/null
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
emit search "stopping pwnagotchi"
systemctl stop pwnagotchi; sleep 2
# take over the e-ink and draw LIVE progress while pwnagotchi is down
if [ -f "$SCREEN" ]; then
    "$PWN_PY" "$SCREEN" >/dev/null 2>&1 &
    SCREEN_PID=$!
    log "live screen started (pid $SCREEN_PID, $PWN_PY)"
fi
/usr/bin/monstop 2>/dev/null
ip link set wlan0mon down 2>/dev/null
iw dev wlan0mon del 2>/dev/null

# (re)create a managed wlan0. brcmfmac sometimes makes the vif vanish, so this
# is a helper we can call again at any point to self-heal ("wlan0 does not exist").
ensure_client_iface(){
    if iw dev "$IFACE" info >/dev/null 2>&1; then
        ip link set "$IFACE" up 2>/dev/null; return 0
    fi
    local PHY
    PHY=$(ls /sys/class/ieee80211/ 2>/dev/null | head -1); [ -z "$PHY" ] && PHY=phy0
    iw dev wlan0mon del 2>/dev/null
    iw phy "$PHY" interface add "$IFACE" type managed 2>/dev/null
    sleep 1
    rfkill unblock wifi 2>/dev/null
    ip link set "$IFACE" up 2>/dev/null; sleep 1
    iw dev "$IFACE" info >/dev/null 2>&1
}

rfkill unblock wifi
if ! ensure_client_iface; then
    log "could not create a client interface on the radio"
    finish no_iface
    exit 1
fi
log "radio ready as $IFACE (client mode)"
emit search "radio ready"

try_connect(){
    local ssid="$1" psk="$2"
    ensure_client_iface || return 1          # self-heal if the vif vanished
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
    iw dev "$IFACE" info >/dev/null 2>&1 || return 1   # vif vanished -> retry
    dhclient -1 "$IFACE" >/dev/null 2>&1
    ip -4 addr show "$IFACE" 2>/dev/null | grep -q "inet " || return 1
    ping -c1 -W3 8.8.8.8 >/dev/null 2>&1
}

# Scan what's actually in range and try ONLY profiled networks that are nearby,
# STRONGEST signal first. So a profile that isn't around (e.g. a car dashcam) is
# never probed, and the best-reception network is tried first.
log "scanning for known networks nearby..."
emit search "scanning"
PLAN=$(IFACE="$IFACE" PROFILES="$PROFILES" python3 -I -c '
import json, os, re, subprocess
prof = json.load(open(os.environ["PROFILES"]))
try:
    out = subprocess.run(["iw", "dev", os.environ["IFACE"], "scan"],
                         capture_output=True, text=True, timeout=25).stdout
except Exception:
    out = ""
sig = -999; seen = {}; total = 0
for ln in out.splitlines():
    ln = ln.strip()
    if ln.startswith("BSS "):
        sig = -999
    m = re.match(r"signal:\s*(-?\d+(?:\.\d+)?)", ln)
    if m:
        sig = float(m.group(1))
    if ln.startswith("SSID: "):
        ssid = ln[6:]; total += 1
        if ssid and ssid in prof and (ssid not in seen or sig > seen[ssid]):
            seen[ssid] = sig
def pw(k):
    v = prof[k]
    return v.get("pw", "") if isinstance(v, dict) else str(v)
if seen:                                     # known nets in range -> strongest first
    for ssid, _s in sorted(seen.items(), key=lambda x: -x[1]):
        print(ssid + chr(9) + pw(ssid))
elif total == 0:                             # scan failed -> fall back to all profiles
    for k in prof:
        print(k + chr(9) + pw(k))
# else: scan worked but none of ours is around -> print nothing (no_profile)
' 2>/dev/null)

ONLINE=""; CONNECTED_ANY=0
if [ -n "$PLAN" ]; then
  while IFS=$'\t' read -r ssid psk; do
    [ -z "$ssid" ] && continue
    for attempt in 1 2; do
        log "trying profile: $ssid (attempt $attempt)"
        NET="$ssid"; emit connect "try $ssid"
        if try_connect "$ssid" "$psk"; then ONLINE="$ssid"; CONNECTED_ANY=1; break; fi
        ip -4 addr show "$IFACE" 2>/dev/null | grep -q "inet " && CONNECTED_ANY=1
        # tear down + rebuild a fresh vif before the retry / next network
        pkill -f wpa_supplicant 2>/dev/null
        ip addr flush dev "$IFACE" 2>/dev/null
        iw dev "$IFACE" del 2>/dev/null
        sleep 1
    done
    [ -n "$ONLINE" ] && break
  done <<< "$PLAN"
fi

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
emit upload "online: $ONLINE"

UP=0; FAIL=0
emit upload "uploading"
for p in "$HS_DIR"/*.pcap; do
    [ -f "$p" ] || continue
    name=$(basename "$p")
    # pretty network name out of "<essid>_<bssid>.pcap"
    net=$(echo "$name" | sed -E 's/\.pcap$//; s/_[0-9A-Fa-f]{12}$//')
    CUR="$net"
    grep -qxF "$name" "$SENT" && continue        # already uploaded -> skip
    # curl can return 000 on a flaky link — retry each file a few times
    code=""
    for attempt in 1 2 3; do
        code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 60 -b "key=$KEY" -F "file=@$p" "$WPASEC" 2>/dev/null)
        [ "$code" = "200" ] || [ "$code" = "302" ] && break
        sleep 2
    done
    if [ "$code" = "200" ] || [ "$code" = "302" ]; then
        echo "$name" >> "$SENT"; UP=$((UP+1)); FAIL=0   # reset on success
        NAMES="$NAMES$net"$'\t'
        emit upload "uploading"
        sleep 1                                   # breathe between uploads
    else
        FAIL=$((FAIL+1))
        [ "$FAIL" -ge 8 ] && { log "too many upload failures ($code), stopping"; break; }
    fi
done
CUR=""
log "uploaded $UP new handshake(s)"
STAGE="sent $UP new"; emit upload

# pull cracked passwords back (updates the potfile pwndex/vslider read)
if curl -s --max-time 40 -b "key=$KEY" "$WPASEC/?api&dl=1" -o /tmp/cracked.potfile 2>/dev/null && [ -s /tmp/cracked.potfile ]; then
    cp /tmp/cracked.potfile "$HS_DIR/wpa-sec.cracked.potfile"
    CRACKED=$(wc -l < /tmp/cracked.potfile)
    log "downloaded cracked list: $CRACKED line(s)"
    STAGE="cracked $CRACKED"; emit upload
fi

finish ok
# hunting is restored by the EXIT trap
