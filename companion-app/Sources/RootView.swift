import SwiftUI
import UIKit

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
                            note: "Режимы / reboot / заливка — в Milestone 2–3")
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
        NavigationView {
            ScrollView {
                VStack(spacing: 16) {
                    HStack(spacing: 8) {
                        Circle().fill(online ? Color.green : Color.red)
                            .frame(width: 10, height: 10)
                        Text(status).font(.subheadline).foregroundColor(.secondary)
                        Spacer()
                    }
                    ZStack {
                        RoundedRectangle(cornerRadius: 14).fill(Color.black)
                        if let img = image {
                            Image(uiImage: img)
                                .resizable().interpolation(.none)
                                .aspectRatio(contentMode: .fit).padding(8)
                        } else {
                            Text(status).foregroundColor(.gray)
                        }
                    }
                    .frame(height: 190)

                    Button {
                        Task { await refresh() }
                    } label: {
                        Label("Обновить", systemImage: "arrow.clockwise")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    Text("Живой экран pwnagotchi.\nMilestone 1 — проверяем коннект к устройству.")
                        .font(.footnote).foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding()
            }
            .navigationTitle("Pwn Companion")
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
            status = "Нет связи — проверь IP / USB / Bluetooth"
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject var conn: ConnectionStore
    var body: some View {
        NavigationView {
            Form {
                Section("Подключение к pwnagotchi") {
                    LabeledField("IP / host", text: $conn.host)
                    LabeledField("Порт", text: $conn.port)
                    LabeledField("Логин", text: $conn.user)
                    HStack {
                        Text("Пароль"); Spacer()
                        SecureField("", text: $conn.pass)
                            .multilineTextAlignment(.trailing)
                    }
                }
                Section("Как подключиться") {
                    Text("USB: 10.0.0.2 : 8080\nBluetooth (BT-PAN) или Wi-Fi: IP устройства в этой сети.\nЛогин/пароль веб-интерфейса — из config.toml (ui.web.username / ui.web.password).")
                        .font(.footnote).foregroundColor(.secondary)
                }
            }
            .navigationTitle("Settings")
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
        NavigationView {
            VStack(spacing: 14) {
                Image(systemName: systemImage)
                    .font(.system(size: 44)).foregroundColor(.secondary)
                Text(note)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }
            .navigationTitle(title)
        }
    }
}
