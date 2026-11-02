import SwiftUI
import WebKit

/// Opens the pwnagotchi web UI inside the app, handling basic-auth with the
/// stored login/password (challenge-based, so sub-resources authenticate too).
struct WebUIView: UIViewRepresentable {
    let url: URL
    let user: String
    let pass: String

    func makeCoordinator() -> Coordinator { Coordinator(user: user, pass: pass) }

    func makeUIView(context: Context) -> WKWebView {
        let wv = WKWebView()
        wv.navigationDelegate = context.coordinator
        wv.load(URLRequest(url: url))
        return wv
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        let user: String
        let pass: String
        init(user: String, pass: String) { self.user = user; self.pass = pass }

        func webView(_ webView: WKWebView,
                     didReceive challenge: URLAuthenticationChallenge,
                     completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
            let method = challenge.protectionSpace.authenticationMethod
            if method == NSURLAuthenticationMethodHTTPBasic
                || method == NSURLAuthenticationMethodHTTPDigest
                || method == NSURLAuthenticationMethodDefault {
                if challenge.previousFailureCount == 0 {
                    let cred = URLCredential(user: user, password: pass, persistence: .forSession)
                    completionHandler(.useCredential, cred)
                } else {
                    completionHandler(.cancelAuthenticationChallenge, nil)
                }
            } else {
                completionHandler(.performDefaultHandling, nil)
            }
        }
    }
}

/// A sheet wrapper with a close button and the device address in the title.
struct WebUISheet: View {
    let url: URL
    let user: String
    let pass: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            WebUIView(url: url, user: user, pass: pass)
                .ignoresSafeArea(edges: .bottom)
                .navigationTitle("Web UI")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Готово") { dismiss() }
                    }
                }
        }
    }
}
