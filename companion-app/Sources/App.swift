import SwiftUI
import UIKit

@main
struct PwnCompanionApp: App {
    @StateObject private var conn = ConnectionStore()
    var body: some Scene {
        WindowGroup {
            Group {
                if conn.entered {
                    RootView()
                } else {
                    ConnectView()
                }
            }
            .environmentObject(conn)
            .preferredColorScheme(conn.theme.scheme)
            .fontDesign(conn.font.design)
            .tint(.primary)
        }
    }
}

enum AppTheme: String, CaseIterable, Identifiable {
    case black, white
    var id: String { rawValue }
    var label: String { self == .black ? "Dark" : "Light" }
    var scheme: ColorScheme { self == .black ? .dark : .light }
}

enum FontStyle: String, CaseIterable, Identifiable {
    case system, rounded, serif, mono
    var id: String { rawValue }
    var label: String {
        ["system": "System", "rounded": "Rounded", "serif": "Serif", "mono": "Mono"][rawValue] ?? rawValue
    }
    var design: Font.Design {
        switch self {
        case .system: return .default
        case .rounded: return .rounded
        case .serif: return .serif
        case .mono: return .monospaced
        }
    }
}

enum Skin: String, CaseIterable, Identifiable {
    case black, white, clear
    var id: String { rawValue }
    var label: String { self == .black ? "Black" : self == .white ? "White" : "Clear" }
    var caseColor: Color {
        switch self {
        case .black: return Color(white: 0.14)
        case .white: return Color(white: 0.92)
        case .clear: return Color.white.opacity(0.08)
        }
    }
    var line: Color { self == .white ? .black.opacity(0.25) : .white.opacity(0.2) }
}

/// Filled button whose label always contrasts the fill (fixes white-on-white).
struct FilledStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.semibold))
            .foregroundStyle(Color(.systemBackground))
            .frame(maxWidth: .infinity).padding(.vertical, 12)
            .background(.primary.opacity(configuration.isPressed ? 0.7 : 1),
                        in: Capsule())
    }
}

/// Connection settings to the pwnagotchi (Bluetooth / Wi-Fi — no cable: iOS has
/// no USB-ethernet). Persisted in UserDefaults.
final class ConnectionStore: ObservableObject {
    @Published var host: String { didSet { save() } }   // Pi IP on the phone's BT-PAN (172.20.10.x)
    @Published var port: String { didSet { save() } }
    @Published var user: String { didSet { save() } }
    @Published var pass: String { didSet { save() } }
    @Published var theme: AppTheme { didSet { save() } }
    @Published var skin: Skin { didSet { save() } }
    @Published var faceColor: Color { didSet { save() } }   // any color (Apple picker)
    @Published var font: FontStyle { didSet { save() } }
    @Published var entered = false     // passed the connect screen
    @Published var demo = false        // demo/beta mode (fake data, no device)

    init() {
        let d = UserDefaults.standard
        host = d.string(forKey: "host") ?? "192.168.50.1"
        port = d.string(forKey: "port") ?? "8080"
        user = d.string(forKey: "user") ?? "changeme"
        pass = d.string(forKey: "pass") ?? "changeme"
        theme = AppTheme(rawValue: d.string(forKey: "theme") ?? "") ?? .black
        skin = Skin(rawValue: d.string(forKey: "skin") ?? "") ?? .black
        let fr = d.object(forKey: "faceR") as? Double ?? 1.0
        let fg = d.object(forKey: "faceG") as? Double ?? 1.0
        let fb = d.object(forKey: "faceB") as? Double ?? 1.0
        faceColor = Color(red: fr, green: fg, blue: fb)
        font = FontStyle(rawValue: d.string(forKey: "font") ?? "") ?? .rounded
    }

    var faceUIColor: UIColor { UIColor(faceColor) }

    private func save() {
        let d = UserDefaults.standard
        d.set(host, forKey: "host"); d.set(port, forKey: "port")
        d.set(user, forKey: "user"); d.set(pass, forKey: "pass")
        d.set(theme.rawValue, forKey: "theme")
        d.set(skin.rawValue, forKey: "skin")
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        UIColor(faceColor).getRed(&r, green: &g, blue: &b, alpha: &a)
        d.set(Double(r), forKey: "faceR"); d.set(Double(g), forKey: "faceG"); d.set(Double(b), forKey: "faceB")
        d.set(font.rawValue, forKey: "font")
    }

    var baseURL: URL? { URL(string: "http://\(host):\(port)") }
    var uiImageURL: URL? { baseURL?.appendingPathComponent("ui") }
    func companionURL(_ action: String, _ extra: String = "") -> URL? {
        URL(string: "http://\(host):\(port)/plugins/companion/?action=\(action)\(extra)")
    }
    var authHeader: String? {
        guard let d = "\(user):\(pass)".data(using: .utf8) else { return nil }
        return "Basic " + d.base64EncodedString()
    }
}

// MARK: - API models

struct DeviceStatus: Codable {
    var name: String?
    var mode: String?
    var uptime: Int?
    var temp: Double?
    var cpu: Double?
    var mem: Double?
    var sd_free: Double?
    var pcaps: Int?
    var networks: Int?
    var cracked: Int?
    var shakes: Int?
}

struct NetItem: Codable, Identifiable {
    var ssid: String
    var mac: String
    var pw: String
    var caught: Bool
    var last: Double?
    var pw_at: Double?
    var id: String { mac }
}

// MARK: - Client

enum PwnClient {
    private static func request(_ url: URL, _ conn: ConnectionStore, timeout: TimeInterval = 8) -> URLRequest {
        var req = URLRequest(url: url, timeoutInterval: timeout)
        if let a = conn.authHeader { req.setValue(a, forHTTPHeaderField: "Authorization") }
        return req
    }

    static func fetchUIImage(_ conn: ConnectionStore) async throws -> UIImage {
        if conn.demo { try? await Task.sleep(nanoseconds: 300_000_000); return DemoData.faceImage(conn.faceUIColor) }
        guard let url = conn.uiImageURL else { throw URLError(.badURL) }
        let (data, resp) = try await URLSession.shared.data(for: request(url, conn))
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let img = UIImage(data: data) else { throw URLError(.cannotParseResponse) }
        return img
    }

    static func fetchStatus(_ conn: ConnectionStore) async throws -> DeviceStatus {
        if conn.demo { return DemoData.status() }
        guard let url = conn.companionURL("status") else { throw URLError(.badURL) }
        let (data, _) = try await URLSession.shared.data(for: request(url, conn))
        return try JSONDecoder().decode(DeviceStatus.self, from: data)
    }

    static func fetchPwndex(_ conn: ConnectionStore) async throws -> [NetItem] {
        if conn.demo { return DemoData.pwndex() }
        guard let url = conn.companionURL("pwndex") else { throw URLError(.badURL) }
        let (data, _) = try await URLSession.shared.data(for: request(url, conn))
        return try JSONDecoder().decode([NetItem].self, from: data)
    }

    @discardableResult
    static func setPassword(_ conn: ConnectionStore, mac: String, pw: String) async throws -> Bool {
        if conn.demo { return true }
        let e = { (s: String) in s.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? s }
        guard let url = conn.companionURL("set", "&mac=\(e(mac))&pw=\(e(pw))") else { throw URLError(.badURL) }
        let (_, resp) = try await URLSession.shared.data(for: request(url, conn))
        return (resp as? HTTPURLResponse).map { (200..<300).contains($0.statusCode) } ?? false
    }

    @discardableResult
    static func control(_ conn: ConnectionStore, cmd: String) async throws -> Bool {
        if conn.demo { try? await Task.sleep(nanoseconds: 400_000_000); return true }
        guard let url = conn.companionURL("control", "&cmd=\(cmd)") else { throw URLError(.badURL) }
        let (_, resp) = try await URLSession.shared.data(for: request(url, conn, timeout: 6))
        return (resp as? HTTPURLResponse).map { (200..<300).contains($0.statusCode) } ?? false
    }

    static func fetchPcaps(_ conn: ConnectionStore) async -> [String] {
        if conn.demo {
            return ["HomeWiFi_a0285da0c4c0.pcap", "Xiaomi_67_504f3bcb39fe.pcap",
                    "MGTS_GPON_112233445566.pcap", "CoffeeHouse_778899aabbcc.pcap"]
        }
        guard let url = conn.companionURL("pcaps") else { return [] }
        do {
            let (data, _) = try await URLSession.shared.data(for: request(url, conn))
            return (try? JSONDecoder().decode([String].self, from: data)) ?? []
        } catch { return [] }
    }

    static func pcapData(_ conn: ConnectionStore, _ name: String) async -> Data? {
        if conn.demo { return Data("demo .pcap: \(name)".utf8) }
        let e = name.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? name
        guard let url = conn.companionURL("pcap", "&name=\(e)") else { return nil }
        return try? await URLSession.shared.data(for: request(url, conn, timeout: 30)).0
    }

    /// Real wpa-sec upload trigger (companion action=upload_all). Returns (ok, message).
    static func uploadAll(_ conn: ConnectionStore) async -> (Bool, String) {
        if conn.demo { try? await Task.sleep(nanoseconds: 600_000_000); return (true, "demo: 17 hashes uploaded") }
        guard let url = conn.companionURL("upload_all") else { return (false, "bad url") }
        do {
            let (data, _) = try await URLSession.shared.data(for: request(url, conn, timeout: 25))
            if let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                return ((j["ok"] as? Bool) ?? false, (j["msg"] as? String) ?? "")
            }
            return (false, "bad response")
        } catch {
            return (false, "no connection")
        }
    }
}
