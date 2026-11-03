import Foundation
import UserNotifications

/// Local notifications: fired when the device catches new handshakes (while the
/// Dash is polling), and a sample when entering demo/beta mode. No server push.
enum Notify {
    /// Keeps a delegate alive so banners also show while the app is foreground.
    private static let delegate = ForegroundDelegate()

    static func requestAuth() {
        UNUserNotificationCenter.current().delegate = delegate
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    static func fire(_ title: String, _ body: String, after: TimeInterval = 0) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = .default
        let trigger = after > 0 ? UNTimeIntervalNotificationTrigger(timeInterval: after, repeats: false) : nil
        let req = UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: trigger)
        UNUserNotificationCenter.current().add(req)
    }

    /// Sample "beta" alert so demo users see how notifications look.
    static func demoSample() {
        requestAuth()
        fire("Beta mode · pwnagotchi", "New handshake captured: HomeWiFi 🐾 (demo notification)", after: 2.5)
    }
}

final class ForegroundDelegate: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }
}
