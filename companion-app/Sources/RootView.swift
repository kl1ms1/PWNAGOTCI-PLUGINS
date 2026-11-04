import SwiftUI
import UIKit

// MARK: - Strict black/white building blocks

struct ThemeBG: View {
    var body: some View { Color(.systemBackground).ignoresSafeArea() }
}

struct GlassCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
                .strokeBorder(.primary.opacity(0.10), lineWidth: 1))
    }
}

struct StatTile: View {
    let label: String
    let value: String
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value).font(.system(size: 22, weight: .bold, design: .rounded)).foregroundStyle(.primary)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(.primary.opacity(0.08), lineWidth: 1))
    }
}

struct FunctionRow: View {
    let icon: String
    let title: String
    let subtitle: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.system(size: 18, weight: .semibold)).foregroundStyle(.primary)
                    .frame(width: 38, height: 38)
                    .background(.primary.opacity(0.10), in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.body.weight(.semibold)).foregroundStyle(.primary)
                    Text(subtitle).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
            }
            .padding(.vertical, 10).padding(.horizontal, 14)
        }
        .buttonStyle(.plain)
    }
}

/// Like FunctionRow but pushes a destination (used by the Control hub).
struct NavRow<Destination: View>: View {
    let icon: String
    let title: String
    let subtitle: String
    @ViewBuilder let destination: () -> Destination
    var body: some View {
        NavigationLink {
            destination()
        } label: {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.system(size: 18, weight: .semibold)).foregroundStyle(.primary)
                    .frame(width: 38, height: 38)
                    .background(.primary.opacity(0.10), in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.body.weight(.semibold)).foregroundStyle(.primary)
                    Text(subtitle).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
            }
            .padding(.vertical, 10).padding(.horizontal, 14)
        }
        .buttonStyle(.plain)
    }
}

/// Tiny line chart for a rolling metric history.
struct Sparkline: View {
    let values: [Double]
    let label: String
    let current: String
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label).font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Text(current).font(.caption.weight(.semibold))
            }
            GeometryReader { geo in
                Path { p in
                    guard values.count > 1 else { return }
                    let maxV = values.max() ?? 1, minV = values.min() ?? 0
                    let range = Swift.max(maxV - minV, 0.001)
                    let stepX = geo.size.width / CGFloat(values.count - 1)
                    for (i, v) in values.enumerated() {
                        let x = CGFloat(i) * stepX
                        let y = geo.size.height * (1 - CGFloat((v - minV) / range))
                        if i == 0 { p.move(to: CGPoint(x: x, y: y)) }
                        else { p.addLine(to: CGPoint(x: x, y: y)) }
                    }
                }.stroke(Color.primary, style: StrokeStyle(lineWidth: 1.5, lineJoin: .round))
            }.frame(height: 30)
        }
        .frame(maxWidth: .infinity)
        .padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(.primary.opacity(0.08), lineWidth: 1))
    }
}

func uptimeStr(_ s: Int?) -> String {
    let s = s ?? 0
    let d = s / 86400, h = (s % 86400) / 3600, m = (s % 3600) / 60
    if d > 0 { return "\(d)d \(h)h" }
    if h > 0 { return "\(h)h \(m)m" }
    return "\(m)m"
}

func batteryIcon(_ pct: Double) -> String {
    switch pct {
    case ..<12: return "battery.0"
    case ..<30: return "battery.25"
    case ..<60: return "battery.50"
    case ..<85: return "battery.75"
    default: return "battery.100"
    }
}

// MARK: - Root

struct RootView: View {
    var body: some View {
        TabView {
            DashView().tabItem { Label("Dash", systemImage: "chart.bar") }
            PwndexView().tabItem { Label("Pwndex", systemImage: "list.star") }
            MapView().tabItem { Label("Map", systemImage: "map") }
            ControlView().tabItem { Label("Control", systemImage: "slider.horizontal.3") }
            SettingsView().tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}

// MARK: - Dash

struct DashView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var image: UIImage?
    @State private var st = DeviceStatus()
    @State private var status = "Connecting…"
    @State private var online = false
    @State private var showWeb = false
    @State private var lastShakes: Int?
    @State private var cpuHist: [Double] = []
    @State private var tempHist: [Double] = []
    @State private var memHist: [Double] = []

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                ScrollView {
                    VStack(spacing: 14) {
                        // LIVE pwnagotchi face — at the very top
                        GlassCard {
                            VStack(spacing: 8) {
                                ZStack {
                                    RoundedRectangle(cornerRadius: 12).fill(Color.black)
                                    if let img = image {
                                        Image(uiImage: img).resizable().interpolation(.none)
                                            .aspectRatio(contentMode: .fit).padding(6)
                                    } else {
                                        Text(status).foregroundStyle(.gray)
                                    }
                                }
                                .frame(height: 150)
                                HStack(spacing: 7) {
                                    Circle().fill(online ? Color.primary : Color.secondary).frame(width: 8, height: 8)
                                    Text(st.name ?? "pwnagotchi").font(.subheadline.weight(.semibold))
                                    Text("· \((st.mode ?? "—").uppercased()) · \(uptimeStr(st.uptime))")
                                        .font(.caption).foregroundStyle(.secondary)
                                    Spacer()
                                    if let b = st.battery {
                                        Image(systemName: batteryIcon(b)).font(.caption)
                                        Text("\(Int(b))%").font(.caption.weight(.semibold))
                                    }
                                }
                            }
                        }

                        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 4), spacing: 10) {
                            StatTile(label: "shakes", value: "\(st.shakes ?? 0)")
                            StatTile(label: "nets", value: "\(st.networks ?? 0)")
                            StatTile(label: "cracked", value: "\(st.cracked ?? 0)")
                            StatTile(label: ".pcap", value: "\(st.pcaps ?? 0)")
                            StatTile(label: "temp", value: st.temp.map { String(format: "%.0f°", $0) } ?? "—")
                            StatTile(label: "CPU", value: st.cpu.map { String(format: "%.0f%%", $0) } ?? "—")
                            StatTile(label: "RAM", value: st.mem.map { String(format: "%.0f%%", $0) } ?? "—")
                            StatTile(label: "SD GB", value: st.sd_free.map { String(format: "%.0f", $0) } ?? "—")
                            StatTile(label: "battery", value: st.battery.map { "\(Int($0))%" } ?? "—")
                        }

                        if cpuHist.count > 1 {
                            HStack(spacing: 10) {
                                Sparkline(values: cpuHist, label: "CPU %",
                                          current: st.cpu.map { String(format: "%.0f", $0) } ?? "—")
                                Sparkline(values: tempHist, label: "Temp °",
                                          current: st.temp.map { String(format: "%.0f", $0) } ?? "—")
                                Sparkline(values: memHist, label: "RAM %",
                                          current: st.mem.map { String(format: "%.0f", $0) } ?? "—")
                            }
                        }

                        HStack(spacing: 10) {
                            Button { Task { await refresh() } } label: {
                                Label("Refresh", systemImage: "arrow.clockwise")
                            }.buttonStyle(FilledStyle())
                            Button { showWeb = true } label: {
                                Label("Web UI", systemImage: "globe").frame(maxWidth: .infinity)
                            }.buttonStyle(.bordered).disabled(conn.baseURL == nil || conn.demo)
                        }

                        NavigationLink { EventsView() } label: {
                            Label("Recent activity", systemImage: "list.bullet.rectangle")
                                .frame(maxWidth: .infinity)
                        }.buttonStyle(.bordered)

                        Text("All tools are on the Control tab")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                    .padding()
                }
            }
            .navigationTitle("Dash")
            .sheet(isPresented: $showWeb) {
                if let url = conn.baseURL { WebUISheet(url: url, user: conn.user, pass: conn.pass) }
            }
        }
        .task { if conn.notify { Notify.requestAuth() }; await loop() }
    }

    private func loop() async {
        while !Task.isCancelled {
            await refresh()
            try? await Task.sleep(nanoseconds: 2_500_000_000)
        }
    }

    private func refresh() async {
        do {
            image = try await PwnClient.fetchUIImage(conn)
            online = true; status = "Online"
        } catch {
            online = false; status = "No link"
        }
        if let s = try? await PwnClient.fetchStatus(conn) {
            st = s
            if conn.notify, let now = s.shakes, let prev = lastShakes, now > prev {
                Notify.fire("New handshake", "\(now - prev) new on \(s.name ?? "pwnagotchi") · \(now) total")
            }
            lastShakes = s.shakes
            if let c = s.cpu { cpuHist.append(c); if cpuHist.count > 30 { cpuHist.removeFirst() } }
            if let t = s.temp { tempHist.append(t); if tempHist.count > 30 { tempHist.removeFirst() } }
            if let m = s.mem { memHist.append(m); if memHist.count > 30 { memHist.removeFirst() } }
        }
    }
}

// MARK: - Pwndex

struct PwndexView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var items: [NetItem] = []
    @State private var loaded = false
    @State private var editing: NetItem?
    @State private var query = ""
    @State private var filter = "all"   // all | cracked | open

    private var filtered: [NetItem] {
        items.filter { n in
            switch filter {
            case "cracked": if n.pw.isEmpty { return false }
            case "open": if !n.pw.isEmpty { return false }
            default: break
            }
            guard !query.isEmpty else { return true }
            let q = query.lowercased()
            return n.ssid.lowercased().contains(q) || n.mac.lowercased().contains(q)
                || n.pw.lowercased().contains(q)
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                List {
                    Picker("", selection: $filter) {
                        Text("All").tag("all")
                        Text("Cracked").tag("cracked")
                        Text("Open").tag("open")
                    }
                    .pickerStyle(.segmented)
                    .listRowBackground(Color.clear)
                    ForEach(filtered) { it in
                        Button { editing = it } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(it.ssid).font(.body.weight(.semibold))
                                    Text(it.mac).font(.caption2).foregroundStyle(.secondary)
                                }
                                Spacer()
                                if it.pw.isEmpty {
                                    Text("no password").font(.caption).foregroundStyle(.secondary)
                                } else {
                                    Text(it.pw).font(.callout.monospaced()).foregroundStyle(.primary)
                                }
                                Image(systemName: "pencil").font(.caption2).foregroundStyle(.tertiary)
                            }
                        }
                        .listRowBackground(Color.primary.opacity(0.05))
                    }
                    if filtered.isEmpty {
                        Text(loaded ? "Nothing found" : "Loading…")
                            .foregroundStyle(.secondary).listRowBackground(Color.clear)
                    }
                }
                .scrollContentBackground(.hidden)
                .searchable(text: $query, prompt: "Search networks")
                .refreshable { await load() }
            }
            .navigationTitle("Pwndex")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { await load() } } label: { Image(systemName: "arrow.clockwise") }
                }
            }
            .sheet(item: $editing) { it in
                EditPwSheet(item: it) { newPw in
                    Task { _ = try? await PwnClient.setPassword(conn, mac: it.mac, pw: newPw); await load() }
                }
            }
        }
        .task { if !loaded { await load() } }
    }

    private func load() async {
        if let list = try? await PwnClient.fetchPwndex(conn) { items = list }
        loaded = true
    }
}

struct EditPwSheet: View {
    @EnvironmentObject var conn: ConnectionStore
    let item: NetItem
    let onSave: (String) -> Void
    @State private var pw: String
    @State private var msg = ""
    @State private var busy = false
    @State private var shareURL: URL?
    @Environment(\.dismiss) private var dismiss
    init(item: NetItem, onSave: @escaping (String) -> Void) {
        self.item = item; self.onSave = onSave; _pw = State(initialValue: item.pw)
    }
    var body: some View {
        NavigationStack {
            Form {
                Section("Network") {
                    Text(item.ssid).font(.headline)
                    Text(item.mac).font(.caption).foregroundStyle(.secondary)
                }
                Section("Password (if your network)") {
                    TextField("password", text: $pw).autocorrectionDisabled().textInputAutocapitalization(.never)
                    Button { onSave(pw); msg = "Password saved" } label: {
                        Label("Save password", systemImage: "key.fill")
                    }
                }
                Section("Actions") {
                    Button { downloadHash() } label: { Label("Download hash (.pcap)", systemImage: "arrow.down.doc") }
                    Button { setWhitelist(true) } label: { Label("Add to whitelist", systemImage: "checkmark.shield") }
                    Button { setWhitelist(false) } label: { Label("Remove from whitelist", systemImage: "shield.slash") }
                    Button { uploadOne() } label: { Label("Upload to wpa-sec", systemImage: "arrow.up.circle") }
                }
                if busy { Section { HStack { ProgressView(); Text("Working…").foregroundStyle(.secondary) } } }
                if !msg.isEmpty {
                    Section { Text(msg + (conn.demo ? " (demo)" : "")).foregroundStyle(.secondary) }
                }
            }
            .navigationTitle(item.ssid).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
            .sheet(item: $shareURL) { url in ActivityView(items: [url]) }
        }
    }

    private func downloadHash() {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            if conn.demo {
                let url = FileManager.default.temporaryDirectory
                    .appendingPathComponent("\(item.ssid)_\(item.mac.replacingOccurrences(of: ":", with: "")).pcap")
                try? Data("demo handshake".utf8).write(to: url)
                shareURL = url; return
            }
            guard let (name, data) = await PwnClient.pcapForMac(conn, item.mac) else {
                msg = "❌ No .pcap found for this network yet"; return
            }
            let url = FileManager.default.temporaryDirectory.appendingPathComponent(name)
            try? data.write(to: url)
            shareURL = url
        }
    }

    private func setWhitelist(_ add: Bool) {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            let (ok, m, list) = await PwnClient.whitelistSet(conn, ssid: item.ssid, add: add)
            msg = (ok ? "✅ " : "❌ ") + (m.isEmpty ? "done" : m) + (ok ? "\nWhitelist: \(list.joined(separator: ", "))" : "")
        }
    }

    private func uploadOne() {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            let (ok, m) = await PwnClient.uploadAll(conn)
            msg = (ok ? "✅ " : "❌ ") + (m.isEmpty ? "triggered wpa-sec upload" : m)
        }
    }
}

// MARK: - Control

struct ControlView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var toast = ""
    @State private var confirm: (title: String, cmd: String)?
    @State private var exportText = ""
    @State private var showExport = false
    @State private var st = DeviceStatus()
    @State private var online = false
    @State private var shareURL: URL?

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                ScrollView {
                    VStack(spacing: 16) {
                        GlassCard {
                            HStack(spacing: 12) {
                                Image(systemName: "cpu").font(.title2).foregroundStyle(.primary)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(st.name ?? "pwnagotchi").font(.headline)
                                    HStack(spacing: 6) {
                                        Circle().fill(online ? Color.primary : Color.secondary).frame(width: 7, height: 7)
                                        Text(online ? (st.mode ?? "—").uppercased() : "offline")
                                            .font(.caption).foregroundStyle(.secondary)
                                        if st.uptime != nil {
                                            Text("· \(uptimeStr(st.uptime))").font(.caption).foregroundStyle(.secondary)
                                        }
                                    }
                                }
                                Spacer()
                                if let b = st.battery {
                                    HStack(spacing: 4) {
                                        Image(systemName: batteryIcon(b))
                                        Text("\(Int(b))%").font(.subheadline.weight(.semibold))
                                    }
                                }
                            }
                        }
                        if !toast.isEmpty {
                            GlassCard { Text(toast).font(.footnote).foregroundStyle(.secondary) }
                        }
                        section("Screens") {
                            NavRow(icon: "terminal", title: "Commands (SSH)", subtitle: "Run shell commands") { CommandsView() }
                            div
                            NavRow(icon: "puzzlepiece.extension", title: "Plugins", subtitle: "Enable/disable, open pages") { PluginsView() }
                            div
                            NavRow(icon: "folder", title: "Files", subtitle: "Browse / edit the filesystem") { FilesView() }
                            div
                            NavRow(icon: "list.bullet.rectangle", title: "Events", subtitle: "Live log from the device") { EventsView() }
                            div
                            NavRow(icon: "face.smiling", title: "Faces", subtitle: "Customize the screen faces") { FacesView() }
                            div
                            NavRow(icon: "stethoscope", title: "Diagnostics", subtitle: "One-tap health checks") { DiagnosticsView() }
                            div
                            NavRow(icon: "chart.xyaxis.line", title: "History", subtitle: "CPU / temp / RAM / battery") { HistoryView() }
                            div
                            NavRow(icon: "photo.on.rectangle", title: "Face images", subtitle: "Upload PNG faces") { FaceImagesView() }
                        }
                        section("Mode") {
                            FunctionRow(icon: "bolt.horizontal.circle", title: "Auto Mode",
                                        subtitle: "Normal hunting") { run("auto") }
                            div
                            FunctionRow(icon: "hand.raised", title: "Manual Mode",
                                        subtitle: "Pause, manual mode") { run("manual") }
                        }
                        section("Device") {
                            FunctionRow(icon: "arrow.clockwise.circle", title: "Restart pwnagotchi",
                                        subtitle: "Restart service") { run("restart") }
                            div
                            FunctionRow(icon: "arrow.counterclockwise.circle", title: "Reboot",
                                        subtitle: "Reboot system") { confirm = ("Reboot?", "reboot") }
                            div
                            FunctionRow(icon: "power.circle", title: "Shutdown",
                                        subtitle: "Power off device") { confirm = ("Power off?", "shutdown") }
                        }
                        section("Data") {
                            FunctionRow(icon: "key.horizontal.fill", title: "Export all passwords",
                                        subtitle: "Networks + passwords → share") { exportPasswords() }
                            div
                            FunctionRow(icon: "arrow.up.circle", title: "Upload all hashes to wpa-sec",
                                        subtitle: "Send all .pcap") { uploadAllHashes() }
                            div
                            FunctionRow(icon: "arrow.down.circle", title: "Download all hashes",
                                        subtitle: "Pull .pcap to phone") { run("download_all") }
                            div
                            FunctionRow(icon: "externaldrive.badge.timemachine", title: "Backup device",
                                        subtitle: "config + pwndex + handshakes → share") { backup() }
                        }
                        section("wpa-sec auto-sync") {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text("Auto upload + fetch cracked").font(.callout.weight(.semibold))
                                    Spacer()
                                    Text(wpasecLabel(st.wpasec_auto ?? 0)).font(.caption).foregroundStyle(.secondary)
                                }
                                Picker("", selection: Binding(
                                    get: { st.wpasec_auto ?? 0 },
                                    set: { setWpasec($0) })) {
                                    Text("Off").tag(0)
                                    Text("1h").tag(60)
                                    Text("3h").tag(180)
                                    Text("6h").tag(360)
                                    Text("12h").tag(720)
                                }.pickerStyle(.segmented)
                                Text("Runs on the device in both AUTO and MANUAL while it has internet — re-sends handshakes and pulls any newly cracked passwords into Pwndex.")
                                    .font(.caption2).foregroundStyle(.secondary)
                            }
                            .padding(14)
                        }
                        section("Recovery") {
                            FunctionRow(icon: "dot.radiowaves.left.and.right", title: "Fix Bluetooth",
                                        subtitle: "Make pairable + restart BT") {
                                shell("sudo btmgmt pairable on; sudo btmgmt connectable on; sudo systemctl restart bluetooth; echo done", "Bluetooth") }
                            div
                            FunctionRow(icon: "wifi.exclamationmark", title: "Self-heal wlan0",
                                        subtitle: "Recover brcmfmac / restart") {
                                shell("sudo systemctl restart pwnagotchi; echo restarting", "wlan0") }
                            div
                            FunctionRow(icon: "arrow.triangle.2.circlepath", title: "Sync wpa-sec now",
                                        subtitle: "Trigger upload + download") { uploadAllHashes() }
                        }
                        section("Interface") {
                            FunctionRow(icon: "globe", title: "Pwnagotchi Web UI",
                                        subtitle: "Open Web UI (on Dash)") {
                                toast = "Web UI is on the Dash tab, 'Web UI' button." }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Control")
            .sheet(isPresented: $showExport) {
                NavigationStack {
                    ScrollView {
                        Text(exportText).font(.callout.monospaced()).textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading).padding()
                    }
                    .navigationTitle("All passwords").navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) { Button("Done") { showExport = false } }
                        ToolbarItem(placement: .topBarTrailing) {
                            ShareLink(item: exportText) { Image(systemName: "square.and.arrow.up") }
                        }
                    }
                }
            }
            .alert(confirm?.title ?? "", isPresented: Binding(
                get: { confirm != nil }, set: { if !$0 { confirm = nil } })) {
                Button("Cancel", role: .cancel) { confirm = nil }
                Button("Yes", role: .destructive) { if let c = confirm { run(c.cmd) }; confirm = nil }
            }
            .task { await loadStatus() }
            .sheet(item: $shareURL) { url in ActivityView(items: [url]) }
        }
    }

    private func wpasecLabel(_ m: Int) -> String {
        m <= 0 ? "off" : (m % 60 == 0 ? "every \(m/60)h" : "every \(m)m")
    }

    private func setWpasec(_ m: Int) {
        st.wpasec_auto = m
        toast = "wpa-sec auto: \(wpasecLabel(m))"
        Task {
            _ = await PwnClient.wpasecAuto(conn, min: m)        // takes effect now
            _ = await PwnClient.cfgSet(conn, "main.plugins.companion.wpasec_auto_min", "\(m)", quote: false)  // survives reboot
        }
    }

    private func backup() {
        toast = "Building backup… (handshakes can be large)"
        Task {
            guard let data = await PwnClient.backupData(conn) else { toast = "❌ backup failed"; return }
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("pwn-backup.tar.gz")
            try? data.write(to: url)
            toast = "✅ backup ready (\(ByteCountFormatter.string(fromByteCount: Int64(data.count), countStyle: .file)))"
            shareURL = url
        }
    }

    private func loadStatus() async {
        while !Task.isCancelled {
            if let s = try? await PwnClient.fetchStatus(conn) { st = s; online = true }
            else { online = false }
            try? await Task.sleep(nanoseconds: 4_000_000_000)
        }
    }

    private var div: some View { Divider().overlay(Color.primary.opacity(0.08)).padding(.leading, 66) }

    @ViewBuilder private func section<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased()).font(.caption).foregroundStyle(.secondary).padding(.leading, 6)
            VStack(spacing: 0) { content() }
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(.primary.opacity(0.08), lineWidth: 1))
        }
    }

    private func run(_ cmd: String) {
        toast = "Sending: \(cmd)…"
        Task {
            let ok = (try? await PwnClient.control(conn, cmd: cmd)) ?? false
            toast = ok ? "✅ \(cmd) done" : "❌ \(cmd): needs a device endpoint (soon)"
        }
    }

    private func shell(_ cmd: String, _ label: String) {
        toast = "\(label): running…"
        Task {
            let out = await PwnClient.exec(conn, cmd)
            toast = "\(label): " + (out.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "done" : out.trimmingCharacters(in: .whitespacesAndNewlines).suffix(80).description)
        }
    }

    private func uploadAllHashes() {
        toast = "Uploading to wpa-sec…"
        Task {
            let (ok, msg) = await PwnClient.uploadAll(conn)
            let m = msg.isEmpty ? (ok ? "done" : "failed") : msg
            toast = (ok ? "✅ " : "❌ ") + m
        }
    }

    private func exportPasswords() {
        Task {
            let nets = (try? await PwnClient.fetchPwndex(conn)) ?? []
            let lines = nets.filter { !$0.pw.isEmpty }
                .map { "\($0.ssid)  —  \($0.pw)   (\($0.mac))" }
            exportText = lines.isEmpty ? "No saved passwords" : lines.joined(separator: "\n")
            showExport = true
        }
    }
}

// MARK: - Settings

struct SettingsView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var editConfig = false
    @State private var devName = ""
    @State private var apiKey = ""
    @State private var idLoaded = false
    @State private var idMsg = ""
    var body: some View {
        NavigationStack {
            Form {
                Section("Device") {
                    HStack {
                        Text("Mode"); Spacer()
                        Text(conn.demo ? "DEMO (Beta)" : "Connection")
                            .foregroundStyle(.secondary)
                    }
                    Button { editConfig = true } label: {
                        Label("Edit config.toml", systemImage: "doc.text")
                    }
                    Button(role: .destructive) {
                        conn.entered = false
                        conn.demo = false
                    } label: {
                        Label("Switch device / exit", systemImage: "arrow.left.circle")
                    }
                }
                Section("Device identity") {
                    HStack {
                        Text("Name"); Spacer()
                        TextField("pwnagotchi", text: $devName).multilineTextAlignment(.trailing)
                            .autocorrectionDisabled().textInputAutocapitalization(.never)
                    }
                    Button { saveCfg("main.name", devName) } label: { Label("Save name", systemImage: "pencil") }
                    HStack {
                        Text("wpa-sec key"); Spacer()
                        SecureField("api_key", text: $apiKey).multilineTextAlignment(.trailing)
                    }
                    Button { saveCfg("main.plugins.wpa-sec.api_key", apiKey) } label: {
                        Label("Save wpa-sec key", systemImage: "key")
                    }
                    if !idMsg.isEmpty { Text(idMsg).font(.caption).foregroundStyle(.secondary) }
                }
                Section("Customize") {
                    NavigationLink { FacesView() } label: { Label("Device faces", systemImage: "face.smiling") }
                }
                Section("Appearance") {
                    Picker("Theme", selection: $conn.theme) {
                        ForEach(AppTheme.allCases) { t in Text(t.label).tag(t) }
                    }.pickerStyle(.segmented)
                    Picker("Font", selection: $conn.font) {
                        ForEach(FontStyle.allCases) { f in Text(f.label).tag(f) }
                    }
                    ColorPicker("Device screen color", selection: $conn.faceColor, supportsOpacity: false)
                }
                Section("Notifications") {
                    Toggle("Alert on new handshakes", isOn: $conn.notify)
                        .onChange(of: conn.notify) { on in if on { Notify.requestAuth() } }
                    Text("A local alert fires when the device catches new handshakes while the app is open on the Dash tab.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("Connection") {
                    LabeledField("Device IP", text: $conn.host)
                    LabeledField("Port", text: $conn.port)
                    LabeledField("Login", text: $conn.user)
                    HStack {
                        Text("Password"); Spacer()
                        SecureField("", text: $conn.pass).multilineTextAlignment(.trailing)
                    }
                }
                Section("How to connect") {
                    Text("Enable the companion plugin on the Pi. On Bluetooth pairing pwnagotchi shows a code full-screen — type it on the iPhone. Then turn on Personal Hotspot: the Pi joins it and shows its IP — put it here (port 8080). Login/password are from config.toml (ui.web.username / ui.web.password).")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section {
                    HStack {
                        Text("App build").foregroundStyle(.secondary)
                        Spacer()
                        Text(APP_BUILD).font(.caption.monospaced()).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .sheet(isPresented: $editConfig) {
                FileSheet(path: "/etc/pwnagotchi/config.toml") {}
            }
            .task {
                if !idLoaded {
                    devName = await PwnClient.cfgGetString(conn, "main.name")
                    apiKey = await PwnClient.cfgGetString(conn, "main.plugins.wpa-sec.api_key")
                    idLoaded = true
                }
            }
        }
    }

    private func saveCfg(_ key: String, _ val: String) {
        idMsg = "Saving…"
        Task {
            let (ok, m) = await PwnClient.cfgSet(conn, key, val, quote: true)
            idMsg = (ok ? "✅ " : "❌ ") + (m.isEmpty ? "saved" : m)
        }
    }
}

struct LabeledField: View {
    let title: String
    @Binding var text: String
    init(_ title: String, text: Binding<String>) { self.title = title; self._text = text }
    var body: some View {
        HStack {
            Text(title); Spacer()
            TextField("", text: $text).multilineTextAlignment(.trailing)
                .autocorrectionDisabled().textInputAutocapitalization(.never)
        }
    }
}

struct PlaceholderView: View {
    let title: String
    let systemImage: String
    let note: String
    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                GlassCard {
                    VStack(spacing: 14) {
                        Image(systemName: systemImage).font(.system(size: 44)).foregroundStyle(.secondary)
                        Text(note).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }.frame(maxWidth: .infinity)
                }.padding()
            }
            .navigationTitle(title)
        }
    }
}
