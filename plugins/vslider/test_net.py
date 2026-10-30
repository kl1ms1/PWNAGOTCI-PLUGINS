import sys, types, os, tempfile, time as _time

# --- stub pwnagotchi ---
pk=types.ModuleType("pwnagotchi");plug=types.ModuleType("pwnagotchi.plugins")
class P:
    def __init__(self): self.options={}
plug.Plugin=P
comp=types.ModuleType("pwnagotchi.ui.components");comp.Widget=object
ui=types.ModuleType("pwnagotchi.ui");pk.plugins=plug;pk.ui=ui
for n,m in [("pwnagotchi",pk),("pwnagotchi.plugins",plug),("pwnagotchi.ui",ui),("pwnagotchi.ui.components",comp)]: sys.modules[n]=m

# --- fake handshakes dir with 5 pcaps ---
hs=tempfile.mkdtemp()
for i in range(5):
    open(os.path.join(hs,"net%d_aa.pcap"%i),"wb").write(b"\x00"*10)

# --- stub requests (simulate wpa-sec accepting over HTTPS/443) ---
req=types.ModuleType("requests")
class R: status_code=200
def post(url, cookies=None, files=None, timeout=None):
    assert url.startswith("https://"), "upload must be HTTPS"
    assert cookies and "key" in cookies, "needs api key cookie"
    return R()
req.post=post
sys.modules["requests"]=req

# --- stub subprocess (simulate the port/link commands + a successful DHCP lease) ---
import subprocess as _sp
class FakePopen:
    def __init__(self,*a,**k): self.args=a
    def terminate(self): pass
    def wait(self,timeout=None): return 0
    def kill(self): pass
class FakeCompleted:
    def __init__(self,rc,out): self.returncode=rc; self.stdout=out; self.stderr=""
def fake_run(args, capture_output=False, text=False, timeout=None):
    cmd=" ".join(args)
    if cmd.startswith("ip -4 addr show"):   # pretend we got a lease
        return FakeCompleted(0,"inet 192.168.1.50/24 scope global wlan0")
    return FakeCompleted(0,"")
_sp.run=fake_run; _sp.Popen=FakePopen

import socket as _socket
_socket.getaddrinfo = lambda *a, **k: [(2, 1, 6, "", ("1.2.3.4", 443))]

sys.path.insert(0,"/home/user/PWNAGOTCI-PLUGINS/plugins/vslider")
import vslider

# speed up: no real sleeping (prove it never *hangs*, just measure logical time)
slept=[0.0]
def fast_sleep(s): slept[0]+=s
vslider.time.sleep=fast_sleep

def mk():
    v=vslider.Vslider()
    v._dir=tempfile.mkdtemp()
    v._uploaded_f=os.path.join(v._dir,"uploaded.json")
    v._hs_dir=hs
    v._wpasec_key="TESTKEY"
    v._ap_live=True
    v._pos=vslider.POS_DASH
    return v

print("== 1. _client_connect (ports: monstop/rfkill/ip/wpa_supplicant/dhclient) ==")
v=mk()
ok=v._client_connect("Kubtek-64_2","21051980")
print("   connected (saw 'inet'):", ok)
assert ok

print("== 2. _upload_wpasec: 5 new -> cumulative 5, counter ticks ==")
ticks=[]
n=v._upload_wpasec(on_progress=lambda c: ticks.append(c))
print("   uploaded total:", n, " live ticks:", ticks, " persisted:", sorted(v._uploaded))
assert n==5 and ticks==[1,2,3,4,5]

print("== 3. re-run upload: all already sent -> 0 new, instant, no ticks ==")
ticks2=[]
n2=v._upload_wpasec(on_progress=lambda c: ticks2.append(c))
print("   total still:", n2, " new ticks:", ticks2)
assert n2==5 and ticks2==[]

print("== 4. new pcap appears -> only it uploads, counter goes 5->6 ==")
open(os.path.join(hs,"net_new_bb.pcap"),"wb").write(b"\x00"*10)
ticks3=[]
n3=v._upload_wpasec(on_progress=lambda c: ticks3.append(c))
print("   total:", n3, " ticks:", ticks3)
assert n3==6 and ticks3==[6]

print("== 5. _do_upload: counter grows, current network name set, really posts ==")
v2=mk()
seen=[]
_orig_post=v2._post_one
def _rec(p):
    seen.append(v2._flow_cur)
    return _orig_post(p)
v2._post_one=_rec
v2._flow_state="upload"
v2._do_upload()
print("   flow_total:", v2._flow_total, " flow_up:", v2._flow_up, " networks:", seen)
assert v2._flow_up==v2._flow_total==6, "all handshakes counted"
assert all(seen), "current network name set for each upload"

print("== 6. full LIVE _flow_run reaches 'done' (happy face) ==")
v3=mk()
v3._nearby=[{"ssid":"Kubtek-64_2","mac":"AA:BB:CC:DD:EE:FF","ch":6,"rssi":-40}]
import json as _j
pf=os.path.join(v3._dir,"profiles.json")
_j.dump({"Kubtek-64_2":{"pw":"21051980"}}, open(pf,"w"))
v3._profiles_f=pf
t0=_time.time()
v3._flow_run()
wall=_time.time()-t0
print("   flow_done:", v3._flow_done, " face:", v3._flow_face, " (expect (^o^))")
print("   logical sleep budget: %.1fs (real wall: %.2fs — never blocked)"%(slept[0],wall))
assert wall < 2.0, "flow must not actually block"
assert v3._flow_done and v3._flow_face=="(^o^)", "ends on the happy done screen"

print("\nALL NETWORK-LOGIC TESTS PASSED")
