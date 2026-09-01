import Foundation
import Network
import Security

/// Recovers the intermediate CA the printer omits from its camera stream.
///
/// The X2D presents different chains on its two TLS ports (measured against
/// firmware 01.02.00.00):
///
/// | Port        | Chain sent                                     |
/// |-------------|------------------------------------------------|
/// | 8883 (MQTT) | leaf `CN=<serial>` + `BBL Device CA <model>-V2` |
/// | 322 (RTSPS) | leaf only                                      |
///
/// So the camera port alone gives no path from the leaf to the roots in
/// ``BambuTrust`` — `Unable to build chain to root (possible missing
/// intermediate)` — which is why other tools resort to disabling verification
/// or pinning a bare fingerprint. The intermediate is right there on the MQTT
/// port though, so fetch it from a throwaway handshake and use it as an
/// additional anchor for the camera connection.
///
/// This stays safe because the harvested chain must itself validate against
/// ``BambuTrust``'s pinned roots before it is adopted: an impostor on 8883
/// cannot inject an anchor it does not already have a Bambu-signed path for.
public enum BambuDeviceCA {
    public enum HarvestError: Error, CustomStringConvertible {
        case handshakeFailed(String)
        case timedOut
        /// The chain validated but carried no intermediate — firmware that
        /// sends a leaf-only chain on 8883 too, leaving nothing to harvest.
        case noIntermediates
        case untrustedChain
        /// Our own bundled roots would not load, or the Security framework
        /// refused the trust setup. Nothing to do with the printer.
        case trustStoreUnavailable

        public var description: String {
            switch self {
            case .handshakeFailed(let why): return "TLS handshake to the printer failed — \(why)"
            case .timedOut: return "Timed out fetching the printer's device CA"
            case .noIntermediates: return "Printer sent no intermediate CA certificate"
            case .untrustedChain:
                return "Printer's certificate did not chain to Bambu's trusted roots"
            case .trustStoreUnavailable:
                return "Could not build a trust store from the bundled Bambu roots"
            }
        }
    }

    /// Certificates (DER) beyond the leaf that the printer presents on `port`,
    /// once the whole chain has been verified against ``BambuTrust``.
    ///
    /// Only the TLS handshake happens here — no MQTT CONNECT is sent, so this
    /// never touches a running print.
    public static func harvest(
        host: String,
        port: UInt16 = 8883,
        timeout: TimeInterval = 10
    ) async throws -> [Data] {
        let queue = DispatchQueue(label: "BambuKit.deviceCA")
        // The timeout gets its own queue. `queue` is serial and runs the
        // connection's state updates and the TLS verify block, so a watchdog
        // scheduled there waits behind exactly the work it is meant to bound —
        // trust evaluation included. `Settled` already makes the two racers
        // safe to resume from different queues.
        let timeoutQueue = DispatchQueue(label: "BambuKit.deviceCA.timeout")
        let verdict = Verdict()

        // Build the anchors once, before dialing. Doing it inside the verify
        // block repeated the work per handshake, and — worse — an anchor set
        // that failed to load there was indistinguishable from the printer
        // presenting a bad chain. A broken bundle is our bug, not its
        // certificate, so it fails here with its own error.
        let decoded = BambuTrust.rootCertificateDERs
            .compactMap { SecCertificateCreateWithData(nil, $0 as CFData) }
        guard !decoded.isEmpty else { throw HarvestError.trustStoreUnavailable }
        let anchors = Anchors(decoded)

        let tls = NWProtocolTLS.Options()
        sec_protocol_options_set_verify_block(
            tls.securityProtocolOptions,
            { _, secTrust, complete in
                let chain = sec_trust_copy_ref(secTrust).takeRetainedValue()
                // Device certificates name a serial, not an address, and run far
                // past Apple's 398-day SSL-policy limit — a basic X.509 policy
                // checks the signature chain without those two constraints.
                guard
                    SecTrustSetAnchorCertificates(chain, anchors.certificates as CFArray)
                        == errSecSuccess,
                    SecTrustSetAnchorCertificatesOnly(chain, true) == errSecSuccess,
                    SecTrustSetPolicies(chain, SecPolicyCreateBasicX509()) == errSecSuccess
                else {
                    // Configuring the evaluation failed — that is us, not the
                    // certificate, and must not read as a rejected chain.
                    verdict.set(.setupFailed)
                    complete(false)
                    return
                }
                guard SecTrustEvaluateWithError(chain, nil) else {
                    verdict.set(.rejected)
                    complete(false)
                    return
                }
                let certs = (SecTrustCopyCertificateChain(chain) as? [SecCertificate]) ?? []
                // Drop the leaf; anything above it is what the camera port
                // fails to send. Roots repeat harmlessly as anchors.
                verdict.set(.accepted(certs.dropFirst().map { SecCertificateCopyData($0) as Data }))
                complete(true)
            }, queue)

        guard let nwPort = NWEndpoint.Port(rawValue: port) else {
            throw HarvestError.handshakeFailed("invalid port \(port)")
        }
        let connection = NWConnection(
            host: NWEndpoint.Host(host), port: nwPort,
            using: NWParameters(tls: tls, tcp: NWProtocolTCP.Options()))

        let settled = Settled()
        do {
            try await withCheckedThrowingContinuation {
                (continuation: CheckedContinuation<Void, Error>) in
                connection.stateUpdateHandler = { state in
                    switch state {
                    case .ready:
                        if settled.claim() { continuation.resume() }
                    case .failed(let error), .waiting(let error):
                        if settled.claim() {
                            continuation.resume(
                                throwing: HarvestError.handshakeFailed(error.localizedDescription))
                        }
                    case .cancelled:
                        // Our own timeout resumes the continuation before it
                        // cancels, so a `.cancelled` that still finds the
                        // continuation unsettled came from somewhere else and
                        // must not borrow the timeout's explanation.
                        if settled.claim() {
                            continuation.resume(
                                throwing: HarvestError.handshakeFailed(
                                    "connection closed before the TLS handshake completed"))
                        }
                    default:
                        break
                    }
                }
                timeoutQueue.asyncAfter(deadline: .now() + timeout) {
                    if settled.claim() { continuation.resume(throwing: HarvestError.timedOut) }
                }
                connection.start(queue: queue)
            }
        } catch {
            connection.cancel()
            // A rejected chain surfaces as a generic handshake failure, so
            // only the verify block having *run and refused* identifies it.
            // Everything else — refused connection, no route, timeout — keeps
            // its own error rather than being blamed on the certificate.
            switch verdict.state {
            case .rejected: throw HarvestError.untrustedChain
            case .setupFailed: throw HarvestError.trustStoreUnavailable
            case .notRun, .accepted: throw error
            }
        }
        // The handshake is all we wanted; never send an MQTT packet.
        connection.cancel()

        guard case .accepted(let intermediates) = verdict.state else {
            throw HarvestError.untrustedChain
        }
        guard !intermediates.isEmpty else { throw HarvestError.noIntermediates }
        return intermediates
    }

    /// What the TLS verify block decided, kept apart from why the connection
    /// failed. The block and the awaiting task are serialized by the handshake
    /// completing before `.ready`, but the lock keeps that from being an
    /// assumption about Network.framework's ordering.
    private final class Verdict: @unchecked Sendable {
        enum State {
            /// The handshake never reached certificate evaluation.
            case notRun
            /// The chain was evaluated and did not validate against the roots.
            case rejected
            /// The evaluation could not be configured — our problem, not the
            /// printer's certificate.
            case setupFailed
            /// The chain validated; these are the certificates above the leaf.
            case accepted([Data])
        }

        private let lock = NSLock()
        private var stored: State = .notRun
        var state: State {
            lock.lock()
            defer { lock.unlock() }
            return stored
        }
        func set(_ value: State) {
            lock.lock()
            stored = value
            lock.unlock()
        }
    }

    /// Anchor certificates shared with the verify block. `SecCertificate` is a
    /// CF type without a `Sendable` conformance, but it is immutable once
    /// created and only read here.
    private final class Anchors: @unchecked Sendable {
        let certificates: [SecCertificate]
        init(_ certificates: [SecCertificate]) { self.certificates = certificates }
    }

    /// One-shot guard so the continuation resumes exactly once across the
    /// state handler and the timeout.
    private final class Settled: @unchecked Sendable {
        private let lock = NSLock()
        private var done = false
        func claim() -> Bool {
            lock.lock()
            defer { lock.unlock() }
            if done { return false }
            done = true
            return true
        }
    }
}
