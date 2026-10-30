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
    v._sync_f=os.path.join(v._dir,"sync.json")
    v._sync_seen_f=os.path.join(v._dir,"sync_seen.json")
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
print("   flow_done:", v3._flow_done, " end state:", v3._flow_state, " (expect idle=dashboard)")
print("   logical sleep budget: %.1fs (real wall: %.2fs — never blocked)"%(slept[0],wall))
assert wall < 2.0, "flow must not actually block"
assert v3._flow_done and v3._flow_state=="idle", "after success: dashboard, no re-loop"

print("== 7. _sync_result_face: each result maps to the right face ==")
f_ok,_=vslider.Vslider._sync_result_face("ok",6,6)
f_np,_=vslider.Vslider._sync_result_face("no_profile",0,6)
f_ni,_=vslider.Vslider._sync_result_face("no_iface",0,6)
f_nn,_=vslider.Vslider._sync_result_face("no_net",0,6)
f_part,t_part=vslider.Vslider._sync_result_face("ok",3,6)
print("   ok:",f_ok," no_profile:",f_np," no_iface:",f_ni," no_net:",f_nn," partial:",f_part,t_part)
assert f_ok=="(^o^)" and f_np=="(x_x)" and f_ni=="(x_x)" and f_nn=="(T_T)"
assert f_part=="(^_^)" and "3" in t_part[1] and "6" in t_part[1]

print("== 8. _launch_sync: writes 'start' sync.json, shows 'launch', guards double-run ==")
v4=mk()
script=os.path.join(v4._dir,"pwn-sync.sh"); open(script,"w").write("#!/bin/bash\n")
v4._sync_script=script
ok,msg=v4._launch_sync()
import json as _j2
s=_j2.load(open(v4._sync_f))
print("   ok:",ok," state file:",s.get("state")," flow:",v4._flow_state," msg:",msg[:40])
assert ok and s.get("state")=="start" and v4._flow_state=="launch"
ok2,msg2=v4._launch_sync()        # already running (not finished, fresh ts)
print("   second call blocked:",(not ok2),"->",msg2[:40])
assert not ok2

print("== 9. _replay_sync: animates up to sent_total, ends on dashboard ==")
v5=mk()
calls=[]
_orig_set=v5._flow_set
def _rec_set(state,face,text): calls.append((state,face)); _orig_set(state,face,text)
v5._flow_set=_rec_set
run={"total":6,"up":4,"sent_total":6,"names":["A","B","C","D","E","F"],
     "result":"ok","finished":True,"fin_ts":int(_time.time())}
t0=_time.time(); v5._replay_sync(run); wall=_time.time()-t0
states=[c[0] for c in calls]
print("   states:",states," final up:",v5._flow_up," flow_done:",v5._flow_done," wall %.2fs"%wall)
assert states[0]=="replay" and ("done" in states) and states[-1]=="idle"
assert v5._flow_done and v5._flow_state=="idle" and wall<2.0
# the 'done' frame carried the happy face
assert any(st=="done" and fc=="(^o^)" for st,fc in calls)

print("== 10. _maybe_replay_sync: fires once for a fresh finished run, then quiet ==")
v6=mk()
_j2.dump({"total":3,"up":3,"sent_total":3,"names":["X","Y","Z"],
          "result":"ok","finished":True,"fin_ts":int(_time.time())}, open(v6._sync_f,"w"))
v6._maybe_replay_sync()
th=v6._flow_thread
if th: th.join(timeout=5)
print("   seen_ts set:",v6._sync_seen_ts>0," ended:",v6._flow_state)
assert v6._sync_seen_ts>0
before=v6._sync_seen_ts
v6._maybe_replay_sync()           # same run again -> nothing
assert v6._sync_seen_ts==before and (v6._flow_thread is th)
# a too-old finished run is remembered silently (no replay)
v7=mk()
_j2.dump({"total":2,"up":2,"sent_total":2,"result":"ok","finished":True,
          "fin_ts":int(_time.time())-5000}, open(v7._sync_f,"w"))
v7._maybe_replay_sync()
print("   old run: seen_ts set:",v7._sync_seen_ts>0," no replay thread:",v7._flow_thread is None)
assert v7._sync_seen_ts>0 and v7._flow_thread is None

print("== 11. _maybe_auto_sync: fires once when a profile is near, respects cooldown ==")
v8=mk(); v8._sync_auto=True
launches=[]
v8._launch_sync=lambda: (launches.append(1), (True,"ok"))[1]
# no profile nearby -> nothing
v8._nearby=[]
v8._maybe_auto_sync()
assert launches==[] and not v8._sync_auto_done
# profile nearby -> fire once, then guarded
v8._nearby=[{"ssid":"Kubtek-64_2","mac":"AA","ch":6,"rssi":-40}]
import json as _j3
_j3.dump({"Kubtek-64_2":{"pw":"x"}}, open(os.path.join(v8._dir,"p.json"),"w"))
v8._profiles_f=os.path.join(v8._dir,"p.json")
v8._maybe_auto_sync(); v8._maybe_auto_sync()
print("   launches after 2 calls:",len(launches)," done:",v8._sync_auto_done)
assert len(launches)==1 and v8._sync_auto_done
# cooldown: a run finished seconds ago -> no fire, just mark done
v9=mk(); v9._sync_auto=True
v9._launch_sync=lambda: (launches.append(1), (True,"ok"))[1]
v9._nearby=v8._nearby; v9._profiles_f=v8._profiles_f
_j3.dump({"finished":True,"fin_ts":int(_time.time())}, open(v9._sync_f,"w"))
v9._maybe_auto_sync()
print("   within cooldown: extra launches:",len(launches)-1," done:",v9._sync_auto_done)
assert len(launches)==1 and v9._sync_auto_done

print("\nALL NETWORK-LOGIC TESTS PASSED")
