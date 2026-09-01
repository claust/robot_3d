import Foundation
import IPCamKit
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

        public var description: String {
            switch self {
            case .handshakeFailed(let why): return "TLS handshake to the printer failed — \(why)"
            case .timedOut: return "Timed out fetching the printer's device CA"
            case .noIntermediates: return "Printer sent no intermediate CA certificate"
            case .untrustedChain:
                return "Printer's certificate did not chain to a Bambu device CA"
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
        let roots = BambuTrust.rootCertificateDERs
        let verdict = Verdict()

        let tls = NWProtocolTLS.Options()
        sec_protocol_options_set_verify_block(
            tls.securityProtocolOptions,
            { _, secTrust, complete in
                let chain = sec_trust_copy_ref(secTrust).takeRetainedValue()
                let anchors = roots.compactMap { SecCertificateCreateWithData(nil, $0 as CFData) }
                // Device certificates name a serial, not an address, and run far
                // past Apple's 398-day SSL-policy limit — a basic X.509 policy
                // checks the signature chain without those two constraints.
                guard !anchors.isEmpty,
                    SecTrustSetAnchorCertificates(chain, anchors as CFArray) == errSecSuccess,
                    SecTrustSetAnchorCertificatesOnly(chain, true) == errSecSuccess,
                    SecTrustSetPolicies(chain, SecPolicyCreateBasicX509()) == errSecSuccess,
                    SecTrustEvaluateWithError(chain, nil)
                else {
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
                        if settled.claim() { continuation.resume(throwing: HarvestError.timedOut) }
                    default:
                        break
                    }
                }
                queue.asyncAfter(deadline: .now() + timeout) {
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
            if case .rejected = verdict.state {
                throw HarvestError.untrustedChain
            }
            throw error
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
