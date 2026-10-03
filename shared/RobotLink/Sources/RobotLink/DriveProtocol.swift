import CoreBluetooth

/// The GATT contract with `pi/robot_car/remote.py`. Change both sides together.
///
/// The car advertises one service with one characteristic. The phone writes
/// a 3-byte command to it without response, `rate` times a second while
/// connected: a sequence number, then the left and right wheel speeds as
/// signed bytes, -100...100. Zeros are sent too, because the stream is also
/// the heartbeat: the Pi stops the wheels when it goes quiet for 300 ms.
///
/// The characteristic only accepts writes over a link authenticated by
/// passkey pairing; `LinkMachine` describes how the first write gets iOS to
/// pair.
public enum DriveProtocol {
    public static let serviceUUID = CBUUID(string: "0BF63E73-EDAC-4F6D-B68E-D6B8F42E2E47")
    public static let driveUUID = CBUUID(string: "93F818BE-A53D-4AEB-B292-BF122D178473")
    public static let rate: Double = 20
    /// The verifying write's sequence number. The stream starts at 0, so 255
    /// keeps the numbering contiguous and the Pi doesn't count the wrap from
    /// one to the other as 255 skipped ticks.
    public static let verifySeq: UInt8 = .max

    public static func encode(_ wheels: WheelSpeeds, seq: UInt8) -> Data {
        Data([seq, byte(wheels.left), byte(wheels.right)])
    }

    private static func byte(_ speed: Double) -> UInt8 {
        UInt8(bitPattern: Int8((speed.clamped(to: -1...1) * 100).rounded()))
    }
}
