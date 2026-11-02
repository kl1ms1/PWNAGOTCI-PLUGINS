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

enum Transport: String, CaseIterable, Identifiable {
    case cable, bluetooth
    var id: String { rawValue }
    var label: String { self == .cable ? "Кабель (USB)" : "Bluetooth" }
    var systemImage: String { self == .cable ? "cable.connector" : "dot.radiowaves.left.and.right" }
}

enum AppTheme: String, CaseIterable, Identifiable {
    case dark, system
    var id: String { rawValue }
    var label: String { self == .dark ? "Тёмная (Liquid Glass)" : "Как в системе" }
}

/// Connection settings to the pwnagotchi web interface, persisted in UserDefaults.
final class ConnectionStore: ObservableObject {
    @Published var transport: Transport { didSet { save() } }
    @Published var cableHost: String { didSet { save() } }   // USB gadget IP
    @Published var btHost: String { didSet { save() } }       // Pi IP on the phone's BT-PAN
    @Published var port: String { didSet { save() } }
    @Published var user: String { didSet { save() } }
    @Published var pass: String { didSet { save() } }
    @Published var theme: AppTheme { didSet { save() } }

    init() {
        let d = UserDefaults.standard
        transport = Transport(rawValue: d.string(forKey: "transport") ?? "") ?? .cable
        cableHost = d.string(forKey: "cableHost") ?? "10.0.0.2"
        btHost = d.string(forKey: "btHost") ?? "172.20.10.6"
        port = d.string(forKey: "port") ?? "8080"
        user = d.string(forKey: "user") ?? "changeme"
        pass = d.string(forKey: "pass") ?? "changeme"
        theme = AppTheme(rawValue: d.string(forKey: "theme") ?? "") ?? .dark
    }

    private func save() {
        let d = UserDefaults.standard
        d.set(transport.rawValue, forKey: "transport")
        d.set(cableHost, forKey: "cableHost")
        d.set(btHost, forKey: "btHost")
        d.set(port, forKey: "port")
        d.set(user, forKey: "user")
        d.set(pass, forKey: "pass")
        d.set(theme.rawValue, forKey: "theme")
    }

    var activeHost: String { transport == .cable ? cableHost : btHost }
    var baseURL: URL? { URL(string: "http://\(activeHost):\(port)") }
    var uiImageURL: URL? { baseURL?.appendingPathComponent("ui") }
    var authHeader: String? {
        guard let d = "\(user):\(pass)".data(using: .utf8) else { return nil }
        return "Basic " + d.base64EncodedString()
    }
}

/// Minimal client — Milestone 1 just fetches the live e-ink image from /ui.
enum PwnClient {
    static func fetchUIImage(_ conn: ConnectionStore) async throws -> UIImage {
        guard let url = conn.uiImageURL else { throw URLError(.badURL) }
        var req = URLRequest(url: url, timeoutInterval: 8)
        if let a = conn.authHeader { req.setValue(a, forHTTPHeaderField: "Authorization") }
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let img = UIImage(data: data) else { throw URLError(.cannotParseResponse) }
        return img
    }
}
