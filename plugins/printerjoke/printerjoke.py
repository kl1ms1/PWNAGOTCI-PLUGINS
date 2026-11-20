"""
printerjoke.py  -  pwnagotchi plugin

AUTHORIZED USE ONLY.
Run this only on a network you OWN or are explicitly authorized to test.
It scans the LAN reachable through a *managed* interface (NOT the monitor
radio pwnagotchi uses), finds printers listening on raw port 9100, and sends
ONE short, harmless page to each printer, exactly once.

It does not read, exfiltrate, delete or alter anything. It just prints a page.
Printing on printers you don't control, without permission, is unauthorized
use - don't. The default message makes clear it is a prank/test.

Trigger from the companion app / browser:
    /plugins/printerjoke/run      -> scan + print one page per new printer
    /plugins/printerjoke/reset    -> forget which printers were already hit
    /plugins/printerjoke/status   -> how many printers were hit so far

Config (config.toml):
    main.plugins.printerjoke.enabled = true
    main.plugins.printerjoke.iface   = "usb0"     # the managed/second interface
    main.plugins.printerjoke.message = "..."      # optional custom text
"""

import os
import json
import socket
import struct
import logging
import ipaddress
import threading
from concurrent.futures import ThreadPoolExecutor

import pwnagotchi.plugins as plugins


class PrinterJoke(plugins.Plugin):
    __author__ = 'Ki213'
    __version__ = '1.0.0'
    __license__ = 'MIT'
    __description__ = 'Authorized/own-network prank: find LAN printers and print one harmless page on each, once.'

    DEFAULT_MESSAGE = (
        "\n\n"
        "  ===================================\n"
        "        HA-HA.  This is a prank.\n"
        "     (authorized test, my own LAN)\n"
        "  ===================================\n"
        "\n\n\f"   # form feed -> eject the page
    )

    def __init__(self):
        self.ready = False
        self._lock = threading.Lock()
        self._done = set()
        self.state_file = '/root/printerjoke_done.json'
        self.iface = 'usb0'
        self.ports = [9100]
        self.message = self.DEFAULT_MESSAGE
        self.connect_timeout = 0.35
        self.max_hosts = 512

    # ---------- lifecycle ----------
    def on_loaded(self):
        self.iface = str(self.options.get('iface', self.iface))
        self.ports = list(self.options.get('ports', self.ports))
        self.message = str(self.options.get('message', self.message))
        self.connect_timeout = float(self.options.get('timeout', self.connect_timeout))
        self.max_hosts = int(self.options.get('max_hosts', self.max_hosts))
        self.state_file = str(self.options.get('state_file', self.state_file))
        self._load_done()
        self.ready = True
        logging.info("[printerjoke] loaded - trigger /plugins/printerjoke/run on iface '%s' "
                     "(AUTHORIZED / own networks only)" % self.iface)

    # ---------- persistence (print once per printer) ----------
    def _load_done(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    self._done = set(json.load(f))
        except Exception as e:
            logging.warning("[printerjoke] could not load state: %s" % e)

    def _save_done(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(sorted(self._done), f)
        except Exception as e:
            logging.warning("[printerjoke] could not save state: %s" % e)

    # ---------- network helpers ----------
    def _iface_network(self):
        """IPv4 network behind self.iface, e.g. 192.168.1.0/24 - or None."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            name = self.iface[:15].encode()
            ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,  # SIOCGIFADDR
                                              struct.pack('256s', name))[20:24])
            mask = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x891b,  # SIOCGIFNETMASK
                                                struct.pack('256s', name))[20:24])
            return ipaddress.IPv4Network("%s/%s" % (ip, mask), strict=False)
        except Exception as e:
            logging.warning("[printerjoke] no IPv4 on '%s': %s" % (self.iface, e))
            return None

    def _printer_port(self, ip):
        for p in self.ports:
            try:
                with socket.create_connection((str(ip), p), timeout=self.connect_timeout):
                    return p
            except Exception:
                continue
        return None

    def _print_page(self, ip, port):
        try:
            with socket.create_connection((str(ip), port), timeout=3.0) as s:
                s.sendall(self.message.encode('latin-1', 'replace'))
            return True
        except Exception as e:
            logging.warning("[printerjoke] print to %s:%s failed: %s" % (ip, port, e))
            return False

    # ---------- the job ----------
    def _run_job(self):
        if not self._lock.acquire(blocking=False):
            logging.info("[printerjoke] already running")
            return
        try:
            net = self._iface_network()
            if net is None:
                return
            hosts = [h for h in net.hosts()][:self.max_hosts]
            targets = [h for h in hosts if str(h) not in self._done]
            logging.info("[printerjoke] scanning %d host(s) on %s" % (len(targets), net))

            found = []
            with ThreadPoolExecutor(max_workers=48) as pool:
                for ip, port in zip(targets, pool.map(self._printer_port, targets)):
                    if port:
                        found.append((ip, port))

            printed = 0
            for ip, port in found:
                if self._print_page(ip, port):
                    self._done.add(str(ip))
                    printed += 1
                    logging.info("[printerjoke] printed one page on %s:%s" % (ip, port))
            self._save_done()
            logging.info("[printerjoke] finished: %d printer(s) hit this run" % printed)
        finally:
            self._lock.release()

    # ---------- trigger ----------
    def on_webhook(self, path, request):
        if not self.ready:
            return "printerjoke not ready"
        p = (path or 'run').strip('/').lower()
        if p == 'reset':
            self._done = set()
            self._save_done()
            return "printerjoke: reset ok"
        if p == 'status':
            return "printerjoke: %d printer(s) already hit" % len(self._done)
        if p in ('', 'run'):
            threading.Thread(target=self._run_job, daemon=True).start()
            return "printerjoke: started on %s (authorized networks only)" % self.iface
        return "printerjoke: use /run, /reset or /status"


# fcntl is Linux-only; import here so the module still imports for inspection elsewhere
import fcntl  # noqa: E402
