import SwiftUI

/// Root filesystem browser: navigate, view/edit text, download, create, delete.
/// For your own device only (companion fs_* endpoints run as root).
struct FilesView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var path = "/root"
    @State private var listing = FsListing(ok: false, path: "/root", items: [], err: nil)
    @State private var loaded = false
    @State private var openFile: String?
    @State private var newName = ""
    @State private var newKind: NewKind?
    @State private var toast = ""

    enum NewKind: Identifiable { case file, folder; var id: Int { self == .file ? 0 : 1 } }

    private let quick: [(String, String)] = [
        ("/root", "house"), ("config", "gearshape"), ("/etc", "folder"),
        ("/home/pi", "person"), ("handshakes", "wave.3.right"),
    ]

    var body: some View {
        ZStack {
            ThemeBG()
            VStack(spacing: 0) {
                // path bar
                HStack(spacing: 8) {
                    Button { goUp() } label: { Image(systemName: "arrow.up.left.circle") }
                        .disabled(path == "/")
                    Text(path).font(.caption.monospaced()).lineLimit(1).truncationMode(.head)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Button { Task { await load() } } label: { Image(systemName: "arrow.clockwise") }
                }
                .padding(.horizontal).padding(.vertical, 8)

                // quick jumps
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(quick, id: \.0) { label, icon in
                            Button { path = resolveQuick(label); Task { await load() } } label: {
                                Label(label, systemImage: icon).font(.caption2)
                                    .padding(.horizontal, 10).padding(.vertical, 6)
                            }
                            .background(.primary.opacity(0.08), in: Capsule())
                        }
                    }.padding(.horizontal)
                }
                .frame(height: 36)

                if !toast.isEmpty {
                    Text(toast).font(.caption).foregroundStyle(.secondary).padding(.vertical, 4)
                }

                List {
                    ForEach(listing.items) { it in
                        Button { tap(it) } label: {
                            HStack {
                                Image(systemName: it.dir ? "folder.fill" : fileIcon(it.name))
                                    .foregroundStyle(it.dir ? .primary : .secondary).frame(width: 22)
                                Text(it.name).font(.callout).lineLimit(1).truncationMode(.middle)
                                Spacer()
                                if it.dir { Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.tertiary) }
                                else { Text(sizeStr(it.size)).font(.caption2).foregroundStyle(.secondary) }
                            }
                        }
                        .listRowBackground(Color.primary.opacity(0.05))
                        .swipeActions {
                            Button(role: .destructive) { delete(it) } label: { Label("Delete", systemImage: "trash") }
                        }
                    }
                    if listing.items.isEmpty {
                        Text(loaded ? (listing.err ?? "Empty") : "Loading…")
                            .foregroundStyle(.secondary).listRowBackground(Color.clear)
                    }
                }
                .scrollContentBackground(.hidden)
                .refreshable { await load() }
            }
        }
        .navigationTitle("Files")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button { newName = ""; newKind = .file } label: { Label("New file", systemImage: "doc.badge.plus") }
                    Button { newName = ""; newKind = .folder } label: { Label("New folder", systemImage: "folder.badge.plus") }
                } label: { Image(systemName: "plus") }
            }
        }
        .sheet(item: Binding(get: { openFile.map { IdPath(path: $0) } },
                             set: { openFile = $0?.path })) { ip in
            FileSheet(path: ip.path) { Task { await load() } }
        }
        .alert(newKind == .folder ? "New folder" : "New file", isPresented: Binding(
            get: { newKind != nil }, set: { if !$0 { newKind = nil } })) {
            TextField("name", text: $newName)
            Button("Cancel", role: .cancel) { newKind = nil }
            Button("Create") { create() }
        }
        .task { if !loaded { await load() } }
    }

    private func resolveQuick(_ label: String) -> String {
        switch label {
        case "config": return "/etc/pwnagotchi"
        case "handshakes": return "/root/handshakes"
        default: return label
        }
    }

    private func load() async {
        listing = await PwnClient.fsList(conn, path)
        if listing.ok { path = listing.path }
        loaded = true
    }

    private func goUp() {
        guard path != "/" else { return }
        path = (path as NSString).deletingLastPathComponent
        if path.isEmpty { path = "/" }
        Task { await load() }
    }

    private func tap(_ it: FileEntry) {
        let full = (path as NSString).appendingPathComponent(it.name)
        if it.dir { path = full; Task { await load() } }
        else { openFile = full }
    }

    private func delete(_ it: FileEntry) {
        let full = (path as NSString).appendingPathComponent(it.name)
        Task {
            let ok = await PwnClient.fsDelete(conn, full, recursive: it.dir)
            toast = ok ? "Deleted \(it.name)" : "Delete failed"
            await load()
        }
    }

    private func create() {
        let name = newName.trimmingCharacters(in: .whitespaces)
        let kind = newKind
        newKind = nil
        guard !name.isEmpty else { return }
        let full = (path as NSString).appendingPathComponent(name)
        Task {
            let ok: Bool
            if kind == .folder { ok = await PwnClient.fsMkdir(conn, full) }
            else { ok = (await PwnClient.fsWrite(conn, full, "")).0 }
            toast = ok ? "Created \(name)" : "Create failed"
            await load()
        }
    }

    private func fileIcon(_ n: String) -> String {
        let l = n.lowercased()
        if l.hasSuffix(".pcap") { return "wave.3.right" }
        if l.hasSuffix(".toml") || l.hasSuffix(".json") || l.hasSuffix(".yml") || l.hasSuffix(".conf") { return "doc.text" }
        if l.hasSuffix(".py") || l.hasSuffix(".sh") { return "chevron.left.forwardslash.chevron.right" }
        if l.hasSuffix(".log") { return "doc.plaintext" }
        return "doc"
    }

    private func sizeStr(_ b: Int) -> String {
        if b >= 1_048_576 { return String(format: "%.1fM", Double(b) / 1_048_576) }
        if b >= 1024 { return String(format: "%.0fK", Double(b) / 1024) }
        return "\(b)B"
    }
}

private struct IdPath: Identifiable { let path: String; var id: String { path } }

/// View/edit/download/delete a single file.
struct FileSheet: View {
    @EnvironmentObject var conn: ConnectionStore
    let path: String
    let onChange: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var isText = false
    @State private var loaded = false
    @State private var msg = ""
    @State private var busy = false
    @State private var shareURL: URL?

    var body: some View {
        NavigationStack {
            ZStack {
                ThemeBG()
                VStack(spacing: 0) {
                    if !loaded {
                        ProgressView().tint(.primary).frame(maxHeight: .infinity)
                    } else if isText {
                        TextEditor(text: $text)
                            .font(.callout.monospaced()).scrollContentBackground(.hidden)
                            .padding(8).background(Color.primary.opacity(0.04))
                            .autocorrectionDisabled().textInputAutocapitalization(.never)
                    } else {
                        VStack(spacing: 14) {
                            Image(systemName: "doc.fill").font(.system(size: 44)).foregroundStyle(.secondary)
                            Text(msg.isEmpty ? "Binary file — download to view." : msg)
                                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        }.frame(maxHeight: .infinity).padding()
                    }
                    if !msg.isEmpty && isText {
                        Text(msg).font(.caption).foregroundStyle(.secondary).padding(6)
                    }
                    HStack(spacing: 10) {
                        if isText {
                            Button { save() } label: { Label("Save", systemImage: "square.and.arrow.down") }
                                .buttonStyle(FilledStyle()).disabled(busy)
                        }
                        Button { download() } label: {
                            Label("Download", systemImage: "arrow.down.circle").frame(maxWidth: .infinity)
                        }.buttonStyle(.bordered)
                    }.padding()
                }
            }
            .navigationTitle((path as NSString).lastPathComponent)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button(role: .destructive) { delete() } label: { Image(systemName: "trash") }
                }
            }
            .sheet(item: $shareURL) { url in ActivityView(items: [url]) }
            .task { await load() }
        }
    }

    private func load() async {
        let (ok, t, content, m) = await PwnClient.fsRead(conn, path)
        isText = ok && t
        text = content
        msg = ok ? "" : m
        if ok && !t { msg = m }
        loaded = true
    }

    private func save() {
        busy = true
        Task {
            let (ok, m) = await PwnClient.fsWrite(conn, path, text)
            msg = ok ? "Saved ✓" : "Save failed: \(m)"
            busy = false
            onChange()
        }
    }

    private func delete() {
        Task {
            _ = await PwnClient.fsDelete(conn, path)
            onChange(); dismiss()
        }
    }

    private func download() {
        Task {
            guard let data = await PwnClient.fsDownload(conn, path) else { msg = "Download failed"; return }
            let url = FileManager.default.temporaryDirectory.appendingPathComponent((path as NSString).lastPathComponent)
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
