import XCTest
@testable import BambuKit

/// The parsing and address arithmetic behind `PrinterDiscovery` — the parts
/// that are pure, and the parts most likely to be quietly wrong.
final class DiscoveryTests: XCTestCase {
    /// Captured verbatim from our X2D answering a directed M-SEARCH.
    private let x2dResponse = """
    HTTP/1.1 200 OK\r
    Server: UPnP/1.0\r
    Date: Fri, 28 Aug 2026 14:50:11 GMT\r
    Location: 192.168.86.97\r
    ST: urn:bambulab-com:device:3dprinter:1\r
    EXT: \r
    USN: 20P5BJ661500023\r
    Cache-Control: max-age=1800\r
    DevModel.bambu.com: N6\r
    DevName.bambu.com: Claudia\r
    DevConnect.bambu.com: lan\r
    DevBind.bambu.com: free\r
    Devseclink.bambu.com: secure\r
    DevInf.bambu.com: wlan0\r
    DevVersion.bambu.com: 01.02.00.00\r
    DevCap.bambu.com: 1\r
    """

    func testParsesPrinterFromRealResponse() throws {
        let printer = try XCTUnwrap(SSDP.parsePrinter(from: x2dResponse, ip: "192.168.86.97"))
        XCTAssertEqual(printer.serial, "20P5BJ661500023")
        XCTAssertEqual(printer.name, "Claudia")
        XCTAssertEqual(printer.model, "N6")
        XCTAssertEqual(printer.modelName, "X2D")
        XCTAssertEqual(printer.version, "01.02.00.00")
        XCTAssertEqual(printer.displayName, "Claudia")
    }

    /// The sender's address wins over the `Location` header, which is what
    /// the printer believes about itself and may be stale.
    func testUsesSenderAddressNotLocationHeader() throws {
        let body = x2dResponse.replacingOccurrences(of: "Location: 192.168.86.97",
                                                    with: "Location: 10.0.0.5")
        let printer = try XCTUnwrap(SSDP.parsePrinter(from: body, ip: "192.168.86.97"))
        XCTAssertEqual(printer.ip, "192.168.86.97")
    }

    func testIgnoresNonBambuResponders() {
        let body = """
        HTTP/1.1 200 OK\r
        ST: urn:schemas-upnp-org:device:MediaRenderer:1\r
        USN: uuid:1234::urn:schemas-upnp-org:device:MediaRenderer:1\r
        """
        XCTAssertNil(SSDP.parsePrinter(from: body, ip: "192.168.86.40"))
    }

    func testIgnoresResponseWithoutSerial() {
        let body = "HTTP/1.1 200 OK\r\nST: urn:bambulab-com:device:3dprinter:1\r\n"
        XCTAssertNil(SSDP.parsePrinter(from: body, ip: "192.168.86.97"))
    }

    /// A nameless printer still has to be pickable in the list.
    func testDisplayNameFallsBackToModelThenSerial() {
        let unnamed = DiscoveredPrinter(ip: "10.0.0.2", serial: "S1", name: "",
                                        model: "N6", version: "")
        XCTAssertEqual(unnamed.displayName, "X2D")
        let bare = DiscoveredPrinter(ip: "10.0.0.2", serial: "S1", name: "",
                                     model: "", version: "")
        XCTAssertEqual(bare.displayName, "S1")
    }

    // MARK: - Subnet arithmetic

    private func subnet(_ address: String, _ mask: String) -> IPv4Subnet {
        IPv4Subnet(address: Self.raw(address), mask: Self.raw(mask))
    }

    private static func raw(_ dotted: String) -> UInt32 {
        dotted.split(separator: ".").reduce(UInt32(0)) { ($0 << 8) | UInt32($1)! }
    }

    func testSlash24SkipsNetworkBroadcastAndSelf() {
        let (hosts, truncated) = subnet("192.168.86.63", "255.255.255.0")
            .hostAddresses(limit: 1024)
        XCTAssertFalse(truncated)
        XCTAssertEqual(hosts.count, 253)  // .1-.254, minus ourselves
        XCTAssertEqual(hosts.first, "192.168.86.1")
        XCTAssertEqual(hosts.last, "192.168.86.254")
        XCTAssertFalse(hosts.contains("192.168.86.0"))
        XCTAssertFalse(hosts.contains("192.168.86.255"))
        XCTAssertFalse(hosts.contains("192.168.86.63"))
        XCTAssertTrue(hosts.contains("192.168.86.97"))
    }

    func testSlash22FitsUnderTheLimit() {
        let (hosts, truncated) = subnet("10.0.4.20", "255.255.252.0")
            .hostAddresses(limit: 1024)
        XCTAssertFalse(truncated)
        XCTAssertEqual(hosts.count, 1021)  // 1022 usable, minus ourselves
    }

    /// A /16 is clamped to a window around our own address rather than
    /// sweeping 65k hosts.
    func testWideSubnetIsClampedAroundOurAddress() {
        let (hosts, truncated) = subnet("172.16.40.10", "255.255.0.0")
            .hostAddresses(limit: 1024)
        XCTAssertTrue(truncated)
        XCTAssertEqual(hosts.count, 1023)
        XCTAssertEqual(hosts.first, "172.16.38.10")
        XCTAssertEqual(hosts.last, "172.16.42.9")
        XCTAssertTrue(hosts.contains("172.16.40.9"))
    }

    /// The window slides instead of running off either end of the subnet.
    func testClampedWindowStaysInsideSubnet() {
        let low = subnet("172.16.0.3", "255.255.0.0").hostAddresses(limit: 1024)
        XCTAssertEqual(low.hosts.first, "172.16.0.1")
        XCTAssertEqual(low.hosts.count, 1023)

        let high = subnet("172.16.255.250", "255.255.0.0").hostAddresses(limit: 1024)
        XCTAssertEqual(high.hosts.last, "172.16.255.254")
        XCTAssertEqual(high.hosts.count, 1023)
    }

    func testPointToPointSubnetsYieldNoHosts() {
        XCTAssertTrue(subnet("10.0.0.1", "255.255.255.254").hostAddresses(limit: 1024).hosts.isEmpty)
        XCTAssertTrue(subnet("10.0.0.1", "255.255.255.255").hostAddresses(limit: 1024).hosts.isEmpty)
    }

    func testPrefixLength() {
        XCTAssertEqual(subnet("192.168.86.63", "255.255.255.0").prefixLength, 24)
        XCTAssertEqual(subnet("10.0.4.20", "255.255.252.0").prefixLength, 22)
    }

    // MARK: - Probe wiring

    /// With no hosts there is nothing to send, and the caller must still be
    /// told the sweep is over or a spinner runs forever.
    func testProbeWithNoHostsFinishes() {
        let probe = SSDPProbe(hosts: [], rounds: 1, roundInterval: 0, listenSeconds: 0)
        let finished = expectation(description: "finished")
        probe.onFinished = { finished.fulfill() }
        probe.start()
        wait(for: [finished], timeout: 2)
    }

    /// Discovery answers on the main queue: the UI binds straight to it.
    func testDiscoveryFinishesOnMainQueue() {
        let discovery = PrinterDiscovery(hostLimit: 4)
        let finished = expectation(description: "finished")
        discovery.onFinished = { _, _ in
            XCTAssertTrue(Thread.isMainThread)
            finished.fulfill()
        }
        discovery.start()
        wait(for: [finished], timeout: 30)
        discovery.stop()
    }
}
