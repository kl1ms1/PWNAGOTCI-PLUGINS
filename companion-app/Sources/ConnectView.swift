import SwiftUI

struct ConnectView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var showBoard = false

    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 22) {
                Spacer(minLength: 20)

                Text("Pwn Companion")
                    .font(.largeTitle.bold())

                DeviceGraphic(showBoard: showBoard)
                    .frame(height: 230)
                    .padding(.horizontal, 24)

                Picker("", selection: $showBoard) {
                    Text("Экран").tag(false)
                    Text("Плата").tag(true)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 60)

                Text("Custom")
                    .font(.headline)
                Text("кастомизация вида — скоро")
                    .font(.caption).foregroundStyle(.secondary)

                Spacer()

                VStack(spacing: 12) {
                    Button {
                        conn.demo = true
                        conn.entered = true
                    } label: {
                        Label("Демо (Beta) — без устройства", systemImage: "play.circle.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)

                    Button {
                        conn.demo = false
                        conn.entered = true
                    } label: {
                        Label("Подключиться", systemImage: "dot.radiowaves.left.and.right")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(.primary)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 24)
            }
        }
    }
}

/// A stylized pwnagotchi device: either its e-ink screen (a face) or the board.
struct DeviceGraphic: View {
    var showBoard: Bool
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color(white: 0.14))
                .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .strokeBorder(.primary.opacity(0.15), lineWidth: 1))
            if showBoard {
                board
            } else {
                screen
            }
        }
    }

    private var screen: some View {
        RoundedRectangle(cornerRadius: 12).fill(.black)
            .overlay(
                VStack(spacing: 6) {
                    Text("(◕‿‿◕)").font(.system(size: 44, weight: .bold)).foregroundStyle(.white)
                    Text("Ki213 · на охоте").font(.caption).foregroundStyle(.gray)
                }
            )
            .padding(26)
    }

    private var board: some View {
        GeometryReader { geo in
            ZStack {
                // traces
                Path { p in
                    for i in 0..<6 {
                        let y = geo.size.height * (0.2 + 0.12 * Double(i))
                        p.move(to: CGPoint(x: 30, y: y)); p.addLine(to: CGPoint(x: geo.size.width - 30, y: y))
                    }
                }.stroke(.primary.opacity(0.12), lineWidth: 1)
                // chips
                HStack(spacing: 18) {
                    chip(40); chip(56); chip(34)
                }
                // GPIO header
                HStack(spacing: 4) {
                    ForEach(0..<10, id: \.self) { _ in
                        Circle().fill(.primary.opacity(0.35)).frame(width: 5, height: 5)
                    }
                }
                .frame(maxHeight: .infinity, alignment: .top)
                .padding(.top, 24)
            }
        }
        .padding(20)
    }

    private func chip(_ s: CGFloat) -> some View {
        RoundedRectangle(cornerRadius: 6).fill(Color(white: 0.25))
            .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(.primary.opacity(0.25), lineWidth: 1))
            .frame(width: s, height: s)
    }
}
