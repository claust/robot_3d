import Foundation
import MQTTNIO
import NIOCore
import NIOPosix
import NIOSSL
import NIOTransportServices

/// Live data source: subscribes to the printer's MQTT report topic and
/// delivers each `print` report dictionary. Reconnects forever until stopped.
public final class BambuMQTTSource {
    private let config: PrinterConfig
    private var task: Task<Void, Never>?

    /// Called with every incoming `print` report (raw dictionary).
    public var onReport: (([String: Any]) -> Void)?
    /// Called with human-readable connection state changes.
    public var onStatus: ((String, Bool) -> Void)?  // (message, isConnected)

    public init(config: PrinterConfig) {
        self.config = config
    }

    public func start() {
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

    /// Failures the user can actually act on deserve a pointer to the fix.
    private static func describe(_ error: Error, host: String) -> String {
        let text = "\(error)".lowercased()
        if text.contains("certificat") || text.contains("handshake") {
            return "TLS failure — \(host) did not present a Bambu device certificate "
                + "(set BAMBU_TLS_INSECURE=1 to skip verification)"
        }
        if text.contains("connection") || text.contains("refused")
            || text.contains("timeout") || text.contains("unreachable") {
            // macOS gates LAN access per app: a freshly installed app cannot
            // reach the printer until Local Network permission is granted.
            return "Can't reach \(host) — check the printer is on, and that this app is "
                + "enabled in System Settings > Privacy & Security > Local Network"
        }
        return "Offline: \(error.localizedDescription)"
    }

    /// Cancellation propagates into runSession's sleeps immediately; its
    /// defer owns the client shutdown, so there is a single shutdown path
    /// and nothing here can block the caller's thread.
    public func stop() {
        task?.cancel()
        task = nil
    }

    private func runSession() async throws {
        onStatus?("Connecting to \(config.ip)…", false)
        let client = try makeClient()
        defer { try? client.syncShutdownGracefully() }

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
        // Platform-tagged and random: two devices sharing a client id would
        // have the broker drop the older session on each reconnect.
        #if os(macOS)
        let platform = "Mac"
        #else
        let platform = "iOS"
        #endif
        let identifier = "PrinterStatus\(platform)-\(UUID().uuidString.prefix(8))"
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
        #if os(macOS)
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
        #elseif os(iOS)
        // iOS builds of MQTTNIO compile NIOSSL support out, leaving only the
        // Network.framework path — whose trust evaluation always applies the
        // SSL policy, which the printer's certificate can never pass (it
        // names the serial, not the IP, lacks the serverAuth EKU and outlives
        // the 825-day limit; verified live: pinning BambuTrust's roots as
        // anchors still fails with SSLHostname/ServerAuthEKU). So iOS skips
        // verification, like the BAMBU_TLS_INSECURE escape hatch; the
        // session is still encrypted, just not authenticated. macOS keeps
        // real chain pinning via NIOSSL above.
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
        #else
        // Each platform must consciously pick its TLS posture; do not let a
        // new platform silently inherit the unverified iOS path.
        #error("Unsupported platform: add an explicit TLS configuration for it")
        #endif
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
