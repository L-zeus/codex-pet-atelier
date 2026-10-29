import AppKit
import Foundation
import Darwin

// The panel is non-activating: it leaves the current app's input focus alone.
final class QuotaPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
    override func cancelOperation(_ sender: Any?) { close() }
    override func sendEvent(_ event: NSEvent) {
        // A deliberate click enables keyboard dismissal; opening remains non-activating.
        if event.type == .leftMouseDown { makeKey() }
        if event.type == .keyDown && event.keyCode == 53 { close(); return }
        super.sendEvent(event)
    }
    override func keyDown(with event: NSEvent) {
        if event.keyCode == 53 { close() } else { super.keyDown(with: event) }
    }
}

struct Configuration: Decodable {
    let python: String
    let codexCLI: String?
    let codexHome: String?
}
struct WindowQuota: Decodable {
    let durationMins: Double?
    let usedPercent: Double?
    let remainingPercent: Double?
    let resetsAt: Double?
}
struct Bucket: Decodable {
    let id: String
    let name: String?
    let windows: [WindowQuota]
    let rateLimitReachedType: String?
}
struct Snapshot: Decodable {
    let status: String
    let fetchedAt: String
    let buckets: [Bucket]
    let ordinaryUsageAllowed: Bool?
    let message: String?
}

final class FlippedView: NSView {
    override var isFlipped: Bool { true }
    override var needsPanelToBecomeKey: Bool { true }
    override var acceptsFirstResponder: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

final class ActionButton: NSButton {
    // A non-activating panel must respond to the very first mouse click.
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

final class BubbleController: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private var panel: QuotaPanel!
    private var scroll: NSScrollView!
    private let lock = NSLock()
    private var task: Process?
    private var closing = false
    private var timeoutWork: DispatchWorkItem?
    private let width: CGFloat = 360
    private let side: CGFloat = 19
    private var y: CGFloat = 0
    private var document: FlippedView!
    private let format: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_CN")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd HH:mm:ss z"
        return f
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        panel = QuotaPanel(contentRect: NSRect(x: 0, y: 0, width: width, height: 190),
                           styleMask: [.borderless, .nonactivatingPanel],
                           backing: .buffered, defer: false)
        panel.delegate = self
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.becomesKeyOnlyIfNeeded = true
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .transient]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        let background = NSVisualEffectView()
        background.material = .popover
        background.blendingMode = .behindWindow
        background.state = .active
        background.wantsLayer = true
        background.layer?.cornerRadius = 18
        background.layer?.masksToBounds = true
        panel.contentView = background
        scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: width, height: 190))
        scroll.autoresizingMask = [.width, .height]
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        background.addSubview(scroll)
        showLoading()
        placePanel()
        panel.orderFrontRegardless()
        // Give AppKit an opportunity to render the loading state before starting the CLI.
        DispatchQueue.main.async { self.startQuery() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !closing {
            if panel.isVisible {
                panel.close()
            } else {
                placePanel()
                panel.orderFrontRegardless()
                if task == nil { showLoading(); startQuery() }
            }
        }
        return false
    }

    private func placePanel() {
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first(where: { $0.frame.contains(mouse) }) ?? NSScreen.main
        guard let visible = screen?.visibleFrame else { return }
        let frame = panel.frame
        panel.setFrameOrigin(NSPoint(x: max(visible.minX, visible.maxX - frame.width - 16),
                                     y: max(visible.minY, visible.maxY - frame.height - 16)))
    }

    private func label(_ text: String, size: CGFloat, weight: NSFont.Weight = .regular,
                       color: NSColor = .labelColor, height: CGFloat = 20) {
        let field = NSTextField(wrappingLabelWithString: text)
        field.font = .systemFont(ofSize: size, weight: weight)
        field.textColor = color
        field.frame = NSRect(x: side, y: y, width: width - 2 * side, height: height)
        document.addSubview(field)
        y += height
    }

    private func button(_ title: String, action: Selector, x: CGFloat, buttonWidth: CGFloat) -> NSButton {
        let b = ActionButton(title: title, target: self, action: action)
        b.bezelStyle = .rounded
        b.frame = NSRect(x: x, y: y, width: buttonWidth, height: 28)
        document.addSubview(b)
        return b
    }

    private func beginContent() {
        document = FlippedView(frame: NSRect(x: 0, y: 0, width: width, height: 500))
        scroll.documentView = document
        y = 17
        let close = ActionButton(title: "×", target: self, action: #selector(closeBubble))
        close.isBordered = false
        close.font = .systemFont(ofSize: 22, weight: .regular)
        close.toolTip = "关闭"
        close.setAccessibilityLabel("关闭额度气泡")
        close.frame = NSRect(x: width - 45, y: 8, width: 30, height: 30)
        document.addSubview(close)
        label("Codex 额度", size: 18, weight: .semibold, height: 25)
        label("来自官方 App Server", size: 11, color: .secondaryLabelColor, height: 21)
        y += 11
    }

    private func endContent() {
        y += 10
        _ = button("查看官方 Usage", action: #selector(openUsage), x: side, buttonWidth: 135)
        _ = button("重试", action: #selector(retryQuery), x: 163, buttonWidth: 70)
        _ = button("关闭", action: #selector(closeBubble), x: width - side - 88, buttonWidth: 88)
        y += 40
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first(where: { $0.frame.contains(mouse) }) ?? NSScreen.main
        let maxHeight = max(190, (screen?.visibleFrame.height ?? 700) - 32)
        let height = min(max(y + 10, 180), maxHeight)
        document.frame = NSRect(x: 0, y: 0, width: width, height: max(y + 10, height))
        panel.setContentSize(NSSize(width: width, height: height))
        placePanel()
        scroll.contentView.scroll(to: .zero)
        scroll.reflectScrolledClipView(scroll.contentView)
    }

    private func showLoading() {
        beginContent()
        label("正在查询额度…", size: 14, weight: .medium, height: 28)
        label("请稍候", size: 12, color: .secondaryLabelColor)
        y += 4
        endContent()
    }

    private func render(_ snapshot: Snapshot) {
        beginContent()
        if snapshot.status != "ok" {
            let message = snapshot.message ?? "暂时无法获取额度，请重试或检查 Codex CLI 登录状态。"
            label("未获取额度", size: 14, weight: .semibold, height: 25)
            label(message, size: 12, color: .secondaryLabelColor, height: 54)
        } else {
            switch snapshot.ordinaryUsageAllowed {
            case true: label("正常使用：允许", size: 12, color: .secondaryLabelColor)
            case false: label("正常使用：暂不允许", size: 12, weight: .medium)
            case nil: label("正常使用：状态未提供", size: 12, color: .secondaryLabelColor)
            }
            y += 8
            for bucket in snapshot.buckets {
                label(bucket.name ?? bucket.id, size: 13, weight: .semibold, height: 23)
                if let reached = bucket.rateLimitReachedType {
                    label("限制状态：\(reached)", size: 11, color: .secondaryLabelColor)
                }
                for item in bucket.windows {
                    let labelText: String
                    switch item.durationMins {
                    case 300: labelText = "5 小时"
                    case 10080: labelText = "每周"
                    case let n?: labelText = "\(String(format: "%g", n)) 分钟"
                    case nil: labelText = "窗口时长未提供"
                    }
                    let used = item.usedPercent.map { String(format: "%g%%", $0) } ?? "未提供"
                    let remaining = item.remainingPercent.map { String(format: "%g%%", $0) } ?? "未提供"
                    label("\(labelText)    剩余 \(remaining)", size: 13, weight: .medium, height: 22)
                    if let remaining = item.remainingPercent {
                        let progress = NSProgressIndicator(frame: NSRect(x: side, y: y + 3, width: width - side * 2, height: 6))
                        progress.style = .bar
                        progress.isIndeterminate = false
                        progress.minValue = 0
                        progress.maxValue = 100
                        progress.doubleValue = remaining
                        document.addSubview(progress)
                        y += 13
                    }
                    let reset = item.resetsAt.map { format.string(from: Date(timeIntervalSince1970: $0)) } ?? "未提供"
                    label("已用 \(used) · 重置 \(reset)", size: 11, color: .secondaryLabelColor, height: 21)
                    y += 7
                }
                y += 5
            }
            let iso = ISO8601DateFormatter()
            iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let fallback = ISO8601DateFormatter()
            let parsed = iso.date(from: snapshot.fetchedAt) ?? fallback.date(from: snapshot.fetchedAt)
            label("查询时间：\(parsed.map { format.string(from: $0) } ?? "未提供")",
                  size: 11, color: .secondaryLabelColor, height: 21)
            label("比例不代表剩余消息数。", size: 11, color: .secondaryLabelColor, height: 20)
        }
        endContent()
    }

    private func showError(_ message: String) {
        let snapshot = Snapshot(status: "error", fetchedAt: "", buckets: [], ordinaryUsageAllowed: nil, message: message)
        render(snapshot)
    }

    private func startQuery() {
        lock.lock()
        if closing || task != nil { lock.unlock(); return }
        let process = Process()
        let configURL = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("config.json")
        let scriptURL = configURL.deletingLastPathComponent().appendingPathComponent("codex_usage.py")
        let config: Configuration
        do {
            config = try JSONDecoder().decode(Configuration.self, from: Data(contentsOf: configURL))
        } catch {
            lock.unlock()
            showError("本地配置不可用，请重新运行安装命令。")
            return
        }
        process.executableURL = URL(fileURLWithPath: config.python)
        process.arguments = [scriptURL.path, "--json", "--timeout", "15"]
        if let cli = config.codexCLI, !cli.isEmpty { process.arguments?.append(contentsOf: ["--codex-cli", cli]) }
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        if let home = config.codexHome, !home.isEmpty { environment["CODEX_HOME"] = home }
        process.environment = environment
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            task = process
        } catch {
            lock.unlock()
            showError("无法启动 Python 查询器，请重新运行安装命令。")
            return
        }
        lock.unlock()
        let timeout = DispatchWorkItem { [weak self, weak process] in
            guard let self, let process else { return }
            self.lock.lock()
            let stillCurrent = self.task === process && process.isRunning
            self.lock.unlock()
            if stillCurrent { kill(process.processIdentifier, SIGINT) }
        }
        timeoutWork = timeout
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 21, execute: timeout)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            DispatchQueue.main.async {
                guard let self else { return }
                self.timeoutWork?.cancel()
                self.lock.lock()
                if self.task === process { self.task = nil }
                let wasClosing = self.closing
                self.lock.unlock()
                if wasClosing { NSApp.terminate(nil); return }
                if let snapshot = try? JSONDecoder().decode(Snapshot.self, from: data) {
                    self.render(snapshot)
                } else {
                    self.showError("额度查询超时或响应无效，请重试并检查 Codex CLI。")
                }
            }
        }
    }

    @objc private func retryQuery() {
        lock.lock(); let busy = task != nil || closing; lock.unlock()
        if !busy { showLoading(); startQuery() }
    }
    @objc private func openUsage() {
        if let url = URL(string: "https://chatgpt.com/codex/settings/usage") { NSWorkspace.shared.open(url) }
    }
    @objc private func closeBubble() { panel.close() }
    func windowWillClose(_ notification: Notification) {
        timeoutWork?.cancel()
        lock.lock()
        closing = true
        let running = task
        lock.unlock()
        if let running, running.isRunning {
            kill(running.processIdentifier, SIGINT)
            // The Python reader's finally block closes its app-server subprocess.
        } else {
            NSApp.terminate(nil)
        }
    }
}

let app = NSApplication.shared
let delegate = BubbleController()
app.delegate = delegate
app.run()
