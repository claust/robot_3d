import Foundation

/// One printer that answered an SSDP `M-SEARCH`. Everything here comes out
/// of the reply headers, so a discovered printer already knows two of the
/// three credentials — only the access code has to be typed in.
public struct DiscoveredPrinter: Hashable, Identifiable, Sendable {
    public var id: String { serial }
    public let ip: String
    /// `USN` header — the printer's serial, which MQTT topics are keyed on.
    public let serial: String
    /// `DevName.bambu.com` — the user-assigned name ("Claudia"), may be empty.
    public let name: String
    /// `DevModel.bambu.com` — a model code, e.g. `N6` for the X2D.
    public let model: String
    /// `DevVersion.bambu.com` — firmware version, e.g. `01.02.00.00`.
    public let version: String

    public init(ip: String, serial: String, name: String, model: String, version: String) {
        self.ip = ip
        self.serial = serial
        self.name = name
        self.model = model
        self.version = version
    }

    /// Model codes are not documented; only the one we can verify against
    /// our own hardware is translated, and anything else shows the raw code
    /// rather than a guess.
    public var modelName: String {
        model == "N6" ? "X2D" : model
    }

    /// What to show as the printer's title in a discovery list.
    public var displayName: String {
        name.isEmpty ? (modelName.isEmpty ? serial : modelName) : name
    }
}

/// The SSDP dialect Bambu printers speak. They answer a directed (unicast)
/// `M-SEARCH` on UDP 1990 and 2021 with a single response carrying the
/// device headers below; they also broadcast the same headers unsolicited,
/// but never listen for those — see `PrinterDiscovery` for why.
enum SSDP {
    /// Both ports answer identically (verified live); probing both costs one
    /// extra datagram per host and survives a firmware that drops one.
    static let ports: [UInt16] = [1990, 2021]

    static let searchTarget = "urn:bambulab-com:device:3dprinter:1"

    /// `MX` is the responder's maximum random delay in seconds. Directed
    /// M-SEARCHes are answered immediately, so keep it at 1: a sweep should
    /// not leave a slow printer three seconds to reply.
    static func searchMessage(host: String, port: UInt16) -> String {
        "M-SEARCH * HTTP/1.1\r\n"
            + "HOST: \(host):\(port)\r\n"
            + "MAN: \"ssdp:discover\"\r\n"
            + "MX: 1\r\n"
            + "ST: \(searchTarget)\r\n\r\n"
    }

    /// Parse an SSDP response body. `ip` is the sender's address, which is
    /// trusted over the `Location` header — the header is the address the
    /// printer believes it has, and a NATed or stale value there would send
    /// MQTT somewhere unreachable. Returns nil for anything that is not a
    /// Bambu device reply, including other UPnP devices that answer.
    static func parsePrinter(from body: String, ip: String) -> DiscoveredPrinter? {
        let headers = parseHeaders(body)
        guard let serial = headers["usn"], !serial.isEmpty else { return nil }
        // Other UPnP devices on the LAN answer too when they see an
        // M-SEARCH; only Bambu's own search target is a printer. Match the
        // value case-insensitively: header names are normalised above, but
        // no firmware promises the casing of what it sends back.
        guard headers["st"]?.lowercased().contains("bambulab") == true
            || headers["devmodel.bambu.com"] != nil else { return nil }
        return DiscoveredPrinter(
            ip: ip,
            serial: serial,
            name: headers["devname.bambu.com"] ?? "",
            model: headers["devmodel.bambu.com"] ?? "",
            version: headers["devversion.bambu.com"] ?? ""
        )
    }

    /// Header names are lowercased; the printer's casing is not guaranteed
    /// across firmware versions. The `HTTP/1.1 200 OK` status line has no
    /// colon and drops out on its own.
    static func parseHeaders(_ body: String) -> [String: String] {
        var headers: [String: String] = [:]
        for line in body.split(whereSeparator: \.isNewline) {
            guard let colon = line.firstIndex(of: ":") else { continue }
            let key = line[..<colon].trimmingCharacters(in: .whitespaces).lowercased()
            let value = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
            guard !key.isEmpty else { continue }
            headers[key] = value
        }
        return headers
    }
}

/// Sends directed SSDP `M-SEARCH` datagrams to a list of hosts and reports
/// whoever answers. One UDP socket, one serial queue; sends are paced
/// because a phone that dumps hundreds of packets at an empty ARP table
/// gets `ENOBUFS` and loses most of them.
///
/// Callbacks fire on the probe's private queue, not the main thread.
final class SSDPProbe {
    /// Called once per response datagram — the caller dedupes.
    var onResponse: ((DiscoveredPrinter) -> Void)?
    /// Called after the last listening window closes, unless stopped first.
    var onFinished: (() -> Void)?

    private let hosts: [String]
    private let ports: [UInt16]
    private let rounds: Int
    private let roundInterval: Double
    private let listenSeconds: Double
    private let queue = DispatchQueue(label: "BambuKit.ssdp")

    /// A burst small enough to sit inside the interface send queue, repeated
    /// every `batchInterval`: ~8000 probes/s, so a /24 (508 datagrams) is
    /// out the door in ~60 ms while staying clear of ENOBUFS.
    private let batchSize = 32
    private let batchInterval: DispatchTimeInterval = .milliseconds(4)

    private var fd: Int32 = -1
    private var readSource: (any DispatchSourceRead)?
    private var sendTimer: (any DispatchSourceTimer)?
    private var pending: [(host: String, port: UInt16)] = []
    private var roundsLeft: Int
    private var stopped = false
    /// How many datagrams may still be put back after an ENOBUFS. Bounded
    /// so a send queue that stays saturated cannot keep `pending` topped up
    /// forever, which would mean the sweep never finishes.
    private var requeueBudget: Int

    /// - Parameters:
    ///   - rounds: how many times to probe every host. UDP has no
    ///     retransmit, so a single lost datagram is a missed printer;
    ///     a second pass costs milliseconds.
    ///   - roundInterval: seconds between rounds. Spacing them out makes a
    ///     round a genuine retry rather than a duplicate riding the same
    ///     buffers, and lets a caller keep asking a printer that is still
    ///     booting.
    ///   - listenSeconds: how long to keep listening after the final send.
    init(hosts: [String], ports: [UInt16] = SSDP.ports, rounds: Int = 2,
         roundInterval: Double = 0.6, listenSeconds: Double = 2.0) {
        self.hosts = hosts
        self.ports = ports
        self.rounds = max(1, rounds)
        self.roundInterval = roundInterval
        self.listenSeconds = listenSeconds
        self.roundsLeft = max(1, rounds)
        self.requeueBudget = hosts.count
    }

    func start() {
        queue.async { [self] in
            guard fd < 0, !stopped else { return }
            // Nothing to probe still has to finish, or a caller's spinner
            // spins forever.
            guard !hosts.isEmpty else {
                onFinished?()
                return
            }
            // Unicast only: no SO_BROADCAST and no multicast join, which is
            // exactly what keeps this off iOS's multicast entitlement.
            fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
            guard fd >= 0 else {
                onFinished?()
                return
            }
            var flags = fcntl(fd, F_GETFL, 0)
            flags |= O_NONBLOCK
            _ = fcntl(fd, F_SETFL, flags)

            let source = DispatchSource.makeReadSource(fileDescriptor: fd, queue: queue)
            source.setEventHandler { [weak self] in self?.drainReplies() }
            source.setCancelHandler { [fd] in close(fd) }
            source.resume()
            readSource = source

            beginRound()
        }
    }

    /// Idempotent, and safe to call from the response callback.
    func stop() {
        queue.async { [self] in
            teardown()
        }
    }

    /// Close the socket and disarm both sources. The fd is closed by the
    /// read source's cancel handler and nowhere else, so a probe that ends
    /// without passing through here leaks its descriptor and keeps
    /// delivering replies. Marks the probe stopped: it is single-shot, and
    /// callers make a new one per sweep. Must run on `queue`.
    private func teardown() {
        guard !stopped else { return }
        stopped = true
        sendTimer?.cancel(); sendTimer = nil
        readSource?.cancel(); readSource = nil
        fd = -1
        pending = []
    }

    private func beginRound() {
        guard !stopped else { return }
        roundsLeft -= 1
        pending = hosts.flatMap { host in ports.map { (host, $0) } }
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now(), repeating: batchInterval)
        timer.setEventHandler { [weak self] in self?.sendBatch() }
        timer.resume()
        sendTimer = timer
    }

    private func sendBatch() {
        guard !stopped else { return }
        guard !pending.isEmpty else {
            sendTimer?.cancel()
            sendTimer = nil
            if roundsLeft > 0 {
                queue.asyncAfter(deadline: .now() + roundInterval) { [weak self] in
                    self?.beginRound()
                }
            } else {
                queue.asyncAfter(deadline: .now() + listenSeconds) { [weak self] in
                    guard let self, !stopped else { return }
                    // Finishing on our own closes the socket exactly as
                    // stop() would; a late reply must not arrive after the
                    // caller has been told the sweep is over.
                    teardown()
                    onFinished?()
                }
            }
            return
        }
        var requeue: [(host: String, port: UInt16)] = []
        for _ in 0..<min(batchSize, pending.count) {
            // from the back: the order hosts are probed in does not matter,
            // and removeFirst would shift the whole array on every datagram
            let target = pending.removeLast()
            // ENOBUFS means the interface queue is full — the packet was
            // never sent, so put it back rather than dropping a host, up to
            // the budget. Past that the next round is the retry: dropping a
            // datagram costs one host one probe, while requeuing without
            // bound would stall the sweep for good.
            if !send(to: target.host, port: target.port), errno == ENOBUFS,
               requeueBudget > 0 {
                requeueBudget -= 1
                requeue.append(target)
            }
        }
        pending.append(contentsOf: requeue)
    }

    private func send(to host: String, port: UInt16) -> Bool {
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = port.bigEndian
        guard inet_pton(AF_INET, host, &addr.sin_addr) == 1 else { return false }
        let message = Array(SSDP.searchMessage(host: host, port: port).utf8)
        let sent = message.withUnsafeBytes { payload in
            withUnsafePointer(to: &addr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                    sendto(fd, payload.baseAddress, payload.count, 0, sa,
                           socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
        }
        return sent > 0
    }

    /// One readable event can cover several queued datagrams; read until the
    /// socket says it would block, or replies pile up unread.
    private func drainReplies() {
        var buffer = [UInt8](repeating: 0, count: 4096)
        while !stopped, fd >= 0 {
            var sender = sockaddr_in()
            var senderLen = socklen_t(MemoryLayout<sockaddr_in>.size)
            let count = buffer.withUnsafeMutableBytes { raw in
                withUnsafeMutablePointer(to: &sender) {
                    $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                        recvfrom(fd, raw.baseAddress, raw.count, 0, sa, &senderLen)
                    }
                }
            }
            guard count > 0 else { return }
            guard let ip = Self.address(of: sender),
                  let body = String(bytes: buffer[..<count], encoding: .utf8),
                  let printer = SSDP.parsePrinter(from: body, ip: ip) else { continue }
            onResponse?(printer)
        }
    }

    private static func address(of addr: sockaddr_in) -> String? {
        var sin = addr.sin_addr
        var chars = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
        return chars.withUnsafeMutableBufferPointer { buf -> String? in
            guard inet_ntop(AF_INET, &sin, buf.baseAddress, socklen_t(INET_ADDRSTRLEN)) != nil,
                  let base = buf.baseAddress else { return nil }
            return String(cString: base)
        }
    }
}
