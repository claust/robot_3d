import AppKit
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
    @Published var cameraFrame: NSImage?
    @Published var cameraStatus = "Camera off"
    @Published var lastFrame: Date?
    @Published var printerName: String?
    @Published var mode: Mode {
        didSet { if mode != oldValue { restart() } }
    }

    let hasCredentials: Bool
    private let config: PrinterConfig?
    private var mqtt: BambuMQTTSource?
    private var sim: SimulatedSource?
    private var camera: CameraSource?
    private var nameSource: PrinterNameSource?
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
        camera?.stop(); camera = nil
        nameSource?.stop(); nameSource = nil
        merged = [:]
        snapshot = PrinterSnapshot()
        lastUpdate = nil
        cameraFrame = nil
        lastFrame = nil

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
