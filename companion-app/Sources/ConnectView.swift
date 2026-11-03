import SwiftUI

struct ConnectView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var searching = false

    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 18) {
                Spacer(minLength: 16)
                Text("Pwn Companion").font(.largeTitle.bold())

                DeviceGraphic(skin: conn.skin, faceColor: conn.faceColor)
                    .frame(height: 210)
                    .padding(.horizontal, 24)

                VStack(spacing: 12) {
                    Picker("", selection: $conn.skin) {
                        ForEach(Skin.allCases) { s in Text(s.label).tag(s) }
                    }
                    .pickerStyle(.segmented)

                    ColorPicker("Screen color", selection: $conn.faceColor, supportsOpacity: false)
                        .font(.subheadline)
                }
                .padding(.horizontal, 40)

                Text("Custom").font(.headline)

                Spacer()

                VStack(spacing: 12) {
                    Button { conn.demo = true; conn.entered = true } label: {
                        Label("Demo (Beta) — no device", systemImage: "play.circle.fill")
                    }
                    .buttonStyle(.bordered).controlSize(.large)
                    .frame(maxWidth: .infinity)

                    Button { searching = true } label: {
                        Label("Connect", systemImage: "dot.radiowaves.left.and.right")
                    }
                    .buttonStyle(FilledStyle())
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 20)
            }
            .fullScreenCover(isPresented: $searching) {
                SearchingView().environmentObject(conn)
            }
        }
    }
}

/// Flipper-style "searching for device" screen (BLE scan comes with the server).
struct SearchingView: View {
    @EnvironmentObject var conn: ConnectionStore
    @Environment(\.dismiss) private var dismiss
    @State private var dots = 0

    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 24) {
                HStack {
                    Button { dismiss() } label: { Image(systemName: "chevron.left").font(.title3) }
                    Spacer()
                    Text("Searching").font(.headline)
                    Spacer()
                    Image(systemName: "chevron.left").opacity(0)
                }
                .padding()

                Spacer()

                HStack(spacing: 10) {
                    Image(systemName: "iphone").font(.system(size: 44)).foregroundStyle(.secondary)
                    HStack(spacing: 6) {
                        ForEach(0..<3, id: \.self) { i in
                            Circle().fill(.primary.opacity(i <= dots ? 1 : 0.2)).frame(width: 7, height: 7)
                        }
                    }
                    Image(systemName: "dot.radiowaves.left.and.right")
                        .font(.system(size: 40)).foregroundStyle(.primary)
                }

                ProgressView().tint(.primary)
                Text("Looking for pwnagotchi over Bluetooth…")
                    .font(.subheadline).foregroundStyle(.secondary)
                Text("Make sure btlink/companion is on.\nDirect BLE scan comes with the BLE server.")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    .padding(.horizontal, 30)

                Spacer()

                Button("Enter anyway") {
                    conn.demo = false; conn.entered = true; dismiss()
                }
                .buttonStyle(FilledStyle())
                .padding(.horizontal, 24).padding(.bottom, 24)
            }
        }
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 450_000_000)
                dots = (dots + 1) % 3
            }
        }
    }
}

/// Stylized pwnagotchi: a case (skin) with its e-ink screen showing the face.
struct DeviceGraphic: View {
    var skin: Skin
    var faceColor: Color
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(skin.caseColor)
                .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .strokeBorder(skin.line, lineWidth: 1))
            RoundedRectangle(cornerRadius: 12).fill(.black)
                .overlay(
                    VStack(spacing: 6) {
                        Text("(◕‿‿◕)").font(.system(size: 44, weight: .bold))
                            .foregroundStyle(faceColor)
                        Text("Ki213 · hunting").font(.caption).foregroundStyle(.gray)
                    }
                )
                .padding(26)
        }
    }
}
