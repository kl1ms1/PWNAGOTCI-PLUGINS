import SwiftUI
import UIKit

@main
struct PwnCompanionApp: App {
    @StateObject private var conn = ConnectionStore()
    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(conn)
        }
    }
}

/// Connection settings to the pwnagotchi web interface, persisted in UserDefaults.
final class ConnectionStore: ObservableObject {
    @Published var host: String { didSet { save("host", host) } }
    @Published var port: String { didSet { save("port", port) } }
    @Published var user: String { didSet { save("user", user) } }
    @Published var pass: String { didSet { save("pass", pass) } }

    init() {
        let d = UserDefaults.standard
        host = d.string(forKey: "host") ?? "10.0.0.2"
        port = d.string(forKey: "port") ?? "8080"
        user = d.string(forKey: "user") ?? "changeme"
        pass = d.string(forKey: "pass") ?? "changeme"
    }

    private func save(_ key: String, _ value: String) {
        UserDefaults.standard.set(value, forKey: key)
    }

    var baseURL: URL? { URL(string: "http://\(host):\(port)") }
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
