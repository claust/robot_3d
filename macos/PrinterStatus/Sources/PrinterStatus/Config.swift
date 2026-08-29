import BambuKit
import Foundation

/// How the Mac resolves the credentials in `PrinterConfig` (which BambuKit
/// defines): from the environment, the installed app's own config file, or
/// the repo's `cad/.env`. The phone resolves the same type from its
/// settings sheet — see the iOS app's AppConfig.swift.
extension PrinterConfig {
    /// Config file used by the installed app, which lives in /Applications
    /// and so cannot find the repo by walking up from its own location.
    /// It holds either the three BAMBU_* values directly, or a single
    /// `BAMBU_ENV_FILE=/path/to/cad/.env` line pointing at them.
    static var appConfigURL: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory,
                                            in: .userDomainMask).first!
        return base.appendingPathComponent("PrinterStatus/config.env")
    }

    /// Resolution order: environment variables, then the app config file
    /// (following a BAMBU_ENV_FILE pointer if present), then `cad/.env`
    /// found by walking up from the working directory and the executable.
    static func load() -> PrinterConfig? {
        let env = ProcessInfo.processInfo.environment
        if let cfg = make(env["BAMBU_PRINTER_IP"], env["BAMBU_PRINTER_SERIAL"],
                          env["BAMBU_ACCESS_CODE"]) {
            return cfg
        }
        if let values = readEnvFile(appConfigURL) {
            if let cfg = make(values["BAMBU_PRINTER_IP"], values["BAMBU_PRINTER_SERIAL"],
                              values["BAMBU_ACCESS_CODE"]) {
                return cfg
            }
            // one hop only — a pointer file may not point at another pointer
            if let pointer = values["BAMBU_ENV_FILE"], !pointer.isEmpty,
               let pointed = readEnvFile(URL(fileURLWithPath: pointer)),
               let cfg = make(pointed["BAMBU_PRINTER_IP"], pointed["BAMBU_PRINTER_SERIAL"],
                              pointed["BAMBU_ACCESS_CODE"]) {
                return cfg
            }
        }
        for start in [FileManager.default.currentDirectoryPath,
                      Bundle.main.bundlePath] {
            var dir = URL(fileURLWithPath: start).standardizedFileURL
            for _ in 0..<8 {
                let envFile = dir.appendingPathComponent("cad/.env")
                if let values = readEnvFile(envFile),
                   let cfg = make(values["BAMBU_PRINTER_IP"], values["BAMBU_PRINTER_SERIAL"],
                                  values["BAMBU_ACCESS_CODE"]) {
                    return cfg
                }
                let parent = dir.deletingLastPathComponent()
                if parent == dir { break }
                dir = parent
            }
        }
        return nil
    }

    /// Parse a `KEY=value` file; nil if it can't be read.
    private static func readEnvFile(_ url: URL) -> [String: String]? {
        guard let text = try? String(contentsOf: url, encoding: .utf8) else { return nil }
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
        return values
    }

    /// All three credentials must be present and non-empty.
    private static func make(_ ip: String?, _ serial: String?, _ code: String?)
        -> PrinterConfig?
    {
        guard let ip, let serial, let code,
              !ip.isEmpty, !serial.isEmpty, !code.isEmpty else { return nil }
        return PrinterConfig(ip: ip, serial: serial, accessCode: code)
    }
}
