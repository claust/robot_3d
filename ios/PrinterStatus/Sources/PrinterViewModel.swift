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
    @Published var cameraFrame: CGImage?
    @Published var cameraStatus = "Camera off"
    @Published var lastFrame: Date?
    @Published var printerName: String?
    @Published var mode: Mode {
        didSet { if mode != oldValue { restart() } }
    }
    @Published private(set) var hasCredentials: Bool

    private var config: PrinterConfig?
    private var mqtt: BambuMQTTSource?
    private var sim: SimulatedSource?
    private var camera: BambuCameraSource?
    private var nameSource: PrinterNameSource?
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
        camera?.stop(); camera = nil
        nameSource?.stop(); nameSource = nil
    }

    private func restart() {
        stopSources()
        merged = [:]
        snapshot = PrinterSnapshot()
        lastUpdate = nil
        cameraFrame = nil
        lastFrame = nil
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
            cam.onFrame = { [weak self] image in
                Task { @MainActor in
                    self?.cameraFrame = image
                    self?.cameraStatus = "Live"
                    self?.lastFrame = Date()
                }
            }
            cam.onStatus = { [weak self] text in
                Task { @MainActor in self?.cameraStatus = text }
            }
            cam.start()
            camera = cam

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
