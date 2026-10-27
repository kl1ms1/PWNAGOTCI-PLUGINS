"""
webshell — a web file manager + terminal for YOUR OWN pwnagotchi.

Browse the whole filesystem, view/edit text files, download them, rename/delete,
make folders, and run shell commands — all from the pwnagotchi web page, like a
little PC. Opens at: http://<ip>:8080/plugins/webshell/

==========================  ⚠️  SECURITY  ==========================
This gives ROOT file access and a ROOT shell over the web. The pwnagotchi
process runs as root, so every command here runs as root. Use it on your OWN
device only.

Protect it with ONE of:
  • set an access password:  main.plugins.webshell.password = "something"
  • and/or enable the pwnagotchi web auth (ui.web.auth = true).

With NO password set, anyone who can reach the web UI gets root. That's fine
over a direct USB link to your own PC, but NOT once the device broadcasts its
own Wi-Fi. Your own device / authorized use only.
====================================================================
"""

import json
import logging
import os
import shutil
import subprocess

import pwnagotchi.plugins as plugins


class Webshell(plugins.Plugin):
    __author__ = "you@example.com"
    __version__ = "0.1.0"
    __license__ = "MIT"
    __description__ = "Web file manager + root terminal (your own device only)."

    def __init__(self):
        self._pw = ""                 # optional access password (empty = open)
        self._cwd = "/root"           # terminal working directory (persists)
        self._max_view = 512 * 1024   # don't inline-view files bigger than this
        self._timeout = 30            # command timeout, seconds

    def on_loaded(self):
        o = self.options or {}
        self._pw = str(o.get("password", "") or "")
        self._cwd = o.get("start_dir", "/root") or "/root"
        try:
            self._timeout = int(o.get("timeout", self._timeout))
        except Exception:
            pass
        logging.info("[webshell] loaded (password=%s) — ROOT access, own device only",
                     "SET" if self._pw else "OFF")

    # --- auth --------------------------------------------------------------
    def _authed(self, request):
        if not self._pw:
            return True
        return request.headers.get("X-Shell-Key", "") == self._pw

    # --- web ---------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort, send_file
        try:
            act = request.args.get("action")

            # the page itself is always reachable (it shows the unlock box)
            if request.method == "GET" and not act and path in (None, "", "/"):
                return self._page()

            # password check (so the UI can verify the key before unlocking)
            if act == "auth":
                body = self._body(request)
                pw = body.get("password", "") if request.method == "POST" else \
                    request.args.get("password", "")
                return jsonify(ok=(not self._pw) or (pw == self._pw),
                               need=bool(self._pw))

            # everything else needs the key (when a password is configured)
            if not self._authed(request):
                return jsonify(ok=False, msg="locked"), 403

            if request.method == "GET":
                if act == "ls":
                    return jsonify(**self._ls(request.args.get("path") or self._cwd))
                if act == "cat":
                    return jsonify(**self._cat(request.args.get("path")))
                if act == "dl":
                    p = request.args.get("path") or ""
                    if p and os.path.isfile(p):
                        return send_file(p, as_attachment=True,
                                         download_name=os.path.basename(p))
                    abort(404)
                abort(404)

            # POST (JSON body; CSRF checked by the pwnagotchi web server)
            body = self._body(request)
            if act == "write":
                return jsonify(**self._write(body.get("path"), body.get("content", "")))
            if act == "rm":
                return jsonify(**self._rm(body.get("path")))
            if act == "mv":
                return jsonify(**self._mv(body.get("src"), body.get("dst")))
            if act == "mkdir":
                return jsonify(**self._mkdir(body.get("path")))
            if act == "run":
                return jsonify(**self._run(body.get("cmd", "")))
            abort(404)
        except Exception as e:
            logging.exception("[webshell] error")
            from flask import jsonify
            return jsonify(ok=False, msg=str(e)), 500

    @staticmethod
    def _body(request):
        try:
            raw = request.get_data(as_text=True)
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    # --- file operations ---------------------------------------------------
    def _ls(self, p):
        p = os.path.abspath(p or "/root")
        if not os.path.isdir(p):
            return {"ok": False, "msg": "not a directory: %s" % p}
        ents = []
        try:
            for name in os.listdir(p):
                full = os.path.join(p, name)
                try:
                    isdir = os.path.isdir(full)
                    size = os.path.getsize(full) if os.path.isfile(full) else 0
                    link = os.path.islink(full)
                except Exception:
                    isdir, size, link = False, 0, False
                ents.append({"name": name, "dir": isdir, "size": size, "link": link})
        except Exception as e:
            return {"ok": False, "msg": str(e)}
        ents.sort(key=lambda e: (not e["dir"], e["name"].lower()))
        return {"ok": True, "path": p, "parent": os.path.dirname(p) or "/",
                "entries": ents}

    def _cat(self, p):
        if not p or not os.path.isfile(p):
            return {"ok": False, "msg": "not a file"}
        try:
            size = os.path.getsize(p)
            if size > self._max_view:
                return {"ok": False, "big": True,
                        "msg": "file is %d KB — too big to view, download it" % (size // 1024)}
            with open(p, "rb") as f:
                raw = f.read()
            try:
                text = raw.decode("utf-8")
            except Exception:
                return {"ok": False, "binary": True,
                        "msg": "binary file — download it instead"}
            return {"ok": True, "path": p, "content": text, "size": size}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def _write(self, p, content):
        if not p:
            return {"ok": False, "msg": "no path"}
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def _rm(self, p):
        if not p:
            return {"ok": False, "msg": "no path"}
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                os.rmdir(p)            # only empty dirs (use the terminal for rm -rf)
            else:
                os.remove(p)
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "msg": str(e)}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def _mv(self, src, dst):
        if not src or not dst:
            return {"ok": False, "msg": "need src and dst"}
        try:
            shutil.move(src, dst)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def _mkdir(self, p):
        if not p:
            return {"ok": False, "msg": "no path"}
        try:
            os.makedirs(p, exist_ok=True)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # --- terminal ----------------------------------------------------------
    def _run(self, cmd):
        cmd = (cmd or "").strip()
        if not cmd:
            return {"ok": True, "out": "", "cwd": self._cwd}
        # keep `cd` working across commands (subprocess can't change our cwd)
        if cmd == "cd" or cmd.startswith("cd ") or cmd.startswith("cd\t"):
            target = cmd[2:].strip() or "~"
            target = os.path.expanduser(target) if target.startswith("~") else target
            newdir = os.path.abspath(os.path.join(self._cwd, target))
            if os.path.isdir(newdir):
                self._cwd = newdir
                return {"ok": True, "out": "", "cwd": self._cwd}
            return {"ok": False, "out": "cd: no such directory: %s" % target,
                    "cwd": self._cwd}
        try:
            r = subprocess.run(cmd, shell=True, cwd=self._cwd,
                               capture_output=True, text=True, timeout=self._timeout)
            out = (r.stdout or "") + (r.stderr or "")
            return {"ok": True, "out": out, "code": r.returncode, "cwd": self._cwd}
        except subprocess.TimeoutExpired:
            return {"ok": False, "out": "(timed out after %ds)" % self._timeout,
                    "cwd": self._cwd}
        except Exception as e:
            return {"ok": False, "out": str(e), "cwd": self._cwd}

    # --- page --------------------------------------------------------------
    def _page(self):
        token = ""
        try:
            from flask_wtf.csrf import generate_csrf
            token = generate_csrf()
        except Exception:
            token = ""
        return _PAGE.replace("__CSRF__", token)


_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>webshell</title><style>
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--line:#30363d;--mut:#8b949e;
--fg:#e6edf3;--acc:#1f6feb;--ok:#238636;--red:#f85149;--gold:#d29922}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:12px}
.wrap{max-width:900px;margin:0 auto}h1{font-size:1.2rem;margin:.2em 0}
.warn{background:#2d1a1a;border:1px solid #5c2b2b;color:#ffb3b3;border-radius:9px;padding:8px 12px;font-size:.8rem;margin:8px 0}
.bar{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:8px 0}
input,button{font-size:.9rem}
input[type=text],input[type=password]{background:#0b0f14;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:8px 10px;flex:1;min-width:120px}
button{background:#30363d;color:#fff;border:0;border-radius:8px;padding:8px 12px;cursor:pointer}
button.acc{background:var(--acc)}button.ok{background:var(--ok)}button.red{background:var(--red)}
.path{font-family:ui-monospace,monospace;color:#9ad1ff;font-size:.82rem;word-break:break-all}
.list{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:6px 0;max-height:46vh;overflow:auto}
.it{display:flex;align-items:center;gap:8px;padding:7px 10px;border-bottom:1px solid #22262d;cursor:pointer}
.it:hover{background:#1c2128}.it .nm{flex:1;font-family:ui-monospace,monospace;font-size:.85rem;word-break:break-all}
.it .sz{color:var(--mut);font-size:.75rem;white-space:nowrap}
.ic{width:16px;text-align:center}
.ed{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;margin:6px 0}
textarea{width:100%;height:34vh;background:#0b0f14;color:var(--fg);border:1px solid var(--line);
border-radius:8px;font-family:ui-monospace,monospace;font-size:.82rem;padding:8px}
.term{background:#000;border:1px solid var(--line);border-radius:10px;margin:8px 0;padding:8px}
#out{font-family:ui-monospace,monospace;font-size:.8rem;white-space:pre-wrap;max-height:34vh;overflow:auto;color:#d6e2ea}
.prompt{display:flex;gap:6px;align-items:center;margin-top:6px}
.prompt .cwd{font-family:ui-monospace,monospace;color:#7ee2a0;font-size:.8rem;white-space:nowrap}
#cmd{flex:1;font-family:ui-monospace,monospace}
.muted{color:var(--mut);font-size:.76rem;text-align:center;margin-top:10px}
.hide{display:none}
h2{font-size:.95rem;margin:14px 0 4px;color:var(--mut)}
</style></head><body><div class="wrap">
<h1>🗂️ webshell</h1>
<div class="warn">⚠️ ROOT доступ ко всей системе и терминал. Только свой девайс.</div>

<div id="lock" class="hide">
  <div class="bar"><input type="password" id="pw" placeholder="пароль плагина"><button class="acc" id="unlock">Войти</button></div>
</div>

<div id="app" class="hide">
  <h2>Файлы</h2>
  <div class="bar">
    <button id="up">⬆ вверх</button>
    <input type="text" id="path" placeholder="/root">
    <button class="acc" id="go">Открыть</button>
    <button id="mkd">+ папка</button>
  </div>
  <div class="path" id="curpath"></div>
  <div class="list" id="list"></div>

  <div class="ed hide" id="editor">
    <div class="bar"><span class="path" id="fname"></span></div>
    <textarea id="content" spellcheck="false"></textarea>
    <div class="bar">
      <button class="ok" id="save">💾 Сохранить</button>
      <button id="dl">⬇ Скачать</button>
      <button class="red" id="del">🗑 Удалить</button>
      <button id="closeed">Закрыть</button>
      <span id="edmsg" style="color:#7ee2a0;font-size:.8rem"></span>
    </div>
  </div>

  <h2>Терминал</h2>
  <div class="term">
    <div id="out"></div>
    <div class="prompt"><span class="cwd" id="cwd">/root</span><span>$</span>
      <input type="text" id="cmd" placeholder="команда (как на ПК) — Enter" autocomplete="off"></div>
  </div>
</div>

<div class="muted">pwnagotchi · только свой девайс / авторизованный доступ 🫡</div>
</div>
<script>
const BASE="/plugins/webshell/", CSRF="__CSRF__";
const $=s=>document.querySelector(s);
let KEY="", CWD="/root", curFile="";
function hdr(){return {"X-CSRFToken":CSRF,"Content-Type":"application/json","X-Shell-Key":KEY};}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function hsize(n){if(n<1024)return n+"B";if(n<1048576)return (n/1024).toFixed(0)+"K";return (n/1048576).toFixed(1)+"M";}

async function post(act,obj){return (await fetch(BASE+"?action="+act,{method:"POST",credentials:"same-origin",
  headers:hdr(),body:JSON.stringify(obj||{})})).json();}
async function get(act,qs){return (await fetch(BASE+"?action="+act+(qs||""),{credentials:"same-origin",
  headers:{"X-Shell-Key":KEY}})).json();}

async function ls(p){
  const j=await get("ls","&path="+encodeURIComponent(p||CWD));
  if(j.status===403){lock();return;}
  if(!j.ok){$("#curpath").textContent="⚠ "+(j.msg||"ошибка");return;}
  CWD=j.path; $("#curpath").textContent=j.path; $("#path").value=j.path; $("#up").dataset.p=j.parent;
  $("#list").innerHTML=j.entries.map(e=>{
    const ic=e.dir?"📁":(e.link?"🔗":"📄");
    return '<div class="it" data-n="'+esc(e.name)+'" data-d="'+(e.dir?1:0)+'">'
      +'<span class="ic">'+ic+'</span><span class="nm">'+esc(e.name)+'</span>'
      +'<span class="sz">'+(e.dir?"":hsize(e.size))+'</span></div>';
  }).join("")||'<div class="it"><span class="nm" style="color:#8b949e">пусто</span></div>';
}
function join(a,b){return (a.endsWith("/")?a:a+"/")+b;}

$("#list").addEventListener("click",e=>{
  const it=e.target.closest(".it"); if(!it||!it.dataset.n)return;
  const full=join(CWD,it.dataset.n);
  if(it.dataset.d==="1"){ls(full);} else {openFile(full);}
});
$("#up").addEventListener("click",()=>ls($("#up").dataset.p||"/"));
$("#go").addEventListener("click",()=>ls($("#path").value.trim()));
$("#path").addEventListener("keydown",e=>{if(e.key==="Enter")ls($("#path").value.trim());});
$("#mkd").addEventListener("click",async()=>{
  const n=prompt("имя новой папки:"); if(!n)return;
  const j=await post("mkdir",{path:join(CWD,n)}); if(!j.ok)alert(j.msg||"ошибка"); ls(CWD);
});

async function openFile(p){
  const j=await get("cat","&path="+encodeURIComponent(p));
  if(!j.ok){ if(confirm((j.msg||"не открыть")+"\nСкачать файл?")) dl(p); return; }
  curFile=p; $("#fname").textContent=p; $("#content").value=j.content;
  $("#editor").classList.remove("hide"); $("#edmsg").textContent="";
  $("#editor").scrollIntoView({behavior:"smooth"});
}
$("#save").addEventListener("click",async()=>{
  const j=await post("write",{path:curFile,content:$("#content").value});
  $("#edmsg").textContent=j.ok?"сохранено ✓":("⚠ "+(j.msg||"ошибка"));
  setTimeout(()=>$("#edmsg").textContent="",2000);
});
$("#del").addEventListener("click",async()=>{
  if(!confirm("Удалить?\n"+curFile))return;
  const j=await post("rm",{path:curFile});
  if(j.ok){$("#editor").classList.add("hide"); ls(CWD);} else alert(j.msg||"ошибка (папку с файлами удаляй в терминале: rm -rf)");
});
function dl(p){window.location=BASE+"?action=dl&path="+encodeURIComponent(p||curFile);}
$("#dl").addEventListener("click",()=>dl(curFile));
$("#closeed").addEventListener("click",()=>$("#editor").classList.add("hide"));

function println(s){const o=$("#out");o.textContent+=s;o.scrollTop=o.scrollHeight;}
$("#cmd").addEventListener("keydown",async e=>{
  if(e.key!=="Enter")return;
  const c=$("#cmd").value; $("#cmd").value="";
  println("\n"+$("#cwd").textContent+"$ "+c+"\n");
  const j=await post("run",{cmd:c});
  if(j.status===403){lock();return;}
  if(j.out)println(j.out);
  if(j.cwd){CWD=j.cwd;$("#cwd").textContent=j.cwd;}
});

function lock(){$("#lock").classList.remove("hide");$("#app").classList.add("hide");}
function unlocked(){$("#lock").classList.add("hide");$("#app").classList.remove("hide");ls("/root");}
$("#unlock").addEventListener("click",async()=>{
  KEY=$("#pw").value;
  const j=await post("auth",{password:KEY});
  if(j.ok)unlocked(); else {$("#pw").value="";alert("неверный пароль");}
});
$("#pw").addEventListener("keydown",e=>{if(e.key==="Enter")$("#unlock").click();});

(async()=>{
  const j=await (await fetch(BASE+"?action=auth",{credentials:"same-origin"})).json();
  if(j.need){lock();} else {unlocked();}
})();
</script></body></html>"""
