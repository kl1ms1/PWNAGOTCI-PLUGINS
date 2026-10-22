"""
pwndex — a "pokedex" of networks for Pwnagotchi (web UI only).

A catalog of every network the device has seen/caught:
  • search by SSID / vendor / MAC;
  • browse by brand (vendor chips, like a marketplace);
  • "Seen / Caught" like a pokedex (seen vs. handshake captured);
  • password store: type it in manually OR pull it from wpa-sec; peek at it;
  • download the captured handshake (.pcap) per caught network;
  • networks you give a password to are auto-added to main.whitelist (your own).

Open: http://<ip>:8080/plugins/pwndex/

⚠️ Passwords are stored in plain text in /root/.pwndex/dex.json and shown in the web
UI (which is behind Basic auth). Your own networks / authorized tests only.
"""

import json
import logging
import os
import threading
import time

import pwnagotchi.plugins as plugins


class Pwndex(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.4.0"
    __license__ = "MIT"
    __description__ = "Network pokedex: AP catalog (SSID/vendor/MAC), search, passwords. Web UI."

    def __init__(self):
        self._dir = "/root/.pwndex"
        self._db = os.path.join(self._dir, "dex.json")
        self._dex = {}                 # mac -> запись
        self._lock = threading.Lock()
        self._dirty = False
        self._last_save = 0
        self._hs_dir = "/home/pi/handshakes"
        self._potfile = None
        self._catalog_seen = True
        self._agent = None
        self._auto_wl = True        # networks with a password -> whitelist (don't attack)

    # --- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        os.makedirs(self._dir, exist_ok=True)
        o = self.options or {}
        self._hs_dir = o.get("handshakes", self._hs_dir)
        if o.get("catalog_seen") is not None:
            self._catalog_seen = bool(o.get("catalog_seen"))
        if o.get("auto_whitelist") is not None:
            self._auto_wl = bool(o.get("auto_whitelist"))
        self._load()
        logging.info("[pwndex] loaded, %d entries", len(self._dex))

    def on_ready(self, agent):
        self._agent = agent
        try:
            cfg = agent.config()
            self._hs_dir = cfg["bettercap"].get("handshakes", self._hs_dir)
        except Exception:
            pass
        self._potfile = os.path.join(self._hs_dir, "wpa-sec.cracked.potfile")
        self._import_potfile()
        self._sync_whitelist()
        self._save(force=True)

    def on_epoch(self, agent, epoch, epoch_data):
        self._agent = agent
        self._import_potfile()
        self._sync_whitelist()
        self._save()

    # --- your networks (with a password) -> whitelist, don't attack them --
    def _sync_whitelist(self):
        if not self._auto_wl or self._agent is None:
            return
        try:
            cfg = getattr(self._agent, "_config", None)
            if cfg is None:
                return
            wl = cfg.setdefault("main", {}).setdefault("whitelist", [])
            if not isinstance(wl, list):
                return
            added = 0
            with self._lock:
                for e in self._dex.values():
                    if not e.get("pw"):
                        continue
                    for v in (e.get("ssid"), (e.get("mac") or "").lower()):
                        if v and v not in wl:
                            wl.append(v)
                            added += 1
            if added:
                logging.info("[pwndex] whitelist += %d (your networks with a password)", added)
        except Exception:
            logging.exception("[pwndex] whitelist sync")

    def on_unload(self, ui):
        self._save(force=True)

    # --- хранилище ---------------------------------------------------------
    def _load(self):
        try:
            with open(self._db, encoding="utf-8") as f:
                self._dex = json.load(f)
        except Exception:
            self._dex = {}

    def _save(self, force=False):
        now = time.time()
        if not force and (not self._dirty or now - self._last_save < 10):
            return
        try:
            tmp = self._db + ".tmp"
            with self._lock:
                data = json.dumps(self._dex, ensure_ascii=False)
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, self._db)
            self._dirty = False
            self._last_save = now
        except Exception:
            logging.exception("[pwndex] save failed")

    # --- каталог -----------------------------------------------------------
    @staticmethod
    def _mac(ap):
        m = (ap.get("mac") or ap.get("bssid") or "").upper().replace("-", ":")
        return m if len(m) == 17 else ""

    def _touch(self, ap, caught=False, pcap=None):
        mac = self._mac(ap)
        if not mac:
            return
        ssid = ap.get("hostname") or ap.get("essid") or ap.get("ssid") or ""
        vendor = ap.get("vendor") or ap.get("manufacturer") or ""
        now = int(time.time())
        with self._lock:
            e = self._dex.get(mac)
            if e is None:
                e = {"ssid": ssid, "mac": mac, "vendor": vendor,
                     "enc": ap.get("encryption") or "", "ch": ap.get("channel") or 0,
                     "rssi": ap.get("rssi") or 0, "first": now, "last": now,
                     "seen": 0, "caught": False, "pw": "", "note": "", "pcap": ""}
                self._dex[mac] = e
            if pcap:
                e["pcap"] = pcap          # path to the captured handshake (.pcap)
            if ssid and not e.get("ssid"):
                e["ssid"] = ssid
            if vendor and not e.get("vendor"):
                e["vendor"] = vendor
            if ap.get("channel"):
                e["ch"] = ap.get("channel")
            if ap.get("rssi"):
                e["rssi"] = ap.get("rssi")
            if ap.get("encryption") and not e.get("enc"):
                e["enc"] = ap.get("encryption")
            e["last"] = now
            e["seen"] = e.get("seen", 0) + 1
            if caught:
                e["caught"] = True
            self._dirty = True

    def on_handshake(self, agent, filename, access_point, client_station):
        self._touch(access_point, caught=True, pcap=filename)
        self._save()

    def on_wifi_update(self, agent, access_points):
        if not self._catalog_seen:
            return
        try:
            for ap in access_points or []:
                self._touch(ap)
        except Exception:
            pass
        self._save()

    def on_unfiltered_ap_list(self, agent, aps):
        if not self._catalog_seen:
            return
        try:
            for ap in aps or []:
                self._touch(ap)
        except Exception:
            pass
        self._save()

    # --- passwords from wpa-sec --------------------------------------------
    @staticmethod
    def _hexmac(s):
        s = (s or "").strip().lower().replace(":", "").replace("-", "")
        if len(s) == 12 and all(c in "0123456789abcdef" for c in s):
            return ":".join(s[i:i + 2] for i in range(0, 12, 2)).upper()
        return ""

    @staticmethod
    def _maybe_unhex(s):
        t = (s or "").strip()
        if len(t) >= 2 and len(t) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in t):
            try:
                return bytes.fromhex(t).decode("utf-8")
            except Exception:
                return s
        return s

    def _parse_pot(self, line):
        """best-effort: (password, mac, ssid) from a wpa-sec cracked-file line."""
        line = line.strip()
        if not line:
            return "", "", ""
        for sep in (":", "*"):
            if sep in line:
                parts = line.split(sep)
                if len(parts) >= 4:
                    mac = self._hexmac(parts[0])
                    ssid = self._maybe_unhex(parts[2])
                    pw = sep.join(parts[3:]).strip()
                    if pw:
                        return pw, mac, ssid.strip()
        # hashcat potfile "hash:password"
        if ":" in line:
            h, _, pw = line.partition(":")
            if pw and len(h) > 20:
                return pw.strip(), "", ""
        return "", "", ""

    def _import_potfile(self):
        p = self._potfile
        if not p or not os.path.exists(p):
            return
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return
        with self._lock:
            by_ssid = {}
            for e in self._dex.values():
                if e.get("ssid"):
                    by_ssid.setdefault(e["ssid"].lower(), e)
            for ln in lines:
                pw, mac, ssid = self._parse_pot(ln)
                if not pw:
                    continue
                e = None
                if mac and mac in self._dex:
                    e = self._dex[mac]
                elif ssid and ssid.lower() in by_ssid:
                    e = by_ssid[ssid.lower()]
                if e is not None and not e.get("pw"):
                    e["pw"] = pw
                    e["caught"] = True
                    self._dirty = True

    # --- статистика --------------------------------------------------------
    def _stats(self):
        with self._lock:
            vals = list(self._dex.values())
        return {
            "total": len(vals),
            "caught": sum(1 for e in vals if e.get("caught")),
            "vendors": len({e.get("vendor") for e in vals if e.get("vendor")}),
            "pw": sum(1 for e in vals if e.get("pw")),
        }

    # --- web ---------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort
        try:
            action = request.args.get("action") or (path or "").strip("/")

            if request.method == "GET":
                if action == "data":
                    with self._lock:
                        src = sorted(
                            self._dex.values(),
                            key=lambda e: (not e.get("caught"),
                                           (e.get("ssid") or "￿").lower()))
                        items = []
                        vendors = set()
                        for e in src:
                            it = dict(e)
                            it["hp"] = bool(it.pop("pcap", ""))   # есть хендшейк
                            if it.get("vendor"):
                                vendors.add(it["vendor"])
                            items.append(it)
                    return jsonify(ok=True, items=items, stats=self._stats(),
                                   vendors=sorted(vendors))
                if action == "pcap":
                    from flask import send_file
                    mac = (request.args.get("mac") or "").upper()
                    with self._lock:
                        e = self._dex.get(mac)
                        p = e.get("pcap") if e else None
                    if p and os.path.exists(p):
                        return send_file(p, as_attachment=True,
                                         download_name=os.path.basename(p))
                    abort(404)
                if path in (None, "", "/"):
                    return self._page()
                abort(404)

            # POST — тело JSON (минуя разбор формы), CSRF проверяется сервером
            body = {}
            try:
                raw = request.get_data(as_text=True)
                if raw:
                    body = json.loads(raw)
            except Exception:
                body = {}

            if action == "set":
                mac = (body.get("mac") or "").upper()
                with self._lock:
                    e = self._dex.get(mac)
                    if e is None:
                        return jsonify(ok=False, msg="No such entry"), 404
                    if "pw" in body:
                        e["pw"] = str(body["pw"])[:128]
                    if "note" in body:
                        e["note"] = str(body["note"])[:200]
                    self._dirty = True
                self._save(force=True)
                self._sync_whitelist()   # password entered -> network to whitelist
                return jsonify(ok=True)

            if action == "rescan":
                self._import_potfile()
                self._save(force=True)
                return jsonify(ok=True, stats=self._stats())

            abort(404)
        except Exception as e:
            logging.exception("[pwndex] webhook error")
            from flask import jsonify
            return jsonify(ok=False, msg=str(e)), 500

    def _page(self):
        token = ""
        try:
            from flask_wtf.csrf import generate_csrf
            token = generate_csrf()
        except Exception:
            token = ""
        return _HTML.replace("__CSRF__", token)


_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>pwndex</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;
--fg:#e6edf3;--acc:#1f6feb;--ok:#238636;--gold:#d29922}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);
margin:0;padding:16px;line-height:1.4}
.wrap{max-width:720px;margin:0 auto}
h1{font-size:1.3rem;margin:.2em 0}
.stats{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:.85rem}
.stat b{font-size:1.1rem}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center}
input[type=search],input[type=text]{background:#0b0f14;color:var(--fg);border:1px solid var(--line);
border-radius:9px;padding:9px 12px;font-size:.95rem;width:100%}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:#21262d;color:var(--fg);border:1px solid var(--line);border-radius:20px;
padding:6px 12px;font-size:.82rem;cursor:pointer}
.chip.on{background:var(--acc);border-color:var(--acc)}
.brands{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;-webkit-overflow-scrolling:touch}
.brand{flex:0 0 auto;background:#21262d;color:var(--fg);border:1px solid var(--line);border-radius:10px;
padding:7px 12px;font-size:.82rem;cursor:pointer;white-space:nowrap}
.brand.on{background:var(--gold);border-color:var(--gold);color:#1a1a1a;font-weight:600}
.brand .n{color:var(--mut);font-size:.72rem;margin-left:4px}
.brand.on .n{color:#1a1a1a}
.lbl-row{font-size:.72rem;color:var(--mut);margin:2px 0 4px}
.btn{background:#30363d;color:#fff;border:0;border-radius:9px;padding:9px 14px;cursor:pointer;font-size:.85rem}
.row{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:8px 0}
.row.caught{border-left:3px solid var(--ok)}
.row.seen{opacity:.72}
.head{display:flex;justify-content:space-between;align-items:center;gap:8px;cursor:pointer}
.ssid{font-weight:600}
.ssid .hidden{color:var(--mut);font-weight:400;font-style:italic}
.meta{color:var(--mut);font-size:.78rem;margin-top:2px;word-break:break-all}
.badge{font-size:.7rem;border-radius:6px;padding:2px 7px;white-space:nowrap}
.b-caught{background:#16331f;color:#7ee2a0;border:1px solid #2ea04366}
.b-seen{background:#21262d;color:var(--mut);border:1px solid var(--line)}
.b-pw{background:#33240b;color:#f0c674;border:1px solid #d2992266}
.det{display:none;margin-top:10px;border-top:1px solid var(--line);padding-top:10px}
.det.open{display:block}
.fld{margin:6px 0}.fld label{display:block;font-size:.78rem;color:var(--mut);margin-bottom:3px}
.pwline{display:flex;gap:6px}.pwline input{flex:1}
.save{background:var(--ok)}
.dl{display:inline-block;margin-top:8px;background:#172f1c;color:#7ee2a0;border:1px solid #2ea04366;
border-radius:8px;padding:7px 12px;font-size:.85rem;text-decoration:none}
.muted{color:var(--mut);font-size:.78rem;text-align:center;margin-top:14px}
.empty{color:var(--mut);text-align:center;padding:30px 0}
</style></head><body><div class="wrap">
<h1>🎮 pwndex</h1>
<div class="stats" id="stats"></div>
<div class="bar"><input type="search" id="q" placeholder="Search: SSID, vendor or MAC…"></div>
<div class="lbl-row">Browse by brand</div>
<div class="brands" id="brands"></div>
<div class="bar"><div class="chips" id="filters">
  <button class="chip on" data-f="all">All</button>
  <button class="chip" data-f="caught">🏆 Caught</button>
  <button class="chip" data-f="pw">🔑 With password</button>
  <button class="chip" data-f="seen">👁 Seen only</button>
</div><button class="btn" id="rescan">↻ Refresh from wpa-sec</button></div>
<div id="list"></div>
<div class="muted">pwndex · passwords for your own networks only 🫡</div>
</div>
<script>
const BASE="/plugins/pwndex/", CSRF="__CSRF__";
const $=s=>document.querySelector(s);
let ALL=[], filter="all", q="", vendorFilter="";

function esc(s){return (s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function fmtAge(t){if(!t)return"";const d=Date.now()/1000-t;
  if(d<3600)return Math.round(d/60)+"m";if(d<86400)return Math.round(d/3600)+"h";return Math.round(d/86400)+"d";}

function renderBrands(){
  // count networks per vendor, show as clickable brand chips (marketplace style)
  const counts={};
  ALL.forEach(e=>{if(e.vendor)counts[e.vendor]=(counts[e.vendor]||0)+1;});
  const brands=Object.keys(counts).sort((a,b)=>counts[b]-counts[a]);
  const box=$("#brands");
  box.innerHTML='<button class="brand'+(vendorFilter===""?" on":"")+'" data-v="">All brands</button>'
    +brands.map(v=>'<button class="brand'+(vendorFilter===v?" on":"")+'" data-v="'+esc(v)+'">'
      +esc(v)+'<span class="n">'+counts[v]+'</span></button>').join("");
  box.querySelectorAll(".brand").forEach(b=>b.addEventListener("click",()=>{
    vendorFilter=b.dataset.v; renderBrands(); render();}));
}
async function load(){
  try{const r=await fetch(BASE+"?action=data",{credentials:"same-origin"});
    const j=await r.json();if(!j.ok)return;ALL=j.items||[];renderBrands();renderStats(j.stats);render();}
  catch(e){$("#list").innerHTML='<div class="empty">Failed to load</div>';}
}
function renderStats(s){s=s||{};$("#stats").innerHTML=
  tile(s.total,"total")+tile(s.caught,"🏆 caught")+tile(s.vendors,"🏭 brands")+tile(s.pw,"🔑 passwords");}
function tile(v,l){return '<div class="stat"><b>'+(v||0)+'</b> '+l+'</div>';}

function match(e){
  if(filter==="caught"&&!e.caught)return false;
  if(filter==="pw"&&!e.pw)return false;
  if(filter==="seen"&&e.caught)return false;
  if(vendorFilter&&e.vendor!==vendorFilter)return false;
  if(q){const s=(e.ssid+" "+e.vendor+" "+e.mac).toLowerCase();if(!s.includes(q))return false;}
  return true;
}
function render(){
  const items=ALL.filter(match);
  if(!items.length){$("#list").innerHTML='<div class="empty">Nothing here. Catch some networks or change the filter.</div>';return;}
  $("#list").innerHTML=items.map(row).join("");
}
function row(e){
  const name=e.ssid?esc(e.ssid):'<span class="hidden">(hidden)</span>';
  const badge=e.caught?'<span class="badge b-caught">🏆 caught</span>':'<span class="badge b-seen">👁 seen</span>';
  const pwb=e.pw?'<span class="badge b-pw">🔑</span>':'';
  return '<div class="row '+(e.caught?'caught':'seen')+'" data-mac="'+esc(e.mac)+'">'
   +'<div class="head" onclick="toggle(this)">'
   +'<div><div class="ssid">'+name+' '+pwb+'</div>'
   +'<div class="meta">'+esc(e.vendor||"—")+' · '+esc(e.mac)+' · '+esc(e.enc||"?")
   +' · ch'+(e.ch||"?")+' · '+fmtAge(e.last)+' ago</div></div>'
   +badge+'</div>'
   +'<div class="det">'
   +'<div class="fld"><label>Password</label><div class="pwline">'
   +'<input type="text" class="pw" value="'+esc(e.pw||"")+'" placeholder="none">'
   +'<button class="btn save" onclick="save(this)">💾</button></div></div>'
   +'<div class="fld"><label>Note</label><input type="text" class="note" value="'+esc(e.note||"")+'" placeholder="—"></div>'
   +(e.hp?'<a class="dl" href="'+BASE+'?action=pcap&mac='+encodeURIComponent(e.mac)+'">⬇ Download .pcap (handshake)</a>':'')
   +'</div></div>';
}
function toggle(h){h.parentElement.querySelector(".det").classList.toggle("open");}
async function save(btn){
  const row=btn.closest(".row"),mac=row.dataset.mac;
  const pw=row.querySelector(".pw").value, note=row.querySelector(".note").value;
  btn.textContent="…";
  try{const r=await fetch(BASE+"?action=set",{method:"POST",credentials:"same-origin",
    headers:{"X-CSRFToken":CSRF,"Content-Type":"application/json"},
    body:JSON.stringify({mac:mac,pw:pw,note:note})});
    const j=await r.json();btn.textContent=j.ok?"✓":"✗";
    const e=ALL.find(x=>x.mac===mac);if(e){e.pw=pw;e.note=note;}
    setTimeout(()=>btn.textContent="💾",1200);}
  catch(e){btn.textContent="✗";setTimeout(()=>btn.textContent="💾",1200);}
}
$("#q").addEventListener("input",()=>{q=$("#q").value.toLowerCase().trim();render();});
document.querySelectorAll("#filters .chip").forEach(c=>c.addEventListener("click",()=>{
  document.querySelectorAll("#filters .chip").forEach(x=>x.classList.remove("on"));
  c.classList.add("on");filter=c.dataset.f;render();}));
$("#rescan").addEventListener("click",async()=>{
  $("#rescan").textContent="…";
  try{await fetch(BASE+"?action=rescan",{method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":CSRF}});}
  catch(e){}
  await load();$("#rescan").textContent="↻ Refresh from wpa-sec";});
load();
</script></body></html>"""
