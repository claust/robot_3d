import CoreBluetooth
import Foundation

/// The link's connection logic as a pure state machine, so it runs in tests
/// without Bluetooth. `Radio` feeds it CoreBluetooth's callbacks as events
/// and carries out the effects it returns.
///
/// It follows one car at a time, `car`. Events about any other peripheral
/// are left over from an earlier attempt and are ignored. Every step that
/// waits on the car (connecting, finding its drive service again) arms a
/// timeout, so no step can hang; a timeout that fires after its step
/// finished carries an old token and is ignored too.
struct LinkMachine {
    enum Event: Equatable {
        case started
        case stopped
        case bluetooth(CBManagerState)
        case discovered(UUID, name: String)
        case connected(UUID)
        case failedToConnect(UUID)
        case disconnected(UUID)
        case driveFound(UUID)
        case driveMissing(UUID)
        case servicesInvalidated(UUID)
        case timedOut(token: Int)
    }

    enum Effect: Equatable {
        case scan
        case stopScan
        case connect(UUID)
        case cancel(UUID)
        case discoverDrive(UUID)
        case startStream
        case stopStream
        case armTimeout(token: Int)
        case report(CarLink.State)
    }

    /// How long connecting, or finding the drive service again, may take.
    static let timeout: TimeInterval = 6

    private(set) var car: UUID?
    private var carName = ""
    private var running = false
    private var bluetooth: CBManagerState = .unknown
    private var token = 0
    private var state: CarLink.State = .idle

    mutating func handle(_ event: Event) -> [Effect] {
        switch event {
        case .started:
            running = true
            return follow(bluetooth)
        case .stopped:
            running = false
            var effects: [Effect] = [.stopStream, .stopScan]
            if let car { effects.append(.cancel(car)) }
            forget()
            return effects + report(.idle)
        case .bluetooth(let new):
            bluetooth = new
            return running ? follow(new) : []
        case .discovered(let id, let name):
            guard running, car == nil, bluetooth == .poweredOn else { return [] }
            car = id
            carName = name
            return [.stopScan, .connect(id), arm()] + report(.connecting(name: name))
        case .connected(let id):
            guard id == car else { return [] }
            return [.discoverDrive(id)]
        case .driveFound(let id):
            guard id == car else { return [] }
            token += 1  // the pending timeout is stale now
            return [.startStream] + report(.connected(name: carName))
        case .driveMissing(let id):
            guard id == car else { return [] }
            // Its disconnect starts the next search.
            return [.stopStream, .cancel(id)]
        case .servicesInvalidated(let id):
            guard id == car else { return [] }
            return [.stopStream, .discoverDrive(id), arm()] + report(.connecting(name: carName))
        case .failedToConnect(let id), .disconnected(let id):
            guard id == car else { return [] }
            return [.stopStream] + search()
        case .timedOut(let fired):
            guard fired == token, let car else { return [] }
            return [.stopStream, .cancel(car)] + search()
        }
    }

    private mutating func follow(_ bluetooth: CBManagerState) -> [Effect] {
        switch bluetooth {
        case .poweredOn:
            return car == nil ? search() : []
        case .poweredOff, .resetting:
            forget()
            return [.stopStream] + report(.bluetoothOff)
        case .unauthorized:
            return report(.unauthorized)
        case .unsupported:
            return report(.unsupported)
        default:
            return []
        }
    }

    private mutating func search() -> [Effect] {
        forget()
        guard bluetooth == .poweredOn else { return [] }
        return [.scan] + report(.searching)
    }

    /// Drop the car, and with it any pending timeout.
    private mutating func forget() {
        car = nil
        carName = ""
        token += 1
    }

    private mutating func arm() -> Effect {
        token += 1
        return .armTimeout(token: token)
    }

    private mutating func report(_ new: CarLink.State) -> [Effect] {
        guard new != state else { return [] }
        state = new
        return [.report(new)]
    }
}
