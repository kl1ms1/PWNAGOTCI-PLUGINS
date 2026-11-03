import SwiftUI

/// Kept for demo data compatibility elsewhere.
struct AppEvent: Identifiable {
    let id = UUID()
    let time: String
    let icon: String
    let text: String
}

/// Live event log tailed from the device (companion action=events), auto-refresh.
struct EventsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var events: [LogEvent] = []
    @State private var loaded = false
    @State private var live = true
    @State private var query = ""
    @State private var filter = "all"

    private let kinds = ["all", "handshake", "deauth", "assoc", "upload", "ai", "peer", "error"]

    private var shown: [LogEvent] {
        events.filter { e in
            (filter == "all" || e.kind == filter) &&
            (query.isEmpty || e.text.lowercased().contains(query.lowercased()))
        }
    }

    var body: some View {
        ZStack {
            ThemeBG()
            List {
                Section {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(kinds, id: \.self) { k in
                                Button { filter = k } label: {
                                    Text(k).font(.caption2.weight(.semibold))
                                        .padding(.horizontal, 10).padding(.vertical, 5)
                                        .foregroundStyle(filter == k ? Color(.systemBackground) : .primary)
                                        .background(filter == k ? AnyShapeStyle(.primary) : AnyShapeStyle(.primary.opacity(0.08)),
                                                    in: Capsule())
                                }.buttonStyle(.plain)
                            }
                        }
                    }
                    .listRowInsets(EdgeInsets(top: 4, leading: 8, bottom: 4, trailing: 8))
                    .listRowBackground(Color.clear)
                }
                ForEach(shown) { e in
                    HStack(spacing: 12) {
                        Image(systemName: e.icon)
                            .font(.system(size: 15))
                            .foregroundStyle(e.kind == "error" ? Color.red : .primary)
                            .frame(width: 26)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(e.text).font(.caption.monospaced()).lineLimit(3)
                            if !e.time.isEmpty { Text(e.time).font(.caption2).foregroundStyle(.secondary) }
                        }
                    }
                    .listRowBackground(Color.primary.opacity(0.05))
                }
                if shown.isEmpty {
                    Text(loaded ? "No matching events (needs plugin 1.6.0)" : "Loading…")
                        .foregroundStyle(.secondary).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .searchable(text: $query, prompt: "Search log")
            .refreshable { await load() }
        }
        .navigationTitle("Events · \(shown.count)")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { live.toggle() } label: {
                    Image(systemName: live ? "pause.circle" : "play.circle")
                }
            }
        }
        .task { await loop() }
    }

    private func loop() async {
        while !Task.isCancelled {
            if live { await load() }
            try? await Task.sleep(nanoseconds: 3_000_000_000)
        }
    }

    private func load() async {
        events = await PwnClient.fetchEvents(conn)
        loaded = true
    }
}
