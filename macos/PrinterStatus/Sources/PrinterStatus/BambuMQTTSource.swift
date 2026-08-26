import Foundation
import MQTTNIO
import NIOCore
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
        task = Task.detached { [weak self] in
            while let self, !Task.isCancelled {
                do {
                    try await self.runSession()
                } catch {
                    self.onStatus?("Offline: \(error.localizedDescription)", false)
                }
                try? await Task.sleep(for: .seconds(5))
                self.onStatus?("Reconnecting…", false)
            }
        }
    }

    func stop() {
        task?.cancel()
        task = nil
        if let client {
            try? client.syncShutdownGracefully()
        }
        client = nil
    }

    private func runSession() async throws {
        onStatus?("Connecting to \(config.ip)…", false)
        let client = MQTTClient(
            host: config.ip,
            port: 8883,
            identifier: "PrinterStatusMac-\(ProcessInfo.processInfo.processIdentifier)",
            eventLoopGroupProvider: .shared(NIOTSEventLoopGroup.singleton),
            configuration: .init(
                version: .v3_1_1,
                userName: "bblp",
                password: config.accessCode,
                useSSL: true,
                // The printer presents a self-signed certificate.
                tlsConfiguration: .ts(TSTLSConfiguration(certificateVerification: .none))
            )
        )
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

    private func requestPushAll(_ client: MQTTClient) async throws {
        let payload = #"{"pushing": {"sequence_id": "1", "command": "pushall"}}"#
        try await client.publish(
            to: "device/\(config.serial)/request",
            payload: ByteBuffer(string: payload),
            qos: .atLeastOnce
        )
    }
}
