import SwiftUI
import UIKit

// MARK: - Liquid-glass building blocks

struct GlassBG: View {
    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0.10, green: 0.16, blue: 0.22),
                                    Color(red: 0.05, green: 0.07, blue: 0.09)],
                           startPoint: .top, endPoint: .bottom)
            Circle().fill(Color.cyan.opacity(0.16)).frame(width: 420, height: 420)
                .blur(radius: 90).offset(x: -130, y: -240)
            Circle().fill(Color.purple.opacity(0.16)).frame(width: 460, height: 460)
                .blur(radius: 100).offset(x: 150, y: 360)
        }
        .ignoresSafeArea()
    }
}

struct GlassCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous)
                .strokeBorder(.white.opacity(0.12), lineWidth: 1))
    }
}

struct Smile: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.addArc(center: CGPoint(x: r.midX, y: r.minY), radius: r.width / 2,
                 startAngle: .degrees(20), endAngle: .degrees(160), clockwise: false)
        return p
    }
}

struct SunglassesAvatar: View {
    var size: CGFloat = 76
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.26, style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay(RoundedRectangle(cornerRadius: size * 0.26, style: .continuous)
                    .strokeBorder(.white.opacity(0.18), lineWidth: 1))
            VStack(spacing: size * 0.10) {
                HStack(spacing: size * 0.10) { lens; lens }
                Smile().stroke(.white.opacity(0.9),
                               style: StrokeStyle(lineWidth: size * 0.05, lineCap: .round))
                    .frame(width: size * 0.4, height: size * 0.16)
            }
            .padding(size * 0.14)
        }
        .frame(width: size, height: size)
    }
    private var lens: some View {
        RoundedRectangle(cornerRadius: size * 0.09, style: .continuous)
            .fill(.white.opacity(0.92))
            .overlay(RoundedRectangle(cornerRadius: size * 0.09, style: .continuous)
                .strokeBorder(.cyan.opacity(0.85), lineWidth: 2))
            .frame(width: size * 0.3, height: size * 0.22)
    }
}

struct StatTile: View {
    let label: String
    let value: String
    var tint: Color = .cyan
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value).font(.system(size: 22, weight: .bold, design: .rounded)).foregroundStyle(tint)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(.white.opacity(0.10), lineWidth: 1))
    }
}

struct FunctionRow: View {
    let icon: String
    let title: String
    let subtitle: String
    var tint: Color = .cyan
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.system(size: 18, weight: .semibold)).foregroundStyle(tint)
                    .frame(width: 38, height: 38)
                    .background(tint.opacity(0.16), in: RoundedRectangle(cornerRadius: 11, style: .continuous))
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
            DashView().tabItem { Label("Dash", systemImage: "chart.bar.fill") }
            PwndexView().tabItem { Label("Pwndex", systemImage: "list.star") }
            PlaceholderView(title: "Events", systemImage: "list.bullet.rectangle",
                            note: "Живой лог (WebSocket) — скоро")
                .tabItem { Label("Events", systemImage: "list.bullet") }
            ControlView().tabItem { Label("Control", systemImage: "wrench.and.screwdriver.fill") }
            SettingsView().tabItem { Label("Settings", systemImage: "gearshape.fill") }
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
                GlassBG()
                ScrollView {
                    VStack(spacing: 16) {
                        GlassCard {
                            HStack(spacing: 14) {
                                SunglassesAvatar(size: 72)
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(st.name ?? "Pwnagotchi").font(.headline)
                                    HStack(spacing: 7) {
                                        Circle().fill(online ? Color.green : Color.red).frame(width: 9, height: 9)
                                        Text(status).font(.subheadline).foregroundStyle(.secondary)
                                    }
                                    Text("режим: \((st.mode ?? "—").uppercased()) · ап \(uptimeStr(st.uptime))")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                            }
                        }

                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()),
                                            GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                            StatTile(label: "shakes", value: "\(st.shakes ?? 0)")
                            StatTile(label: "сети", value: "\(st.networks ?? 0)", tint: .green)
                            StatTile(label: "пароли", value: "\(st.cracked ?? 0)", tint: .yellow)
                            StatTile(label: ".pcap", value: "\(st.pcaps ?? 0)", tint: .purple)
                            StatTile(label: "темп", value: st.temp.map { String(format: "%.0f°", $0) } ?? "—", tint: .orange)
                            StatTile(label: "CPU", value: st.cpu.map { String(format: "%.0f%%", $0) } ?? "—")
                            StatTile(label: "RAM", value: st.mem.map { String(format: "%.0f%%", $0) } ?? "—", tint: .green)
                            StatTile(label: "SD ГБ", value: st.sd_free.map { String(format: "%.0f", $0) } ?? "—", tint: .purple)
                        }

                        GlassCard {
                            VStack(spacing: 10) {
                                ZStack {
                                    RoundedRectangle(cornerRadius: 14).fill(Color.black)
                                    if let img = image {
                                        Image(uiImage: img).resizable().interpolation(.none)
                                            .aspectRatio(contentMode: .fit).padding(8)
                                    } else {
                                        Text(status).foregroundStyle(.gray)
                                    }
                                }
                                .frame(height: 170)
                                HStack(spacing: 10) {
                                    Button { Task { await refresh() } } label: {
                                        Label("Обновить", systemImage: "arrow.clockwise").frame(maxWidth: .infinity)
                                    }.buttonStyle(.borderedProminent)
                                    Button { showWeb = true } label: {
                                        Label("Веб-морда", systemImage: "globe").frame(maxWidth: .infinity)
                                    }.buttonStyle(.bordered).disabled(conn.baseURL == nil)
                                }
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Dash")
            .toolbarColorScheme(.dark, for: .navigationBar)
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
            online = false; status = "Нет связи — проверь Bluetooth"
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
                GlassBG()
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
                                    Text(it.pw).font(.callout.monospaced()).foregroundStyle(.green)
                                }
                                Image(systemName: "pencil").font(.caption2).foregroundStyle(.tertiary)
                            }
                        }
                        .listRowBackground(Color.white.opacity(0.06))
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
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { await load() } } label: { Image(systemName: "arrow.clockwise") }
                }
            }
            .sheet(item: $editing) { it in
                EditPwSheet(item: it) { newPw in
                    Task {
                        _ = try? await PwnClient.setPassword(conn, mac: it.mac, pw: newPw)
                        await load()
                    }
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
                Section("Сеть") {
                    Text(item.ssid); Text(item.mac).font(.caption).foregroundStyle(.secondary)
                }
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
                GlassBG()
                ScrollView {
                    VStack(spacing: 16) {
                        if !toast.isEmpty {
                            GlassCard { Text(toast).font(.footnote).foregroundStyle(.secondary) }
                        }
                        section("Режим") {
                            FunctionRow(icon: "bolt.horizontal.circle.fill", title: "Auto Mode",
                                        subtitle: "Обычная охота", tint: .green) { run("auto") }
                            div
                            FunctionRow(icon: "hand.raised.fill", title: "Manual Mode",
                                        subtitle: "Пауза, ручной режим", tint: .orange) { run("manual") }
                        }
                        section("Устройство") {
                            FunctionRow(icon: "arrow.clockwise.circle.fill", title: "Restart pwnagotchi",
                                        subtitle: "Перезапустить сервис", tint: .cyan) { run("restart") }
                            div
                            FunctionRow(icon: "arrow.counterclockwise.circle.fill", title: "Reboot",
                                        subtitle: "Перезагрузить систему", tint: .yellow) {
                                confirm = ("Перезагрузить устройство?", "reboot") }
                            div
                            FunctionRow(icon: "power.circle.fill", title: "Shutdown",
                                        subtitle: "Выключить устройство", tint: .red) {
                                confirm = ("Выключить устройство?", "shutdown") }
                        }
                        section("Интерфейс") {
                            FunctionRow(icon: "globe", title: "Pwnagotchi Web UI",
                                        subtitle: "Открыть веб-морду", tint: .purple) {
                                toast = "Веб-морда — на вкладке Dash, кнопка «Веб-морда»." }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Control")
            .toolbarColorScheme(.dark, for: .navigationBar)
            .alert(confirm?.title ?? "", isPresented: Binding(
                get: { confirm != nil }, set: { if !$0 { confirm = nil } })) {
                Button("Отмена", role: .cancel) { confirm = nil }
                Button("Да", role: .destructive) { if let c = confirm { run(c.cmd) }; confirm = nil }
            }
        }
    }

    private var div: some View { Divider().overlay(Color.white.opacity(0.08)).padding(.leading, 66) }

    @ViewBuilder private func section<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased()).font(.caption).foregroundStyle(.secondary).padding(.leading, 6)
            VStack(spacing: 0) { content() }
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(.white.opacity(0.10), lineWidth: 1))
        }
    }

    private func run(_ cmd: String) {
        toast = "Отправляю: \(cmd)…"
        Task {
            let ok = (try? await PwnClient.control(conn, cmd: cmd)) ?? false
            toast = ok ? "✅ \(cmd) выполнено" : "❌ не вышло (\(cmd)) — проверь связь"
        }
    }
}

// MARK: - Settings

struct SettingsView: View {
    @EnvironmentObject var conn: ConnectionStore
    var body: some View {
        NavigationStack {
            ZStack {
                GlassBG()
                Form {
                    Section("Подключение (Bluetooth / Wi-Fi)") {
                        LabeledField("IP устройства", text: $conn.host)
                        LabeledField("Порт", text: $conn.port)
                        LabeledField("Логин", text: $conn.user)
                        HStack {
                            Text("Пароль"); Spacer()
                            SecureField("", text: $conn.pass).multilineTextAlignment(.trailing)
                        }
                    }.listRowBackground(Color.white.opacity(0.06))

                    Section("Вид") {
                        Picker("Тема", selection: $conn.theme) {
                            ForEach(AppTheme.allCases) { t in Text(t.label).tag(t) }
                        }
                    }.listRowBackground(Color.white.opacity(0.06))

                    Section("Как подключиться") {
                        Text("iPhone не умеет USB-ethernet, поэтому только Bluetooth (или общий Wi-Fi).\nВключи на Pi плагин btlink — он входит в Bluetooth-точку телефона, и показывает свой IP (обычно 172.20.10.x) на экране. Впиши его сюда. Логин/пароль — из config.toml (ui.web.username / ui.web.password).")
                            .font(.footnote).foregroundStyle(.secondary)
                    }.listRowBackground(Color.white.opacity(0.06))
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Settings")
            .toolbarColorScheme(.dark, for: .navigationBar)
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
                GlassBG()
                GlassCard {
                    VStack(spacing: 14) {
                        Image(systemName: systemImage).font(.system(size: 44)).foregroundStyle(.secondary)
                        Text(note).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }.frame(maxWidth: .infinity)
                }.padding()
            }
            .navigationTitle(title)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }
}
