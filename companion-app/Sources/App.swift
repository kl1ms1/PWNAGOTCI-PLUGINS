import SwiftUI
import UIKit

@main
struct PwnCompanionApp: App {
    @StateObject private var conn = ConnectionStore()
    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(conn)
                .preferredColorScheme(conn.theme == .system ? nil : .dark)
                .tint(.cyan)
        }
    }
}

enum AppTheme: String, CaseIterable, Identifiable {
    case dark, system
    var id: String { rawValue }
    var label: String { self == .dark ? "Тёмная (Liquid Glass)" : "Как в системе" }
}

/// Connection settings to the pwnagotchi (Bluetooth / Wi-Fi — no cable: iOS has
/// no USB-ethernet). Persisted in UserDefaults.
final class ConnectionStore: ObservableObject {
    @Published var host: String { didSet { save() } }   // Pi IP on the phone's BT-PAN (172.20.10.x)
    @Published var port: String { didSet { save() } }
    @Published var user: String { didSet { save() } }
    @Published var pass: String { didSet { save() } }
    @Published var theme: AppTheme { didSet { save() } }

    init() {
        let d = UserDefaults.standard
        host = d.string(forKey: "host") ?? "172.20.10.6"
        port = d.string(forKey: "port") ?? "8080"
        user = d.string(forKey: "user") ?? "changeme"
        pass = d.string(forKey: "pass") ?? "changeme"
        theme = AppTheme(rawValue: d.string(forKey: "theme") ?? "") ?? .dark
    }

    private func save() {
        let d = UserDefaults.standard
        d.set(host, forKey: "host"); d.set(port, forKey: "port")
        d.set(user, forKey: "user"); d.set(pass, forKey: "pass")
        d.set(theme.rawValue, forKey: "theme")
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
        guard let url = conn.uiImageURL else { throw URLError(.badURL) }
        let (data, resp) = try await URLSession.shared.data(for: request(url, conn))
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let img = UIImage(data: data) else { throw URLError(.cannotParseResponse) }
        return img
    }

    static func fetchStatus(_ conn: ConnectionStore) async throws -> DeviceStatus {
        guard let url = conn.companionURL("status") else { throw URLError(.badURL) }
        let (data, _) = try await URLSession.shared.data(for: request(url, conn))
        return try JSONDecoder().decode(DeviceStatus.self, from: data)
    }

    static func fetchPwndex(_ conn: ConnectionStore) async throws -> [NetItem] {
        guard let url = conn.companionURL("pwndex") else { throw URLError(.badURL) }
        let (data, _) = try await URLSession.shared.data(for: request(url, conn))
        return try JSONDecoder().decode([NetItem].self, from: data)
    }

    @discardableResult
    static func setPassword(_ conn: ConnectionStore, mac: String, pw: String) async throws -> Bool {
        let e = { (s: String) in s.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? s }
        guard let url = conn.companionURL("set", "&mac=\(e(mac))&pw=\(e(pw))") else { throw URLError(.badURL) }
        let (_, resp) = try await URLSession.shared.data(for: request(url, conn))
        return (resp as? HTTPURLResponse).map { (200..<300).contains($0.statusCode) } ?? false
    }

    @discardableResult
    static func control(_ conn: ConnectionStore, cmd: String) async throws -> Bool {
        guard let url = conn.companionURL("control", "&cmd=\(cmd)") else { throw URLError(.badURL) }
        let (_, resp) = try await URLSession.shared.data(for: request(url, conn, timeout: 6))
        return (resp as? HTTPURLResponse).map { (200..<300).contains($0.statusCode) } ?? false
    }
}
