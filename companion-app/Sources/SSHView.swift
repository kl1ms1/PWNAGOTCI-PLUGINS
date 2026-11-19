import SwiftUI
import Citadel
import NIOCore

/// Real SSH terminal — connects straight to the device's system sshd (port 22).
/// Works even if the companion plugin / pwnagotchi is down. Needs a network
/// path to the Pi (same Wi-Fi / hotspot). For your own device only.
struct SSHView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var cmd = ""
    @State private var log: [Line] = [Line(.info, "SSH terminal. Connect to run commands on the Pi (system SSH, no plugin needed).")]
    @State private var history: [String] = []
    @State private var client: SSHClient?
    @State private var connected = false
    @State private var busy = false

    struct Line: Identifiable { enum K { case cmd, out, info, err }
        let id = UUID(); let k: K; let t: String
        init(_ k: K, _ t: String) { self.k = k; self.t = t } }

    private let presets = ["uptime", "tail -n 40 /root/pwn-reboots.log",
                           "grep -oE 'up=[0-9]+s' /root/pwn-reboots.log | tail -40",
                           "sudo systemctl restart pwnagotchi", "vcgencmd measure_temp"]

    var body: some View {
        ZStack {
            ThemeBG()
            VStack(spacing: 10) {
                // connection row
                HStack(spacing: 8) {
                    Circle().fill(connected ? Color.green : Color.secondary).frame(width: 9, height: 9)
                    Text(connected ? "\(conn.sshUser)@\(conn.host)" : "not connected")
                        .font(.caption.monospaced()).foregroundStyle(.secondary).lineLimit(1)
                    Spacer()
                    Button(connected ? "Disconnect" : "Connect") {
                        connected ? disconnect() : connectSSH()
                    }.font(.caption.weight(.semibold)).disabled(busy || conn.demo)
                }.padding(.horizontal)

                if connected {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(presets, id: \.self) { p in
                                Button { cmd = p; run(p) } label: {
                                    Text(p.count > 22 ? String(p.prefix(20)) + "…" : p)
                                        .font(.caption2.weight(.semibold))
                                        .padding(.horizontal, 10).padding(.vertical, 6).foregroundStyle(.primary)
                                }.background(.primary.opacity(0.08), in: Capsule()).disabled(busy)
                            }
                        }.padding(.horizontal)
                    }.frame(height: 38)
                }

                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(log) { l in
                                Text(l.prefix + l.t).font(.caption.monospaced())
                                    .foregroundStyle(l.color).textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading).id(l.id)
                            }
                            Color.clear.frame(height: 1).id("B")
                        }.padding(10)
                    }
                    .background(Color.black.opacity(0.9), in: RoundedRectangle(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(.primary.opacity(0.1)))
                    .padding(.horizontal)
                    .onChange(of: log.count) { _ in withAnimation { proxy.scrollTo("B", anchor: .bottom) } }
                }

                HStack(spacing: 8) {
                    TextField("command…", text: $cmd)
                        .font(.callout.monospaced()).autocorrectionDisabled().textInputAutocapitalization(.never)
                        .submitLabel(.send).onSubmit { run(cmd) }
                        .padding(10).background(.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                    Button { run(cmd) } label: {
                        Image(systemName: busy ? "hourglass" : "arrow.up.circle.fill").font(.title2)
                    }.disabled(!connected || busy || cmd.trimmingCharacters(in: .whitespaces).isEmpty)
                }.padding(.horizontal).padding(.bottom, 10)
            }
        }
        .navigationTitle("SSH")
        .navigationBarTitleDisplayMode(.inline)
        .onDisappear { disconnect() }
    }

    private func append(_ k: Line.K, _ t: String) {
        for ln in t.split(separator: "\n", omittingEmptySubsequences: false) {
            log.append(Line(k, String(ln)))
        }
    }

    private func connectSSH() {
        guard !conn.demo else { append(.info, "demo mode — SSH disabled"); return }
        busy = true
        append(.info, "connecting to \(conn.host):\(conn.sshPort) …")
        let host = conn.host, port = Int(conn.sshPort) ?? 22
        let user = conn.sshUser, pass = conn.sshPass
        Task {
            do {
                let c = try await SSHClient.connect(
                    host: host, port: port,
                    authenticationMethod: .passwordBased(username: user, password: pass),
                    hostKeyValidator: .acceptAnything(),
                    reconnect: .never)
                client = c; connected = true
                append(.info, "connected ✓  (\(user)@\(host))")
            } catch {
                append(.err, "connect failed: \(error.localizedDescription)")
            }
            busy = false
        }
    }

    private func disconnect() {
        let c = client; client = nil; connected = false
        Task { try? await c?.close() }
    }

    private func run(_ raw: String) {
        let command = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty, let c = client, !busy else { return }
        busy = true
        append(.cmd, command)
        if history.last != command { history.append(command) }
        cmd = ""
        Task {
            do {
                let buffer = try await c.executeCommand(command)
                var buf = buffer
                let out = buf.readString(length: buf.readableBytes) ?? ""
                append(.out, out.isEmpty ? "(no output)" : out)
            } catch {
                append(.err, "error: \(error.localizedDescription)")
            }
            busy = false
        }
    }
}

private extension SSHView.Line {
    var prefix: String { k == .cmd ? "$ " : "" }
    var color: Color {
        switch k {
        case .cmd: return .white
        case .out: return .green
        case .info: return .gray
        case .err: return .red
        }
    }
}
