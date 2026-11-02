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
            .overlay(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .strokeBorder(.white.opacity(0.12), lineWidth: 1)
            )
    }
}

struct Smile: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.addArc(center: CGPoint(x: r.midX, y: r.minY),
                 radius: r.width / 2,
                 startAngle: .degrees(20), endAngle: .degrees(160), clockwise: false)
        return p
    }
}

/// The sunglasses `(⌐■_■)` face, in glass — no text under it.
struct SunglassesAvatar: View {
    var size: CGFloat = 76
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.26, style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay(RoundedRectangle(cornerRadius: size * 0.26, style: .continuous)
                    .strokeBorder(.white.opacity(0.18), lineWidth: 1))
            VStack(spacing: size * 0.10) {
                HStack(spacing: size * 0.10) {
                    lens; lens
                }
                Smile()
                    .stroke(.white.opacity(0.9), style: StrokeStyle(lineWidth: size * 0.05, lineCap: .round))
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

// MARK: - Root

struct RootView: View {
    var body: some View {
        TabView {
            DashView()
                .tabItem { Label("Dash", systemImage: "chart.bar.fill") }
            PlaceholderView(title: "WiFi", systemImage: "wifi",
                            note: "Список сетей — в Milestone 2")
                .tabItem { Label("WiFi", systemImage: "wifi") }
            PlaceholderView(title: "Events", systemImage: "list.bullet.rectangle",
                            note: "Живой лог (WebSocket) — в Milestone 2")
                .tabItem { Label("Events", systemImage: "list.bullet") }
            PlaceholderView(title: "Control", systemImage: "wrench.and.screwdriver.fill",
                            note: "Режимы / reboot / заливка — M2–M3")
                .tabItem { Label("Control", systemImage: "wrench.and.screwdriver") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}

struct DashView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var image: UIImage?
    @State private var status = "Подключаюсь…"
    @State private var online = false

    var body: some View {
        NavigationStack {
            ZStack {
                GlassBG()
                ScrollView {
                    VStack(spacing: 16) {
                        GlassCard {
                            HStack(spacing: 14) {
                                SunglassesAvatar(size: 76)
                                VStack(alignment: .leading, spacing: 6) {
                                    Text("Pwnagotchi").font(.headline)
                                    HStack(spacing: 7) {
                                        Circle().fill(online ? Color.green : Color.red)
                                            .frame(width: 9, height: 9)
                                        Text(status).font(.subheadline).foregroundStyle(.secondary)
                                    }
                                    Text(conn.transport.label).font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                            }
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
                                .frame(height: 185)
                                Button {
                                    Task { await refresh() }
                                } label: {
                                    Label("Обновить", systemImage: "arrow.clockwise")
                                        .frame(maxWidth: .infinity)
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Dash")
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .task { await loop() }
    }

    private func loop() async {
        while !Task.isCancelled {
            await refresh()
            try? await Task.sleep(nanoseconds: 2_000_000_000)
        }
    }

    private func refresh() async {
        do {
            image = try await PwnClient.fetchUIImage(conn)
            online = true
            status = "На связи"
        } catch {
            online = false
            status = "Нет связи — проверь подключение"
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject var conn: ConnectionStore
    var body: some View {
        NavigationStack {
            ZStack {
                GlassBG()
                Form {
                    Section("Подключение") {
                        Picker("Способ", selection: $conn.transport) {
                            ForEach(Transport.allCases) { t in
                                Label(t.label, systemImage: t.systemImage).tag(t)
                            }
                        }
                        .pickerStyle(.segmented)

                        if conn.transport == .cable {
                            LabeledField("IP (USB)", text: $conn.cableHost)
                        } else {
                            LabeledField("IP (Bluetooth)", text: $conn.btHost)
                        }
                        LabeledField("Порт", text: $conn.port)
                        LabeledField("Логин", text: $conn.user)
                        HStack {
                            Text("Пароль"); Spacer()
                            SecureField("", text: $conn.pass).multilineTextAlignment(.trailing)
                        }
                    }
                    .listRowBackground(Color.white.opacity(0.06))

                    Section("Вид") {
                        Picker("Тема", selection: $conn.theme) {
                            ForEach(AppTheme.allCases) { t in Text(t.label).tag(t) }
                        }
                    }
                    .listRowBackground(Color.white.opacity(0.06))

                    Section("Как подключиться") {
                        Text("Кабель (USB): 10.0.0.2 : 8080.\nBluetooth: включи на Pi плагин btlink — Pi входит в Bluetooth-раздачу телефона, его IP обычно 172.20.10.x. Логин/пароль веб-интерфейса — из config.toml (ui.web.username / ui.web.password).")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    .listRowBackground(Color.white.opacity(0.06))
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
    init(_ title: String, text: Binding<String>) {
        self.title = title
        self._text = text
    }
    var body: some View {
        HStack {
            Text(title); Spacer()
            TextField("", text: $text)
                .multilineTextAlignment(.trailing)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
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
                        Image(systemName: systemImage)
                            .font(.system(size: 44)).foregroundStyle(.secondary)
                        Text(note).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                }
                .padding()
            }
            .navigationTitle(title)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }
}
