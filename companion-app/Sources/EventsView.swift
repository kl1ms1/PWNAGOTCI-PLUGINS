import SwiftUI

struct AppEvent: Identifiable {
    let id = UUID()
    let time: String
    let icon: String
    let text: String
}

struct EventsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var events: [AppEvent] = []

    var body: some View {
        ZStack {
            ThemeBG()
            List {
                ForEach(events) { e in
                    HStack(spacing: 12) {
                        Image(systemName: e.icon)
                            .font(.system(size: 15)).foregroundStyle(.primary)
                            .frame(width: 26)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(e.text).font(.callout)
                            Text(e.time).font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                    .listRowBackground(Color.primary.opacity(0.05))
                }
                if events.isEmpty {
                    Text(conn.demo ? "" : "Лог появится, когда заведём BLE-поток событий")
                        .foregroundStyle(.secondary).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("События")
        .navigationBarTitleDisplayMode(.inline)
        .task { if conn.demo { events = DemoData.events() } }
    }
}
