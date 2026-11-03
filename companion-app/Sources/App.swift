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
            .tint(.primary)
        }
    }
}

enum AppTheme: String, CaseIterable, Identifiable {
    case black, white
    var id: String { rawValue }
    var label: String { self == .black ? "Чёрная" : "Белая" }
    var scheme: ColorScheme { self == .black ? .dark : .light }
}

enum Skin: String, CaseIterable, Identifiable {
    case black, white, clear
    var id: String { rawValue }
    var label: String { self == .black ? "Чёрный" : self == .white ? "Белый" : "Прозрачный" }
    var caseColor: Color {
        switch self {
        case .black: return Color(white: 0.14)
        case .white: return Color(white: 0.92)
        case .clear: return Color.white.opacity(0.08)
        }
    }
    var line: Color { self == .white ? .black.opacity(0.25) : .white.opacity(0.2) }
}

enum FaceColor: String, CaseIterable, Identifiable {
    case white, green, amber, blue
    var id: String { rawValue }
    var label: String { ["white": "Белый", "green": "Зелёный", "amber": "Янтарь", "blue": "Синий"][rawValue] ?? rawValue }
    var color: Color {
        switch self {
        case .white: return .white
        case .green: return Color(red: 0.55, green: 1.0, blue: 0.6)
        case .amber: return Color(red: 1.0, green: 0.78, blue: 0.35)
        case .blue: return Color(red: 0.55, green: 0.8, blue: 1.0)
        }
    }
    var uiColor: UIColor { UIColor(color) }
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
    @Published var faceColor: FaceColor { didSet { save() } }
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
        faceColor = FaceColor(rawValue: d.string(forKey: "faceColor") ?? "") ?? .white
    }

    private func save() {
        let d = UserDefaults.standard
        d.set(host, forKey: "host"); d.set(port, forKey: "port")
        d.set(user, forKey: "user"); d.set(pass, forKey: "pass")
        d.set(theme.rawValue, forKey: "theme")
        d.set(skin.rawValue, forKey: "skin")
        d.set(faceColor.rawValue, forKey: "faceColor")
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
        if conn.demo { try? await Task.sleep(nanoseconds: 300_000_000); return DemoData.faceImage(conn.faceColor.uiColor) }
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
}
