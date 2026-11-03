#!/usr/bin/env python3
"""
btlink_ble — a BLE GATT server so the Companion app connects to pwnagotchi
DIRECTLY over Bluetooth Low Energy (like the Flipper app): no IP, no hotspot.

It advertises a custom service with:
  • STATUS  characteristic (read + notify)  -> live status JSON
  • CMD     characteristic (write)          -> "restart" / "reboot" / "shutdown"
                                               / "manual" / "auto"

The iOS app (CoreBluetooth) scans for the SERVICE UUID, connects, reads STATUS
and writes CMD. Values are chunked by BLE's MTU; the app concatenates reads.

Run it with the SYSTEM python (it needs python3-gi + python3-bluezero, which the
pwnagotchi venv doesn't have):
    sudo apt install -y python3-gi python3-dbus python3-bluezero bluez
    sudo python3 /home/pi/btlink_ble.py        # or as a systemd service

Own device only.
"""

import json
import os
import socket
import subprocess
import time

SERVICE_UUID = "a0b40001-1111-2222-3333-444455556666"
STATUS_UUID = "a0b40002-1111-2222-3333-444455556666"
CMD_UUID = "a0b40003-1111-2222-3333-444455556666"

DEX = "/root/.pwndex/dex.json"
HS_DIR = "/home/pi/handshakes"


# --- data (read straight from the system, no HTTP/auth needed) -------------
def _read_int(path, div=1.0, rnd=1):
    try:
        with open(path) as f:
            return round(int(f.read().strip()) / div, rnd)
    except Exception:
        return None


def _cpu():
    try:
        def snap():
            with open("/proc/stat") as f:
                p = [int(x) for x in f.readline().split()[1:]]
            idle = p[3] + (p[4] if len(p) > 4 else 0)
            return sum(p), idle
        t0, i0 = snap(); time.sleep(0.1); t1, i1 = snap()
        dt, di = t1 - t0, i1 - i0
        return round(100.0 * (dt - di) / dt, 1) if dt > 0 else 0.0
    except Exception:
        return None


def _mem():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for ln in f:
                k, _, v = ln.partition(":")
                info[k] = int(v.split()[0])
        tot = info.get("MemTotal", 0)
        av = info.get("MemAvailable", info.get("MemFree", 0))
        return round(100.0 * (tot - av) / tot, 1) if tot else None
    except Exception:
        return None


def _uptime():
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0


def _pcaps():
    try:
        return sum(1 for f in os.listdir(HS_DIR) if f.endswith(".pcap"))
    except Exception:
        return 0


def _dex():
    try:
        with open(DEX, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def status_bytes():
    dex = _dex()
    d = {
        "name": socket.gethostname(),
        "mode": "manual" if os.path.exists("/root/.pwnagotchi-manual") else "auto",
        "uptime": _uptime(),
        "temp": _read_int("/sys/class/thermal/thermal_zone0/temp", 1000.0, 1),
        "cpu": _cpu(), "mem": _mem(),
        "pcaps": _pcaps(), "networks": len(dex),
        "cracked": sum(1 for e in dex.values() if e.get("pw")),
    }
    return json.dumps(d).encode("utf-8")


def run_cmd(text):
    text = (text or "").strip().lower()
    if text == "reboot":
        subprocess.Popen(["systemctl", "reboot"])
    elif text == "shutdown":
        subprocess.Popen(["systemctl", "poweroff"])
    elif text == "restart":
        subprocess.Popen(["systemctl", "restart", "pwnagotchi"])
    elif text in ("manual", "auto"):
        flag = "/root/.pwnagotchi-manual"
        try:
            if text == "manual":
                open(flag, "a").close()
            elif os.path.exists(flag):
                os.remove(flag)
        except Exception:
            pass
        subprocess.Popen(["systemctl", "restart", "pwnagotchi"])


# --- BLE peripheral --------------------------------------------------------
def main():
    from bluezero import adapter, peripheral

    dongle = list(adapter.Adapter.available())[0]
    dongle.powered = True

    def on_status_read():
        return list(status_bytes())

    def on_cmd_write(value, options):
        try:
            run_cmd(bytes(value).decode("utf-8", "ignore"))
        except Exception:
            pass

    pwn = peripheral.Peripheral(dongle.address, local_name="pwnagotchi")
    pwn.add_service(srv_id=1, uuid=SERVICE_UUID, primary=True)
    pwn.add_characteristic(srv_id=1, chr_id=1, uuid=STATUS_UUID,
                           value=[], notifying=False,
                           flags=["read", "notify"],
                           read_callback=on_status_read)
    pwn.add_characteristic(srv_id=1, chr_id=2, uuid=CMD_UUID,
                           value=[], notifying=False,
                           flags=["write", "write-without-response"],
                           write_callback=on_cmd_write)
    print("btlink_ble: advertising as 'pwnagotchi' (service %s)" % SERVICE_UUID)
    pwn.publish()


if __name__ == "__main__":
    main()
