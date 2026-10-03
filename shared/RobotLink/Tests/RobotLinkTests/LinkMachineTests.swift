import Foundation
import Testing
@testable import RobotLink

@Suite struct LinkMachineTests {
    let car = UUID()
    let other = UUID()

    /// Started with Bluetooth on: scanning.
    func searching() -> LinkMachine {
        var machine = LinkMachine()
        _ = machine.handle(.bluetooth(.poweredOn))
        _ = machine.handle(.started)
        return machine
    }

    /// Connecting to `car`; returns the timeout token it armed.
    func connecting(_ machine: inout LinkMachine) -> Int {
        let effects = machine.handle(.discovered(car, name: "RobotCar"))
        for case .armTimeout(let token, _) in effects { return token }
        Issue.record("no timeout armed")
        return -1
    }

    func connected() -> LinkMachine {
        var machine = searching()
        _ = connecting(&machine)
        _ = machine.handle(.connected(car))
        _ = machine.handle(.driveFound(car))
        _ = machine.handle(.verified(car))
        return machine
    }

    @Test func startsScanningOnceBluetoothIsOn() {
        var machine = LinkMachine()
        #expect(machine.handle(.started) == [])
        #expect(machine.handle(.bluetooth(.poweredOn)) == [.scan, .report(.searching)])
    }

    @Test func connectsToTheFirstCarFound() {
        var machine = searching()
        let effects = machine.handle(.discovered(car, name: "RobotCar"))
        #expect(effects.prefix(2) == [.stopScan, .connect(car)])
        #expect(effects.last == .report(.connecting(name: "RobotCar")))
        #expect(machine.handle(.discovered(other, name: "Other")) == [])
        #expect(machine.handle(.connected(car)).first == .discoverDrive(car))
        let verify = machine.handle(.driveFound(car))
        #expect(verify.first == .verify(car))
        #expect(machine.handle(.verified(car)) == [.startStream, .report(.connected(name: "RobotCar"))])
    }

    @Test func staleFailureForAnotherPeripheralIsIgnored() {
        var machine = searching()
        _ = connecting(&machine)
        #expect(machine.handle(.failedToConnect(other)) == [])
        #expect(machine.handle(.disconnected(other)) == [])
        #expect(machine.car == car)
    }

    @Test func connectTimeoutCancelsAndSearchesAgain() {
        var machine = searching()
        let token = connecting(&machine)
        let effects = machine.handle(.timedOut(token: token))
        #expect(effects.prefix(2) == [.stopStream, .cancel(car)])
        #expect(effects.suffix(2) == [.scan, .report(.searching)])
        #expect(machine.car == nil)
        // The cancelled connection's disconnect only settles it: scan afresh.
        #expect(machine.handle(.disconnected(car)) == [.scan])
    }

    @Test func lateCancelCallbackCannotTearDownANewAttempt() {
        var machine = searching()
        let token = connecting(&machine)
        _ = machine.handle(.timedOut(token: token))
        // The car still advertises, but isn't taken until its cancel settles.
        #expect(machine.handle(.discovered(car, name: "RobotCar")) == [])
        #expect(machine.handle(.disconnected(car)) == [.scan])
        #expect(machine.handle(.discovered(car, name: "RobotCar")).contains(.connect(car)))
        // A second, stale disconnect for the old attempt would have matched
        // here before; now the new attempt is the only one tracked.
        #expect(machine.car == car)
    }

    @Test func cancelThatNeverReportsSettlesOnItsTimeout() {
        var machine = searching()
        let token = connecting(&machine)
        var settle = -1
        for case .armSettleTimeout(_, let armed, _) in machine.handle(.timedOut(token: token)) { settle = armed }
        #expect(machine.handle(.discovered(car, name: "RobotCar")) == [])
        #expect(machine.handle(.settleTimedOut(car, token: settle)) == [.scan])
        #expect(machine.handle(.discovered(car, name: "RobotCar")).contains(.connect(car)))
    }

    @Test func timeoutAfterConnectingIsStale() {
        var machine = searching()
        let token = connecting(&machine)
        _ = machine.handle(.connected(car))
        _ = machine.handle(.driveFound(car))
        _ = machine.handle(.verified(car))
        #expect(machine.handle(.timedOut(token: token)) == [])
    }

    @Test func invalidatedServiceIsFoundAgain() {
        var machine = connected()
        let effects = machine.handle(.servicesInvalidated(car))
        #expect(effects.prefix(2) == [.stopStream, .discoverDrive(car)])
        #expect(effects.last == .report(.connecting(name: "RobotCar")))
        #expect(machine.handle(.driveFound(car)).first == .verify(car))
        #expect(machine.handle(.verified(car)) == [.startStream, .report(.connected(name: "RobotCar"))])
    }

    @Test func rediscoveryThatNeverAnswersTimesOut() {
        var machine = connected()
        var token = -1
        for case .armTimeout(let armed, _) in machine.handle(.servicesInvalidated(car)) { token = armed }
        let effects = machine.handle(.timedOut(token: token))
        #expect(effects.prefix(2) == [.stopStream, .cancel(car)])
        #expect(effects.suffix(2) == [.scan, .report(.searching)])
    }

    @Test func missingDriveServiceDropsTheConnection() {
        var machine = searching()
        _ = connecting(&machine)
        _ = machine.handle(.connected(car))
        #expect(machine.handle(.driveMissing(car)) == [.stopStream, .cancel(car)])
        #expect(machine.handle(.disconnected(car)) == [.stopStream, .scan, .report(.searching)])
    }

    @Test func disconnectSearchesAgain() {
        var machine = connected()
        #expect(machine.handle(.disconnected(car)) == [.stopStream, .scan, .report(.searching)])
    }

    @Test func bluetoothOffDropsTheCarAndOnSearchesAgain() {
        var machine = connected()
        #expect(machine.handle(.bluetooth(.poweredOff)) == [.stopStream, .report(.bluetoothOff)])
        #expect(machine.car == nil)
        #expect(machine.handle(.bluetooth(.poweredOn)) == [.scan, .report(.searching)])
    }

    @Test func stopLetsGoAndIgnoresLaterEvents() {
        var machine = connected()
        let stopped = machine.handle(.stopped)
        #expect(stopped.prefix(3) == [.stopStream, .stopScan, .cancel(car)])
        #expect(stopped.last == .report(.idle))
        #expect(machine.handle(.disconnected(car)) == [])
        #expect(machine.handle(.bluetooth(.poweredOn)) == [])
        #expect(machine.handle(.discovered(car, name: "RobotCar")) == [])
    }

    @Test func streamStartsOnlyAfterTheVerifyingWrite() {
        var machine = searching()
        _ = connecting(&machine)
        _ = machine.handle(.connected(car))
        let effects = machine.handle(.driveFound(car))
        #expect(effects.first == .verify(car))
        #expect(!effects.contains(.startStream))
        // Long enough for someone to answer the "Pair?" dialog.
        #expect(effects.contains { if case .armTimeout(_, LinkMachine.pairingTimeout) = $0 { true } else { false } })
    }

    @Test func failedPairingWaitsForRetry() {
        var machine = searching()
        _ = connecting(&machine)
        _ = machine.handle(.connected(car))
        _ = machine.handle(.driveFound(car))
        let failed = machine.handle(.verifyFailed(car))
        #expect(failed.prefix(2) == [.stopStream, .cancel(car)])
        #expect(failed.last == .report(.pairingFailed(name: "RobotCar")))
        #expect(machine.car == nil)
        // The cancelled link's disconnect doesn't start a search by itself.
        #expect(machine.handle(.disconnected(car)) == [])
        #expect(machine.handle(.retry) == [.scan, .report(.searching)])
    }

    @Test func discoveryGetsAFreshTimeout() {
        var machine = searching()
        let connectToken = connecting(&machine)
        let effects = machine.handle(.connected(car))
        #expect(effects.contains { if case .armTimeout(_, LinkMachine.timeout) = $0 { true } else { false } })
        #expect(machine.handle(.timedOut(token: connectToken)) == [])
    }

    @Test func eventsOutOfPhaseAreIgnored() {
        var machine = searching()
        _ = connecting(&machine)
        #expect(machine.handle(.driveFound(car)) == [])
        #expect(machine.handle(.verified(car)) == [])
        #expect(machine.handle(.servicesInvalidated(car)) == [])
        _ = machine.handle(.connected(car))
        #expect(machine.handle(.connected(car)) == [])
        #expect(machine.handle(.verified(car)) == [])
    }

    @Test func verifyFromBeforeAnInvalidationIsIgnored() {
        var machine = searching()
        _ = connecting(&machine)
        _ = machine.handle(.connected(car))
        _ = machine.handle(.driveFound(car))
        _ = machine.handle(.servicesInvalidated(car))
        // The old characteristic's write answers late, during rediscovery.
        #expect(machine.handle(.verified(car)) == [])
        #expect(machine.handle(.verifyFailed(car)) == [])
        #expect(machine.handle(.driveFound(car)).first == .verify(car))
        #expect(machine.handle(.verified(car)) == [.startStream, .report(.connected(name: "RobotCar"))])
    }

    @Test func verifyingReportsPairing() {
        var machine = searching()
        _ = connecting(&machine)
        _ = machine.handle(.connected(car))
        #expect(machine.handle(.driveFound(car)).last == .report(.pairing(name: "RobotCar")))
    }

    @Test func losingPermissionLetsGoAndRecoversWhenItReturns() {
        var machine = connected()
        #expect(machine.handle(.bluetooth(.unauthorized)) == [.stopStream, .report(.unauthorized)])
        #expect(machine.car == nil)
        #expect(machine.handle(.bluetooth(.poweredOn)) == [.scan, .report(.searching)])
    }

    @Test func unsupportedLetsGoToo() {
        var machine = connected()
        #expect(machine.handle(.bluetooth(.unsupported)) == [.stopStream, .report(.unsupported)])
        #expect(machine.car == nil)
    }

    @Test func retryOnlyMeansSomethingAfterAFailedPairing() {
        var machine = connected()
        #expect(machine.handle(.retry) == [])
    }

    @Test func restartSearchesAgain() {
        var machine = connected()
        _ = machine.handle(.stopped)
        #expect(machine.handle(.started) == [.scan, .report(.searching)])
    }
}
