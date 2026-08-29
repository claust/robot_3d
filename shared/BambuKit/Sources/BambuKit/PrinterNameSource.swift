import Foundation

/// The printer's user-assigned name ("Claudia") is not in the MQTT report —
/// it lives in the SSDP headers (`DevName.bambu.com`). This is the
/// single-host case of `PrinterDiscovery`: a directed M-SEARCH to a printer
/// we already know the address of, answered unicast to our ephemeral port.
///
/// Retries a few times, then gives up quietly; the name is cosmetic. The
/// callback fires on the probe's private queue, not the main thread.
public final class PrinterNameSource {
    public var onName: ((String) -> Void)?

    private let probe: SSDPProbe

    public init(ip: String) {
        // Ten attempts three seconds apart: a printer that is still booting
        // when the app opens gets half a minute to start answering.
        probe = SSDPProbe(hosts: [ip], rounds: 10, roundInterval: 3, listenSeconds: 3)
    }

    public func start() {
        probe.onResponse = { [weak self] printer in
            guard let self, !printer.name.isEmpty else { return }
            onName?(printer.name)
            probe.stop()  // the name does not change mid-session
        }
        probe.start()
    }

    public func stop() {
        probe.stop()
    }
}
