#!/usr/bin/env bash
#
# pwn-watchdog.sh — install a tiny watchdog that auto-heals the
# "waiting for bettercap API ..." startup hang on pwnagotchi.
#
# It installs a background systemd service that, every ~90 s, checks whether
# pwnagotchi is stuck waiting for bettercap; if so, it restarts bettercap (and
# pwnagotchi). During normal hunting the log shows CHANNEL/epoch lines, not
# "waiting for bettercap API", so it never fires then — hunting is untouched.
#
# Run once:   sudo bash pwn-watchdog.sh
# Remove:     sudo bash pwn-watchdog.sh --uninstall
#
set -euo pipefail

SCRIPT=/usr/local/bin/pwn-bettercap-watchdog.sh
UNIT=/etc/systemd/system/pwn-watchdog.service
LOG=/etc/pwnagotchi/log/pwnagotchi.log

if [[ "${1:-}" == "--uninstall" ]]; then
    systemctl disable --now pwn-watchdog.service 2>/dev/null || true
    rm -f "$UNIT" "$SCRIPT"
    systemctl daemon-reload
    echo "pwn-watchdog removed."
    exit 0
fi

if [[ $EUID -ne 0 ]]; then
    echo "run with sudo: sudo bash pwn-watchdog.sh"; exit 1
fi

# --- the watchdog loop ------------------------------------------------------
cat > "$SCRIPT" <<EOF
#!/usr/bin/env bash
# Auto-heal pwnagotchi: (1) the "waiting for bettercap API" startup hang, and
# (2) the BCM43430 radio firmware crash ("bus is down") that shows up as
# "0 networks" until the driver re-inits. Installed by pwn-watchdog.sh.
LOG="$LOG"
MARK=/tmp/pwn_busdown
set +e
# baseline the bus-down counter so old crashes already in the ring buffer don't
# trigger a restart on the very first check
dmesg 2>/dev/null | grep -c "bus is down" > "\$MARK"
while true; do
    sleep 90
    # our field-sync stops pwnagotchi on purpose and juggles the radio — don't fight it
    pgrep -f pwn-sync.sh >/dev/null 2>&1 && continue
    systemctl is-active --quiet pwnagotchi || continue

    # (1) bettercap startup hang
    if [ -f "\$LOG" ]; then
        stuck=\$(tail -n 12 "\$LOG" 2>/dev/null | grep -c "waiting for bettercap API")
        if [ "\${stuck:-0}" -ge 10 ]; then
            logger -t pwn-watchdog "stuck waiting for bettercap -> restarting engine"
            if systemctl list-unit-files 2>/dev/null | grep -q '^bettercap'; then
                systemctl restart bettercap; sleep 10
            fi
            systemctl restart pwnagotchi
            dmesg 2>/dev/null | grep -c "bus is down" > "\$MARK"
            sleep 150
            continue
        fi
    fi

    # (2) radio firmware crash: a NEW "bus is down" since last check -> re-init
    busdown=\$(dmesg 2>/dev/null | grep -c "bus is down")
    prev=\$(cat "\$MARK" 2>/dev/null || echo 0)
    echo "\${busdown:-0}" > "\$MARK"
    if [ "\${busdown:-0}" -gt "\${prev:-0}" ]; then
        logger -t pwn-watchdog "radio bus-down detected (\$prev -> \$busdown) -> restarting pwnagotchi"
        systemctl restart pwnagotchi
        dmesg 2>/dev/null | grep -c "bus is down" > "\$MARK"
        sleep 150
    fi
done
EOF
chmod +x "$SCRIPT"

# --- the service ------------------------------------------------------------
cat > "$UNIT" <<EOF
[Unit]
Description=pwnagotchi bettercap watchdog (auto-heal the startup hang)
After=pwnagotchi.service

[Service]
Type=simple
ExecStart=$SCRIPT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now pwn-watchdog.service

echo "✅ pwn-watchdog installed and running."
echo "   It will auto-restart bettercap if pwnagotchi ever hangs on 'waiting for bettercap API'."
echo "   Check it:   systemctl status pwn-watchdog --no-pager"
echo "   Its actions: journalctl -t pwn-watchdog --no-pager"
echo "   Remove:     sudo bash pwn-watchdog.sh --uninstall"
