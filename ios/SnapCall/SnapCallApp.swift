import SwiftUI
import WebKit

/// Snap Call for iPhone and iPad: the look preview game (both rule sets), played from files inside the app.
/// The pages come from `python3 build.py --app-web ios/SnapCall/web`, which Xcode runs before every build.
@main
struct SnapCallApp: App {
    var body: some Scene {
        WindowGroup {
            GameView()
                .ignoresSafeArea()
                .background(Color("LaunchBackground").ignoresSafeArea())
                .preferredColorScheme(.dark)
        }
    }
}

struct GameView: UIViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.setURLSchemeHandler(GameFiles(), forURLScheme: GameFiles.scheme)
        // Browser storage (Hard memory, level, game length) stays on the device between launches.
        config.websiteDataStore = .default()
        // The home screen asks for a light tap when you press Start game (window.webkit.messageHandlers.haptic).
        config.userContentController.add(context.coordinator, name: "haptic")

        let web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = context.coordinator
        web.allowsLinkPreview = false
        web.allowsBackForwardNavigationGestures = false
        web.isOpaque = false
        web.backgroundColor = UIColor(named: "LaunchBackground")
        web.scrollView.backgroundColor = UIColor(named: "LaunchBackground")
        // The page pads itself for the notch and home bar (viewport-fit=cover + env(safe-area-inset-*)).
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.scrollView.bounces = false
        var start = GameFiles.start
        #if DEBUG
        web.isInspectable = true
        // Test hooks for debug builds (simctl launch with SIMCTL_CHILD_SNAPCALL_START / SNAPCALL_JS): open a given
        // page, and run a script after each page load, printing its result and any page errors to the console.
        let env = ProcessInfo.processInfo.environment
        if let path = env["SNAPCALL_START"], let url = URL(string: path, relativeTo: GameFiles.start) { start = url }
        if env["SNAPCALL_JS"] != nil {
            let errors = "window.__errs = []; addEventListener('error', e => __errs.push(e.message));"
                + " addEventListener('unhandledrejection', e => __errs.push(String(e.reason)));"
            config.userContentController.addUserScript(
                WKUserScript(source: errors, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
        #endif
        web.load(URLRequest(url: start))
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        private let tap = UIImpactFeedbackGenerator(style: .light)

        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
            if message.name == "haptic" { tap.impactOccurred() }
        }

        // Game pages open in the app; anything on the web opens in Safari.
        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = action.request.url, let scheme = url.scheme?.lowercased() else {
                decisionHandler(.cancel)
                return
            }
            if scheme == GameFiles.scheme || scheme == "about" || scheme == "data" || scheme == "blob" {
                decisionHandler(.allow)
            } else if action.targetFrame?.isMainFrame ?? true, scheme == "http" || scheme == "https" {
                if action.navigationType == .linkActivated || action.targetFrame == nil {
                    UIApplication.shared.open(url)
                    decisionHandler(.cancel)
                } else {
                    decisionHandler(.allow)
                }
            } else {
                decisionHandler(.allow)
            }
        }

        #if DEBUG
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            guard let js = ProcessInfo.processInfo.environment["SNAPCALL_JS"] else { return }
            webView.callAsyncJavaScript(js, arguments: [:], in: nil, in: .page) { result in
                switch result {
                case .success(let value): print("SNAPCALL_JS ok:", value ?? "nil")
                case .failure(let error): print("SNAPCALL_JS error:", error)
                }
            }
        }
        #endif

        // If iOS ever drops the page in the background, load it again instead of showing a blank screen.
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            webView.load(URLRequest(url: GameFiles.start))
        }
    }
}

/// Serves the bundled game files at snapcall://game/..., so the pages behave as they do on a web server:
/// a folder address opens its index.html (downs/?new=28), and relative card paths (../cards/) resolve.
final class GameFiles: NSObject, WKURLSchemeHandler {
    static let scheme = "snapcall"
    static let start = URL(string: "snapcall://game/")!
    private let root = Bundle.main.resourceURL!.appendingPathComponent("web", isDirectory: true).standardizedFileURL

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let url = task.request.url else { return }
        let path = URLComponents(url: url, resolvingAgainstBaseURL: false)?.percentEncodedPath.removingPercentEncoding ?? "/"
        var file = root.appendingPathComponent(String(path.drop(while: { $0 == "/" }))).standardizedFileURL
        var isFolder: ObjCBool = false
        if FileManager.default.fileExists(atPath: file.path, isDirectory: &isFolder), isFolder.boolValue {
            file.appendPathComponent("index.html")
        }
        let inside = file.path.hasPrefix(root.path + "/")
        guard inside, let data = try? Data(contentsOf: file) else {
            let missing = HTTPURLResponse(url: url, statusCode: 404, httpVersion: "HTTP/1.1", headerFields: nil)!
            task.didReceive(missing)
            task.didReceive(Data())
            task.didFinish()
            return
        }
        let headers = ["Content-Type": Self.type(of: file.pathExtension), "Content-Length": String(data.count),
                       "Cache-Control": "no-cache"]
        task.didReceive(HTTPURLResponse(url: url, statusCode: 200, httpVersion: "HTTP/1.1", headerFields: headers)!)
        task.didReceive(data)
        task.didFinish()
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}

    private static func type(of ext: String) -> String {
        switch ext.lowercased() {
        case "html": return "text/html; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "js": return "text/javascript; charset=utf-8"
        case "json": return "application/json"
        case "webp": return "image/webp"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "svg": return "image/svg+xml"
        case "woff2": return "font/woff2"
        case "woff": return "font/woff"
        case "ttf": return "font/ttf"
        default: return "application/octet-stream"
        }
    }
}
