import os, sys, json, tempfile, shutil, types

# --- stub pwnagotchi.plugins ---
pk = types.ModuleType("pwnagotchi"); pk.__path__=[]
pl = types.ModuleType("pwnagotchi.plugins")
class _P:
    def __init__(self,*a,**k): pass
pl.Plugin=_P
sys.modules["pwnagotchi"]=pk; sys.modules["pwnagotchi.plugins"]=pl

sys.path.insert(0, "/home/user/PWNAGOTCI-PLUGINS/plugins/full_save")
import full_save as FS

SIG = FS._EAPOL_SIG
def mk_eapol(key_info, pmkid=False):
    body = bytes([0x02,0x03,0x00,0x5f,0x02, (key_info>>8)&0xff, key_info&0xff])
    body += b"\x00"*20
    if pmkid: body += b"xxxx"+FS._PMKID_KDE+b"yyyy"
    return SIG+body
M1=0x008a; M2=0x010a; M3=0x13ca
def write(path,*frames):
    with open(path,"wb") as f:
        f.write(b"PCAPJUNKHEADER");
        for fr in frames: f.write(b"....."+fr)

ok=True
def check(name,cond):
    global ok
    print(("PASS " if cond else "FAIL ")+name); ok=ok and cond

# ========== 1. EAPOL detection ==========
tmp=tempfile.mkdtemp()
p=os.path.join(tmp,"a.pcap"); write(p, mk_eapol(M1), mk_eapol(M2))
check("M1+M2 -> crackable", FS._is_crackable(p) is True)
p=os.path.join(tmp,"b.pcap"); write(p, mk_eapol(M1))
check("only M1 -> NOT crackable", FS._is_crackable(p) is False)
p=os.path.join(tmp,"c.pcap"); write(p, mk_eapol(M2), mk_eapol(M3))
check("M2+M3 -> crackable", FS._is_crackable(p) is True)
p=os.path.join(tmp,"d.pcap"); write(p, mk_eapol(M1, pmkid=True))
check("PMKID -> crackable", FS._is_crackable(p) is True)
p=os.path.join(tmp,"e.pcap"); write(p, mk_eapol(M1), mk_eapol(M3))
check("M1+M3 only (no SNonce) -> NOT crackable", FS._is_crackable(p) is False)

# ========== 2. bssid grouping ==========
check("bssid parse A", FS._bssid_of("MyNet_aabbccddeeff.pcap")=="aabbccddeeff")
check("bssid parse B (empty essid)", FS._bssid_of("_aabbccddeeff.pcap")=="aabbccddeeff")
check("bssid parse junk -> ''", FS._bssid_of("MyNet_2.pcap")=="")

# ========== 3. SAFETY: tidy only inside base, never symlink/outside ==========
root=tempfile.mkdtemp()
base=os.path.join(root,"handshakes"); os.makedirs(base)
outside=os.path.join(root,"SYSTEM_IMPORTANT.txt")
open(outside,"w").write("DO NOT TOUCH")
# a symlink inside base pointing OUTSIDE, named like a pcap
evil=os.path.join(base,"evil_aabbccddeeff.pcap")
os.symlink(outside, evil)
# a nested subdir with a pcap (must not be touched)
sub=os.path.join(base,"sub"); os.makedirs(sub)
nested=os.path.join(sub,"deep_aabbccddeeff.pcap"); open(nested,"wb").write(b"x")

# network AABBCC: one complete + one incomplete (different essid prefix, same bssid)
complete=os.path.join(base,"HomeNet_aabbccddeeff.pcap")
write(complete, mk_eapol(M1), mk_eapol(M2))               # crackable
incomplete=os.path.join(base,"_aabbccddeeff.pcap")
write(incomplete, mk_eapol(M1))                           # incomplete
# a DIFFERENT network, incomplete only -> must be left alone
other=os.path.join(base,"Cafe_112233445566.pcap")
write(other, mk_eapol(M1))

plug=FS.FullSave()
plug.options={"handshakes":base,"hard_delete":False}
plug.on_loaded()           # runs scan_all

trash=os.path.join(base,"_full_save_trash")
check("outside SYSTEM file untouched", os.path.exists(outside) and open(outside).read()=="DO NOT TOUCH")
check("symlink refused (_safe_pcap False)", plug._safe_pcap(evil) is False)
check("symlink still present / target intact", os.path.islink(evil) and os.path.exists(outside))
check("nested pcap untouched", os.path.exists(nested))
check("complete handshake KEPT", os.path.exists(complete))
check("incomplete dup MOVED out of base", not os.path.exists(incomplete))
check("incomplete dup now in trash", os.path.exists(os.path.join(trash, os.path.basename(incomplete))))
check("other network's lone file LEFT ALONE", os.path.exists(other))
check("done.json records the network", plug._done.get("aabbccddeeff",{}).get("essid")=="HomeNet")

# ========== 4. SAFETY: _safe_pcap rejects everything dangerous ==========
check("reject non-pcap", plug._safe_pcap(os.path.join(base,"notes.txt")) is False)
check("reject dir", plug._safe_pcap(sub) is False)
check("reject path outside base", plug._safe_pcap(outside) is False)
check("reject file in trash", plug._safe_pcap(os.path.join(trash,os.path.basename(incomplete))) is False)

# ========== 5. hard_delete path still guarded ==========
base2=tempfile.mkdtemp()
comp2=os.path.join(base2,"N_aabbccddeeff.pcap"); write(comp2, mk_eapol(M1),mk_eapol(M2))
inc2=os.path.join(base2,"_aabbccddeeff.pcap"); write(inc2, mk_eapol(M1))
out2=os.path.join(os.path.dirname(base2),"keepme.txt"); open(out2,"w").write("keep")
plug2=FS.FullSave(); plug2.options={"handshakes":base2,"hard_delete":True}; plug2.on_loaded()
check("hard_delete removed the dup", not os.path.exists(inc2))
check("hard_delete kept the complete", os.path.exists(comp2))
check("hard_delete did NOT touch outside file", os.path.exists(out2))

shutil.rmtree(tmp,ignore_errors=True); shutil.rmtree(root,ignore_errors=True)
shutil.rmtree(base2,ignore_errors=True)
print("\n"+("ALL TESTS PASSED ✅" if ok else "SOME TESTS FAILED ❌"))
sys.exit(0 if ok else 1)
