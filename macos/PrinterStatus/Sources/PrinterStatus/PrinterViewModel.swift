import AppKit
import BambuKit
import Foundation
import Observation
import SwiftUI

/// `@Observable`, not `ObservableObject`. SwiftUI's ObservableObject
/// bridge allocates observation-registrar state on every publish and never
/// releases it — measured at ~5 leaked allocations per update, with or
/// without the camera running, which is what kept the app growing until the
/// OS jetsammed it. Observation registers per property actually read.
@MainActor
@Observable
final class PrinterViewModel {
    enum Mode: String, CaseIterable, Identifiable {
        case live = "Live"
        case simulated = "Simulate"
        var id: String { rawValue }
    }

    /// Image and arrival time travel together in one value. As three
    /// separate `@Published` properties each frame fired three graph
    /// invalidations, so a 5 fps camera drove 15 SwiftUI updates a second.
    struct CameraFrame {
        let image: NSImage
        let received: Date
    }

    var snapshot = PrinterSnapshot()
    var connectionText = "Starting…"
    var isConnected = false
    var lastUpdate: Date?
    private(set) var camera: CameraFrame?
    var cameraStatus = "Camera off"
    var printerName: String?
    var mode: Mode {
        didSet { if mode != oldValue { restart() } }
    }

    var cameraFrame: NSImage? { camera?.image }
    var lastFrame: Date? { camera?.received }

    let hasCredentials: Bool
    private let config: PrinterConfig?
    private var mqtt: BambuMQTTSource?
    private var sim: SimulatedSource?
    private var cameraSource: CameraSource?
    private var nameSource: PrinterNameSource?
    private var frameTask: Task<Void, Never>?
    private var frameContinuation: AsyncStream<NSImage>.Continuation?
    private var merged: [String: Any] = [:]

    init(forceSimulate: Bool = false) {
        config = PrinterConfig.load()
        hasCredentials = config != nil
        mode = (forceSimulate || config == nil) ? .simulated : .live
        restart()
    }

    private func restart() {
        mqtt?.stop(); mqtt = nil
        sim?.stop(); sim = nil
        cameraSource?.stop(); cameraSource = nil
        nameSource?.stop(); nameSource = nil
        frameContinuation?.finish(); frameContinuation = nil
        frameTask?.cancel(); frameTask = nil
        merged = [:]
        snapshot = PrinterSnapshot()
        lastUpdate = nil
        camera = nil

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
                connectionText = "No credentials (see config.env, BAMBU_* env vars, or cad/.env)"
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

            let cam = CameraSource(config: config)
            // Newest-frame-only buffering is the backpressure. A
            // `Task { @MainActor }` per frame is an unbounded queue: when the
            // main actor cannot keep up with 5 fps, the pending closures pile
            // up, each retaining a decoded NSImage. Here a slow consumer just
            // misses frames. Reports deliberately keep the per-event Task —
            // they are deltas that deepMerge accumulates, so dropping one
            // would lose state that never comes again.
            let (frames, continuation) = AsyncStream.makeStream(
                of: NSImage.self, bufferingPolicy: .bufferingNewest(1))
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

            // the friendly device name only exists in SSDP announcements;
            // keep the last one we heard if the listener has nothing yet
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
