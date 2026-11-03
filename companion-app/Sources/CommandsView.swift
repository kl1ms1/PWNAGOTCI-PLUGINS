import SwiftUI

/// Run shell commands on the pwnagotchi (companion action=exec, bash -lc).
/// Preset buttons + a free text field. For your own device only.
struct CommandsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var cmd = ""
    @State private var output = "Ready. Pick a preset or type a command."
    @State private var running = false

    private let presets: [(String, String)] = [
        ("Uptime / load", "uptime"),
        ("Temperature", "vcgencmd measure_temp 2>/dev/null || cat /sys/class/thermal/thermal_zone0/temp"),
        ("Disk free", "df -h /"),
        ("Memory", "free -h"),
        ("Pwnagotchi log (tail)", "tail -n 40 /var/log/pwnagotchi.log 2>/dev/null || journalctl -u pwnagotchi -n 40 --no-pager"),
        ("Handshake count", "ls -1 /root/handshakes/*.pcap 2>/dev/null | wc -l"),
        ("wlan0mon status", "iwconfig 2>/dev/null | grep -A1 wlan0 || ip link"),
        ("Battery (UPS-Lite)", "i2cget -y 1 0x36 4 w 2>/dev/null || echo 'no i2c'"),
        ("Bluetooth status", "bluetoothctl show 2>/dev/null | grep -E 'Powered|Discoverable|Pairable' || hciconfig"),
        ("Restart pwnagotchi", "sudo systemctl restart pwnagotchi"),
    ]

    var body: some View {
        ZStack {
            ThemeBG()
            VStack(spacing: 12) {
                ScrollView {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 8) {
                        ForEach(presets, id: \.0) { title, c in
                            Button { cmd = c; send(c) } label: {
                                Text(title).font(.caption.weight(.semibold))
                                    .frame(maxWidth: .infinity, minHeight: 40)
                                    .foregroundStyle(.primary)
                            }
                            .background(.primary.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                            .disabled(running)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top, 4)
                }
                .frame(maxHeight: 230)

                HStack(spacing: 8) {
                    TextField("command…", text: $cmd)
                        .font(.callout.monospaced())
                        .autocorrectionDisabled().textInputAutocapitalization(.never)
                        .padding(10)
                        .background(.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                    Button { send(cmd) } label: {
                        Image(systemName: running ? "hourglass" : "arrow.up.circle.fill").font(.title2)
                    }.disabled(running || cmd.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding(.horizontal)

                ScrollView {
                    Text(output).font(.caption.monospaced()).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(10)
                }
                .background(Color.black.opacity(0.85), in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(.primary.opacity(0.1)))
                .foregroundStyle(Color.green)
                .padding(.horizontal).padding(.bottom)
            }
        }
        .navigationTitle("Commands")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func send(_ c: String) {
        let c = c.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !c.isEmpty else { return }
        running = true
        output = "$ \(c)\n…"
        Task {
            let out = await PwnClient.exec(conn, c)
            output = "$ \(c)\n" + (out.isEmpty ? "(no output)" : out)
            running = false
        }
    }
}
