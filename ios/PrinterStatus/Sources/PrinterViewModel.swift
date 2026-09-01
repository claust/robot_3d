import BambuKit
import CoreGraphics
import Foundation
import SwiftUI

@MainActor
final class PrinterViewModel: ObservableObject {
    enum Mode: String, CaseIterable, Identifiable {
        case live = "Live"
        case simulated = "Simulate"
        var id: String { rawValue }
    }

    @Published var snapshot = PrinterSnapshot()
    @Published var connectionText = "Starting…"
    @Published var isConnected = false
    @Published var lastUpdate: Date?
    /// Image and arrival time travel together in one value: as separate
    /// published properties, each frame fired several graph invalidations.
    /// The macOS app learned this the hard way (see its PrinterViewModel).
    struct CameraFrame {
        let image: CGImage
        let received: Date
    }

    @Published private(set) var camera: CameraFrame?
    @Published var cameraStatus = "Camera off"
    @Published var printerName: String?

    var cameraFrame: CGImage? { camera?.image }
    var lastFrame: Date? { camera?.received }
    @Published var mode: Mode {
        didSet { if mode != oldValue { restart() } }
    }
    @Published private(set) var hasCredentials: Bool

    private var config: PrinterConfig?
    private var mqtt: BambuMQTTSource?
    private var sim: SimulatedSource?
    private var cameraSource: BambuCameraSource?
    private var nameSource: PrinterNameSource?
    private var frameTask: Task<Void, Never>?
    private var frameContinuation: AsyncStream<CGImage>.Continuation?
    private var merged: [String: Any] = [:]

    init() {
        let config = PrinterConfig.load()
        self.config = config
        hasCredentials = config != nil
        mode = config == nil ? .simulated : .live
        restart()
    }

    /// Called when the settings sheet saves: re-resolve credentials and
    /// reconnect. Switches into live mode when credentials first appear,
    /// and back to simulated when they are cleared — the sheet disables
    /// the mode picker without credentials, so staying in live mode would
    /// strand the user on "No printer configured".
    func reloadConfig() {
        config = PrinterConfig.load()
        hasCredentials = config != nil
        if config != nil, mode == .simulated {
            mode = .live  // didSet restarts
        } else if config == nil, mode == .live {
            mode = .simulated  // didSet restarts
        } else {
            restart()
        }
    }

    /// The app cannot talk to the printer from the background; tear the
    /// session down on scene-phase changes rather than letting iOS kill the
    /// socket mid-frame, and reconnect cleanly on return. The launch
    /// transition to .active arrives with the init()-started sources still
    /// running — restarting then would just churn the connection.
    func setActive(_ active: Bool) {
        if active {
            if mqtt == nil && sim == nil { restart() }
        } else {
            stopSources()
        }
    }

    /// "Live" only while frames are actually fresh — the stream delivers
    /// several per second, so anything older than a few seconds is stale.
    var isCameraLive: Bool {
        guard let lastFrame else { return false }
        return Date().timeIntervalSince(lastFrame) < 5
    }

    private func stopSources() {
        mqtt?.stop(); mqtt = nil
        sim?.stop(); sim = nil
        cameraSource?.stop(); cameraSource = nil
        frameContinuation?.finish(); frameContinuation = nil
        frameTask?.cancel(); frameTask = nil
        nameSource?.stop(); nameSource = nil
        // A decoded 1080p frame is megabytes, and backgrounding comes through
        // here — no reason to hold one while the app is not on screen, and it
        // would be stale on return anyway.
        camera = nil
        cameraStatus = "Camera off"
    }

    private func restart() {
        stopSources()
        merged = [:]
        snapshot = PrinterSnapshot()
        lastUpdate = nil
        // the name belongs to the previous session's printer; keeping it
        // would leave a stale title in simulate mode or after an IP change
        printerName = nil

        switch mode {
        case .simulated:
            connectionText = "Simulated data"
            isConnected = true
            cameraStatus = "No camera in simulation"
            let source = SimulatedSource()
            source.onReport = { [weak self] report in
                Task { @MainActor in self?.apply(report) }
            }
            source.start()
            sim = source
        case .live:
            guard let config else {
                connectionText = "No printer configured"
                cameraStatus = "No printer configured"
                isConnected = false
                return
            }
            connectionText = "Connecting…"
            isConnected = false
            let source = BambuMQTTSource(config: config)
            source.onReport = { [weak self] report in
                Task { @MainActor in self?.apply(report) }
            }
            source.onStatus = { [weak self] text, connected in
                Task { @MainActor in
                    self?.connectionText = text
                    self?.isConnected = connected
                }
            }
            source.start()
            mqtt = source

            let cam = BambuCameraSource(config: config)
            // Newest-frame-only buffering is the backpressure. A
            // `Task { @MainActor }` per frame is an unbounded queue: when the
            // main actor cannot keep up, the pending closures pile up, each
            // retaining a decoded frame. Here a slow consumer just misses
            // frames. Reports deliberately keep the per-event Task — they are
            // deltas that deepMerge accumulates, so dropping one would lose
            // state that never comes again.
            let (frames, continuation) = AsyncStream.makeStream(
                of: CGImage.self, bufferingPolicy: .bufferingNewest(1))
            cam.onFrame = { continuation.yield($0) }
            frameContinuation = continuation
            frameTask = Task { @MainActor [weak self] in
                for await image in frames {
                    guard let self else { return }
                    self.camera = CameraFrame(image: image, received: Date())
                    // assigning an unchanged value still publishes
                    if self.cameraStatus != "Live" { self.cameraStatus = "Live" }
                }
            }
            cam.onStatus = { [weak self] text in
                Task { @MainActor in
                    guard let self, self.cameraStatus != text else { return }
                    self.cameraStatus = text
                }
            }
            cam.start()
            cameraSource = cam

            let names = PrinterNameSource(ip: config.ip)
            names.onName = { [weak self] name in
                Task { @MainActor in self?.printerName = name }
            }
            names.start()
            nameSource = names
        }
    }

    private func apply(_ report: [String: Any]) {
        deepMerge(&merged, report)
        snapshot = PrinterSnapshot.decode(from: merged)
        lastUpdate = Date()
    }
}
