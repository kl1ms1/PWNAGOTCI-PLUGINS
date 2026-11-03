import SwiftUI

/// Real SSH-style terminal on the pwnagotchi (companion action=exec, bash -lc).
/// Scrollback, command history, presets, and free typing. Your own device only.
struct CommandsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var cmd = ""
    @State private var log: [TermLine] = [TermLine(kind: .info, text: "pwnagotchi shell — ready. Pick a preset or type a command.")]
    @State private var history: [String] = []
    @State private var running = false

    struct TermLine: Identifiable { enum Kind { case cmd, out, info }; let id = UUID(); let kind: Kind; let text: String }

    private let presets: [(String, String)] = [
        ("uptime", "uptime"),
        ("temp", "vcgencmd measure_temp 2>/dev/null || awk '{printf \"%.1f°C\\n\",$1/1000}' /sys/class/thermal/thermal_zone0/temp"),
        ("disk", "df -h /"),
        ("mem", "free -h"),
        ("log tail", "tail -n 40 /var/log/pwnagotchi.log 2>/dev/null || journalctl -u pwnagotchi -n 40 --no-pager"),
        ("handshakes", "ls -1 /root/handshakes/*.pcap /home/pi/handshakes/*.pcap 2>/dev/null | wc -l"),
        ("iface", "iwconfig 2>/dev/null | grep -A1 wlan || ip -br link"),
        ("battery", "i2cget -y 1 0x36 4 w 2>/dev/null || echo 'no i2c'"),
        ("bluetooth", "bluetoothctl show 2>/dev/null | grep -E 'Powered|Discoverable|Pairable' || hciconfig"),
        ("plugins", "grep -E 'main.plugins..*.enabled' /etc/pwnagotchi/config.toml 2>/dev/null"),
        ("pwnkill", "sudo systemctl restart pwnagotchi"),
        ("reboot", "sudo reboot"),
    ]

    var body: some View {
        ZStack {
            ThemeBG()
            VStack(spacing: 10) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(presets, id: \.0) { title, c in
                            Button { cmd = c; send(c) } label: {
                                Text(title).font(.caption.weight(.semibold))
                                    .padding(.horizontal, 12).padding(.vertical, 7).foregroundStyle(.primary)
                            }
                            .background(.primary.opacity(0.08), in: Capsule())
                            .disabled(running)
                        }
                    }.padding(.horizontal)
                }
                .frame(height: 40)

                // terminal scrollback
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(log) { line in
                                Text(line.prefix + line.text)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(line.color)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .textSelection(.enabled).id(line.id)
                            }
                            Color.clear.frame(height: 1).id("BOTTOM")
                        }.padding(10)
                    }
                    .background(Color.black.opacity(0.9), in: RoundedRectangle(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(.primary.opacity(0.1)))
                    .padding(.horizontal)
                    .onChange(of: log.count) { _ in withAnimation { proxy.scrollTo("BOTTOM", anchor: .bottom) } }
                }

                HStack(spacing: 8) {
                    if !history.isEmpty {
                        Menu {
                            ForEach(Array(history.enumerated().reversed()), id: \.offset) { _, h in
                                Button(h) { cmd = h }
                            }
                        } label: { Image(systemName: "clock.arrow.circlepath").font(.title3) }
                    }
                    TextField("command…", text: $cmd)
                        .font(.callout.monospaced())
                        .autocorrectionDisabled().textInputAutocapitalization(.never)
                        .submitLabel(.send).onSubmit { send(cmd) }
                        .padding(10).background(.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                    Button { send(cmd) } label: {
                        Image(systemName: running ? "hourglass" : "arrow.up.circle.fill").font(.title2)
                    }.disabled(running || cmd.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding(.horizontal).padding(.bottom, 10)
            }
        }
        .navigationTitle("Commands")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { log = [TermLine(kind: .info, text: "cleared.")] } label: { Image(systemName: "trash") }
            }
        }
    }

    private func send(_ c: String) {
        let c = c.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !c.isEmpty, !running else { return }
        running = true
        log.append(TermLine(kind: .cmd, text: c))
        if history.last != c { history.append(c); if history.count > 40 { history.removeFirst() } }
        cmd = ""
        Task {
            let out = await PwnClient.exec(conn, c)
            for ln in (out.isEmpty ? "(no output)" : out).split(separator: "\n", omittingEmptySubsequences: false) {
                log.append(TermLine(kind: .out, text: String(ln)))
            }
            running = false
        }
    }
}

private extension CommandsView.TermLine {
    var prefix: String { kind == .cmd ? "$ " : "" }
    var color: Color {
        switch kind {
        case .cmd: return .white
        case .out: return .green
        case .info: return .gray
        }
    }
}
