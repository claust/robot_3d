import Foundation
import Observation

/// The phone's end of the drive link, for the UI: finds the car, stays
/// connected, and streams `wheels` to it `DriveProtocol.rate` times a second.
///
/// Set `wheels` whenever the thumb moves; the next tick sends the latest
/// value. The Bluetooth work happens on `Radio`'s own queue, off the main
/// thread, and the connection logic is `LinkMachine`; this class only
/// mirrors their state for SwiftUI.
///
/// It connects to the first car advertising `DriveProtocol.serviceUUID` and
/// goes back to scanning whenever the connection drops or a step stalls.
/// `simulated` skips Bluetooth and pretends to connect, for the iOS
/// Simulator, which has none.
@MainActor @Observable
public final class CarLink {
    public enum State: Equatable, Sendable {
        case idle
        case bluetoothOff
        case unauthorized
        case unsupported
        case searching
        case connecting(name: String)
        case connected(name: String)
        /// Pairing was cancelled or the passkey was wrong; waits for `retry()`.
        case pairingFailed(name: String)
    }

    public private(set) var state: State = .idle
    /// Signal strength of the connection, refreshed once a second.
    public private(set) var rssi: Int?
    /// What the wheels should do now.
    public var wheels: WheelSpeeds = .stop {
        didSet { radio?.setWheels(wheels) }
    }

    public let simulated: Bool

    @ObservationIgnored private var radio: Radio?
    @ObservationIgnored private var running = false
    @ObservationIgnored private var simulation: Task<Void, Never>?

    public init(simulated: Bool = false) {
        self.simulated = simulated
    }

    public var isConnected: Bool {
        if case .connected = state { return true }
        return false
    }

    /// Start looking for the car. The first call asks for Bluetooth permission.
    public func start() {
        guard !running else { return }
        running = true
        if simulated { return simulate() }
        if radio == nil {
            // Reports come from the radio's queue in order; main.async keeps it.
            radio = Radio(
                onState: { [weak self] state in
                    DispatchQueue.main.async { MainActor.assumeIsolated { self?.update(state) } }
                },
                onRSSI: { [weak self] rssi in
                    DispatchQueue.main.async { MainActor.assumeIsolated { self?.rssi = rssi } }
                })
        }
        radio?.setWheels(wheels)
        radio?.start()
    }

    /// Look for the car again after `.pairingFailed`.
    public func retry() {
        guard running, !simulated else { return }
        radio?.retry()
    }

    /// Stop the wheels and let go of the car, e.g. when the app leaves the
    /// screen. The radio reports `.idle` once it has.
    public func stop() {
        guard running else { return }
        running = false
        wheels = .stop
        if simulated {
            simulation?.cancel()
            return update(.idle)
        }
        radio?.stop()
    }

    private func update(_ new: State) {
        state = new
        if !isConnected { rssi = nil }
    }

    private func simulate() {
        let name = "RobotCar (simulated)"
        update(.connecting(name: name))
        simulation = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(700))
            guard let self, !Task.isCancelled else { return }
            self.update(.connected(name: name))
            self.rssi = -55
        }
    }
}
