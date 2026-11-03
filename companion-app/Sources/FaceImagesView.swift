import SwiftUI
import PhotosUI

/// Upload a custom PNG image for a face slot (ui.faces.png + ui.faces.<KEY>).
/// Needs the device to support PNG faces (jayofelony custom-faces mod).
struct FaceImagesView: View {
    @EnvironmentObject var conn: ConnectionStore
    @State private var key = "HAPPY"
    @State private var item: PhotosPickerItem?
    @State private var image: UIImage?
    @State private var msg = ""
    @State private var busy = false

    private let keys = ["AWAKE", "LOOK_R", "LOOK_L", "SLEEP", "HAPPY", "GRATEFUL",
                        "EXCITED", "MOTIVATED", "BORED", "SAD", "LONELY", "INTENSE",
                        "COOL", "SMART", "FRIEND", "BROKEN", "DEBUG", "UPLOAD"]

    var body: some View {
        ZStack {
            ThemeBG()
            ScrollView {
                VStack(spacing: 16) {
                    Text("Pick a face slot, choose a PNG, upload. Sets ui.faces.png = true and points that face at the image on the device. Applies after a restart.")
                        .font(.footnote).foregroundStyle(.secondary)

                    Picker("Face", selection: $key) {
                        ForEach(keys, id: \.self) { Text($0).tag($0) }
                    }.pickerStyle(.menu)

                    ZStack {
                        RoundedRectangle(cornerRadius: 14).fill(Color.black)
                        if let img = image {
                            Image(uiImage: img).resizable().interpolation(.none)
                                .aspectRatio(contentMode: .fit).padding(8)
                        } else {
                            Text("no image").foregroundStyle(.gray)
                        }
                    }.frame(height: 150)

                    PhotosPicker(selection: $item, matching: .images) {
                        Label("Choose PNG", systemImage: "photo").frame(maxWidth: .infinity)
                    }.buttonStyle(.bordered)

                    Button { upload() } label: {
                        HStack { if busy { ProgressView() }; Text("Upload to \(key)").frame(maxWidth: .infinity) }
                    }.buttonStyle(FilledStyle()).disabled(busy || image == nil)

                    if !msg.isEmpty { Text(msg).font(.footnote).foregroundStyle(.secondary) }
                }.padding()
            }
        }
        .navigationTitle("Face images")
        .navigationBarTitleDisplayMode(.inline)
        .onChange(of: item) { newItem in
            Task {
                if let data = try? await newItem?.loadTransferable(type: Data.self),
                   let ui = UIImage(data: data) { image = ui }
            }
        }
    }

    private func upload() {
        guard let img = image, let png = img.pngData() else { msg = "Not a valid image"; return }
        busy = true; msg = ""
        Task {
            defer { busy = false }
            let (ok, m) = await PwnClient.setFacePng(conn, key: key, png: png)
            msg = (ok ? "✅ Uploaded. Restart pwnagotchi to apply." : "❌ \(m)")
                + (conn.demo ? " (demo)" : "")
        }
    }
}
