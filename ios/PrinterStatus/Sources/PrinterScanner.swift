import BambuKit
import SwiftUI

/// View state around BambuKit's `PrinterDiscovery`: what the sweep has
/// found so far, and whether it is still running. Both the onboarding flow
/// and the settings sheet drive one of these.
@MainActor
final class PrinterScanner: ObservableObject {
    @Published private(set) var printers: [DiscoveredPrinter] = []
    @Published private(set) var isScanning = false
    /// nil until a sweep has completed at least once — which is what tells
    /// the UI apart from "found nothing yet" and "found nothing, we're done".
    @Published private(set) var lastOutcome: PrinterDiscovery.Outcome?

    private var discovery: PrinterDiscovery?

    var hasFinishedEmpty: Bool { !isScanning && lastOutcome != nil && printers.isEmpty }

    func scan() {
        guard !isScanning else { return }
        printers = []
        lastOutcome = nil
        isScanning = true

        let discovery = PrinterDiscovery()
        // PrinterDiscovery documents delivery on the main queue, so this is
        // already the main actor's turn — it just cannot be proved statically.
        discovery.onPrinter = { printer in
            MainActor.assumeIsolated { [weak self] in
                self?.printers.append(printer)
            }
        }
        discovery.onFinished = { printers, outcome in
            MainActor.assumeIsolated { [weak self] in
                guard let self else { return }
                self.printers = printers
                lastOutcome = outcome
                isScanning = false
                self.discovery = nil
            }
        }
        self.discovery = discovery
        discovery.start()
    }

    /// Stop a sweep in flight — leaving the screen, or picking a printer
    /// before the last round finishes.
    func cancel() {
        discovery?.stop()
        discovery = nil
        isScanning = false
    }
}
