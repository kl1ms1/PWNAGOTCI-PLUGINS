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

func uptimeStr(_ s: Int?) -> String {
    let s = s ?? 0
    let d = s / 86400, h = (s % 86400) / 3600, m = (s % 3600) / 60
    if d > 0 { return "\(d)d \(h)h" }
    if h > 0 { return "\(h)h \(m)m" }
    return "\(m)m"
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
                            Label("Events", systemImage: "list.bullet.rectangle")
                                .frame(maxWidth: .infinity)
                        }.buttonStyle(.bordered)
                    }
                    .padding()
                }
            }
            .navigationTitle("Dash")
            .sheet(isPresented: $showWeb) {
                if let url = conn.baseURL { WebUISheet(url: url, user: conn.user, pass: conn.pass) }
            }
        }
        .task { await loop() }
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
        if let s = try? await PwnClient.fetchStatus(conn) { st = s }
    }
}

// MARK: - Pwndex

struct PwndexView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var items: [NetItem] = []
    @State private var loaded = false
    @State private var editing: NetItem?
    @State private var query = ""

    private var filtered: [NetItem] {
        guard !query.isEmpty else { return items }
        let q = query.lowercased()
        return items.filter {
            $0.ssid.lowercased().contains(q) || $0.mac.lowercased().contains(q)
                || $0.pw.lowercased().contains(q)
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                List {
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
                    actionRow("Download hash (.pcap)", "arrow.down.doc", "Hash downloaded")
                    actionRow("Add to whitelist", "checkmark.shield", "To whitelist")
                    actionRow("Upload to wpa-sec", "arrow.up.circle", "Sent to wpa-sec")
                }
                if !msg.isEmpty {
                    Section { Text("✅ " + msg + (conn.demo ? " (demo)" : "")).foregroundStyle(.secondary) }
                }
            }
            .navigationTitle(item.ssid).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
        }
    }

    private func actionRow(_ title: String, _ icon: String, _ done: String) -> some View {
        Button { msg = done } label: { Label(title, systemImage: icon) }
    }
}

// MARK: - Control

struct ControlView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var toast = ""
    @State private var confirm: (title: String, cmd: String)?
    @State private var exportText = ""
    @State private var showExport = false

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                ScrollView {
                    VStack(spacing: 16) {
                        if !toast.isEmpty {
                            GlassCard { Text(toast).font(.footnote).foregroundStyle(.secondary) }
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
                                        subtitle: "Send all .pcap") { run("upload_all") }
                            div
                            FunctionRow(icon: "arrow.down.circle", title: "Download all hashes",
                                        subtitle: "Pull .pcap to phone") { run("download_all") }
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
    var body: some View {
        NavigationStack {
            Form {
                Section("Device") {
                    HStack {
                        Text("Mode"); Spacer()
                        Text(conn.demo ? "DEMO (Beta)" : "Connection")
                            .foregroundStyle(.secondary)
                    }
                    Button(role: .destructive) {
                        conn.entered = false
                        conn.demo = false
                    } label: {
                        Label("Switch device / exit", systemImage: "arrow.left.circle")
                    }
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
            }
            .navigationTitle("Settings")
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
