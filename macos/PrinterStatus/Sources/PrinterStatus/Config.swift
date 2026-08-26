import Foundation

/// Printer credentials, resolved from the environment or from `cad/.env`.
struct PrinterConfig {
    let ip: String
    let serial: String
    let accessCode: String

    /// Environment variables win; otherwise walk up from the working
    /// directory (and the executable's location) looking for `cad/.env`.
    static func load() -> PrinterConfig? {
        let env = ProcessInfo.processInfo.environment
        if let ip = env["BAMBU_PRINTER_IP"],
           let serial = env["BAMBU_PRINTER_SERIAL"],
           let code = env["BAMBU_ACCESS_CODE"] {
            return PrinterConfig(ip: ip, serial: serial, accessCode: code)
        }
        for start in [FileManager.default.currentDirectoryPath,
                      Bundle.main.bundlePath] {
            var dir = URL(fileURLWithPath: start).standardizedFileURL
            for _ in 0..<8 {
                let envFile = dir.appendingPathComponent("cad/.env")
                if let cfg = parse(envFile: envFile) { return cfg }
                let parent = dir.deletingLastPathComponent()
                if parent == dir { break }
                dir = parent
            }
        }
        return nil
    }

    private static func parse(envFile: URL) -> PrinterConfig? {
        guard let text = try? String(contentsOf: envFile, encoding: .utf8) else { return nil }
        var values: [String: String] = [:]
        for line in text.split(separator: "\n") {
            // trim newline characters too — the file may have CRLF endings
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.hasPrefix("#"), let eq = trimmed.firstIndex(of: "=") else { continue }
            let key = String(trimmed[..<eq]).trimmingCharacters(in: .whitespaces)
            var value = String(trimmed[trimmed.index(after: eq)...])
            value = value.trimmingCharacters(
                in: CharacterSet(charactersIn: "\"'").union(.whitespacesAndNewlines))
            values[key] = value
        }
        guard let ip = values["BAMBU_PRINTER_IP"],
              let serial = values["BAMBU_PRINTER_SERIAL"],
              let code = values["BAMBU_ACCESS_CODE"] else { return nil }
        return PrinterConfig(ip: ip, serial: serial, accessCode: code)
    }
}
