import UIKit
import CoreLocation

/// Fake data for the demo/beta mode — try every screen with no device.
enum DemoData {
    static func status() -> DeviceStatus {
        DeviceStatus(name: "Ki213", mode: "auto", uptime: 7320, temp: 47, cpu: 22,
                     mem: 58, sd_free: 9, pcaps: 17, networks: 42, cracked: 5, shakes: 3)
    }

    static func pwndex() -> [NetItem] {
        [
            NetItem(ssid: "HomeWiFi", mac: "A0:28:5D:A0:C4:C0", pw: "qwerty12345", caught: true, last: 0, pw_at: 0),
            NetItem(ssid: "Keenetic-home", mac: "50:FF:20:11:22:33", pw: "", caught: true, last: 0, pw_at: 0),
            NetItem(ssid: "Xiaomi_67", mac: "50:4F:3B:CB:39:FE", pw: "23851658", caught: true, last: 0, pw_at: 0),
            NetItem(ssid: "TP-Link_179C", mac: "6A:06:C3:9B:17:9C", pw: "", caught: false, last: 0, pw_at: 0),
            NetItem(ssid: "MGTS_GPON", mac: "11:22:33:44:55:66", pw: "password1", caught: true, last: 0, pw_at: 0),
            NetItem(ssid: "CoffeeHouse", mac: "77:88:99:AA:BB:CC", pw: "", caught: false, last: 0, pw_at: 0),
        ]
    }

    static func events() -> [AppEvent] {
        [
            AppEvent(time: "12:03:41", icon: "antenna.radiowaves.left.and.right", text: "deauth → Xiaomi_67 (50:4F:3B…)"),
            AppEvent(time: "12:03:40", icon: "person.2.fill", text: "associate → Keenetic-home"),
            AppEvent(time: "12:03:38", icon: "hand.wave.fill", text: "handshake captured: HomeWiFi"),
            AppEvent(time: "12:03:12", icon: "wifi", text: "new network: MGTS_GPON"),
            AppEvent(time: "12:02:55", icon: "arrow.up.circle", text: "uploaded to wpa-sec: 2 .pcap"),
            AppEvent(time: "12:02:10", icon: "bolt.fill", text: "channel → 6"),
            AppEvent(time: "12:01:00", icon: "face.smiling", text: "face: (⌐■_■) — caught!"),
            AppEvent(time: "12:00:02", icon: "play.circle", text: "mode: AUTO, hunting started"),
        ]
    }

    static func logEvents() -> [LogEvent] {
        [
            LogEvent(time: "12:03:41", kind: "deauth", text: "wifi: deauth → Xiaomi_67 (50:4F:3B:CB:39:FE) ch6"),
            LogEvent(time: "12:03:40", kind: "assoc", text: "wifi: associate → Keenetic-home"),
            LogEvent(time: "12:03:38", kind: "handshake", text: "wifi: handshake captured: HomeWiFi"),
            LogEvent(time: "12:03:12", kind: "info", text: "wifi: new network MGTS_GPON (ch11)"),
            LogEvent(time: "12:02:55", kind: "upload", text: "wpa-sec: uploaded 2 .pcap"),
            LogEvent(time: "12:02:10", kind: "ai", text: "ai: epoch 318, reward 1.42"),
            LogEvent(time: "12:01:40", kind: "peer", text: "grid: new peer seen (f.0e7a)"),
            LogEvent(time: "12:00:02", kind: "info", text: "mode: AUTO, hunting started"),
        ]
    }

    static func pins() -> [CatchPin] {
        [
            CatchPin(id: "A0:28:5D:A0:C4:C0", ssid: "HomeWiFi", lat: 45.0350, lon: 38.9750, date: 0),
            CatchPin(id: "50:4F:3B:CB:39:FE", ssid: "Xiaomi_67", lat: 45.0398, lon: 38.9820, date: 0),
            CatchPin(id: "11:22:33:44:55:66", ssid: "MGTS_GPON", lat: 45.0421, lon: 38.9688, date: 0),
        ]
    }

    /// Demo config.toml values for cfg_get.
    static func cfg(_ key: String) -> Any? {
        switch key {
        case "main.name": return "Ki213"
        case "main.plugins.wpa-sec.api_key": return ""
        case "ui.faces":
            return ["LOOK_R": "( ⚆_⚆)", "LOOK_L": "(☉_☉ )", "SLEEP": "(⇀‿‿↼)",
                    "AWAKE": "(◕‿‿◕)", "HAPPY": "(•‿‿•)", "COOL": "(⌐■_■)",
                    "INTENSE": "(°▃▃°)", "BORED": "(-__-)", "SAD": "(╥☁╥ )",
                    "EXCITED": "(ᵔ◡◡ᵔ)"]
        default: return nil
        }
    }

    /// Believable shell output for the demo terminal (so beta feels real).
    static func shell(_ raw: String) -> String {
        let cmd = raw.trimmingCharacters(in: .whitespaces)
        let l = cmd.lowercased()
        func has(_ s: String) -> Bool { l.contains(s) }

        if l == "ls" || l.hasPrefix("ls ") {
            if has("/etc/pwnagotchi") { return "config.toml\nconfig.toml.companion.bak\nlog" }
            if has("handshake") { return "HomeWiFi_a0285da0c4c0.pcap\nXiaomi_67_504f3bcb39fe.pcap\nMGTS_GPON_112233445566.pcap" }
            if has("/home/pi") { return "handshakes  scripts  .bashrc  .profile" }
            return "brain.json  btlink_ble.py  handshakes  .pwndex"
        }
        if has("uptime") { return " 20:13:02 up 2:02,  1 user,  load average: 0.41, 0.33, 0.29" }
        if has("temp") { return "temp=47.3'C" }
        if has("df") { return "Filesystem      Size  Used Avail Use% Mounted on\n/dev/mmcblk0p2   29G   18G  9.4G  66% /" }
        if has("free") { return "               total        used        free\nMem:           452Mi       262Mi       118Mi\nSwap:          100Mi        12Mi        88Mi" }
        if has("pwnagotchi.log") || has("journalctl") {
            return "[demo] 20:12:58 wifi: deauth → Xiaomi_67 (50:4F:3B:CB:39:FE)\n[demo] 20:12:59 wifi: handshake HomeWiFi captured\n[demo] 20:13:01 ai: reward 1.42, epoch 318\n[demo] 20:13:02 ui: face (⌐■_■)" }
        if has("handshakes") && has("wc") { return "17" }
        if has("iwconfig") || has("ip -br") || has("ip link") {
            return "wlan0mon  IEEE 802.11  Mode:Monitor  Frequency:2.437 GHz  Tx-Power=31 dBm" }
        if has("i2cget") { return "0x5a3c" }
        if has("bluetoothctl") || has("hciconfig") { return "Powered: yes\nDiscoverable: yes\nPairable: yes" }
        if has("whoami") { return "root" }
        if has("hostname") { return "Ki213" }
        if has("config.toml") && has("grep") {
            return "main.plugins.companion.enabled = true\nmain.plugins.wpa-sec.enabled = true\nmain.plugins.grid.enabled = true" }
        if has("restart") || has("pwnkill") { return "[demo] pwnagotchi.service restarted" }
        if has("reboot") { return "[demo] rebooting…" }
        if has("uname") { return "Linux Ki213 6.6.31+rpt-rpi-v8 aarch64 GNU/Linux" }
        return "[demo] executed: \(cmd)"
    }

    /// Fake root filesystem for the demo file browser.
    static func fsListing(_ path: String) -> FsListing {
        let tree: [String: [FileEntry]] = [
            "/root": [
                FileEntry(name: "handshakes", dir: true, size: 0),
                FileEntry(name: ".pwndex", dir: true, size: 0),
                FileEntry(name: "brain.json", dir: false, size: 4096),
                FileEntry(name: "btlink_ble.py", dir: false, size: 5120),
            ],
            "/root/handshakes": [
                FileEntry(name: "HomeWiFi_a0285da0c4c0.pcap", dir: false, size: 24576),
                FileEntry(name: "Xiaomi_67_504f3bcb39fe.pcap", dir: false, size: 18432),
            ],
            "/etc/pwnagotchi": [
                FileEntry(name: "config.toml", dir: false, size: 2048),
                FileEntry(name: "config.toml.companion.bak", dir: false, size: 2040),
            ],
        ]
        return FsListing(ok: true, path: path, items: tree[path] ?? [
            FileEntry(name: "(demo) no listing", dir: false, size: 0)
        ], err: nil)
    }

    /// A drawn pwnagotchi-style face for the Dash "screen" in demo mode.
    static func faceImage(_ color: UIColor = .white) -> UIImage {
        let size = CGSize(width: 250, height: 122)
        let r = UIGraphicsImageRenderer(size: size)
        return r.image { ctx in
            UIColor.black.setFill()
            ctx.fill(CGRect(origin: .zero, size: size))
            let face = "(◕‿‿◕)"
            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 40, weight: .bold),
                .foregroundColor: color,
            ]
            let s = face.size(withAttributes: attrs)
            face.draw(at: CGPoint(x: (size.width - s.width) / 2, y: (size.height - s.height) / 2 - 8),
                      withAttributes: attrs)
            let st = "DEMO · hunting"
            let a2: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 12), .foregroundColor: UIColor.gray]
            let s2 = st.size(withAttributes: a2)
            st.draw(at: CGPoint(x: (size.width - s2.width) / 2, y: size.height - 22), withAttributes: a2)
        }
    }
}
