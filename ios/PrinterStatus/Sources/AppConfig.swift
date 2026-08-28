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

    /// False when the access code could not be stored in the Keychain —
    /// the caller must surface that, or the credential is silently lost.
    /// The Keychain write goes first: a failed save must not leave a
    /// half-updated config (new IP/serial, old or missing access code).
    static func save(ip: String, serial: String, accessCode: String) -> Bool {
        guard Keychain.setAccessCode(accessCode.trimmingCharacters(in: .whitespaces)) else {
            return false
        }
        let defaults = UserDefaults.standard
        defaults.set(ip.trimmingCharacters(in: .whitespaces), forKey: SettingsKey.ip)
        defaults.set(serial.trimmingCharacters(in: .whitespaces), forKey: SettingsKey.serial)
        return true
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
        var q = query
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    /// Store (or, for an empty value, remove) the access code. False when
    /// the Keychain refused the write — locked, missing entitlement — and
    /// the caller has to tell the user rather than pretend the save
    /// happened. Add-or-update rather than delete-then-add, so a failed
    /// write leaves the previously working credential in place.
    static func setAccessCode(_ value: String) -> Bool {
        guard !value.isEmpty else {
            let status = SecItemDelete(query as CFDictionary)
            return status == errSecSuccess || status == errSecItemNotFound
        }
        guard let data = value.data(using: .utf8) else { return false }
        // ThisDeviceOnly keeps the code out of backups and iCloud Keychain;
        // WhenUnlocked suffices since the app only reads it in the foreground.
        let attrs: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        ]
        var add = query
        attrs.forEach { add[$0] = $1 }
        let status = SecItemAdd(add as CFDictionary, nil)
        if status == errSecDuplicateItem {
            return SecItemUpdate(query as CFDictionary, attrs as CFDictionary) == errSecSuccess
        }
        return status == errSecSuccess
    }
}
