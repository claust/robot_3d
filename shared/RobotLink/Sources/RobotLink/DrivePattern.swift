import Foundation

/// Preset routes the car drives by itself, each 40 cm across.
///
/// The car has no wheel sensors, so a pattern is open loop: timed wheel
/// commands, worked out from the car's geometry and a model of how fast a
/// wheel rolls for a given command (`speed`). How far it really goes
/// depends on the floor, the battery and the drag of the nose, so
/// `Calibration` corrects each kind of move. On top of that, each command
/// reaches the car on the next 20 Hz tick, and over Bluetooth some arrive a
/// tick late, so moves scatter by a few degrees or millimetres from run to
/// run.
///
/// The Pi's slew limit ramps each wheel up and down at the same rate, so a
/// held speed covers the distance its time says: the ramp-up lost at the
/// start comes back in the ramp-down at the end.
public enum DrivePattern: String, CaseIterable, Identifiable, Sendable {
    /// 40 cm sides, turning left on the spot at each corner; it ends where
    /// it started, facing the same way.
    case square
    /// One 40 cm circle to the left, back to the start.
    case circle
    /// A 40 cm circle to the left, then one to the right: an eight lying
    /// across the car's path, its loops meeting where the car started.
    case figureEight

    public var id: Self { self }

    /// Corrections to the model, one per kind of move. Each is 1 when the
    /// model is right. Factors are clamped to `range`, and one that isn't a
    /// number counts as 1.
    public struct Calibration: Equatable, Sendable {
        /// Scales the time of the square's sides.
        public var straight: Double
        /// Scales the time of the square's corners, turned on the spot.
        public var corners: Double
        /// Scales the circle the wheel speeds aim for, in the circle and the
        /// eight's two loops, but not the time it takes. A circle that comes
        /// out too wide has wheels running closer to the same speed than the
        /// model says, so it turns too slowly as well; aiming for a tighter
        /// one fixes both.
        public var circleSize: Double
        /// Scales the time of each circle: how far round it goes.
        public var circleLength: Double

        public static let range: ClosedRange<Double> = 0.5...2

        public init(straight: Double = 1, corners: Double = 1, circleSize: Double = 1, circleLength: Double = 1) {
            self.straight = straight
            self.corners = corners
            self.circleSize = circleSize
            self.circleLength = circleLength
        }
    }

    /// The side of the square and the diameter of each circle, in cm.
    public static let size = 40.0

    /// The moves that drive this pattern. The last one is a pause at rest,
    /// so the pattern ends once the wheels have ramped down.
    public func steps(_ calibration: Calibration = Calibration()) -> [DriveStep] {
        let radius = Self.size / 2
        let circle = { (side: Side) in
            Self.arc(side, radius: radius, size: calibration.circleSize, length: calibration.circleLength)
        }
        switch self {
        case .square:
            let side = Self.straight(Self.size, factor: calibration.straight)
            let corner = Self.spin(.left, by: .pi / 2, factor: calibration.corners)
            return Array(repeatElement([side, Self.rest, corner, Self.rest], count: 4).joined())
        case .circle:
            return [circle(.left), Self.rest]
        case .figureEight:
            return [circle(.left), circle(.right), Self.rest]
        }
    }

    // MARK: - The car, as the timing sees it

    /// Distance between the tyres' centre lines, in cm. The tyres sit
    /// 55.6 mm either side of the car's centre line (cad/robot_car,
    /// `wheel_geometry` in assembly.py).
    static let track = 11.1
    /// The track the car turns on the spot as if it had, in cm. Fitted to
    /// floor runs of the square: spinning, it turns faster than its real
    /// track says.
    static let spinTrack = 10.0
    /// A wheel's ground speed in cm/s just above zero command, and at full
    /// command. The Pi lifts any command above zero to the motors' 25 %
    /// starting duty, and on the floor that already rolls the car at a third
    /// of its top speed; above it, speed grows in proportion to the command.
    /// Fitted to floor runs of the square and the circle.
    static let minSpeed = 7.5
    static let fullSpeed = 22.5
    /// The commands each kind of move runs at; for a circle, the outer
    /// wheel's. The circle's is the highest, so its inner wheel still gets a
    /// command well clear of zero, at least `minArcCommand`, so it never
    /// stops or reverses.
    static let straightCommand = 0.5
    static let spinCommand = 0.4
    static let arcCommand = 0.8
    static let minArcCommand = 0.05
    /// Rest between moves, long enough for the wheels to ramp down, so the
    /// end of one move doesn't blend into the next.
    static let pause = 0.3

    /// Ground speed in cm/s for a signed command in -1...1.
    static func speed(_ command: Double) -> Double {
        guard command != 0 else { return 0 }
        let magnitude = minSpeed + (fullSpeed - minSpeed) * min(abs(command), 1)
        return command > 0 ? magnitude : -magnitude
    }

    /// The forward command that rolls a wheel at `cmPerSecond`: `speed`
    /// undone, before any clamping.
    static func command(_ cmPerSecond: Double) -> Double {
        (cmPerSecond - minSpeed) / (fullSpeed - minSpeed)
    }

    /// How the model says the car moves under `wheels`: its centre's speed
    /// in cm/s, and its turn rate in rad/s, anticlockwise positive. Wheels
    /// running opposite ways turn it on `spinTrack`.
    static func motion(_ wheels: WheelSpeeds) -> (speed: Double, turnRate: Double) {
        let left = speed(wheels.left)
        let right = speed(wheels.right)
        let track = left * right < 0 ? spinTrack : track
        return ((left + right) / 2, (right - left) / track)
    }

    enum Side { case left, right }

    static let rest = DriveStep(wheels: .stop, seconds: pause)

    static func straight(_ cm: Double, factor: Double) -> DriveStep {
        let wheels = WheelSpeeds(left: straightCommand, right: straightCommand)
        return DriveStep(wheels: wheels, seconds: cm / motion(wheels).speed * trim(factor))
    }

    /// Turn on the spot, the wheels running opposite ways.
    static func spin(_ side: Side, by radians: Double, factor: Double) -> DriveStep {
        let left = side == .left ? -spinCommand : spinCommand
        let wheels = WheelSpeeds(left: left, right: -left)
        return DriveStep(wheels: wheels, seconds: radians / abs(motion(wheels).turnRate) * trim(factor))
    }

    /// One full circle with the car's centre on `radius`: the outer wheel at
    /// `arcCommand`, the inner one slower in proportion to its smaller
    /// circle. `size` scales the circle the speeds aim for; the time is that
    /// of the nominal circle, scaled by `length`.
    static func arc(_ side: Side, radius: Double, size: Double, length: Double) -> DriveStep {
        let outer = speed(arcCommand)
        func inner(_ r: Double) -> Double {
            max(minArcCommand, command(outer * (r - track / 2) / (r + track / 2)))
        }
        let turnRate = motion(WheelSpeeds(left: inner(radius), right: arcCommand)).turnRate
        let aimed = inner(radius * trim(size))
        return DriveStep(
            wheels: side == .left
                ? WheelSpeeds(left: aimed, right: arcCommand)
                : WheelSpeeds(left: arcCommand, right: aimed),
            seconds: 2 * .pi / turnRate * trim(length))
    }

    static func trim(_ factor: Double) -> Double {
        factor.isFinite ? factor.clamped(to: Calibration.range) : 1
    }
}

/// One move of a pattern: wheel speeds held for a time.
public struct DriveStep: Equatable, Sendable {
    public let wheels: WheelSpeeds
    public let seconds: Double

    public init(wheels: WheelSpeeds, seconds: Double) {
        self.wheels = wheels
        self.seconds = seconds
    }
}
