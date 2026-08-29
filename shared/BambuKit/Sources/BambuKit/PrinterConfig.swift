import Foundation

/// The three credentials every LAN connection needs. Only the value type is
/// shared: *resolving* it is per-app and lives in each app's own module —
/// the Mac walks up to `cad/.env`, the phone reads UserDefaults and the
/// Keychain — as `static func load()` in an extension on this type.
public struct PrinterConfig: Equatable {
    public let ip: String
    public let serial: String
    public let accessCode: String

    public init(ip: String, serial: String, accessCode: String) {
        self.ip = ip
        self.serial = serial
        self.accessCode = accessCode
    }
}
