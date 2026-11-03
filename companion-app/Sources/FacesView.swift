import SwiftUI

/// Customize the pwnagotchi ASCII faces (ui.faces.* in config.toml).
struct FacesView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var faces: [String: String] = [:]
    @State private var loaded = false
    @State private var msg = ""
    @State private var busy = false

    // curated, ordered subset of the faces pwnagotchi uses most
    private let keys = ["LOOK_R", "LOOK_L", "AWAKE", "SLEEP", "HAPPY", "GRATEFUL",
                        "EXCITED", "MOTIVATED", "BORED", "SAD", "LONELY", "INTENSE",
                        "COOL", "SMART", "FRIEND", "BROKEN", "DEBUG", "UPLOAD"]

    var body: some View {
        ZStack {
            ThemeBG()
            Form {
                Section {
                    Text("Edit the faces shown on the device screen. Monospace recommended. Applies after a restart.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("Faces") {
                    ForEach(keys, id: \.self) { k in
                        HStack {
                            Text(k).font(.caption2.monospaced()).foregroundStyle(.secondary)
                                .frame(width: 92, alignment: .leading)
                            TextField("(◕‿‿◕)", text: Binding(
                                get: { faces[k] ?? "" },
                                set: { faces[k] = $0 }))
                                .font(.callout.monospaced())
                                .autocorrectionDisabled().textInputAutocapitalization(.never)
                                .multilineTextAlignment(.trailing)
                        }
                    }
                }
                Section {
                    Button { save() } label: {
                        HStack { if busy { ProgressView() }; Text("Save faces").frame(maxWidth: .infinity) }
                    }.buttonStyle(FilledStyle()).disabled(busy)
                    if !msg.isEmpty { Text(msg).font(.footnote).foregroundStyle(.secondary) }
                }
                .listRowBackground(Color.clear)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Faces")
        .navigationBarTitleDisplayMode(.inline)
        .task { if !loaded { faces = await PwnClient.cfgGetDict(conn, "ui.faces"); loaded = true } }
    }

    private func save() {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            var okAll = true
            for k in keys {
                let v = (faces[k] ?? "").trimmingCharacters(in: .whitespaces)
                guard !v.isEmpty else { continue }
                let (ok, _) = await PwnClient.cfgSet(conn, "ui.faces.\(k)", v, quote: true)
                okAll = okAll && ok
            }
            msg = okAll ? "✅ Saved. Restart pwnagotchi to apply (Control → Restart)."
                        : "⚠️ Some faces failed to save."
        }
    }
}
