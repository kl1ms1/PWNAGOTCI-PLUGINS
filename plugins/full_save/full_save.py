"""
full_save — one good handshake per network, no endless re-attacking, no clutter.

For every network it checks whether a CRACKABLE handshake already exists — a
complete 4-way EAPOL (an AP message M1/M3 together with a client MIC message
M2/M4) or a PMKID — the same thing Wireshark/aircrack look for. Then:

  • if it's crackable  -> the network is added to the whitelist so pwnagotchi
    stops deauthing it, and the *extra* .pcap duplicates of that same network
    are tidied away (MOVED to a trash subfolder — not hard-deleted by default);
  • if it's NOT crackable yet -> nothing is touched; it keeps capturing.

======================  SAFETY (read this)  ======================
This plugin NEVER runs `rm -rf`, never touches directories, never follows
symlinks, and never touches anything OUTSIDE the handshakes directory. Every
file it moves must be:
    * a regular file (not a symlink, not a dir),
    * ending in ".pcap",
    * located DIRECTLY inside the handshakes dir (verified via realpath).
By default it MOVES superseded duplicates into `<handshakes>/_full_save_trash/`
(recoverable), and only when `hard_delete = true` does it actually delete — and
even then only files that pass every check above. When anything is uncertain,
it does nothing. The whitelist is kept in the plugin's own file
(/root/.full_save/done.json) and applied at runtime — config.toml is never
edited.
==================================================================
"""

import json
import logging
import os
import time

import pwnagotchi.plugins as plugins

# LLC/SNAP + EAPOL ethertype signature that precedes every 802.11 EAPOL frame.
_EAPOL_SIG = b"\xaa\xaa\x03\x00\x00\x00\x88\x8e"
_PMKID_KDE = b"\x00\x0f\xac\x04"   # RSN PMKID KDE OUI+type


def _is_hex12(s):
    return len(s) == 12 and all(c in "0123456789abcdefABCDEF" for c in s)


def _bssid_of(filename):
    """pwnagotchi names captures '<essid>_<bssid>.pcap'; the bssid is the last
    12-hex token. Returns lowercase bssid or '' if it doesn't look like one."""
    base = os.path.basename(filename)
    if not base.lower().endswith(".pcap"):
        return ""
    stem = base[:-5]
    tok = stem.rsplit("_", 1)[-1]
    return tok.lower() if _is_hex12(tok) else ""


def _essid_of(filename):
    base = os.path.basename(filename)
    stem = base[:-5] if base.lower().endswith(".pcap") else base
    if "_" in stem and _is_hex12(stem.rsplit("_", 1)[-1]):
        return stem.rsplit("_", 1)[0]
    return stem


def _eapol_messages(path, limit=4 * 1024 * 1024):
    """Scan a .pcap for EAPOL-Key frames. Returns (set_of_msg_kinds, pmkid_bool).

    msg kinds: 1 = M1 (AP, ACK only), 2 = client MIC msg (M2/M4), 3 = M3.
    Pure byte-scan of the LLC/SNAP+EAPOL signature — robust across radiotap /
    plain-802.11 captures and needs no external tools.
    """
    with open(path, "rb") as f:
        data = f.read(limit)
    msgs = set()
    pmkid = False
    i = 0
    n = len(data)
    while True:
        j = data.find(_EAPOL_SIG, i)
        if j < 0:
            break
        e = j + len(_EAPOL_SIG)         # start of the EAPOL header
        # EAPOL: version(1) type(1) length(2); EAPOL-Key body starts at e+4
        if e + 7 <= n and data[e + 1] == 3:   # packet_type 3 = EAPOL-Key
            ki = (data[e + 5] << 8) | data[e + 6]   # key_information (BE)
            mic = bool(ki & 0x0100)
            ack = bool(ki & 0x0080)
            inst = bool(ki & 0x0040)
            if ack and not mic and not inst:
                msgs.add(1)                       # M1
                if data.find(_PMKID_KDE, e, e + 300) >= 0:
                    pmkid = True
            elif mic and ack and inst:
                msgs.add(3)                       # M3
            elif mic and not ack and not inst:
                msgs.add(2)                       # M2 or M4 (client MIC msg)
        i = j + 1
    return msgs, pmkid


def _is_crackable(path):
    """True / False / None(unknown). Crackable = PMKID, or an AP nonce msg
    (M1/M3) together with a client MIC msg (M2/M4)."""
    try:
        msgs, pmkid = _eapol_messages(path)
    except Exception:
        return None
    if pmkid:
        return True
    return bool((1 in msgs or 3 in msgs) and 2 in msgs)


class FullSave(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "Stop re-attacking fully-captured nets; tidy duplicate .pcaps (safely)."

    def __init__(self):
        self._dir = "/home/pi/handshakes"
        self._state_dir = "/root/.full_save"
        self._done_f = os.path.join(self._state_dir, "done.json")
        self._trash = None
        self._hard_delete = False
        self._whitelist_done = True
        self._done = {}            # bssid -> {essid, at, keep}
        self._moved = 0
        self._agent = None

    # ---- config / load ----------------------------------------------------
    def on_loaded(self):
        o = self.options or {}
        self._dir = o.get("handshakes", self._dir)
        self._hard_delete = bool(o.get("hard_delete", False))
        self._whitelist_done = bool(o.get("whitelist_done", True))
        self._trash = o.get("trash_dir") or os.path.join(self._dir, "_full_save_trash")
        os.makedirs(self._state_dir, exist_ok=True)
        self._load_done()
        logging.info("[full_save] loaded (dir=%s, hard_delete=%s, known_done=%d)",
                     self._dir, self._hard_delete, len(self._done))
        # one full pass over whatever is already on disk
        try:
            self._scan_all()
        except Exception:
            logging.exception("[full_save] initial scan failed")

    def on_ready(self, agent):
        self._agent = agent
        if self._whitelist_done:
            self._apply_whitelist()

    def on_handshake(self, agent, filename, access_point, client_station):
        self._agent = agent
        try:
            bssid = _bssid_of(filename) or self._mac(access_point)
            essid = _essid_of(filename) or (access_point or {}).get("hostname") \
                or (access_point or {}).get("essid") or ""
            if bssid:
                self._evaluate(bssid, essid)
        except Exception:
            logging.exception("[full_save] on_handshake")

    # ---- safety helpers ---------------------------------------------------
    def _base(self):
        return os.path.realpath(self._dir)

    def _safe_pcap(self, path):
        """A file we are allowed to move/delete: a regular .pcap file, not a
        symlink, located DIRECTLY inside the handshakes dir."""
        try:
            if os.path.islink(path):
                return False
            if not path.lower().endswith(".pcap"):
                return False
            if not os.path.isfile(path):
                return False
            rp = os.path.realpath(path)
            base = self._base()
            # must live directly in the handshakes dir, not nested, not trash
            if os.path.dirname(rp) != base:
                return False
            if os.path.realpath(self._trash) in (rp, os.path.dirname(rp)):
                return False
            return True
        except Exception:
            return False

    def _list_for(self, bssid):
        """All .pcap files in the handshakes dir belonging to one bssid."""
        out = []
        try:
            base = self._base()
            for name in os.listdir(base):
                if not name.lower().endswith(".pcap"):
                    continue
                if _bssid_of(name) == bssid:
                    p = os.path.join(base, name)
                    if self._safe_pcap(p):
                        out.append(p)
        except Exception:
            pass
        return out

    # ---- core evaluation --------------------------------------------------
    def _evaluate(self, bssid, essid=""):
        files = self._list_for(bssid)
        if not files:
            return
        crackable = [p for p in files if _is_crackable(p) is True]
        if not crackable:
            return     # not enough yet — keep everything, keep hunting

        # keep the newest crackable; tidy every other file for this bssid
        crackable.sort(key=lambda p: self._mtime(p), reverse=True)
        keep = crackable[0]
        # the network name comes from the kept (real) capture; fall back to the
        # one passed in, then to any sibling file that carries a name.
        essid = _essid_of(keep) or essid or next(
            (_essid_of(p) for p in files if _essid_of(p)), "")
        for p in files:
            if os.path.realpath(p) != os.path.realpath(keep):
                self._tidy(p)

        self._done[bssid] = {"essid": essid, "keep": os.path.basename(keep),
                             "at": int(time.time())}
        self._save_done()
        if self._whitelist_done and essid:
            self._whitelist(essid)
        logging.info("[full_save] '%s' (%s) complete -> kept %s, tidied rest",
                     essid or "?", bssid, os.path.basename(keep))

    def _scan_all(self):
        base = self._base()
        if not os.path.isdir(base):
            return
        seen = set()
        for name in os.listdir(base):
            if not name.lower().endswith(".pcap"):
                continue
            b = _bssid_of(name)
            if b and b not in seen:
                seen.add(b)
                self._evaluate(b, _essid_of(name))

    # ---- tidy (move to trash / optional hard delete) ----------------------
    def _tidy(self, path):
        if not self._safe_pcap(path):
            logging.warning("[full_save] refused to tidy unsafe path: %s", path)
            return False
        try:
            if self._hard_delete:
                os.remove(path)
                self._moved += 1
                return True
            os.makedirs(self._trash, exist_ok=True)
            dest = os.path.join(self._trash, os.path.basename(path))
            if os.path.exists(dest):
                dest = "%s.%d" % (dest, int(time.time()))
            os.rename(path, dest)       # same filesystem -> atomic move
            self._moved += 1
            return True
        except Exception:
            logging.exception("[full_save] tidy failed: %s", path)
            return False

    # ---- whitelist (runtime only — config.toml is never touched) ----------
    def _whitelist(self, essid):
        try:
            cfg = getattr(self._agent, "_config", None) if self._agent else None
            if not cfg:
                return
            wl = cfg.setdefault("main", {}).setdefault("whitelist", [])
            if essid and essid not in wl:
                wl.append(essid)
        except Exception:
            logging.debug("[full_save] could not add to whitelist")

    def _apply_whitelist(self):
        for info in self._done.values():
            e = info.get("essid")
            if e:
                self._whitelist(e)

    # ---- persistence ------------------------------------------------------
    def _load_done(self):
        try:
            with open(self._done_f, encoding="utf-8") as f:
                self._done = json.load(f) or {}
        except Exception:
            self._done = {}

    def _save_done(self):
        try:
            tmp = self._done_f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._done, f)
            os.replace(tmp, self._done_f)
        except Exception:
            logging.debug("[full_save] could not save done.json")

    # ---- misc -------------------------------------------------------------
    @staticmethod
    def _mac(ap):
        return ((ap or {}).get("mac") or (ap or {}).get("bssid") or "") \
            .replace(":", "").replace("-", "").lower()

    @staticmethod
    def _mtime(p):
        try:
            return os.path.getmtime(p)
        except Exception:
            return 0

    # ---- tiny web status --------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        if request.method != "GET":
            abort(405)
        if request.args.get("action") == "data":
            return jsonify(ok=True, done=self._done, moved=self._moved,
                           hard_delete=self._hard_delete, trash=self._trash)
        if path in (None, "", "/"):
            rows = "".join(
                "<tr><td>%s</td><td>%s</td></tr>" % (
                    (v.get("essid") or "?"), k)
                for k, v in self._done.items())
            return (
                "<!doctype html><meta charset=utf-8><title>full_save</title>"
                "<style>body{font-family:system-ui;background:#0d1117;color:#e6edf3;"
                "padding:16px}table{border-collapse:collapse}td{border:1px solid #30363d;"
                "padding:4px 10px}</style><h1>✅ full_save</h1>"
                "<p>Полностью пойманных сетей: <b>%d</b> · прибрано дублей: <b>%d</b> "
                "(%s)</p><table><tr><td>сеть</td><td>bssid</td></tr>%s</table>"
                "<p style='color:#8b949e'>Дубли переносятся в: %s</p>" % (
                    len(self._done), self._moved,
                    "удаление" if self._hard_delete else "в корзину",
                    rows, self._trash))
        abort(404)
