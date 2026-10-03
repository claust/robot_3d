import CoreBluetooth
import Foundation
import os

/// CoreBluetooth on a serial queue of its own, so nothing the UI does on the
/// main thread can delay the command stream. It turns CoreBluetooth's
/// callbacks into `LinkMachine` events, carries out the effects, and while
/// the machine says so sends the latest wheels `DriveProtocol.rate` times a
/// second.
///
/// A tick is skipped rather than queued when CoreBluetooth has no room for
/// another write-without-response, so a slow link delivers fresh commands
/// late instead of old ones in a burst. The sequence number still advances
/// on a skipped tick, which lets the Pi's log count them.
///
/// Wheel commands count only while the stream is live. Each stream starts
/// from stop, and a value set while the link was down or searching is
/// dropped, so a reconnect never resumes motion from a command meant for
/// the old link: the car waits for fresh input.
///
/// Everything here runs on `queue`, except `setWheels`, which goes through
/// a lock, and the two report closures, which the owner hops back from.
final class Radio: NSObject, @unchecked Sendable {
    private struct Command {
        var wheels = WheelSpeeds.stop
        var live = false
    }

    private let queue = DispatchQueue(label: "RobotLink.radio", qos: .userInteractive)
    private let command = OSAllocatedUnfairLock(initialState: Command())
    private let onState: @Sendable (CarLink.State) -> Void
    private let onRSSI: @Sendable (Int) -> Void

    private var machine = LinkMachine()
    private var central: CBCentralManager?
    private var peripherals: [UUID: CBPeripheral] = [:]
    private var drive: CBCharacteristic?
    private var stream: DispatchSourceTimer?
    private var seq: UInt8 = 0

    init(onState: @escaping @Sendable (CarLink.State) -> Void,
         onRSSI: @escaping @Sendable (Int) -> Void) {
        self.onState = onState
        self.onRSSI = onRSSI
    }

    func setWheels(_ value: WheelSpeeds) {
        command.withLock { if $0.live { $0.wheels = value } }
    }

    func start() {
        queue.async { [self] in
            if let central {
                handle(.bluetooth(central.state))
            } else {
                // Its first state arrives as a delegate call; the first one
                // also asks for Bluetooth permission.
                central = CBCentralManager(delegate: self, queue: queue)
            }
            handle(.started)
        }
    }

    func retry() {
        queue.async { [self] in handle(.retry) }
    }

    /// Send the current wheels once more (the owner sets them to stop
    /// first), then let go of the car.
    func stop() {
        queue.async { [self] in
            send()
            handle(.stopped)
        }
    }

    private func handle(_ event: LinkMachine.Event) {
        for effect in machine.handle(event) {
            run(effect)
        }
    }

    private func run(_ effect: LinkMachine.Effect) {
        let poweredOn = central?.state == .poweredOn
        switch effect {
        case .scan:
            central?.scanForPeripherals(withServices: [DriveProtocol.serviceUUID])
        case .stopScan:
            if poweredOn { central?.stopScan() }
        case .connect(let id):
            guard let car = peripherals[id] else { return }
            car.delegate = self
            central?.connect(car)
        case .cancel(let id):
            if poweredOn, let car = peripherals[id] { central?.cancelPeripheralConnection(car) }
        case .discoverDrive(let id):
            drive = nil
            peripherals[id]?.discoverServices([DriveProtocol.serviceUUID])
        case .verify(let id):
            // A stop command, with response: see LinkMachine on pairing.
            guard let car = peripherals[id], let drive else { return handle(.verifyFailed(id)) }
            car.writeValue(DriveProtocol.encode(.stop, seq: DriveProtocol.verifySeq), for: drive, type: .withResponse)
        case .startStream:
            startStream()
        case .stopStream:
            command.withLock { $0 = Command() }
            stream?.cancel()
            stream = nil
            drive = nil
        case .armTimeout(let token, let seconds):
            queue.asyncAfter(deadline: .now() + seconds) { [weak self] in
                self?.handle(.timedOut(token: token))
            }
        case .report(let state):
            onState(state)
        }
    }

    private func startStream() {
        command.withLock { $0 = Command(wheels: .stop, live: true) }
        seq = 0
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now(), repeating: 1 / DriveProtocol.rate, leeway: .milliseconds(2))
        timer.setEventHandler { [weak self] in self?.send() }
        stream?.cancel()
        stream = timer
        timer.resume()
    }

    private func send() {
        defer { seq &+= 1 }
        guard let id = machine.car, let car = peripherals[id], let drive else { return }
        if seq % UInt8(DriveProtocol.rate) == 0 { car.readRSSI() }
        guard car.canSendWriteWithoutResponse else { return }
        let bytes = DriveProtocol.encode(command.withLock { $0.wheels }, seq: seq)
        car.writeValue(bytes, for: drive, type: .withoutResponse)
    }
}

// MARK: - CoreBluetooth delegates (all on `queue`)

extension Radio: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        handle(.bluetooth(central.state))
    }

    func centralManager(
        _ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any], rssi RSSI: NSNumber
    ) {
        let id = peripheral.identifier
        peripherals[id] = peripheral
        let name = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        handle(.discovered(id, name: name ?? peripheral.name ?? "Robot car"))
        if machine.car == id { onRSSI(RSSI.intValue) }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        handle(.connected(peripheral.identifier))
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        handle(.failedToConnect(peripheral.identifier))
    }

    func centralManager(
        _ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?
    ) {
        handle(.disconnected(peripheral.identifier))
    }
}

extension Radio: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let service = peripheral.services?.first(where: { $0.uuid == DriveProtocol.serviceUUID }) else {
            return handle(.driveMissing(peripheral.identifier))
        }
        peripheral.discoverCharacteristics([DriveProtocol.driveUUID], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        let id = peripheral.identifier
        guard let found = service.characteristics?.first(where: { $0.uuid == DriveProtocol.driveUUID }) else {
            return handle(.driveMissing(id))
        }
        if id == machine.car { drive = found }
        handle(.driveFound(id))
    }

    /// Only the verifying write expects a response. One for a characteristic
    /// other than the current `drive` belongs to a service that has since
    /// been invalidated and found again.
    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        guard characteristic === drive else { return }
        handle(error == nil ? .verified(peripheral.identifier) : .verifyFailed(peripheral.identifier))
    }

    /// Restarting remote.py on the Pi unregisters the drive service but
    /// leaves the radio link up, so the service vanishes under a live
    /// connection.
    func peripheral(_ peripheral: CBPeripheral, didModifyServices invalidatedServices: [CBService]) {
        if invalidatedServices.contains(where: { $0.uuid == DriveProtocol.serviceUUID }) {
            handle(.servicesInvalidated(peripheral.identifier))
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didReadRSSI RSSI: NSNumber, error: Error?) {
        if error == nil, peripheral.identifier == machine.car { onRSSI(RSSI.intValue) }
    }
}
