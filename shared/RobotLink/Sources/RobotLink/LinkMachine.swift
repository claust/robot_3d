import CoreBluetooth
import Foundation

/// The link's connection logic as a pure state machine, so it runs in tests
/// without Bluetooth. `Radio` feeds it CoreBluetooth's callbacks as events
/// and carries out the effects it returns.
///
/// It follows one car at a time, `car`, through the phases connecting,
/// discovering, verifying and streaming. An event counts only for the car
/// and only in the phase that waits for it. Anything else is a callback
/// left over from an earlier attempt, or from before the car's service was
/// invalidated (which keeps the peripheral, and so its UUID), and is
/// ignored. Each waiting phase arms its own timeout, so no step can hang; a
/// timeout that fires after its phase ended carries an old token and is
/// ignored too.
///
/// The car only takes drive writes over an encrypted link from a bonded
/// phone, so once the drive characteristic is found the link verifies it
/// with one write that expects a response. iOS answers the car's "insufficient
/// encryption" by pairing (the system asks "Pair?") or, once bonded, by
/// encrypting the link, and then retries the write. Only a successful write
/// starts the stream. A failed one (pairing cancelled, or refused because
/// the car's pairing window after power-on has closed) parks the link at
/// `.pairingFailed` until `retry`, so the phone doesn't ask again and again.
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
        case verified(UUID)
        case verifyFailed(UUID)
        case servicesInvalidated(UUID)
        case timedOut(token: Int)
        case retry
    }

    enum Effect: Equatable {
        case scan
        case stopScan
        case connect(UUID)
        case cancel(UUID)
        case discoverDrive(UUID)
        case verify(UUID)
        case startStream
        case stopStream
        case armTimeout(token: Int, seconds: TimeInterval)
        case report(CarLink.State)
    }

    private enum Phase {
        case none, connecting, discovering, verifying, streaming
    }

    /// How long connecting, or finding the drive service, may take.
    static let timeout: TimeInterval = 6
    /// How long the verifying write may take, which includes someone
    /// answering the pairing dialog.
    static let pairingTimeout: TimeInterval = 90

    private(set) var car: UUID?
    private var carName = ""
    private var phase = Phase.none
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
            phase = .connecting
            return [.stopScan, .connect(id), arm(Self.timeout)] + report(.connecting(name: name))
        case .connected(let id):
            guard id == car, phase == .connecting else { return [] }
            phase = .discovering
            return [.discoverDrive(id), arm(Self.timeout)]
        case .driveFound(let id):
            guard id == car, phase == .discovering else { return [] }
            phase = .verifying
            return [.verify(id), arm(Self.pairingTimeout)] + report(.pairing(name: carName))
        case .driveMissing(let id):
            guard id == car, phase == .discovering else { return [] }
            // Its disconnect starts the next search.
            return [.stopStream, .cancel(id)]
        case .verified(let id):
            guard id == car, phase == .verifying else { return [] }
            phase = .streaming
            token += 1  // the pending timeout is stale now
            return [.startStream] + report(.connected(name: carName))
        case .verifyFailed(let id):
            guard id == car, phase == .verifying else { return [] }
            let name = carName
            forget()
            return [.stopStream, .cancel(id)] + report(.pairingFailed(name: name))
        case .retry:
            guard running, case .pairingFailed = state else { return [] }
            return search()
        case .servicesInvalidated(let id):
            guard id == car, phase != .connecting else { return [] }
            phase = .discovering
            return [.stopStream, .discoverDrive(id), arm(Self.timeout)] + report(.connecting(name: carName))
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
            forget()
            return [.stopStream] + report(.unauthorized)
        case .unsupported:
            forget()
            return [.stopStream] + report(.unsupported)
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
        phase = .none
        token += 1
    }

    private mutating func arm(_ seconds: TimeInterval) -> Effect {
        token += 1
        return .armTimeout(token: token, seconds: seconds)
    }

    private mutating func report(_ new: CarLink.State) -> [Effect] {
        guard new != state else { return [] }
        state = new
        return [.report(new)]
    }
}
