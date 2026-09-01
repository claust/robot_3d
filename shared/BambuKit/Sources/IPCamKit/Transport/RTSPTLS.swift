// Copyright (c) 2025 Steel Brain
// SPDX-License-Identifier: MIT
// TLS configuration for RTSPS (RTSP over TLS) connections.

import Foundation
import Network
import Security

/// TLS settings for an `rtsps://` connection.
///
/// Cameras that speak RTSPS frequently present a certificate issued by the
/// vendor's own device CA, naming the device's serial rather than the address
/// you dial. `trust` and `verifyHostname` exist so such a chain can still be
/// verified properly instead of falling back to accepting anything.
public struct TLSOptions: Sendable {
  /// How the server's certificate chain is evaluated.
  public enum Trust: Sendable {
    /// The system trust store — correct for a publicly signed certificate.
    case system
    /// Evaluate against these anchors only (DER-encoded certificates).
    /// `SecCertificate` is not `Sendable`, so anchors travel as DER bytes and
    /// are rebuilt inside the verify block.
    case pinnedRoots([Data])
    /// Accept any certificate. For diagnostics only — never ship it.
    case insecure
  }

  public var trust: Trust
  /// Whether the certificate must also match the host being dialed. Device
  /// certificates naming a serial number need this off.
  public var verifyHostname: Bool

  public init(trust: Trust = .system, verifyHostname: Bool = true) {
    self.trust = trust
    self.verifyHostname = verifyHostname
  }

  /// Anchors parsed from a PEM bundle (concatenated `-----BEGIN CERTIFICATE-----`
  /// blocks), the shape vendor CA bundles usually ship in.
  public static func pinned(pem: String, verifyHostname: Bool = true) -> TLSOptions {
    TLSOptions(trust: .pinnedRoots(derCertificates(fromPEM: pem)), verifyHostname: verifyHostname)
  }

  public static func derCertificates(fromPEM pem: String) -> [Data] {
    var ders: [Data] = []
    var base64 = ""
    var inCert = false
    for line in pem.split(separator: "\n", omittingEmptySubsequences: false) {
      let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
      if trimmed.hasPrefix("-----BEGIN CERTIFICATE") {
        inCert = true
        base64 = ""
      } else if trimmed.hasPrefix("-----END CERTIFICATE") {
        inCert = false
        if let der = Data(base64Encoded: base64) { ders.append(der) }
      } else if inCert {
        base64 += trimmed
      }
    }
    return ders
  }

  /// Network parameters carrying this TLS posture, plus the TCP options RTSP
  /// needs. `host` is only used for SNI and hostname verification.
  func parameters(host: String, queue: DispatchQueue) -> NWParameters {
    let tls = NWProtocolTLS.Options()
    let sec = tls.securityProtocolOptions

    // An IP literal is not a legal SNI value (RFC 6066), and a printer that
    // dislikes the extension would fail the handshake outright, so only send a
    // server name for real hostnames.
    if !host.isEmpty, IPv4Address(host) == nil, IPv6Address(host) == nil {
      sec_protocol_options_set_tls_server_name(sec, host)
    }

    // .system + hostname verification is exactly the default evaluation, so
    // leave the block unset and let Network.framework do it.
    let needsCustomVerify: Bool
    switch trust {
    case .system: needsCustomVerify = !verifyHostname
    case .pinnedRoots, .insecure: needsCustomVerify = true
    }
    if needsCustomVerify {
      let trust = self.trust
      let verifyHostname = self.verifyHostname
      sec_protocol_options_set_verify_block(
        sec,
        { _, secTrust, complete in
          if case .insecure = trust {
            complete(true)
            return
          }
          let chain = sec_trust_copy_ref(secTrust).takeRetainedValue()
          if case .pinnedRoots(let ders) = trust {
            let anchors = ders.compactMap { SecCertificateCreateWithData(nil, $0 as CFData) }
            guard !anchors.isEmpty,
              SecTrustSetAnchorCertificates(chain, anchors as CFArray) == errSecSuccess,
              SecTrustSetAnchorCertificatesOnly(chain, true) == errSecSuccess
            else {
              complete(false)
              return
            }
          }
          // A basic X.509 policy checks the chain and its validity dates but
          // not the name; SecPolicyCreateSSL adds the hostname match.
          let policy =
            verifyHostname
            ? SecPolicyCreateSSL(true, host as CFString)
            : SecPolicyCreateBasicX509()
          guard SecTrustSetPolicies(chain, policy) == errSecSuccess else {
            complete(false)
            return
          }
          complete(SecTrustEvaluateWithError(chain, nil))
        }, queue)
    }
    return NWParameters(tls: tls, tcp: NWProtocolTCP.Options())
  }
}
