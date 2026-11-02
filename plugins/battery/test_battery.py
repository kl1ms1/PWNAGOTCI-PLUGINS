import sys, types, time as _time

# --- stub pwnagotchi ---
pk = types.ModuleType("pwnagotchi"); plug = types.ModuleType("pwnagotchi.plugins")
class P:
    def __init__(self): self.options = {}
plug.Plugin = P
comp = types.ModuleType("pwnagotchi.ui.components"); comp.Widget = object
ui = types.ModuleType("pwnagotchi.ui"); pk.plugins = plug; pk.ui = ui
for n, m in [("pwnagotchi", pk), ("pwnagotchi.plugins", plug),
             ("pwnagotchi.ui", ui), ("pwnagotchi.ui.components", comp)]:
    sys.modules[n] = m

# --- stub smbus2 (what the UPS Lite MAX17040 would return over I2C) ---
# SMBus.read_word_data returns bytes in SMBus order (swapped vs the device),
# which the plugin swaps back. We store DEVICE words and swap here to mimic that.
REGS = {}
def _smbus_order(devword):
    return ((devword & 0xFF) << 8) | (devword >> 8)
smbus2 = types.ModuleType("smbus2")
class SMBus:
    def __init__(self, bus): self.bus = bus
    def read_word_data(self, addr, reg): return _smbus_order(REGS.get(reg, 0))
    def close(self): pass
smbus2.SMBus = SMBus
sys.modules["smbus2"] = smbus2

sys.path.insert(0, "/home/user/PWNAGOTCI-PLUGINS/plugins/battery")
import battery

def set_cell(volts, pct):
    # VCELL: 12-bit, (reg>>4)*1.25mV  -> devword = round(volts/1.25mV)<<4
    REGS[0x02] = (int(round(volts * 1000 / 1.25)) << 4) & 0xFFFF
    # SOC: high byte = integer %, low byte = fraction/256
    ip = int(pct); fr = int(round((pct - ip) * 256)) & 0xFF
    REGS[0x04] = ((ip & 0xFF) << 8) | fr

def mk():
    b = battery.Battery()
    b.options = {}                     # framework sets this in real pwnagotchi
    b.on_loaded()
    return b

print("== 1. fuel-gauge math: voltage + capacity decode ==")
b = mk(); set_cell(3.9, 77.5)
v = b._read_voltage(); c = b._read_capacity()
print("   volts:", v, " pct:", c)
assert abs(v - 3.9) < 0.02, v
assert abs(c - 77.5) < 0.1, c

print("== 2. charging by VOLTAGE (>=4.15) ==")
b = mk(); set_cell(4.20, 90)
b._sample()
print("   volts:", b._volts, " charging:", b._charging, " anim_until>now:", b._anim_until > _time.time())
assert b._charging is True
assert b._anim_until > _time.time(), "rising edge should arm the plug-in animation"

print("== 3. NOT charging on battery (low volts, steady %) ==")
b = mk(); set_cell(3.75, 60)
b._sample()
print("   volts:", b._volts, " charging:", b._charging)
assert b._charging is False

print("== 4. charging by RISING % (voltage low but SOC climbs >=1%) ==")
b = mk()
t = 1000.0
_orig = battery.time.time
battery.time.time = lambda: t
try:
    set_cell(3.80, 50.0); b._sample()          # first sample
    for step in range(1, 5):
        t += 10; set_cell(3.80, 50.0 + step)    # % climbs 1 each read
        b._sample()
    print("   charging (rising):", b._charging, " hist:", len(b._hist))
    assert b._charging is True
finally:
    battery.time.time = _orig

print("== 5. no HAT / no I2C -> stays blank, never crashes ==")
b = mk(); REGS.clear()                           # reads return 0 -> treat as present? ensure no crash
# simulate a totally missing bus: force _open_bus to None
b._open_bus = lambda: None
b._pct = None
b._sample()
print("   pct:", b._pct, " (expected None, no crash)")
assert b._pct is None

print("\nALL BATTERY TESTS PASSED")
