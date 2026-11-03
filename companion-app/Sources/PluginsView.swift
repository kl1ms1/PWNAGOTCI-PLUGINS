import SwiftUI

/// Lists pwnagotchi plugins (companion action=plugins). Toggle enable/disable
/// (writes config.toml, applies after a restart) and open each plugin's page.
struct PluginsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var items: [PluginItem] = []
    @State private var loaded = false
    @State private var webURL: URL?
    @State private var toast = ""
    @State private var dirty = false

    var body: some View {
        ZStack {
            ThemeBG()
            VStack(spacing: 0) {
                if !toast.isEmpty {
                    Text(toast).font(.caption).foregroundStyle(.secondary).padding(.vertical, 6)
                }
                List {
                    ForEach($items) { $p in
                        HStack(spacing: 12) {
                            Image(systemName: p.enabled ? "puzzlepiece.extension.fill" : "puzzlepiece.extension")
                                .foregroundStyle(p.enabled ? .primary : .secondary).frame(width: 24)
                            Button { open(p) } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(p.name).font(.body.weight(.semibold)).foregroundStyle(.primary)
                                    Text(p.enabled ? "tap to open page" : "disabled")
                                        .font(.caption2).foregroundStyle(.secondary)
                                }
                            }
                            .buttonStyle(.plain).disabled(!p.enabled || conn.demo)
                            Spacer()
                            Toggle("", isOn: $p.enabled)
                                .labelsHidden()
                                .onChange(of: p.enabled) { on in setPlugin(p.name, on) }
                        }
                        .listRowBackground(Color.primary.opacity(0.05))
                    }
                    if items.isEmpty {
                        Text(loaded ? "No plugins" : "Loading…")
                            .foregroundStyle(.secondary).listRowBackground(Color.clear)
                    }
                    if dirty {
                        Button {
                            Task { _ = try? await PwnClient.control(conn, cmd: "restart"); toast = "Restarting pwnagotchi…" }
                        } label: {
                            Label("Restart to apply changes", systemImage: "arrow.clockwise.circle.fill")
                        }
                        .listRowBackground(Color.primary.opacity(0.08))
                    }
                }
                .scrollContentBackground(.hidden)
                .refreshable { await load() }
            }
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
        guard !conn.demo, p.enabled else { return }
        webURL = URL(string: "http://\(conn.host):\(conn.port)\(p.path)")
    }

    private func setPlugin(_ name: String, _ on: Bool) {
        Task {
            let (ok, msg) = await PwnClient.pluginSet(conn, name, on)
            toast = ok ? "\(name) → \(on ? "on" : "off") (\(msg))" : "Failed: \(msg)"
            if ok { dirty = true }
        }
    }
}
