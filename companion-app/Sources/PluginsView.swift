import SwiftUI

/// Lists the pwnagotchi plugins (companion action=plugins). Tap an enabled one
/// to open its web page inside the app.
struct PluginsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var items: [PluginItem] = []
    @State private var loaded = false
    @State private var webURL: URL?

    var body: some View {
        ZStack {
            ThemeBG()
            List {
                ForEach(items) { p in
                    Button { open(p) } label: {
                        HStack {
                            Image(systemName: p.enabled ? "puzzlepiece.extension.fill" : "puzzlepiece.extension")
                                .foregroundStyle(p.enabled ? .primary : .secondary)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(p.name).font(.body.weight(.semibold))
                                Text(p.enabled ? "enabled" : "disabled")
                                    .font(.caption2).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if p.enabled {
                                Image(systemName: "globe").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                    .disabled(!p.enabled)
                    .listRowBackground(Color.primary.opacity(0.05))
                }
                if items.isEmpty {
                    Text(loaded ? "No plugins" : "Loading…")
                        .foregroundStyle(.secondary).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .refreshable { await load() }
        }
        .navigationTitle("Plugins · \(items.count)")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $webURL) { url in
            WebUISheet(url: url, user: conn.user, pass: conn.pass)
        }
        .task { if !loaded { await load() } }
    }

    private func load() async {
        items = await PwnClient.fetchPlugins(conn)
        loaded = true
    }

    private func open(_ p: PluginItem) {
        guard !conn.demo else { return }
        webURL = URL(string: "http://\(conn.host):\(conn.port)\(p.path)")
    }
}
