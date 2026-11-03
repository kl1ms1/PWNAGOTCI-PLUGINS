import SwiftUI

/// Handshake files (.pcap): list from the device, tap to download + share/save.
struct FilesView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var files: [String] = []
    @State private var loaded = false
    @State private var busy: String?
    @State private var shareURL: URL?

    var body: some View {
        ZStack {
            ThemeBG()
            List {
                ForEach(files, id: \.self) { name in
                    Button { download(name) } label: {
                        HStack {
                            Image(systemName: "doc.badge.arrow.up").foregroundStyle(.primary)
                            Text(name).font(.callout.monospaced()).lineLimit(1).truncationMode(.middle)
                            Spacer()
                            if busy == name { ProgressView() }
                            else { Image(systemName: "arrow.down.circle").foregroundStyle(.secondary) }
                        }
                    }
                    .listRowBackground(Color.primary.opacity(0.05))
                }
                if files.isEmpty {
                    Text(loaded ? "No .pcap files" : "Loading…")
                        .foregroundStyle(.secondary).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .refreshable { await load() }
        }
        .navigationTitle("Files · \(files.count)")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $shareURL) { url in
            ActivityView(items: [url])
        }
        .task { if !loaded { await load() } }
    }

    private func load() async {
        files = await PwnClient.fetchPcaps(conn)
        loaded = true
    }

    private func download(_ name: String) {
        busy = name
        Task {
            defer { busy = nil }
            guard let data = await PwnClient.pcapData(conn, name) else { return }
            let url = FileManager.default.temporaryDirectory.appendingPathComponent(name)
            try? data.write(to: url)
            shareURL = url
        }
    }
}

extension URL: Identifiable { public var id: String { absoluteString } }

/// UIActivityViewController wrapper (share/save a file).
struct ActivityView: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}
