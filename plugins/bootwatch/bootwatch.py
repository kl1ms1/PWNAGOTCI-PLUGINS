import logging
import os
import subprocess
import threading
import time

import pwnagotchi.plugins as plugins


class BootWatch(plugins.Plugin):
    """Black box + watchdog for a pwnagotchi (jayofelony).

    Starts with the system, logs EVERYTHING that could explain a crash, hang,
    reboot, 'no networks' or dead Bluetooth/Wi-Fi to /root/pwn-reboots.log:

      * a boot marker the moment plugins load (so a log that ends without a
        clean-unload marker before the next boot == a hard crash/reboot);
      * a heartbeat line every ~60s (uptime, load, mem, temp, throttle, mode,
        screen/epoch staleness, Bluetooth state, IP, last AP count) so the last
        seconds before a reboot are on disk;
      * a FULL snapshot on events: UI frozen (screen stopped updating), mode
        flip to manual, Wi-Fi 'bus is down' (brcmfmac), undervoltage, long
        'no networks' stretch, and on clean shutdown.

    Dependency-free and independent of Bluetooth/companion so it keeps logging
    even when those break. For your own device / authorized testing only.
    """

    __author__ = "companion"
    __version__ = "2.0.0"
    __license__ = "MIT"
    __description__ = "Black-box watchdog: logs every crash/hang/reboot cause"

    LOG = "/root/pwn-reboots.log"
    MAX = 512 * 1024
    HEARTBEAT = 60          # seconds between heartbeat lines
    UI_FREEZE = 45          # screen not updated for this long -> hang
    EPOCH_STALL = 240       # no epoch for this long (auto) -> stall
    NONET_EPOCHS = 8        # consecutive 0-AP epochs -> 'no networks'

    def __init__(self):
        self._agent = None
        self._ready = False
        self._start = time.time()
        self._last_ui = 0.0
        self._last_epoch = 0.0
        self._last_shake = 0.0
        self._epochs = 0
        self._last_aps = -1
        self._nonet_streak = 0
        self._froze = False
        self._last_mode = None
        self._last_hb = 0.0
        self._bus_down_seen = ""

    # --- lifecycle --------------------------------------------------------
    def on_loaded(self):
        self._append("===== BOOT @ %s (bootwatch %s) =====\n%s"
                     % (self._ts(), self.__version__, self._light()))
        threading.Thread(target=self._loop, daemon=True).start()
        logging.info("[bootwatch] loaded")

    def on_ready(self, agent):
        self._agent = agent
        self._ready = True
        self._last_ui = time.time()
        self._last_epoch = time.time()
        self._append("--- READY @ %s ---\n%s" % (self._ts(), self._snapshot()))

    def on_ui_update(self, ui):
        self._last_ui = time.time()
        if self._froze:
            self._froze = False
            self._append("+++ UI RESUMED @ %s (was frozen) +++" % self._ts())

    def on_epoch(self, agent, epoch, data):
        self._last_epoch = time.time()
        self._epochs += 1
        aps = self._aps(data)
        self._last_aps = aps
        if aps == 0:
            self._nonet_streak += 1
            if self._nonet_streak == self.NONET_EPOCHS:
                self._append("!!! NO NETWORKS for %d epochs @ %s !!!\n%s\n%s"
                             % (self._nonet_streak, self._ts(),
                                self._wifi_block(), self._pwnlog()))
        else:
            self._nonet_streak = 0

    def on_handshake(self, agent, filename, access_point, client_station):
        self._last_shake = time.time()

    def on_unload(self, ui):
        self._append("===== CLEAN UNLOAD @ %s (uptime %s) =====\n%s"
                     % (self._ts(), self._uptime(), self._light()))

    # --- watchdog loop ----------------------------------------------------
    def _loop(self):
        while True:
            try:
                now = time.time()
                # heartbeat
                if now - self._last_hb >= self.HEARTBEAT:
                    self._last_hb = now
                    self._append(self._light())
                # mode flip
                mode = self._mode()
                if self._last_mode is not None and mode != self._last_mode:
                    self._append("*** MODE %s -> %s @ %s ***\n%s"
                                 % (self._last_mode, mode, self._ts(), self._light()))
                self._last_mode = mode
                # UI freeze (screen stopped updating)
                if self._ready and self._last_ui and (now - self._last_ui) > self.UI_FREEZE and not self._froze:
                    self._froze = True
                    self._append("!!! UI FROZEN %.0fs @ %s (screen not updating) !!!\n%s"
                                 % (now - self._last_ui, self._ts(), self._snapshot()))
                # epoch stall (auto only)
                if (self._ready and mode == "auto" and self._last_epoch
                        and (now - self._last_epoch) > self.EPOCH_STALL):
                    self._append("!!! EPOCH STALL %.0fs @ %s !!!\n%s"
                                 % (now - self._last_epoch, self._ts(), self._snapshot()))
                    self._last_epoch = now  # avoid spamming
                # wifi bus-down
                bd = self._run("dmesg 2>/dev/null | grep -iE 'brcmfmac.*(bus is down|failed|error)|bus is down' | tail -3")
                if bd and bd != self._bus_down_seen:
                    self._bus_down_seen = bd
                    self._append("!!! WIFI MODULE ISSUE @ %s !!!\n%s\n%s"
                                 % (self._ts(), bd, self._light()))
                # undervoltage right now
                thr = self._run("vcgencmd get_throttled 2>/dev/null | sed 's/.*=//'")
                try:
                    if thr and (int(thr, 16) & 0x1):
                        self._append("!!! UNDERVOLTAGE NOW @ %s (throttled=%s) !!!" % (self._ts(), thr))
                except Exception:
                    pass
            except Exception:
                logging.debug("[bootwatch] loop tick failed")
            time.sleep(10)

    # --- helpers ----------------------------------------------------------
    def _ts(self):
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _run(self, cmd, t=6):
        try:
            r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=t)
            return ((r.stdout or "") + (r.stderr or "")).strip()
        except Exception as e:
            return "ERR: %s" % e

    def _uptime(self):
        return self._run("uptime -p 2>/dev/null || uptime")

    def _mode(self):
        return "manual" if os.path.exists("/root/.pwnagotchi-manual") else "auto"

    def _ip(self):
        return self._run("ip -4 -br addr 2>/dev/null | grep -Ev 'lo ' | awk '{print $1\"=\"$3}' | tr '\\n' ' '")

    def _bt(self):
        return self._run("bluetoothctl show 2>/dev/null | grep -Ei 'Powered|Discoverable|Pairable' | awk '{print $1$2}' | tr '\\n' ' '; systemctl is-active bluetooth 2>/dev/null")

    def _aps(self, data):
        try:
            if isinstance(data, dict):
                for k in ("aps", "num_aps", "access_points", "tot_aps", "aps_on_channel"):
                    if k in data and isinstance(data[k], (int, float)):
                        return int(data[k])
        except Exception:
            pass
        return -1

    def _light(self):
        """One compact heartbeat line."""
        now = time.time()
        ui_age = int(now - self._last_ui) if self._last_ui else -1
        ep_age = int(now - self._last_epoch) if self._last_epoch else -1
        up = self._run("cut -d. -f1 /proc/uptime 2>/dev/null")
        load = self._run("cut -d' ' -f1-3 /proc/loadavg 2>/dev/null")
        mem = self._run("free -m 2>/dev/null | awk '/Mem:/{printf \"%d/%dMB\",$3,$2}'")
        temp = self._run("vcgencmd measure_temp 2>/dev/null | sed 's/temp=//'")
        thr = self._run("vcgencmd get_throttled 2>/dev/null | sed 's/.*=//'")
        return ("HB %s | up=%ss mode=%s load=%s mem=%s temp=%s thr=%s | "
                "ui_age=%ss ep_age=%ss epochs=%d aps=%s | bt=[%s] ip=[%s]"
                % (self._ts(), up, self._mode(), load, mem, temp, thr,
                   ui_age, ep_age, self._epochs, self._last_aps,
                   self._bt(), self._ip()))

    def _wifi_block(self):
        return ("WIFI:\n" + self._run(
            "iwconfig 2>/dev/null | grep -iE 'mode|wlan'; ip -br link 2>/dev/null | grep -i wlan; "
            "dmesg 2>/dev/null | grep -iE 'brcmfmac|bus is down|clm_blob|firmware' | tail -10"))

    def _pwnlog(self):
        return ("PWNLOG:\n" + self._run(
            "tail -n 25 /var/log/pwnagotchi.log 2>/dev/null || journalctl -u pwnagotchi -n 25 --no-pager 2>/dev/null"))

    def _snapshot(self):
        p = ["---- SNAPSHOT %s ----" % self._ts()]
        p.append(self._light())
        p.append("throttle/temp: " + self._run("vcgencmd get_throttled 2>/dev/null; vcgencmd measure_temp 2>/dev/null; vcgencmd measure_volts 2>/dev/null"))
        p.append("battery: " + self._run("i2cget -y 1 0x36 4 w 2>/dev/null || echo 'no i2c'"))
        p.append("mem/disk: " + self._run("free -h | awk '/Mem:/{print}'; df -h / | awk 'NR==2{print}'"))
        p.append("top mem: " + self._run("ps -eo pmem,rss,comm --sort=-rss 2>/dev/null | head -6 | tr '\\n' '|'"))
        p.append("power/SD/oom:\n" + self._run("dmesg 2>/dev/null | grep -iE 'under-voltage|mmc|ext4-fs error|I/O error|oom|killed process|panic|watchdog' | tail -15"))
        p.append(self._wifi_block())
        p.append("bluetooth: " + self._bt() + "\n" + self._run("dmesg 2>/dev/null | grep -iE 'bluetooth|hci|btbcm|brcm_patchram' | tail -8"))
        p.append("last reboots:\n" + self._run("last -x 2>/dev/null | grep -Ei 'reboot|shutdown' | head -5"))
        p.append(self._pwnlog())
        return "\n".join(p)

    def _append(self, text):
        try:
            old = ""
            if os.path.exists(self.LOG):
                with open(self.LOG, "r", errors="ignore") as f:
                    old = f.read()
                if len(old) > self.MAX:
                    old = old[-self.MAX // 2:]
            with open(self.LOG, "w") as f:
                f.write(old + "\n" + text + "\n")
        except Exception:
            logging.exception("[bootwatch] write failed")
