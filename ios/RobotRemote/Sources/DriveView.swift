import RobotLink
import SwiftUI

/// The one screen: link status at the top, what each wheel is being told in
/// the middle, the top-speed cap, and the thumbstick filling the bottom half
/// where a thumb reaches it.
struct DriveView: View {
    @Bindable var link: CarLink
    @AppStorage("topSpeed") private var topSpeed = 0.6
    @State private var stick = (x: 0.0, y: 0.0)

    var body: some View {
        VStack(spacing: 20) {
            StatusBadge(state: link.state, rssi: link.rssi)
            HStack(spacing: 48) {
                WheelBar(label: "L", speed: link.wheels.left)
                WheelBar(label: "R", speed: link.wheels.right)
            }
            .frame(height: 170)
            VStack(spacing: 4) {
                HStack {
                    Text("Top speed")
                    Spacer()
                    Text(topSpeed, format: .percent.precision(.fractionLength(0)))
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                }
                Slider(value: $topSpeed, in: 0.3...1, step: 0.05)
            }
            Thumbstick { x, y in
                stick = (x, y)
                drive()
            }
            .opacity(link.isConnected ? 1 : 0.5)
        }
        .padding()
        .onChange(of: topSpeed) { drive() }
        .onChange(of: link.isConnected) { _, connected in
            // The screen must not lock half-way through a drive.
            UIApplication.shared.isIdleTimerDisabled = connected
        }
        .sensoryFeedback(trigger: link.isConnected) { _, connected in
            connected ? .success : .warning
        }
    }

    private func drive() {
        link.wheels = WheelSpeeds.arcade(x: stick.x, y: stick.y).scaled(by: topSpeed)
    }
}

private struct StatusBadge: View {
    let state: CarLink.State
    let rssi: Int?

    var body: some View {
        HStack(spacing: 8) {
            Circle().fill(colour).frame(width: 10, height: 10)
            Text(text)
                .font(.headline)
            if case .unauthorized = state {
                Button("Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) {
                        UIApplication.shared.open(url)
                    }
                }
                .font(.subheadline)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.thinMaterial, in: Capsule())
    }

    private var text: String {
        switch state {
        case .idle: "Starting…"
        case .bluetoothOff: "Bluetooth is off"
        case .unauthorized: "Bluetooth not allowed"
        case .unsupported: "No Bluetooth LE on this device"
        case .searching: "Looking for the car…"
        case .connecting(let name): "Connecting to \(name)…"
        case .connected(let name):
            if let rssi { "\(name) · \(rssi) dBm" } else { name }
        }
    }

    private var colour: Color {
        switch state {
        case .connected: .green
        case .searching, .connecting, .idle: .orange
        default: .red
        }
    }
}

/// One wheel's commanded speed: a bar growing up from the centre line for
/// forward, down for reverse.
private struct WheelBar: View {
    let label: String
    let speed: Double

    var body: some View {
        VStack(spacing: 6) {
            GeometryReader { geo in
                let half = geo.size.height / 2
                let length = half * abs(speed)
                ZStack(alignment: .top) {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(.quaternary)
                    RoundedRectangle(cornerRadius: 6)
                        .fill(speed >= 0 ? Color.green : Color.orange)
                        .frame(height: length)
                        .offset(y: speed >= 0 ? half - length : half)
                        .padding(.horizontal, 4)
                    Rectangle()
                        .fill(.secondary)
                        .frame(height: 1)
                        .offset(y: half)
                }
                .animation(.linear(duration: 0.05), value: speed)
            }
            .frame(width: 44)
            Text("\(label) \(Int((speed * 100).rounded()))%")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
        }
    }
}
