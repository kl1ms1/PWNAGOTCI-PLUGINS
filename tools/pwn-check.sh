#!/usr/bin/env bash
# pwn-check.sh — one-shot health/crash report for a pwnagotchi (jayofelony).
# Run ON the Pi as root:   sudo bash /tmp/pwn-check.sh
# It prints the report AND saves it to /root/pwn-check.txt (fetch with scp).
#
# For YOUR OWN device / authorized testing only.

OUT=/root/pwn-check.txt
exec > >(tee "$OUT") 2>&1

line(){ printf '\n===== %s =====\n' "$1"; }
run(){ echo "\$ $*"; eval "$@" 2>&1; echo; }

echo "######## PWN-CHECK $(date '+%Y-%m-%d %H:%M:%S') ########"
echo "host: $(hostname)   kernel: $(uname -r)"

line "UPTIME"
run "uptime"
run "cat /proc/uptime"

line "POWER / THROTTLING  (the #1 cause of random reboots)"
if command -v vcgencmd >/dev/null 2>&1; then
  T=$(vcgencmd get_throttled 2>/dev/null | sed 's/.*=//')
  echo "get_throttled = $T"
  V=$(( ${T:-0} ))
  dec(){ [ $(( (V>>$1)&1 )) -eq 1 ] && echo "  [!] $2"; }
  dec 0  "under-voltage RIGHT NOW"
  dec 1  "ARM frequency capped now"
  dec 2  "currently throttled"
  dec 3  "soft temperature limit now"
  dec 16 "under-voltage has occurred since boot"
  dec 17 "ARM freq cap has occurred since boot"
  dec 18 "throttling has occurred since boot"
  dec 19 "soft temp limit has occurred since boot"
  [ "$V" -eq 0 ] && echo "  OK — no throttling/undervoltage flags"
  run "vcgencmd measure_temp"
  run "vcgencmd measure_volts"
else
  echo "vcgencmd not available"
fi

line "BATTERY  (UPS-Lite MAX17040 @ 0x36)"
if command -v i2cget >/dev/null 2>&1; then
  run "i2cget -y 1 0x36 2 w"   # voltage reg
  run "i2cget -y 1 0x36 4 w"   # capacity reg
else
  echo "i2c-tools not installed (apt install i2c-tools) — can't read battery"
fi

line "REBOOT / SHUTDOWN HISTORY"
run "who -b"
run "last -x 2>/dev/null | grep -Ei 'reboot|shutdown|crash' | head -15"
run "journalctl --list-boots 2>/dev/null | tail -15"

line "KERNEL ERRORS: power / SD-card / crashes / OOM"
run "dmesg 2>/dev/null | grep -iE 'under-voltage|voltage|hwmon|rpi_firmware' | tail -20"
run "dmesg 2>/dev/null | grep -iE 'mmc|ext4-fs error|I/O error|card|read-only' | tail -20"
run "dmesg 2>/dev/null | grep -iE 'oom|killed process|panic|oops|segfault|watchdog' | tail -20"

line "WIFI CHIP (brcmfmac 'bus is down')"
run "dmesg 2>/dev/null | grep -iE 'brcmfmac|firmware|wlan|clm_blob' | tail -25"
run "iwconfig 2>/dev/null"
run "ip -br link"

line "BLUETOOTH"
run "rfkill list"
run "systemctl is-active bluetooth"
run "systemctl status bluetooth --no-pager -n 15"
run "hciconfig -a 2>/dev/null"
run "bluetoothctl show 2>/dev/null"
run "dmesg 2>/dev/null | grep -iE 'bluetooth|hci|btbcm|brcm_patchram|firmware' | tail -25"

line "PWNAGOTCHI SERVICE"
run "systemctl is-active pwnagotchi"
run "systemctl status pwnagotchi --no-pager -n 20"
run "grep -iE 'error|exception|traceback|bus is down|no clm|reboot|restart' /var/log/pwnagotchi.log 2>/dev/null | tail -40"

line "DISK / MEMORY / SD HEALTH"
run "df -h /"
run "free -h"
run "mount | grep ' / '"

line "COMPANION BLACK-BOX (if installed)"
run "tail -120 /root/pwn-diag.log 2>/dev/null || echo 'no /root/pwn-diag.log'"
run "tail -120 /root/pwn-reboots.log 2>/dev/null || echo 'no /root/pwn-reboots.log'"

echo
echo "######## END — saved to $OUT ########"
echo "Fetch it:  scp pi@10.0.0.2:/root/pwn-check.txt ."
