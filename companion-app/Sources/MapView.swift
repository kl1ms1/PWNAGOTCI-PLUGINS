import SwiftUI
import MapKit
import CoreLocation

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

    private var pins: [CatchPin] { conn.demo ? DemoData.pins() : store.pins }

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                Map(coordinateRegion: $region, showsUserLocation: true,
                    annotationItems: pins) { pin in
                    MapAnnotation(coordinate: pin.coord) {
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
                }
                .ignoresSafeArea(edges: .top)

                GlassCard {
                    HStack {
                        Image(systemName: "mappin.and.ellipse").foregroundStyle(.primary)
                        Text("Уловов на карте: \(pins.count)")
                            .font(.subheadline)
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
            }
            .navigationTitle("Карта уловов")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
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
}
