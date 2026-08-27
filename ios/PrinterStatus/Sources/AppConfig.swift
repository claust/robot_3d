import Foundation
import Security

/// Printer credentials. Same shape as the macOS app's PrinterConfig — the
/// shared BambuMQTTSource and PrinterNameSource compile against it — but
/// resolved differently: a phone has no `cad/.env` to walk up to, so the
/// values come from the in-app settings sheet (IP and serial in
/// UserDefaults, access code in the Keychain). BAMBU_* environment
/// variables still win when present, which is how the simulator gets live
/// credentials injected during development.
struct PrinterConfig {
    let ip: String
    let serial: String
    let accessCode: String

    static func load() -> PrinterConfig? {
        let env = ProcessInfo.processInfo.environment
        if let cfg = make(env["BAMBU_PRINTER_IP"], env["BAMBU_PRINTER_SERIAL"],
                          env["BAMBU_ACCESS_CODE"]) {
            return cfg
        }
        let defaults = UserDefaults.standard
        return make(defaults.string(forKey: SettingsKey.ip),
                    defaults.string(forKey: SettingsKey.serial),
                    Keychain.accessCode)
    }

    static func save(ip: String, serial: String, accessCode: String) {
        let defaults = UserDefaults.standard
        defaults.set(ip.trimmingCharacters(in: .whitespaces), forKey: SettingsKey.ip)
        defaults.set(serial.trimmingCharacters(in: .whitespaces), forKey: SettingsKey.serial)
        Keychain.accessCode = accessCode.trimmingCharacters(in: .whitespaces)
    }

    private static func make(_ ip: String?, _ serial: String?, _ code: String?)
        -> PrinterConfig?
    {
        guard let ip, let serial, let code,
              !ip.isEmpty, !serial.isEmpty, !code.isEmpty else { return nil }
        return PrinterConfig(ip: ip, serial: serial, accessCode: code)
    }
}

enum SettingsKey {
    static let ip = "printerIP"
    static let serial = "printerSerial"
}

/// Minimal Keychain wrapper for the one secret the app holds. The access
/// code unlocks camera and control on the printer, so it does not belong in
/// UserDefaults, which backs up as plaintext.
enum Keychain {
    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: "dk.delectosoft.printerstatus",
         kSecAttrAccount as String: "bambu-access-code"]
    }

    static var accessCode: String? {
        get {
            var q = query
            q[kSecReturnData as String] = true
            q[kSecMatchLimit as String] = kSecMatchLimitOne
            var result: AnyObject?
            guard SecItemCopyMatching(q as CFDictionary, &result) == errSecSuccess,
                  let data = result as? Data else { return nil }
            return String(data: data, encoding: .utf8)
        }
        set {
            SecItemDelete(query as CFDictionary)
            guard let newValue, !newValue.isEmpty,
                  let data = newValue.data(using: .utf8) else { return }
            var q = query
            q[kSecValueData as String] = data
            q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            SecItemAdd(q as CFDictionary, nil)
        }
    }
}
