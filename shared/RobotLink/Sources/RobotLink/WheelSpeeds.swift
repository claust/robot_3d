import Foundation

/// Signed wheel speeds, each in -1...1: positive drives the car forward.
public struct WheelSpeeds: Equatable, Sendable {
    public var left: Double
    public var right: Double

    public static let stop = WheelSpeeds(left: 0, right: 0)

    public init(left: Double, right: Double) {
        self.left = left.clamped(to: -1...1)
        self.right = right.clamped(to: -1...1)
    }

    /// One thumb, arcade style. `x` is right-positive and `y` forward-positive,
    /// in the unit disc. Straight up drives both wheels forward, straight down
    /// both back, sideways spins the car on the spot, and anything between is
    /// an arc: left = y + x, right = y - x, scaled back so neither exceeds 1.
    ///
    /// Inside `deadZone` of the centre the car stays still, so a resting thumb
    /// doesn't creep. Past it the throw is rescaled to start from zero, so the
    /// Pi's minimum-duty jump begins right at the dead zone's edge.
    public static func arcade(x: Double, y: Double, deadZone: Double = 0.08) -> WheelSpeeds {
        let r = (x * x + y * y).squareRoot()
        guard r > deadZone else { return .stop }
        let scale = min(1, (min(r, 1) - deadZone) / (1 - deadZone)) / r
        let (x, y) = (x * scale, y * scale)
        let left = y + x
        let right = y - x
        let over = max(1, abs(left), abs(right))
        return WheelSpeeds(left: left / over, right: right / over)
    }

    public func scaled(by factor: Double) -> WheelSpeeds {
        WheelSpeeds(left: left * factor, right: right * factor)
    }
}

extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}
