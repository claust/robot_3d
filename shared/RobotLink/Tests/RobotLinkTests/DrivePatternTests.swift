import Foundation
import Testing
@testable import RobotLink

/// Drives each pattern through the same model the timing comes from, so the
/// shapes are checked in centimetres: if the car moved exactly as modelled,
/// this is the path it would take.
@Suite struct DrivePatternTests {
    /// The car's centre in cm and its heading in radians, anticlockwise from
    /// +x. It starts at the origin facing +y.
    struct Pose {
        var x = 0.0
        var y = 0.0
        var heading = Double.pi / 2
    }

    static func advance(_ p: Pose, _ wheels: WheelSpeeds, for t: Double) -> Pose {
        let (v, omega) = DrivePattern.motion(wheels)
        var q = p
        if abs(omega) < 1e-12 {
            q.x += v * t * cos(p.heading)
            q.y += v * t * sin(p.heading)
        } else {
            q.heading += omega * t
            q.x += v / omega * (sin(q.heading) - sin(p.heading))
            q.y -= v / omega * (cos(q.heading) - cos(p.heading))
        }
        return q
    }

    /// The pose at the end of each step.
    static func ends(_ steps: [DriveStep]) -> [Pose] {
        var pose = Pose()
        return steps.map { step in
            pose = advance(pose, step.wheels, for: step.seconds)
            return pose
        }
    }

    /// Every pose along the way, sampled every 10 ms.
    static func path(_ steps: [DriveStep]) -> [Pose] {
        var pose = Pose()
        var poses = [pose]
        for step in steps {
            var t = 0.0
            while t < step.seconds {
                let dt = min(0.01, step.seconds - t)
                pose = advance(pose, step.wheels, for: dt)
                poses.append(pose)
                t += dt
            }
        }
        return poses
    }

    static func bounds(_ poses: [Pose]) -> (x: ClosedRange<Double>, y: ClosedRange<Double>) {
        let xs = poses.map(\.x), ys = poses.map(\.y)
        return (xs.min()!...xs.max()!, ys.min()!...ys.max()!)
    }

    func near(_ a: Double, _ b: Double, _ tolerance: Double = 0.01) -> Bool {
        abs(a - b) < tolerance
    }

    func at(_ pose: Pose, _ x: Double, _ y: Double, heading: Double) -> Bool {
        near(pose.x, x) && near(pose.y, y) && near(pose.heading, heading, 1e-6)
    }

    @Test func squareHas40cmSidesAndLeftCorners() {
        let ends = Self.ends(DrivePattern.square.steps())
        #expect(ends.count == 16)
        // Side, rest, corner, rest, four times over.
        #expect(at(ends[0], 0, 40, heading: .pi / 2))
        #expect(at(ends[2], 0, 40, heading: .pi))
        #expect(at(ends[4], -40, 40, heading: .pi))
        #expect(at(ends[8], -40, 0, heading: 3 * .pi / 2))
        #expect(at(ends[12], 0, 0, heading: 2 * .pi))
        #expect(at(ends[15], 0, 0, heading: .pi / 2 + 2 * .pi))
    }

    @Test func circleIs40cmAcrossAndCloses() {
        let steps = DrivePattern.circle.steps()
        #expect(at(Self.ends(steps).last!, 0, 0, heading: .pi / 2 + 2 * .pi))
        let box = Self.bounds(Self.path(steps))
        #expect(near(box.x.lowerBound, -40) && near(box.x.upperBound, 0))
        #expect(near(box.y.lowerBound, -20) && near(box.y.upperBound, 20))
    }

    @Test func eightIsTwoLoopsMeetingAtTheStart() {
        let steps = DrivePattern.figureEight.steps()
        let ends = Self.ends(steps)
        #expect(at(ends[0], 0, 0, heading: .pi / 2 + 2 * .pi))
        #expect(at(ends[1], 0, 0, heading: .pi / 2))
        let box = Self.bounds(Self.path(steps))
        #expect(near(box.x.lowerBound, -40) && near(box.x.upperBound, 40))
        #expect(near(box.y.lowerBound, -20) && near(box.y.upperBound, 20))
    }

    @Test func everyPatternEndsAtRest() {
        for pattern in DrivePattern.allCases {
            #expect(pattern.steps().last?.wheels == .stop)
        }
    }

    @Test func speedModelInvertsAndStopsAtZero() {
        for command in stride(from: 0.05, through: 1, by: 0.05) {
            #expect(near(DrivePattern.command(DrivePattern.speed(command)), command, 1e-12))
        }
        #expect(DrivePattern.speed(0) == 0)
        #expect(DrivePattern.speed(-0.4) == -DrivePattern.speed(0.4))
    }

    @Test func circlesInnerWheelStaysWellClearOfZero() {
        for step in DrivePattern.figureEight.steps().dropLast() {
            #expect(min(step.wheels.left, step.wheels.right) > 0.15)
        }
    }

    @Test func calibrationScalesOnlyItsOwnMoves() {
        let plain = DrivePattern.square.steps()
        let longer = DrivePattern.square.steps(.init(straight: 1.5))
        #expect(near(longer[0].seconds, plain[0].seconds * 1.5, 1e-9))
        #expect(longer[2] == plain[2])
        let turned = DrivePattern.square.steps(.init(corners: 0.8))
        #expect(near(turned[2].seconds, plain[2].seconds * 0.8, 1e-9))
        #expect(turned[0] == plain[0])

        let eight = DrivePattern.figureEight.steps()
        let longer8 = DrivePattern.figureEight.steps(.init(straight: 2, corners: 2, circleLength: 1.1))
        #expect(near(longer8[0].seconds, eight[0].seconds * 1.1, 1e-9))
        #expect(near(longer8[1].seconds, eight[1].seconds * 1.1, 1e-9))
        #expect(longer8[0].wheels == eight[0].wheels)
    }

    @Test func circleSizeChangesTheWheelsButNotTheTime() {
        let plain = DrivePattern.circle.steps()[0]
        let tighter = DrivePattern.circle.steps(.init(circleSize: 0.8))[0]
        #expect(tighter.seconds == plain.seconds)
        #expect(tighter.wheels.right == plain.wheels.right)
        #expect(tighter.wheels.left < plain.wheels.left)
        // Aimed at, the tighter circle is 32 cm across.
        let box = Self.bounds(Self.path([DriveStep(wheels: tighter.wheels, seconds: 30)]))
        #expect(near(box.x.upperBound - box.x.lowerBound, 32))
    }

    @Test func aVeryTightCircleNeverStopsTheInnerWheel() {
        let step = DrivePattern.circle.steps(.init(circleSize: 0.5))[0]
        #expect(step.wheels.left == DrivePattern.minArcCommand)
        #expect(step.seconds.isFinite && step.seconds > 0)
    }

    @Test func calibrationIsClampedAndNaNIgnored() {
        let plain = DrivePattern.square.steps()
        #expect(near(DrivePattern.square.steps(.init(straight: 9))[0].seconds, plain[0].seconds * 2, 1e-9))
        #expect(near(DrivePattern.square.steps(.init(straight: 0))[0].seconds, plain[0].seconds * 0.5, 1e-9))
        #expect(DrivePattern.square.steps(.init(straight: .nan)) == plain)
        #expect(DrivePattern.square.steps(.init(corners: .infinity)) == plain)
    }
}

/// The pattern player in `CarLink`, on the simulated car.
@MainActor @Suite struct CarLinkPatternTests {
    func waitUntil(_ condition: () -> Bool) async throws {
        let deadline = ContinuousClock.now + .seconds(3)
        while !condition() {
            guard ContinuousClock.now < deadline else {
                Issue.record("timed out")
                return
            }
            try await Task.sleep(for: .milliseconds(10))
        }
    }

    func connected() async throws -> CarLink {
        let link = CarLink(simulated: true)
        link.start()
        try await waitUntil { link.isConnected }
        return link
    }

    @Test func drivesEachStepThenStops() async throws {
        let link = try await connected()
        let forward = WheelSpeeds(left: 0.5, right: 0.5)
        let spin = WheelSpeeds(left: -0.4, right: 0.4)
        link.play([DriveStep(wheels: forward, seconds: 0.2), DriveStep(wheels: spin, seconds: 0.2)], as: .square)
        #expect(link.pattern?.pattern == .square)
        try await waitUntil { link.wheels == forward }
        try await waitUntil { link.wheels == spin }
        try await waitUntil { link.pattern == nil }
        #expect(link.wheels == .stop)
    }

    @Test func theThumbTakesOver() async throws {
        let link = try await connected()
        link.drive(.square)
        let thumb = WheelSpeeds(left: 0.2, right: 0.3)
        link.wheels = thumb
        #expect(link.pattern == nil)
        // The player's task never got to run its first step, and won't now.
        try await Task.sleep(for: .milliseconds(100))
        #expect(link.wheels == thumb)
    }

    @Test func stopEndsThePatternAndTheWheels() async throws {
        let link = try await connected()
        link.drive(.circle)
        try await waitUntil { link.wheels != .stop }
        link.stopPattern()
        #expect(link.pattern == nil)
        #expect(link.wheels == .stop)
    }

    @Test func losingTheLinkEndsThePatternForGood() async throws {
        let link = try await connected()
        link.drive(.figureEight)
        try await waitUntil { link.wheels != .stop }
        link.stop()
        #expect(link.pattern == nil)
        #expect(link.wheels == .stop)
        link.start()
        try await waitUntil { link.isConnected }
        try await Task.sleep(for: .milliseconds(100))
        #expect(link.wheels == .stop)
        #expect(link.pattern == nil)
    }

    @Test func nothingDrivesWithoutALink() {
        let link = CarLink(simulated: true)
        link.drive(.square)
        #expect(link.pattern == nil)
        #expect(link.wheels == .stop)
    }
}
