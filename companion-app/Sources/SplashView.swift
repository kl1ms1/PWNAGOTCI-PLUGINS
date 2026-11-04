import SwiftUI

/// Launch animation: a pwnagotchi and a phone slide together, then the
/// pwnagotchi's face leaps in an arc into the phone's screen. Monochrome.
struct SplashView: View {
    var onDone: () -> Void

    @State private var slid = false        // devices slid together
    @State private var jump = 0.0          // 0 = on pwnagotchi, 1 = in phone
    @State private var faceOnPwn = true
    @State private var litPhone = false
    @State private var title = false
    @State private var fade = false

    private let gapApart: CGFloat = 150
    private let gapClose: CGFloat = 86

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            // the two devices
            HStack(spacing: 0) {
                PwnDevice(showFace: faceOnPwn)
                    .frame(width: 150, height: 110)
                    .offset(x: slid ? (gapApart - gapClose) / 2 : 0)
                Spacer().frame(width: slid ? gapClose : gapApart)
                PhoneDevice(lit: litPhone)
                    .frame(width: 92, height: 170)
                    .offset(x: slid ? -(gapApart - gapClose) / 2 : 0)
            }

            // the flying face (visible only mid-jump)
            if !faceOnPwn && !litPhone {
                Text("(◕‿‿◕)")
                    .font(.system(size: 26, weight: .bold))
                    .foregroundStyle(.white)
                    .modifier(ArcJump(progress: jump, fromX: -40, toX: 66, arc: 90))
            }

            VStack {
                Spacer()
                Text("PWN COMPANION")
                    .font(.system(.headline, design: .monospaced)).tracking(4)
                    .foregroundStyle(.white)
                    .opacity(title ? 1 : 0)
                    .padding(.bottom, 80)
            }
        }
        .opacity(fade ? 0 : 1)
        .contentShape(Rectangle())
        .onTapGesture { finish() }
        .task { await run() }
    }

    private func run() async {
        try? await Task.sleep(nanoseconds: 350_000_000)
        withAnimation(.spring(response: 0.6, dampingFraction: 0.7)) { slid = true }
        try? await Task.sleep(nanoseconds: 750_000_000)
        faceOnPwn = false
        withAnimation(.easeInOut(duration: 0.75)) { jump = 1 }
        try? await Task.sleep(nanoseconds: 760_000_000)
        withAnimation(.spring(response: 0.4, dampingFraction: 0.5)) { litPhone = true }
        withAnimation(.easeIn(duration: 0.4)) { title = true }
        try? await Task.sleep(nanoseconds: 900_000_000)
        finish()
    }

    private func finish() {
        guard !fade else { return }
        withAnimation(.easeInOut(duration: 0.4)) { fade = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.42) { onDone() }
    }
}

/// Moves content along an arc (real per-frame curve via animatableData).
struct ArcJump: AnimatableModifier {
    var progress: Double
    let fromX: CGFloat
    let toX: CGFloat
    let arc: CGFloat
    var animatableData: Double { get { progress } set { progress = newValue } }
    func body(content: Content) -> some View {
        let x = fromX + (toX - fromX) * CGFloat(progress)
        let y = -arc * CGFloat(sin(Double.pi * progress))
        let s = 1 + 0.5 * CGFloat(sin(Double.pi * progress))
        return content.scaleEffect(s).offset(x: x, y: y)
    }
}

/// Stylized pwnagotchi: white case outline with a black e-ink screen.
struct PwnDevice: View {
    var showFace: Bool
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.white, lineWidth: 2)
                .background(RoundedRectangle(cornerRadius: 16).fill(Color(white: 0.08)))
            RoundedRectangle(cornerRadius: 8).fill(Color.black)
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Color.white.opacity(0.3)))
                .padding(12)
            if showFace {
                Text("(◕‿‿◕)").font(.system(size: 26, weight: .bold)).foregroundStyle(.white)
            }
        }
    }
}

/// Stylized phone: white outline, screen lights up with the face.
struct PhoneDevice: View {
    var lit: Bool
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 20)
                .stroke(Color.white, lineWidth: 2)
                .background(RoundedRectangle(cornerRadius: 20).fill(Color.black))
            RoundedRectangle(cornerRadius: 14)
                .fill(lit ? Color.white : Color(white: 0.06))
                .padding(8)
            if lit {
                Text("(◕‿‿◕)").font(.system(size: 22, weight: .bold)).foregroundStyle(.black)
            }
            // notch
            Capsule().fill(Color.white.opacity(0.5)).frame(width: 26, height: 4)
                .offset(y: -74)
        }
    }
}
