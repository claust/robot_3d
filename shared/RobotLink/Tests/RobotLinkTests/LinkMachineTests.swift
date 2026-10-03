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
        #expect(machine.handle(.connected(car)) == [.discoverDrive(car)])
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
        #expect(machine.handle(.timedOut(token: token)) == [.stopStream, .cancel(car), .scan, .report(.searching)])
        #expect(machine.car == nil)
        // The cancelled connection's disconnect is old news by now.
        #expect(machine.handle(.disconnected(car)) == [])
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
        #expect(machine.handle(.timedOut(token: token)) == [.stopStream, .cancel(car), .scan, .report(.searching)])
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
        #expect(machine.handle(.stopped) == [.stopStream, .stopScan, .cancel(car), .report(.idle)])
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
        // Long enough for someone to fetch the passkey and type it.
        #expect(effects.contains { if case .armTimeout(_, LinkMachine.pairingTimeout) = $0 { true } else { false } })
    }

    @Test func failedPairingWaitsForRetry() {
        var machine = searching()
        _ = connecting(&machine)
        _ = machine.handle(.connected(car))
        _ = machine.handle(.driveFound(car))
        #expect(machine.handle(.verifyFailed(car)) == [.stopStream, .cancel(car), .report(.pairingFailed(name: "RobotCar"))])
        #expect(machine.car == nil)
        // The cancelled link's disconnect doesn't start a search by itself.
        #expect(machine.handle(.disconnected(car)) == [])
        #expect(machine.handle(.retry) == [.scan, .report(.searching)])
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
