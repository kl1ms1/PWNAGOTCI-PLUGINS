import SwiftUI

/// One-tap health checks: runs a battery of shell probes and shows pass/fail.
struct DiagnosticsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var results: [Check] = []
    @State private var running = false

    struct Check: Identifiable {
        let id = UUID()
        let title: String
        var state: State = .pending
        var detail = ""
        enum State { case pending, ok, warn, fail }
    }

    private struct Probe { let title: String; let cmd: String; let pass: (String) -> Bool }

    private let probes: [Probe] = [
        Probe(title: "pwnagotchi service", cmd: "systemctl is-active pwnagotchi 2>/dev/null",
              pass: { $0.contains("active") }),
        Probe(title: "Monitor interface (wlan0mon)", cmd: "iwconfig 2>/dev/null | grep -qi mon && echo OK || echo FAIL",
              pass: { $0.contains("OK") }),
        Probe(title: "Bluetooth pairable", cmd: "bluetoothctl show 2>/dev/null | grep -i pairable",
              pass: { $0.lowercased().contains("yes") }),
        Probe(title: "Disk space (>500MB)", cmd: "df -Pm / | awk 'NR==2{print $4}'",
              pass: { (Int($0.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0) > 500 }),
        Probe(title: "Internet", cmd: "ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 && echo OK || echo FAIL",
              pass: { $0.contains("OK") }),
        Probe(title: "Battery (UPS-Lite i2c)", cmd: "i2cget -y 1 0x36 4 w 2>/dev/null || echo none",
              pass: { !$0.contains("none") }),
        Probe(title: "Recent errors in log", cmd: "tail -n 80 /var/log/pwnagotchi.log 2>/dev/null | grep -ci 'bus is down\\|traceback\\|error' || echo 0",
              pass: { (Int($0.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0) == 0 }),
    ]

    var body: some View {
        ZStack {
            ThemeBG()
            ScrollView {
                VStack(spacing: 10) {
                    ForEach(results) { c in
                        HStack(spacing: 12) {
                            icon(c.state)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(c.title).font(.body.weight(.semibold))
                                if !c.detail.isEmpty {
                                    Text(c.detail).font(.caption2.monospaced()).foregroundStyle(.secondary).lineLimit(2)
                                }
                            }
                            Spacer()
                        }
                        .padding(12)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(.primary.opacity(0.08)))
                    }
                    Button { Task { await run() } } label: {
                        HStack { if running { ProgressView() }; Text(running ? "Running…" : "Run diagnostics").frame(maxWidth: .infinity) }
                    }.buttonStyle(FilledStyle()).disabled(running).padding(.top, 4)
                }.padding()
            }
        }
        .navigationTitle("Diagnostics")
        .navigationBarTitleDisplayMode(.inline)
        .task { if results.isEmpty { await run() } }
    }

    @ViewBuilder private func icon(_ s: Check.State) -> some View {
        switch s {
        case .pending: ProgressView().frame(width: 24)
        case .ok: Image(systemName: "checkmark.circle.fill").foregroundStyle(.green).frame(width: 24)
        case .warn: Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.yellow).frame(width: 24)
        case .fail: Image(systemName: "xmark.circle.fill").foregroundStyle(.red).frame(width: 24)
        }
    }

    private func run() async {
        running = true
        results = probes.map { Check(title: $0.title) }
        for (i, p) in probes.enumerated() {
            let out = await PwnClient.exec(conn, p.cmd)
            let trimmed = out.trimmingCharacters(in: .whitespacesAndNewlines)
            results[i].state = p.pass(out) ? .ok : .fail
            results[i].detail = trimmed.isEmpty ? "(no output)" : String(trimmed.prefix(80))
        }
        running = false
    }
}
