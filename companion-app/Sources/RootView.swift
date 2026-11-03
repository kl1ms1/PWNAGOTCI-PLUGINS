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
    if d > 0 { return "\(d)д \(h)ч" }
    if h > 0 { return "\(h)ч \(m)м" }
    return "\(m)м"
}

// MARK: - Root

struct RootView: View {
    var body: some View {
        TabView {
            DashView().tabItem { Label("Dash", systemImage: "chart.bar") }
            PwndexView().tabItem { Label("Pwndex", systemImage: "list.star") }
            MapView().tabItem { Label("Карта", systemImage: "map") }
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
    @State private var status = "Подключаюсь…"
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
                            StatTile(label: "сети", value: "\(st.networks ?? 0)")
                            StatTile(label: "пароли", value: "\(st.cracked ?? 0)")
                            StatTile(label: ".pcap", value: "\(st.pcaps ?? 0)")
                            StatTile(label: "темп", value: st.temp.map { String(format: "%.0f°", $0) } ?? "—")
                            StatTile(label: "CPU", value: st.cpu.map { String(format: "%.0f%%", $0) } ?? "—")
                            StatTile(label: "RAM", value: st.mem.map { String(format: "%.0f%%", $0) } ?? "—")
                            StatTile(label: "SD ГБ", value: st.sd_free.map { String(format: "%.0f", $0) } ?? "—")
                        }

                        HStack(spacing: 10) {
                            Button { Task { await refresh() } } label: {
                                Label("Обновить", systemImage: "arrow.clockwise").frame(maxWidth: .infinity)
                            }.buttonStyle(.borderedProminent).tint(.primary)
                            Button { showWeb = true } label: {
                                Label("Веб-морда", systemImage: "globe").frame(maxWidth: .infinity)
                            }.buttonStyle(.bordered).disabled(conn.baseURL == nil)
                        }
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
            online = true; status = "На связи"
        } catch {
            online = false; status = "Нет связи"
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

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                List {
                    ForEach(items) { it in
                        Button { editing = it } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(it.ssid).font(.body.weight(.semibold))
                                    Text(it.mac).font(.caption2).foregroundStyle(.secondary)
                                }
                                Spacer()
                                if it.pw.isEmpty {
                                    Text("нет пароля").font(.caption).foregroundStyle(.secondary)
                                } else {
                                    Text(it.pw).font(.callout.monospaced()).foregroundStyle(.primary)
                                }
                                Image(systemName: "pencil").font(.caption2).foregroundStyle(.tertiary)
                            }
                        }
                        .listRowBackground(Color.primary.opacity(0.05))
                    }
                    if items.isEmpty {
                        Text(loaded ? "Каталог пуст" : "Загрузка…")
                            .foregroundStyle(.secondary).listRowBackground(Color.clear)
                    }
                }
                .scrollContentBackground(.hidden)
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
    let item: NetItem
    let onSave: (String) -> Void
    @State private var pw: String
    @Environment(\.dismiss) private var dismiss
    init(item: NetItem, onSave: @escaping (String) -> Void) {
        self.item = item; self.onSave = onSave; _pw = State(initialValue: item.pw)
    }
    var body: some View {
        NavigationStack {
            Form {
                Section("Сеть") { Text(item.ssid); Text(item.mac).font(.caption).foregroundStyle(.secondary) }
                Section("Пароль") {
                    TextField("пароль", text: $pw).autocorrectionDisabled().textInputAutocapitalization(.never)
                }
            }
            .navigationTitle("Правка").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Отмена") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) { Button("Сохранить") { onSave(pw); dismiss() } }
            }
        }
    }
}

// MARK: - Control

struct ControlView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var toast = ""
    @State private var confirm: (title: String, cmd: String)?

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                ScrollView {
                    VStack(spacing: 16) {
                        if !toast.isEmpty {
                            GlassCard { Text(toast).font(.footnote).foregroundStyle(.secondary) }
                        }
                        section("Режим") {
                            FunctionRow(icon: "bolt.horizontal.circle", title: "Auto Mode",
                                        subtitle: "Обычная охота") { run("auto") }
                            div
                            FunctionRow(icon: "hand.raised", title: "Manual Mode",
                                        subtitle: "Пауза, ручной режим") { run("manual") }
                        }
                        section("Устройство") {
                            FunctionRow(icon: "arrow.clockwise.circle", title: "Restart pwnagotchi",
                                        subtitle: "Перезапустить сервис") { run("restart") }
                            div
                            FunctionRow(icon: "arrow.counterclockwise.circle", title: "Reboot",
                                        subtitle: "Перезагрузить систему") { confirm = ("Перезагрузить?", "reboot") }
                            div
                            FunctionRow(icon: "power.circle", title: "Shutdown",
                                        subtitle: "Выключить устройство") { confirm = ("Выключить?", "shutdown") }
                        }
                        section("Интерфейс") {
                            FunctionRow(icon: "globe", title: "Pwnagotchi Web UI",
                                        subtitle: "Открыть веб-морду (на Dash)") {
                                toast = "Веб-морда — на вкладке Dash, кнопка «Веб-морда»." }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Control")
            .alert(confirm?.title ?? "", isPresented: Binding(
                get: { confirm != nil }, set: { if !$0 { confirm = nil } })) {
                Button("Отмена", role: .cancel) { confirm = nil }
                Button("Да", role: .destructive) { if let c = confirm { run(c.cmd) }; confirm = nil }
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
        toast = "Отправляю: \(cmd)…"
        Task {
            let ok = (try? await PwnClient.control(conn, cmd: cmd)) ?? false
            toast = ok ? "✅ \(cmd) выполнено" : "❌ не вышло (\(cmd))"
        }
    }
}

// MARK: - Settings

struct SettingsView: View {
    @EnvironmentObject var conn: ConnectionStore
    var body: some View {
        NavigationStack {
            Form {
                Section("Устройство") {
                    HStack {
                        Text("Режим"); Spacer()
                        Text(conn.demo ? "ДЕМО (Beta)" : "Подключение")
                            .foregroundStyle(.secondary)
                    }
                    Button(role: .destructive) {
                        conn.entered = false
                        conn.demo = false
                    } label: {
                        Label("Сменить устройство / выход", systemImage: "arrow.left.circle")
                    }
                }
                Section("Вид") {
                    Picker("Тема", selection: $conn.theme) {
                        ForEach(AppTheme.allCases) { t in Text(t.label).tag(t) }
                    }.pickerStyle(.segmented)
                }
                Section("Подключение") {
                    LabeledField("IP устройства", text: $conn.host)
                    LabeledField("Порт", text: $conn.port)
                    LabeledField("Логин", text: $conn.user)
                    HStack {
                        Text("Пароль"); Spacer()
                        SecureField("", text: $conn.pass).multilineTextAlignment(.trailing)
                    }
                }
                Section("Как подключиться") {
                    Text("Включи на Pi плагин btlink — при сопряжении по Bluetooth pwnagotchi покажет код на весь экран, введи его на айфоне. Потом включи Личную точку, Pi войдёт в неё и покажет свой IP — впиши его сюда (порт 8080). Логин/пароль — из config.toml (ui.web.username / ui.web.password).")
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
