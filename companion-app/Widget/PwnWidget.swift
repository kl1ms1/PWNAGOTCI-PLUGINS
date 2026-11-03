import WidgetKit
import SwiftUI

private let appGroup = "group.com.pwncompanion"

struct PwnEntry: TimelineEntry {
    let date: Date
    let name: String
    let mode: String
    let battery: Int
    let shakes: Int
    let nets: Int
    let cracked: Int
    let stale: Bool

    static let sample = PwnEntry(date: Date(), name: "Ki213", mode: "AUTO",
                                 battery: 76, shakes: 1234, nets: 42, cracked: 5, stale: false)
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> PwnEntry { .sample }
    func getSnapshot(in context: Context, completion: @escaping (PwnEntry) -> Void) { completion(read()) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<PwnEntry>) -> Void) {
        let next = Calendar.current.date(byAdding: .minute, value: 15, to: Date()) ?? Date().addingTimeInterval(900)
        completion(Timeline(entries: [read()], policy: .after(next)))
    }
    private func read() -> PwnEntry {
        let d = UserDefaults(suiteName: appGroup)
        let updated = d?.double(forKey: "updated") ?? 0
        let stale = updated == 0 || Date().timeIntervalSince1970 - updated > 1800
        return PwnEntry(date: Date(),
                        name: d?.string(forKey: "name") ?? "pwnagotchi",
                        mode: d?.string(forKey: "mode") ?? "—",
                        battery: d?.integer(forKey: "battery") ?? 0,
                        shakes: d?.integer(forKey: "shakes") ?? 0,
                        nets: d?.integer(forKey: "nets") ?? 0,
                        cracked: d?.integer(forKey: "cracked") ?? 0,
                        stale: stale)
    }
}

struct PwnWidgetView: View {
    @Environment(\.widgetFamily) var family
    let entry: PwnEntry

    var body: some View {
        ZStack {
            Color.black
            if family == .systemSmall { small } else { medium }
        }
        .foregroundStyle(.white)
    }

    private var face: String { entry.stale ? "(-__-)" : (entry.cracked > 0 ? "(⌐■_■)" : "(◕‿‿◕)") }

    private var small: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(face).font(.system(size: 30, weight: .bold))
            Spacer()
            Text(entry.name).font(.caption.weight(.semibold)).lineLimit(1)
            HStack(spacing: 4) {
                Image(systemName: "battery.100").font(.caption2)
                Text("\(entry.battery)%").font(.caption2)
                Spacer()
                Text(entry.stale ? "stale" : entry.mode).font(.caption2).foregroundStyle(.gray)
            }
        }
        .padding(12)
    }

    private var medium: some View {
        HStack(spacing: 14) {
            VStack(spacing: 4) {
                Text(face).font(.system(size: 34, weight: .bold))
                Text(entry.name).font(.caption.weight(.semibold)).lineLimit(1)
            }
            Divider().overlay(Color.white.opacity(0.3))
            VStack(alignment: .leading, spacing: 6) {
                row("hand.wave.fill", "\(entry.shakes)", "shakes")
                row("wifi", "\(entry.nets)", "nets")
                row("key.fill", "\(entry.cracked)", "cracked")
                row("battery.100", "\(entry.battery)%", entry.stale ? "stale" : entry.mode)
            }
            Spacer()
        }
        .padding(14)
    }

    private func row(_ icon: String, _ value: String, _ label: String) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon).font(.caption2).frame(width: 16)
            Text(value).font(.subheadline.weight(.bold))
            Text(label).font(.caption2).foregroundStyle(.gray)
        }
    }
}

struct PwnWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "PwnWidget", provider: Provider()) { entry in
            PwnWidgetView(entry: entry)
        }
        .configurationDisplayName("Pwnagotchi")
        .description("Battery, handshakes and status at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

@main
struct PwnWidgetBundle: WidgetBundle {
    var body: some Widget { PwnWidget() }
}
