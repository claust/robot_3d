import SwiftUI

/// A floating thumbstick: wherever the thumb lands becomes the centre, so the
/// car can be driven without looking at the phone. Reports the thumb's offset
/// in the unit disc, x right and y up, and (0, 0) when the thumb lifts or the
/// system cancels the touch.
///
/// VoiceOver, Voice Control and Switch Control can't drag, so the stick is
/// also one adjustable element: swipe up or down to step the speed, and
/// actions to turn, go straight or stop (as do the escape and magic-tap
/// gestures). That command holds until it is changed, instead of lasting
/// as long as a touch, and it resets when the app leaves the screen,
/// `active` goes false (the link drops, or a pattern takes the wheels) or a
/// real drag takes over.
struct Thumbstick: View {
    var active: Bool
    var radius: CGFloat = 80
    var onChange: (_ x: Double, _ y: Double) -> Void

    private struct Touch: Equatable {
        var start: CGPoint
        var location: CGPoint
    }

    // GestureState resets by itself when the gesture ends *or* is cancelled
    // (a call, Control Centre), and onChange below turns that into a stop.
    @GestureState private var touch: Touch?
    @State private var held = Held()
    @Environment(\.scenePhase) private var scenePhase

    /// The assistive-technology command: speed and turn, in quarter steps.
    private struct Held: Equatable {
        var speed = 0.0
        var turn = 0.0
    }

    private static let speedStep = 0.25
    private static let turn = 0.5

    var body: some View {
        GeometryReader { geo in
            ZStack {
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .fill(.quaternary.opacity(0.5))
                if let touch {
                    stick(centre: touch.start, knob: clampedOffset(touch))
                } else if held != Held() {
                    let centre = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
                    stick(centre: centre, knob: CGSize(width: held.turn * radius, height: -held.speed * radius))
                } else {
                    VStack(spacing: 8) {
                        Image(systemName: "hand.point.up.left")
                            .font(.system(size: 34))
                        Text("Put your thumb down anywhere here and drag")
                            .font(.callout)
                            .multilineTextAlignment(.center)
                    }
                    .foregroundStyle(.secondary)
                    .padding()
                }
            }
        }
        .contentShape(Rectangle())
        .gesture(
            DragGesture(minimumDistance: 0)
                .updating($touch) { value, state, _ in
                    state = Touch(start: value.startLocation, location: value.location)
                }
        )
        .onChange(of: touch) { _, touch in
            held = Held()
            guard let touch else { return onChange(0, 0) }
            let knob = clampedOffset(touch)
            onChange(knob.width / radius, -knob.height / radius)
        }
        .sensoryFeedback(.impact(weight: .light), trigger: touch == nil)
        .accessibilityElement()
        .accessibilityLabel("Drive")
        .accessibilityValue(heldDescription)
        .accessibilityHint("Swipe up or down to change speed. Actions turn or stop the car.")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: hold(speed: held.speed + Self.speedStep)
            case .decrement: hold(speed: held.speed - Self.speedStep)
            @unknown default: break
            }
        }
        .accessibilityAction(named: "Stop") { stopHeld() }
        .accessibilityAction(named: "Turn left") { hold(turn: -Self.turn) }
        .accessibilityAction(named: "Turn right") { hold(turn: Self.turn) }
        .accessibilityAction(named: "Straight") { hold(turn: 0) }
        .accessibilityAction(.escape) { stopHeld() }
        .accessibilityAction(.magicTap) { stopHeld() }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active { stopHeld() }
        }
        .onChange(of: active) { _, active in
            if !active { stopHeld() }
        }
    }

    private func stick(centre: CGPoint, knob: CGSize) -> some View {
        ZStack {
            Circle()
                .stroke(.secondary.opacity(0.5), lineWidth: 2)
                .frame(width: radius * 2, height: radius * 2)
                .position(centre)
            Circle()
                .fill(.tint)
                .frame(width: 64, height: 64)
                .shadow(radius: 4, y: 2)
                .position(x: centre.x + knob.width, y: centre.y + knob.height)
        }
    }

    private func hold(speed: Double? = nil, turn: Double? = nil) {
        guard active else { return }
        if let speed { held.speed = min(1, max(-1, speed)) }
        if let turn { held.turn = turn }
        onChange(held.turn, held.speed)
    }

    private func stopHeld() {
        held = Held()
        onChange(0, 0)
    }

    private var heldDescription: String {
        let side = held.turn < 0 ? "left" : "right"
        guard held.speed != 0 else { return held.turn == 0 ? "Stopped" : "Spinning \(side)" }
        let speed = Int((abs(held.speed) * 100).rounded())
        let motion = "\(held.speed > 0 ? "Forward" : "Reverse") \(speed) percent"
        return held.turn == 0 ? motion : "\(motion), turning \(side)"
    }

    private func clampedOffset(_ touch: Touch) -> CGSize {
        let dx = touch.location.x - touch.start.x
        let dy = touch.location.y - touch.start.y
        let length = (dx * dx + dy * dy).squareRoot()
        let scale = length > radius ? radius / length : 1
        return CGSize(width: dx * scale, height: dy * scale)
    }
}
