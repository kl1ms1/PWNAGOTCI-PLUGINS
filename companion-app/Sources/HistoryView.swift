import SwiftUI

/// Live history charts for CPU, temperature, RAM and battery (session rolling).
struct HistoryView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var cpu: [Double] = []
    @State private var temp: [Double] = []
    @State private var mem: [Double] = []
    @State private var bat: [Double] = []

    var body: some View {
        ZStack {
            ThemeBG()
            ScrollView {
                VStack(spacing: 14) {
                    MetricChart(title: "CPU", unit: "%", values: cpu)
                    MetricChart(title: "Temperature", unit: "°C", values: temp)
                    MetricChart(title: "RAM", unit: "%", values: mem)
                    MetricChart(title: "Battery", unit: "%", values: bat)
                    Text("Rolling history for this session (polls every 2s).")
                        .font(.caption2).foregroundStyle(.secondary)
                }.padding()
            }
        }
        .navigationTitle("History")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loop() }
    }

    private func loop() async {
        while !Task.isCancelled {
            if let s = try? await PwnClient.fetchStatus(conn) {
                if let v = s.cpu { push(&cpu, v) }
                if let v = s.temp { push(&temp, v) }
                if let v = s.mem { push(&mem, v) }
                if let v = s.battery { push(&bat, v) }
            }
            try? await Task.sleep(nanoseconds: 2_000_000_000)
        }
    }

    private func push(_ a: inout [Double], _ v: Double) {
        a.append(v); if a.count > 60 { a.removeFirst() }
    }
}

struct MetricChart: View {
    let title: String
    let unit: String
    let values: [Double]
    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(title).font(.subheadline.weight(.semibold))
                    Spacer()
                    if let last = values.last {
                        Text("\(fmt(last))\(unit)").font(.title3.weight(.bold))
                    } else {
                        Text("—").foregroundStyle(.secondary)
                    }
                }
                GeometryReader { geo in
                    ZStack {
                        if values.count > 1 {
                            let maxV = values.max() ?? 1, minV = values.min() ?? 0
                            let range = Swift.max(maxV - minV, 0.001)
                            let pts: [CGPoint] = values.enumerated().map { i, v in
                                CGPoint(x: geo.size.width * CGFloat(i) / CGFloat(values.count - 1),
                                        y: geo.size.height * (1 - CGFloat((v - minV) / range)))
                            }
                            Path { p in
                                p.move(to: CGPoint(x: pts[0].x, y: geo.size.height))
                                for pt in pts { p.addLine(to: pt) }
                                p.addLine(to: CGPoint(x: pts.last!.x, y: geo.size.height))
                                p.closeSubpath()
                            }.fill(.primary.opacity(0.08))
                            Path { p in
                                p.move(to: pts[0])
                                for pt in pts.dropFirst() { p.addLine(to: pt) }
                            }.stroke(Color.primary, style: StrokeStyle(lineWidth: 2, lineJoin: .round))
                        } else {
                            Text("collecting…").font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }.frame(height: 70)
                if values.count > 1 {
                    HStack {
                        Text("min \(fmt(values.min() ?? 0))").font(.caption2).foregroundStyle(.secondary)
                        Spacer()
                        Text("max \(fmt(values.max() ?? 0))").font(.caption2).foregroundStyle(.secondary)
                        Spacer()
                        Text("avg \(fmt(values.reduce(0,+)/Double(values.count)))").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
    private func fmt(_ v: Double) -> String { String(format: "%.0f", v) }
}
