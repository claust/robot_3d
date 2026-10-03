import Foundation
import Testing
@testable import RobotLink

@Suite struct ArcadeMixTests {
    @Test func centreAndDeadZoneStayStill() {
        #expect(WheelSpeeds.arcade(x: 0, y: 0) == .stop)
        #expect(WheelSpeeds.arcade(x: 0.05, y: -0.05) == .stop)
    }

    @Test func straightUpAndDownDriveBothWheels() {
        #expect(WheelSpeeds.arcade(x: 0, y: 1) == WheelSpeeds(left: 1, right: 1))
        #expect(WheelSpeeds.arcade(x: 0, y: -1) == WheelSpeeds(left: -1, right: -1))
    }

    @Test func sidewaysSpinsOnTheSpot() {
        #expect(WheelSpeeds.arcade(x: 1, y: 0) == WheelSpeeds(left: 1, right: -1))
        #expect(WheelSpeeds.arcade(x: -1, y: 0) == WheelSpeeds(left: -1, right: 1))
    }

    @Test func diagonalArcsAroundTheInsideWheel() {
        let s = 0.5.squareRoot()
        let forwardRight = WheelSpeeds.arcade(x: s, y: s)
        #expect(abs(forwardRight.left - 1) < 1e-9)
        #expect(abs(forwardRight.right) < 1e-9)
    }

    @Test func throwStartsFromZeroAtTheDeadZoneEdge() {
        let justPast = WheelSpeeds.arcade(x: 0, y: 0.09, deadZone: 0.08)
        #expect(justPast.left > 0 && justPast.left < 0.02)
        let half = WheelSpeeds.arcade(x: 0, y: 0.54, deadZone: 0.08)
        #expect(abs(half.left - 0.5) < 1e-9)
    }

    @Test func initClampsToTheUnitRange() {
        #expect(WheelSpeeds(left: 10, right: -3) == WheelSpeeds(left: 1, right: -1))
    }

    @Test func nonFiniteSpeedsStopBothWheels() {
        #expect(WheelSpeeds(left: .nan, right: 0.5) == .stop)
        #expect(WheelSpeeds(left: 0.5, right: .infinity) == .stop)
        #expect(WheelSpeeds(left: 1, right: 1).scaled(by: .nan) == .stop)
        // And it encodes without trapping.
        #expect(Array(DriveProtocol.encode(WheelSpeeds(left: .nan, right: .nan), seq: 1)) == [1, 0, 0])
    }

    @Test func pastTheRimIsFullThrow() {
        #expect(WheelSpeeds.arcade(x: 0, y: 3) == WheelSpeeds(left: 1, right: 1))
    }
}

@Suite struct DriveProtocolTests {
    @Test func encodesSequenceThenSignedSpeeds() {
        let data = DriveProtocol.encode(WheelSpeeds(left: 1, right: -0.5), seq: 7)
        #expect(Array(data) == [7, 100, UInt8(bitPattern: -50)])
    }

    @Test func verifyWriteRunsStraightIntoTheStream() {
        // The stream's first tick is seq 0.
        #expect(DriveProtocol.verifySeq &+ 1 == 0)
    }

    @Test func clampsToTheByteRange() {
        let data = DriveProtocol.encode(WheelSpeeds(left: 4, right: -4).scaled(by: 2), seq: 255)
        #expect(Array(data) == [255, 100, UInt8(bitPattern: -100)])
    }
}
