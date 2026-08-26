import Foundation
import MQTTNIO
import NIOCore
import NIOPosix
import NIOSSL
import NIOTransportServices

/// Live data source: subscribes to the printer's MQTT report topic and
/// delivers each `print` report dictionary. Reconnects forever until stopped.
final class BambuMQTTSource {
    private let config: PrinterConfig
    private var client: MQTTClient?
    private var task: Task<Void, Never>?

    /// Called with every incoming `print` report (raw dictionary).
    var onReport: (([String: Any]) -> Void)?
    /// Called with human-readable connection state changes.
    var onStatus: ((String, Bool) -> Void)?  // (message, isConnected)

    init(config: PrinterConfig) {
        self.config = config
    }

    func start() {
        stop()  // idempotent: never run two session loops
        task = Task.detached { [weak self] in
            while let self, !Task.isCancelled {
                do {
                    try await self.runSession()
                } catch {
                    guard !Task.isCancelled else { break }
                    self.onStatus?(Self.describe(error, host: self.config.ip), false)
                }
                try? await Task.sleep(for: .seconds(5))
                guard !Task.isCancelled else { break }
                self.onStatus?("Reconnecting…", false)
            }
        }
    }

    /// A certificate failure deserves a pointer to the escape hatch.
    private static func describe(_ error: Error, host: String) -> String {
        let text = "\(error)".lowercased()
        if text.contains("certificat") || text.contains("handshake") {
            return "TLS failure — \(host) did not present a Bambu device certificate "
                + "(set BAMBU_TLS_INSECURE=1 to skip verification)"
        }
        return "Offline: \(error.localizedDescription)"
    }

    func stop() {
        task?.cancel()
        task = nil
        if let client {
            self.client = nil
            // off the caller's thread — stop() is reached from the main
            // actor when switching Live/Simulate, and shutdown can block
            DispatchQueue.global().async {
                try? client.syncShutdownGracefully()
            }
        }
    }

    private func runSession() async throws {
        onStatus?("Connecting to \(config.ip)…", false)
        let client = try makeClient()
        self.client = client
        defer {
            try? client.syncShutdownGracefully()
            self.client = nil
        }

        try await client.connect()
        onStatus?("Connected", true)

        client.addPublishListener(named: "report") { [weak self] result in
            guard case .success(let publish) = result else { return }
            var buffer = publish.payload
            guard let data = buffer.readData(length: buffer.readableBytes),
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let report = json["print"] as? [String: Any] else { return }
            self?.onReport?(report)
        }

        _ = try await client.subscribe(to: [
            MQTTSubscribeInfo(topicFilter: "device/\(config.serial)/report", qos: .atMostOnce)
        ])
        try await requestPushAll(client)

        // Keep the session alive; refresh the full state every few minutes
        // (the printer only pushes sparsely when idle) and bail out to the
        // reconnect loop if the connection drops.
        var sinceRefresh = 0
        while !Task.isCancelled {
            try await Task.sleep(for: .seconds(5))
            guard client.isActive() else {
                throw NSError(domain: "PrinterStatus", code: 1, userInfo: [
                    NSLocalizedDescriptionKey: "connection lost"
                ])
            }
            sinceRefresh += 5
            if sinceRefresh >= 180 {
                sinceRefresh = 0
                try await requestPushAll(client)
            }
        }
    }

    /// The printer's certificate chains to Bambu's device CA (see
    /// BambuTrust), which is used as the trust root. Hostname verification
    /// stays off — the certificate names the printer's serial, not its IP —
    /// but the chain itself must validate. Set BAMBU_TLS_INSECURE=1 to skip
    /// verification entirely (e.g. for non-Bambu test brokers).
    private func makeClient() throws -> MQTTClient {
        let identifier = "PrinterStatusMac-\(ProcessInfo.processInfo.processIdentifier)"
        if ProcessInfo.processInfo.environment["BAMBU_TLS_INSECURE"] == "1" {
            return MQTTClient(
                host: config.ip,
                port: 8883,
                identifier: identifier,
                eventLoopGroupProvider: .shared(NIOTSEventLoopGroup.singleton),
                configuration: .init(
                    version: .v3_1_1,
                    userName: "bblp",
                    password: config.accessCode,
                    useSSL: true,
                    tlsConfiguration: .ts(TSTLSConfiguration(certificateVerification: .none))
                )
            )
        }
        var tls = TLSConfiguration.makeClientConfiguration()
        tls.certificateVerification = .noHostnameVerification
        tls.trustRoots = .certificates(try BambuTrust.trustRoots())
        return MQTTClient(
            host: config.ip,
            port: 8883,
            identifier: identifier,
            eventLoopGroupProvider: .shared(MultiThreadedEventLoopGroup.singleton),
            configuration: .init(
                version: .v3_1_1,
                userName: "bblp",
                password: config.accessCode,
                useSSL: true,
                tlsConfiguration: .niossl(tls),
                // NIOSSL rejects IP literals as SNI names; the printer
                // ignores SNI, and verification is against the pinned chain.
                sniServerName: "bambu-printer"
            )
        )
    }

    private func requestPushAll(_ client: MQTTClient) async throws {
        let payload = #"{"pushing": {"sequence_id": "1", "command": "pushall"}}"#
        try await client.publish(
            to: "device/\(config.serial)/request",
            payload: ByteBuffer(string: payload),
            qos: .atLeastOnce
        )
    }
}
