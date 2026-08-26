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
    @Published var mode: Mode {
        didSet { if mode != oldValue { restart() } }
    }

    let hasCredentials: Bool
    private let config: PrinterConfig?
    private var mqtt: BambuMQTTSource?
    private var sim: SimulatedSource?
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
        merged = [:]
        snapshot = PrinterSnapshot()
        lastUpdate = nil

        switch mode {
        case .simulated:
            connectionText = "Simulated data"
            isConnected = true
            let source = SimulatedSource()
            source.onReport = { [weak self] report in
                Task { @MainActor in self?.apply(report) }
            }
            source.start()
            sim = source
        case .live:
            guard let config else {
                connectionText = "No credentials (set BAMBU_* env vars or cad/.env)"
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
        }
    }

    private func apply(_ report: [String: Any]) {
        deepMerge(&merged, report)
        snapshot = PrinterSnapshot.decode(from: merged)
        lastUpdate = Date()
    }
}
