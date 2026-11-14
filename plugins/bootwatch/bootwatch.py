import logging
import os
import subprocess
import threading
import time

import pwnagotchi.plugins as plugins


class BootWatch(plugins.Plugin):
    """Independent black box: on every start it appends a snapshot (uptime,
    undervoltage/throttle, battery, reboot history, SD/Wi-Fi/BT/kernel errors,
    pwnagotchi log errors) to /root/pwn-reboots.log. Deliberately tiny and
    dependency-free so it keeps logging even when Bluetooth / companion break.

    For your own device / authorized testing only.
    """

    __author__ = "companion"
    __version__ = "1.0.0"
    __license__ = "MIT"
    __description__ = "Logs every reboot and errors to /root/pwn-reboots.log"

    LOG = "/root/pwn-reboots.log"
    MAX = 256 * 1024

    def on_loaded(self):
        threading.Thread(target=self._snapshot, daemon=True).start()
        logging.info("[bootwatch] loaded")

    def _run(self, cmd, t=6):
        try:
            r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                               text=True, timeout=t)
            return ((r.stdout or "") + (r.stderr or "")).strip()
        except Exception as e:
            return "ERR: %s" % e

    def _snapshot(self):
        time.sleep(25)  # let the system settle after boot
        p = ["===== BOOT @ %s =====" % time.strftime("%Y-%m-%d %H:%M:%S")]
        p.append("uptime: " + self._run("uptime"))
        p.append("throttle/temp: " + self._run(
            "vcgencmd get_throttled 2>/dev/null; vcgencmd measure_temp 2>/dev/null"))
        p.append("battery: " + self._run("i2cget -y 1 0x36 4 w 2>/dev/null || echo 'no i2c'"))
        p.append("last reboots:\n" + self._run(
            "last -x 2>/dev/null | grep -Ei 'reboot|shutdown' | head -5"))
        p.append("power/SD errors:\n" + self._run(
            "dmesg 2>/dev/null | grep -iE 'under-voltage|mmc|ext4-fs error|I/O error|oom|killed process|panic|watchdog' | tail -15"))
        p.append("wifi errors:\n" + self._run(
            "dmesg 2>/dev/null | grep -iE 'brcmfmac|bus is down|clm_blob' | tail -10"))
        p.append("bluetooth:\n" + self._run(
            "rfkill list bluetooth 2>/dev/null; hciconfig 2>/dev/null | head -4; systemctl is-active bluetooth"))
        p.append("pwnagotchi errors:\n" + self._run(
            "grep -iE 'error|exception|traceback|bus is down' /var/log/pwnagotchi.log 2>/dev/null | tail -15"))
        snap = "\n".join(p) + "\n"
        try:
            old = ""
            if os.path.exists(self.LOG):
                with open(self.LOG, "r", errors="ignore") as f:
                    old = f.read()
                if len(old) > self.MAX:
                    old = old[-self.MAX // 2:]
            with open(self.LOG, "w") as f:
                f.write(old + "\n" + snap)
            logging.info("[bootwatch] snapshot written to %s", self.LOG)
        except Exception:
            logging.exception("[bootwatch] write failed")
