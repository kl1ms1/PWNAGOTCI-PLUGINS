import SwiftUI
import MapKit
import CoreLocation
import UniformTypeIdentifiers

// MARK: - Location

final class LocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let mgr = CLLocationManager()
    @Published var coord: CLLocationCoordinate2D?

    override init() {
        super.init()
        mgr.delegate = self
        mgr.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
    }

    func start() {
        mgr.requestWhenInUseAuthorization()
        mgr.startUpdatingLocation()
    }

    func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        if let c = locs.last?.coordinate { coord = c }
    }
    func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {}
}

// MARK: - Catch pins (persisted locally; the phone supplies the GPS)

struct CatchPin: Identifiable, Codable {
    var id: String          // network MAC
    var ssid: String
    var lat: Double
    var lon: Double
    var date: Double
    var coord: CLLocationCoordinate2D { .init(latitude: lat, longitude: lon) }
}

final class MapStore: ObservableObject {
    @Published private(set) var pins: [CatchPin] = []
    private let key = "catchPins"

    init() { load() }

    private func load() {
        if let d = UserDefaults.standard.data(forKey: key),
           let arr = try? JSONDecoder().decode([CatchPin].self, from: d) {
            pins = arr
        }
    }
    private func save() {
        if let d = try? JSONEncoder().encode(pins) {
            UserDefaults.standard.set(d, forKey: key)
        }
    }

    /// Stamp newly-cracked networks with the phone's current location (once each).
    func tag(_ nets: [NetItem], at coord: CLLocationCoordinate2D?) {
        guard let c = coord else { return }
        var changed = false
        let known = Set(pins.map { $0.id })
        for n in nets where !n.pw.isEmpty && !known.contains(n.mac) {
            pins.append(CatchPin(id: n.mac, ssid: n.ssid,
                                 lat: c.latitude, lon: c.longitude, date: Date().timeIntervalSince1970))
            changed = true
        }
        if changed { save() }
    }

    func clear() { pins = []; save() }

    /// Merge imported pins (dedupe by MAC) so maps can be shared between phones.
    func merge(_ incoming: [CatchPin]) {
        var known = Set(pins.map { $0.id })
        var changed = false
        for p in incoming where !known.contains(p.id) {
            pins.append(p); known.insert(p.id); changed = true
        }
        if changed { save() }
    }
}

// MARK: - Map tab

struct MapView: View {
    @EnvironmentObject var conn: ConnectionStore
    @StateObject private var loc = LocationManager()
    @StateObject private var store = MapStore()
    @State private var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 45.0, longitude: 39.0),
        span: MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05))
    @State private var centered = false

    @State private var selectedPin: CatchPin?
    @State private var shareURL: URL?
    @State private var importing = false
    @State private var importMsg = ""
    private var pins: [CatchPin] { conn.demo ? DemoData.pins() : store.pins }

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                Map(coordinateRegion: $region, showsUserLocation: true,
                    annotationItems: pins) { pin in
                    MapAnnotation(coordinate: pin.coord) {
                        Button { selectedPin = pin } label: {
                            VStack(spacing: 2) {
                                Image(systemName: "wifi")
                                    .font(.system(size: 13, weight: .bold)).foregroundStyle(.white)
                                    .padding(7)
                                    .background(Color.black, in: Circle())
                                    .overlay(Circle().strokeBorder(.white.opacity(0.8), lineWidth: 1.5))
                                Text(pin.ssid).font(.caption2.weight(.semibold))
                                    .padding(.horizontal, 5).padding(.vertical, 1)
                                    .background(.ultraThinMaterial, in: Capsule())
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .ignoresSafeArea(edges: .top)

                GlassCard {
                    HStack {
                        Image(systemName: "mappin.and.ellipse").foregroundStyle(.primary)
                        Text("Catches: \(pins.count)")
                            .font(.subheadline)
                        if !importMsg.isEmpty {
                            Text("· \(importMsg)").font(.caption2).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button {
                            if let c = loc.coord {
                                region = MKCoordinateRegion(center: c,
                                    span: MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02))
                            }
                        } label: { Image(systemName: "location.fill") }
                    }
                }
                .padding()
                .sheet(item: $shareURL) { url in ActivityView(items: [url]) }
            }
            .navigationTitle("Catch map")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button { export() } label: { Label("Export map (.json)", systemImage: "square.and.arrow.up") }
                        Button { importing = true } label: { Label("Import map (.json)", systemImage: "square.and.arrow.down") }
                        if !conn.demo {
                            Button(role: .destructive) { store.clear() } label: { Label("Clear pins", systemImage: "trash") }
                        }
                    } label: { Image(systemName: "ellipsis.circle") }
                }
            }
            .sheet(item: $selectedPin) { pin in PinSheet(pin: pin) }
            .fileImporter(isPresented: $importing, allowedContentTypes: [.json]) { result in
                handleImport(result)
            }
        }
        .task {
            if conn.demo {
                if let first = DemoData.pins().first {
                    region = MKCoordinateRegion(center: first.coord,
                        span: MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02))
                }
                return
            }
            loc.start()
            while !Task.isCancelled {
                if !centered, let c = loc.coord {
                    region = MKCoordinateRegion(center: c,
                        span: MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02))
                    centered = true
                }
                if let nets = try? await PwnClient.fetchPwndex(conn) {
                    store.tag(nets, at: loc.coord)
                }
                try? await Task.sleep(nanoseconds: 5_000_000_000)
            }
        }
    }

    private func export() {
        guard let data = try? JSONEncoder().encode(pins) else { return }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("pwn-map-\(Int(Date().timeIntervalSince1970)).json")
        try? data.write(to: url)
        shareURL = url
    }

    private func handleImport(_ result: Result<URL, Error>) {
        guard case .success(let url) = result else { importMsg = "import failed"; return }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url),
              let arr = try? JSONDecoder().decode([CatchPin].self, from: data) else {
            importMsg = "bad file"; return
        }
        let before = store.pins.count
        store.merge(arr)
        importMsg = "+\(store.pins.count - before) imported"
    }
}

/// Tap a map bubble -> this menu (ssid + real actions, like pwndex).
struct PinSheet: View {
    @EnvironmentObject var conn: ConnectionStore
    let pin: CatchPin
    @State private var msg = ""
    @State private var busy = false
    @State private var shareURL: URL?
    @State private var pw = ""
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Network") {
                    Text(pin.ssid).font(.headline)
                    Text(pin.id).font(.caption).foregroundStyle(.secondary)
                    Text(String(format: "%.5f, %.5f", pin.lat, pin.lon))
                        .font(.caption2).foregroundStyle(.secondary)
                }
                Section("Password (if your network)") {
                    TextField("password", text: $pw)
                        .autocorrectionDisabled().textInputAutocapitalization(.never)
                    Button { savePassword() } label: { Label("Save password", systemImage: "key.fill") }
                }
                Section("Actions") {
                    Button { downloadHash() } label: { Label("Download hash (.pcap)", systemImage: "arrow.down.doc") }
                    Button { whitelist() } label: { Label("Add to whitelist", systemImage: "checkmark.shield") }
                    Button { upload() } label: { Label("Upload to wpa-sec", systemImage: "arrow.up.circle") }
                }
                if busy { Section { HStack { ProgressView(); Text("Working…").foregroundStyle(.secondary) } } }
                if !msg.isEmpty { Section { Text(msg + (conn.demo ? " (demo)" : "")).foregroundStyle(.secondary) } }
            }
            .navigationTitle(pin.ssid).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
            .sheet(item: $shareURL) { url in ActivityView(items: [url]) }
        }
    }

    private func savePassword() {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            let ok = (try? await PwnClient.setPassword(conn, mac: pin.id, pw: pw)) ?? false
            msg = ok ? "✅ Saved & synced to Pwndex" : "❌ Save failed"
        }
    }

    private func downloadHash() {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            if conn.demo {
                let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(pin.ssid).pcap")
                try? Data("demo handshake".utf8).write(to: url); shareURL = url; return
            }
            guard let (name, data) = await PwnClient.pcapForMac(conn, pin.id) else {
                msg = "❌ No .pcap for this network yet"; return
            }
            let url = FileManager.default.temporaryDirectory.appendingPathComponent(name)
            try? data.write(to: url); shareURL = url
        }
    }

    private func whitelist() {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            let (ok, m, _) = await PwnClient.whitelistSet(conn, ssid: pin.ssid, add: true)
            msg = (ok ? "✅ " : "❌ ") + (m.isEmpty ? "done" : m)
        }
    }

    private func upload() {
        busy = true; msg = ""
        Task {
            defer { busy = false }
            let (ok, m) = await PwnClient.uploadAll(conn)
            msg = (ok ? "✅ " : "❌ ") + (m.isEmpty ? "triggered" : m)
        }
    }
}
