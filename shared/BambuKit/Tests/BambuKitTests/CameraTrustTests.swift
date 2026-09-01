import IPCamKit
import Security
import XCTest

@testable import BambuKit

/// The trust plumbing behind the chamber camera. The stream itself needs a
/// printer, but the certificate handling is pure and is what silently breaks:
/// a PEM parser that drops a root leaves the camera unable to verify anything.
final class CameraTrustTests: XCTestCase {
    func testRootsParseToUsableCertificates() {
        let ders = BambuTrust.rootCertificateDERs
        // Bambu ships five today: three self-signed roots plus two cross-signed
        // CA2 certificates. A minimum, not an equality — adding a root or a
        // cross-sign is a legitimate bundle update and should not fail a test
        // about whether the roots are usable. Dropped blocks are caught by
        // `testPEMParserKeepsEveryBlock`, which does not depend on the bundle.
        XCTAssertGreaterThanOrEqual(ders.count, 5)
        for der in ders {
            XCTAssertNotNil(
                SecCertificateCreateWithData(nil, der as CFData),
                "a root failed to decode as DER — the PEM parser mangled it")
        }
    }

    func testPEMParserKeepsEveryBlock() {
        // The failure that actually matters: a bundle goes in, fewer
        // certificates come out, and trust evaluation quietly loses an anchor.
        let blocks = [
            Data([0x30, 0x82, 0x01, 0x02]),
            Data([0x30, 0x82, 0x03, 0x04]),
            Data([0x30, 0x82, 0x05, 0x06]),
        ]
        let pem = blocks
            .map { "-----BEGIN CERTIFICATE-----\n\($0.base64EncodedString())\n-----END CERTIFICATE-----" }
            .joined(separator: "\n")
        XCTAssertEqual(TLSOptions.derCertificates(fromPEM: pem), blocks)
    }

    func testRootsCarryTheIssuerOfTheDeviceCA() throws {
        // The camera port sends a leaf only, so verification depends on the
        // harvested "BBL Device CA", which is issued by "BBL CA2 RSA". If that
        // root ever drops out of the bundle, harvesting silently stops working.
        //
        // Read the common name, not `SecCertificateCopySubjectSummary`: the
        // summary is a display string Apple may reformat between OS releases,
        // whereas the CN is a field in the certificate itself.
        let names = BambuTrust.rootCertificateDERs
            .compactMap { SecCertificateCreateWithData(nil, $0 as CFData) }
            .compactMap { certificate -> String? in
                var commonName: CFString?
                guard SecCertificateCopyCommonName(certificate, &commonName) == errSecSuccess
                else { return nil }
                return commonName as String?
            }
        XCTAssertTrue(
            names.contains("BBL CA2 RSA"),
            "expected the device CA's issuer among the roots, got \(names)")
    }

    func testPEMParserIgnoresSurroundingNoise() {
        // Bundles arrive with comments and blank lines around the blocks; the
        // parser must key off the BEGIN/END markers, not the file's shape.
        let pem = """
            # a comment
            -----BEGIN CERTIFICATE-----
            \(Data([0x30, 0x82, 0x01, 0x02]).base64EncodedString())
            -----END CERTIFICATE-----

            trailing junk
            """
        let ders = TLSOptions.derCertificates(fromPEM: pem)
        XCTAssertEqual(ders, [Data([0x30, 0x82, 0x01, 0x02])])
    }

    func testPEMParserReturnsNothingForAnEmptyBundle() {
        XCTAssertTrue(TLSOptions.derCertificates(fromPEM: "").isEmpty)
        XCTAssertTrue(TLSOptions.derCertificates(fromPEM: "no certificates here").isEmpty)
    }
}

/// The camera source's lifetime, which is easy to get wrong and invisible
/// when it is: a stream that outlives its owner keeps decoding and holding the
/// network with nothing left to show it to.
final class CameraSourceLifetimeTests: XCTestCase {
    /// TEST-NET-3 (RFC 5737): guaranteed not to be a real printer, so `start()`
    /// exercises the connect path without reaching anything.
    private var unreachable: PrinterConfig {
        PrinterConfig(ip: "203.0.113.1", serial: "TEST", accessCode: "none")
    }

    func testDroppingAStartedSourceDeallocatesIt() {
        weak var released: BambuCameraSource?
        do {
            let source = BambuCameraSource(config: unreachable)
            released = source
            source.start()
            XCTAssertNotNil(released)
        }
        // If the streaming task held the source, this is where it would show:
        // the owner has let go and nothing else should be keeping it alive.
        XCTAssertNil(
            released,
            "a started source outlived its owner — the streaming task is retaining it, "
                + "so a caller that simply drops the source leaks a running stream")
    }

    func testStopIsSafeToCallWithoutStart() {
        let source = BambuCameraSource(config: unreachable)
        source.stop()
        source.stop()
    }
}
