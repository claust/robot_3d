import Foundation

/// An IPv4 address plus netmask, as reported by one network interface.
public struct IPv4Subnet: Equatable, Sendable {
    /// Host byte order throughout; conversion happens at the socket edge.
    public let address: UInt32
    public let mask: UInt32
    public let interface: String

    public init(address: UInt32, mask: UInt32, interface: String = "") {
        self.address = address
        self.mask = mask
        self.interface = interface
    }

    public var prefixLength: Int { mask.nonzeroBitCount }

    /// Every usable host address in this subnet, minus our own — the
    /// network and broadcast addresses are excluded, and a `/31` or `/32`
    /// yields nothing at all.
    ///
    /// A wide subnet is clamped to `limit` addresses centred on our own,
    /// and reports `truncated`. Sweeping a /16 would be 65k hosts × 2
    /// ports: minutes of radio time on Wi-Fi for a printer that is almost
    /// certainly numbered near us. The caller decides what to tell the user.
    public func hostAddresses(limit: Int) -> (hosts: [String], truncated: Bool) {
        guard prefixLength < 31 else { return ([], false) }
        let network = address & mask
        let broadcast = network | ~mask
        guard broadcast > network + 1 else { return ([], false) }
        let first = network + 1
        let last = broadcast - 1

        var start = first
        var end = last
        var truncated = false
        // clamping: `limit` is public API, and a caller's Int can be
        // larger than UInt32 can hold
        let window = UInt32(clamping: max(2, limit))
        if last - first + 1 > window {
            truncated = true
            let half = window / 2
            // centre the window on our own address, then slide it back
            // inside the subnet at either end
            let centred = address >= first + half ? address - half : first
            start = min(centred, last - window + 1)
            end = start + window - 1
        }
        var hosts: [String] = []
        hosts.reserveCapacity(Int(end - start + 1))
        for raw in start...end where raw != address {
            hosts.append(Self.string(from: raw))
        }
        return (hosts, truncated)
    }

    public static func string(from raw: UInt32) -> String {
        "\((raw >> 24) & 0xFF).\((raw >> 16) & 0xFF).\((raw >> 8) & 0xFF).\(raw & 0xFF)"
    }

    /// The IPv4 subnets worth sweeping: Ethernet and Wi-Fi only. Cellular
    /// (`pdp_ip0`), VPN tunnels (`utun*`), Apple Wireless Direct (`awdl0`,
    /// `llw0`) and loopback are not paths to a printer, and probing them
    /// would be hundreds of pointless datagrams — or, on cellular, metered
    /// traffic to strangers.
    public static func localSubnets() -> [IPv4Subnet] {
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0, let first = head else { return [] }
        defer { freeifaddrs(head) }

        var subnets: [IPv4Subnet] = []
        for ptr in sequence(first: first, next: { $0.pointee.ifa_next }) {
            let flags = Int32(ptr.pointee.ifa_flags)
            guard flags & IFF_UP != 0, flags & IFF_RUNNING != 0,
                  flags & IFF_LOOPBACK == 0, flags & IFF_POINTOPOINT == 0,
                  let addr = ptr.pointee.ifa_addr, addr.pointee.sa_family == UInt8(AF_INET),
                  let netmask = ptr.pointee.ifa_netmask else { continue }
            let name = String(cString: ptr.pointee.ifa_name)
            guard name.hasPrefix("en"), !name.hasPrefix("enX") else { continue }
            let address = raw(addr)
            // 169.254/16 means DHCP never answered: nothing is reachable there
            guard address >> 16 != 0xA9FE else { continue }
            let subnet = IPv4Subnet(address: address, mask: raw(netmask), interface: name)
            // Dedupe by network, not by address: a Mac with both Wi-Fi and
            // Ethernet on the same LAN has two addresses in one subnet, and
            // sweeping it twice doubles the traffic for nothing.
            guard subnet.mask != 0, !subnets.contains(where: {
                $0.mask == subnet.mask && $0.address & $0.mask == subnet.address & subnet.mask
            }) else { continue }
            subnets.append(subnet)
        }
        return subnets
    }

    private static func raw(_ sa: UnsafeMutablePointer<sockaddr>) -> UInt32 {
        sa.withMemoryRebound(to: sockaddr_in.self, capacity: 1) {
            UInt32(bigEndian: $0.pointee.sin_addr.s_addr)
        }
    }
}

/// Finds Bambu printers on the local network by sweeping the subnet with
/// directed SSDP `M-SEARCH` datagrams, one per host.
///
/// Bambu's own discovery is a broadcast to 255.255.255.255, which is the
/// obvious thing to listen for and the wrong thing to build on here. Two
/// reasons: iOS gates broadcast and multicast behind the
/// `com.apple.developer.networking.multicast` entitlement, which Apple
/// grants by application only; and a passive listener on UDP 2021 loses to
/// SO_REUSEPORT — the kernel hands each broadcast to exactly one bound
/// socket, so Bambu Studio can starve it indefinitely (see RESEARCH.md).
/// Unicast has neither problem and answers in well under a second.
///
/// Both platforms still need their LAN privacy permission — Local Network
/// on iOS, System Settings > Privacy & Security > Local Network on macOS.
/// Neither has an API to read the grant, so a denied permission is
/// indistinguishable from an empty network: the sweep simply finds nothing,
/// and the UI has to offer that as an explanation.
///
/// Callbacks are delivered on the main queue.
public final class PrinterDiscovery {
    public enum Outcome: Equatable, Sendable {
        /// The sweep ran. `truncated` means at least one subnet was too
        /// large to probe exhaustively, so "not found" is not conclusive.
        case completed(hostsProbed: Int, truncated: Bool)
        /// No Ethernet or Wi-Fi IPv4 address — the device is offline, or on
        /// cellular only. Nothing was sent.
        case noLocalNetwork
    }

    /// Called once per newly discovered printer, as replies arrive.
    public var onPrinter: ((DiscoveredPrinter) -> Void)?
    /// Called once when the sweep finishes, with everything found.
    public var onFinished: (([DiscoveredPrinter], Outcome) -> Void)?

    /// Enough for a /22. Home networks are /24s; anything wider is either a
    /// misconfiguration or an office, and both want a bounded sweep.
    private let hostLimit: Int
    private var probe: SSDPProbe?
    private var found: [DiscoveredPrinter] = []
    private var stopped = false

    public init(hostLimit: Int = 1024) {
        self.hostLimit = hostLimit
    }

    /// Sweeps every local subnet. Single-shot: once it has finished or been
    /// stopped this object is spent, and another sweep means another
    /// `PrinterDiscovery` — which is what the scan buttons do. A second call
    /// while a sweep is running is ignored.
    public func start() {
        guard probe == nil, !stopped else { return }
        found = []

        var hosts: [String] = []
        var truncated = false
        for subnet in IPv4Subnet.localSubnets() {
            let (subnetHosts, wasTruncated) = subnet.hostAddresses(limit: hostLimit)
            hosts.append(contentsOf: subnetHosts)
            truncated = truncated || wasTruncated
        }
        guard !hosts.isEmpty else {
            DispatchQueue.main.async { [weak self] in
                self?.onFinished?([], .noLocalNetwork)
            }
            return
        }

        let probe = SSDPProbe(hosts: hosts)
        probe.onResponse = { printer in
            DispatchQueue.main.async { [weak self] in
                guard let self, !self.stopped else { return }
                // Both ports answer and every round re-probes, so the same
                // printer arrives several times; the first sighting wins.
                guard !self.found.contains(where: { $0.serial == printer.serial }) else { return }
                self.found.append(printer)
                self.onPrinter?(printer)
            }
        }
        probe.onFinished = {
            DispatchQueue.main.async { [weak self] in
                guard let self, !self.stopped else { return }
                // spent either way, so a stray restart cannot mix a new
                // sweep's results into this one's
                self.stopped = true
                self.probe = nil
                self.onFinished?(self.found,
                                 .completed(hostsProbed: hosts.count, truncated: truncated))
            }
        }
        self.probe = probe
        probe.start()
    }

    /// Stops the sweep; no further callbacks fire.
    public func stop() {
        stopped = true
        probe?.stop()
        probe = nil
    }
}
