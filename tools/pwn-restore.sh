#!/usr/bin/env bash
# =============================================================================
#  pwn-restore.sh  —  восстановитель Pwnagotchi "Ki213" (под пользователя)
#
#  Что делает:
#    1) бэкапит текущий config.toml (с датой),
#    2) копирует наши плагины из /home/pi в custom-plugins (если они там лежат),
#    3) пишет ЧИСТЫЙ правильный config.toml (без багов, что роняли устройство),
#    4) проверяет синтаксис (если плохо — откатывает бэкап и выходит),
#    5) чинит папку хендшейков и права,
#    6) перезапускает pwnagotchi.
#
#  Запуск:
#     sudo bash /home/pi/pwn-restore.sh
#
#  Безопасно гонять повторно. Твои данные (пароли/хендшейки/статы) не трогаются.
# =============================================================================
set -u

CFG=/etc/pwnagotchi/config.toml
PLUG=/usr/local/share/pwnagotchi/custom-plugins
PY=/home/pi/.pwn/bin/python3
STAMP=$(date +%Y%m%d-%H%M%S)
BAK="$CFG.bak.$STAMP"

echo "==> 1/6  Бэкап текущего конфига"
if [ -f "$CFG" ]; then
  cp "$CFG" "$BAK" && echo "    сохранён: $BAK"
else
  echo "    (конфига не было — создаём с нуля)"
fi

echo "==> 2/6  Наши плагины в custom-plugins"
mkdir -p "$PLUG"
for f in bootlogo brain callout pwndex vslider voice_ru; do
  if [ -f "/home/pi/$f.py" ]; then
    cp "/home/pi/$f.py" "$PLUG/" && echo "    + $f.py (обновлён из /home/pi)"
  elif [ -f "$PLUG/$f.py" ]; then
    echo "    = $f.py (уже на месте)"
  else
    echo "    ! $f.py НЕ найден — залей его в /home/pi и прогони скрипт ещё раз"
  fi
done
rm -rf "$PLUG/__pycache__"

echo "==> 3/6  Пишу чистый config.toml"
cat > "$CFG" <<'TOML'
main.name = "Ki213"
main.lang = "ru"
main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins"
main.whitelist = ["Xiaomi_67", "TP-Link_179C", "Lider", "Kubtek-64_2", "fo:od:ba"]
main.confd = "/etc/pwnagotchi/conf.d/"
main.custom_plugin_repos = [
  "https://github.com/jayofelony/pwnagotchi-torch-plugins/archive/master.zip",
  "https://github.com/Sniffleupagus/pwnagotchi_plugins/archive/master.zip",
  "https://github.com/NeonLightning/pwny/archive/master.zip",
  "https://github.com/marbasec/UPSLite_Plugin_1_3/archive/master.zip",
  "https://github.com/wpa-2/Pwnagotchi-Plugins/archive/master.zip",
]
main.iface = "wlan0mon"
main.mon_start_cmd = "/usr/bin/monstart"
main.mon_stop_cmd = "/usr/bin/monstop"
main.mon_max_blind_epochs = 5
main.no_restart = false

# ---------- НАШИ ПЛАГИНЫ ----------
main.plugins.brain.enabled = true
main.plugins.callout.enabled = true
main.plugins.pwndex.enabled = true
main.plugins.pwndex.catalog_seen = true
main.plugins.pwndex.auto_whitelist = true
main.plugins.vslider.enabled = true
main.plugins.voice_ru.enabled = true
main.plugins.bootlogo.enabled = true
main.plugins.bootlogo.path = "/root/pwnagotchi-bootlogo.png"

# ---------- КОММЬЮНИТИ-ПЛАГИНЫ (как у тебя было) ----------
main.plugins.auto-tune.enabled = true
main.plugins.auto-tune.show_hidden = false
main.plugins.auto-tune.reset_history = true
main.plugins.auto-tune.extra_channels = 15

# ВНИМАНИЕ: auto-update ВЫКЛЮЧЕН специально — он обновлял pwngrid до версии,
# которая роняла устройство (GLIBC). Включишь сам, когда захочешь обновиться.
main.plugins.auto-update.enabled = false
main.plugins.auto-update.install = true
main.plugins.auto-update.interval = 1
main.plugins.auto-update.token = ""

main.plugins.fix_services.enabled = true

main.plugins.grid.enabled = true
main.plugins.grid.report = true

main.plugins.logtail.enabled = true
main.plugins.logtail."max-lines" = 10000

main.plugins.session-stats.enabled = true
main.plugins.session-stats.save_directory = "/var/tmp/pwnagotchi/sessions/"

main.plugins.wpa-sec.enabled = true
main.plugins.wpa-sec.api_key = "6e542c158018d6e8eb4ec4ee2a967f4b"
main.plugins.wpa-sec.api_url = "https://wpa-sec.stanev.org"
main.plugins.wpa-sec.download_results = true
main.plugins.wpa-sec.show_pwd = false
main.plugins.wpa-sec.single_files = false

main.plugins.wpa-sec-list.enabled = true

main.plugins.memtemp-plus.enabled = true
main.plugins.memtemp-plus.orientation = "horizontal"
main.plugins.memtemp-plus.scale = "celsius"
main.plugins.memtemp-plus.fields = "mem,cpu,temp"
main.plugins.memtemp-plus.linespacing = 12
main.plugins.memtemp-plus.position = "170,85"

main.plugins.handshakes-dl.enabled = true

main.plugins.better_quickdic.enabled = true
main.plugins.better_quickdic.face = "(·ω·)"
main.plugins.better_quickdic.wordlist_folder = "/home/pi/wordlists/"
main.plugins.better_quickdic.api = ""
main.plugins.better_quickdic.id = ""

main.plugins.display-password.enabled = true
main.plugins.display-password.orientation = "horizontal"

main.plugins.enable_assoc.enabled = true
main.plugins.enable_deauth.enabled = true
main.plugins.internet-connection.enabled = true
main.plugins.tweak_view.enabled = true

main.plugins.wof.enabled = true
main.plugins.wof.wof_file = "/home/pi/Wall-of-Flippers/Flipper.json"
main.plugins.wof.online_timespan = 60
main.plugins.wof.icon = true
main.plugins.wof.icon_reverse = false
main.plugins.wof.position.x = 5
main.plugins.wof.position.y = 82

main.plugins.auto_backup.enabled = true
main.plugins.auto_backup.backup_location = "/etc/pwnagotchi/backups"

# ---------- выключенные (как у тебя) ----------
main.plugins.bt-tether.enabled = false
main.plugins.gdrivesync.enabled = false
main.plugins.gpio_buttons.enabled = false
main.plugins.gps.enabled = false
main.plugins.gps_listener.enabled = false
main.plugins.memtemp.enabled = false
main.plugins.ohcapi.enabled = false
main.plugins.pwndroid.enabled = false
main.plugins.pisugarx.enabled = false
main.plugins.ups_hat_c.enabled = false
main.plugins.ups_lite.enabled = false
main.plugins.webgpsmap.enabled = false
main.plugins.wigle.enabled = false
main.plugins.exp.enabled = false
main.plugins.IPDisplay.enabled = false
main.plugins.pixel_lab.enabled = false
main.plugins.pwncrack.enabled = false
main.plugins.pwnstore_ui.enabled = false

# webcfg: ОСТАВЛЕН ВКЛЮЧЁННЫМ для просмотра, но НЕ сохраняй через него
# конфиг (его кнопка Save = та самая Error 500, что стёрла настройки).
main.plugins.webcfg.enabled = true

# ---------- логи ----------
main.log.path = "/etc/pwnagotchi/log/pwnagotchi.log"
main.log."path-debug" = "/etc/pwnagotchi/log/pwnagotchi-debug.log"
main.log.rotation.enabled = true
main.log.rotation.size = "10M"

# ---------- интерфейс / экран ----------
ui.invert = true
ui.cursor = true
ui.fps = 1

ui.web.enabled = true
ui.web.username = "rofl"
ui.web.password = "1234"
ui.web.address = "::"
ui.web.auth = false
ui.web.origin = ""
ui.web.port = 8080
ui.web.on_frame = ""

ui.web.theme.accent_r = 76
ui.web.theme.accent_g = 175
ui.web.theme.accent_b = 80

ui.display.enabled = true
ui.display.type = "waveshare_4"
ui.display.color = "black"
ui.display.rotation = 180

ui.font.name = "DejaVuSansMono"
ui.font.size_offset = 0

ui.faces.look_r = "( ⚆_⚆)"
ui.faces.look_l = "(☉_☉ )"
ui.faces.look_r_happy = "( ◕‿◕)"
ui.faces.look_l_happy = "(◕‿◕ )"
ui.faces.sleep = "(⇀‿‿↼)"
ui.faces.sleep2 = "(≖‿‿≖)"
ui.faces.awake = "(◕‿‿◕)"
ui.faces.bored = "(-__-)"
ui.faces.intense = "(°▃▃°)"
ui.faces.cool = "(⌐■_■)"
ui.faces.happy = "(•‿‿•)"
ui.faces.excited = "(ᵔ◡◡ᵔ)"
ui.faces.grateful = "(^‿‿^)"
ui.faces.motivated = "(☼‿‿☼)"
ui.faces.demotivated = "(≖__≖)"
ui.faces.smart = "(✜‿‿✜)"
ui.faces.lonely = "(ب__ب)"
ui.faces.sad = "(╥☁╥ )"
ui.faces.angry = "(-_-')"
ui.faces.friend = "(♥‿‿♥)"
ui.faces.broken = "(☓‿‿☓)"
ui.faces.debug = "(#__#)"
ui.faces.upload = "(1__0)"
ui.faces.upload1 = "(1__1)"
ui.faces.upload2 = "(0__1)"
ui.faces.png = false
ui.faces.position_x = 0
ui.faces.position_y = 34

# ---------- поведение ----------
# advertise = false  -> pwnagotchi НЕ лезет к pwngrid (это и роняло экран).
personality.advertise = false
personality.deauth = true
personality.associate = true
personality.channels = [1, 2, 6, 7, 8, 11, 6, 2, 11, 3, 9, 7, 8, 1, 12, 5, 10, 13, 4]
personality.min_rssi = -200
personality.ap_ttl = 120
personality.sta_ttl = 300
personality.recon_time = 30
personality.max_inactive_scale = 2
personality.recon_inactive_multiplier = 2
personality.hop_recon_time = 10
personality.min_recon_time = 5
personality.max_interactions = 3
personality.max_misses_for_recon = 5
personality.excited_num_epochs = 10
personality.bored_num_epochs = 15
personality.sad_num_epochs = 25
personality.bond_encounters_factor = 20000
personality.throttle_a = 0.4
personality.throttle_d = 0.9
personality.capture_broken_frames = true

# ---------- bettercap: ВАЖНО для счётчика PWND ----------
# именно тут лежат твои 44 хендшейка — поэтому PWND будет считать их.
bettercap.handshakes = "/home/pi/handshakes"
bettercap.silence = [
  "ble.device.new", "ble.device.lost", "ble.device.disconnected",
  "ble.device.connected", "ble.device.service.discovered",
  "ble.device.characteristic.discovered", "wifi.client.new",
  "wifi.client.lost", "wifi.client.probe", "wifi.ap.new",
  "wifi.ap.lost", "mod.started",
]

# ---------- RAM-диски (как у тебя) ----------
fs.memory.enabled = true
fs.memory.mounts.log.enabled = true
fs.memory.mounts.log.mount = "/etc/pwnagotchi/log/"
fs.memory.mounts.log.size = "50M"
fs.memory.mounts.log.sync = 60
fs.memory.mounts.log.zram = true
fs.memory.mounts.log.rsync = true
fs.memory.mounts.data.enabled = true
fs.memory.mounts.data.mount = "/var/tmp/pwnagotchi"
fs.memory.mounts.data.size = "10M"
fs.memory.mounts.data.sync = 3600
fs.memory.mounts.data.zram = true
fs.memory.mounts.data.rsync = true
TOML

echo "==> 4/6  Проверка синтаксиса конфига"
if ! $PY -c "import toml; toml.load('$CFG')" 2>/tmp/cfgerr; then
  echo "    !!! ОШИБКА в конфиге:"; cat /tmp/cfgerr
  if [ -f "$BAK" ]; then
    cp "$BAK" "$CFG" && echo "    откатил бэкап $BAK — ничего не сломано."
  fi
  exit 1
fi
echo "    config OK ✓"

echo "==> 5/6  Папка хендшейков и права"
mkdir -p /home/pi/handshakes
chown -R pi:pi /home/pi/handshakes 2>/dev/null || true

echo "==> 6/6  Перезапуск pwnagotchi"
systemctl restart pwnagotchi

echo
echo "================  ГОТОВО  ================"
echo "Через ~1-2 мин проверь экран: лицо, PWND (должно подтянуть ~44),"
echo "и веб http://10.0.0.2:8080/plugins/ — все плагины на месте."
echo "Бэкап старого конфига лежит тут: $BAK"
