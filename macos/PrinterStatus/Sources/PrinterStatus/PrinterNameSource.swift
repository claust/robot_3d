import Foundation

/// The printer's user-assigned name ("Claudia") is not in the MQTT report —
/// it lives in the SSDP headers (`DevName.bambu.com`). Passively listening
/// on the broadcast port (UDP 2021) is fragile: with SO_REUSEPORT the kernel
/// hands each broadcast to only one of the bound sockets, so Bambu Studio or
/// a second instance can starve us forever (observed live). Instead, send a
/// directed M-SEARCH to the printer, which replies unicast to our ephemeral
/// port — immediate and contention-free. Retries a few times, then gives up
/// quietly; the name is cosmetic.
final class PrinterNameSource {
    var onName: ((String) -> Void)?

    private let ip: String
    private let queue = DispatchQueue(label: "PrinterStatus.ssdp")
    private var readSource: (any DispatchSourceRead)?
    private var timer: (any DispatchSourceTimer)?
    private var fd: Int32 = -1
    private var attempts = 0

    init(ip: String) {
        self.ip = ip
    }

    func start() {
        fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        guard fd >= 0 else { return }
        let src = DispatchSource.makeReadSource(fileDescriptor: fd, queue: queue)
        src.setEventHandler { [weak self] in self?.readReply() }
        src.setCancelHandler { [fd] in close(fd) }
        src.resume()
        readSource = src

        let t = DispatchSource.makeTimerSource(queue: queue)
        t.schedule(deadline: .now(), repeating: .seconds(3))
        t.setEventHandler { [weak self] in self?.sendQuery() }
        t.resume()
        timer = t
    }

    func stop() {
        timer?.cancel(); timer = nil
        readSource?.cancel(); readSource = nil
    }

    private func sendQuery() {
        attempts += 1
        if attempts > 10 {
            stop()
            return
        }
        let message = "M-SEARCH * HTTP/1.1\r\n"
            + "HOST: \(ip):2021\r\n"
            + "MAN: \"ssdp:discover\"\r\n"
            + "MX: 3\r\n"
            + "ST: urn:bambulab-com:device:3dprinter:1\r\n\r\n"
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = UInt16(2021).bigEndian
        guard inet_pton(AF_INET, ip, &addr.sin_addr) == 1 else { return }
        let payload = Array(message.utf8)
        _ = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                sendto(fd, payload, payload.count, 0, sa,
                       socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
    }

    private func readReply() {
        var buffer = [UInt8](repeating: 0, count: 4096)
        var sender = sockaddr_in()
        var senderLen = socklen_t(MemoryLayout<sockaddr_in>.size)
        let count = withUnsafeMutablePointer(to: &sender) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                recvfrom(fd, &buffer, buffer.count, 0, sa, &senderLen)
            }
        }
        guard count > 0 else { return }
        var ipChars = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
        var senderAddr = sender.sin_addr
        inet_ntop(AF_INET, &senderAddr, &ipChars, socklen_t(INET_ADDRSTRLEN))
        guard String(cString: ipChars) == ip,
              let text = String(bytes: buffer[..<count], encoding: .utf8) else { return }
        for line in text.split(whereSeparator: \.isNewline) {
            let prefix = "DevName.bambu.com:"
            guard line.hasPrefix(prefix) else { continue }
            let name = line.dropFirst(prefix.count).trimmingCharacters(in: .whitespaces)
            if !name.isEmpty {
                onName?(name)
                stop()
            }
            return
        }
    }
}
