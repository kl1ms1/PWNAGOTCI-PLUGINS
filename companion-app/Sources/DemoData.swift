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

    static func pins() -> [CatchPin] {
        [
            CatchPin(id: "A0:28:5D:A0:C4:C0", ssid: "HomeWiFi", lat: 45.0350, lon: 38.9750, date: 0),
            CatchPin(id: "50:4F:3B:CB:39:FE", ssid: "Xiaomi_67", lat: 45.0398, lon: 38.9820, date: 0),
            CatchPin(id: "11:22:33:44:55:66", ssid: "MGTS_GPON", lat: 45.0421, lon: 38.9688, date: 0),
        ]
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
