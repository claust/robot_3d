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
        let subjects = BambuTrust.rootCertificateDERs
            .compactMap { SecCertificateCreateWithData(nil, $0 as CFData) }
            .compactMap { SecCertificateCopySubjectSummary($0) as String? }
        XCTAssertTrue(
            subjects.contains("BBL CA2 RSA"),
            "expected the device CA's issuer among the roots, got \(subjects)")
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
