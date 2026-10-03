import SwiftUI

/// A floating thumbstick: wherever the thumb lands becomes the centre, so the
/// car can be driven without looking at the phone. Reports the thumb's offset
/// in the unit disc, x right and y up, and (0, 0) when the thumb lifts or the
/// system cancels the touch.
struct Thumbstick: View {
    var radius: CGFloat = 80
    var onChange: (_ x: Double, _ y: Double) -> Void

    private struct Touch: Equatable {
        var start: CGPoint
        var location: CGPoint
    }

    // GestureState resets by itself when the gesture ends *or* is cancelled
    // (a call, Control Centre), and onChange below turns that into a stop.
    @GestureState private var touch: Touch?

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(.quaternary.opacity(0.5))
            if let touch {
                let knob = clampedOffset(touch)
                Circle()
                    .stroke(.secondary.opacity(0.5), lineWidth: 2)
                    .frame(width: radius * 2, height: radius * 2)
                    .position(touch.start)
                Circle()
                    .fill(.tint)
                    .frame(width: 64, height: 64)
                    .shadow(radius: 4, y: 2)
                    .position(x: touch.start.x + knob.width, y: touch.start.y + knob.height)
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
        .contentShape(Rectangle())
        .gesture(
            DragGesture(minimumDistance: 0)
                .updating($touch) { value, state, _ in
                    state = Touch(start: value.startLocation, location: value.location)
                }
        )
        .onChange(of: touch) { _, touch in
            guard let touch else { return onChange(0, 0) }
            let knob = clampedOffset(touch)
            onChange(knob.width / radius, -knob.height / radius)
        }
        .sensoryFeedback(.impact(weight: .light), trigger: touch == nil)
    }

    private func clampedOffset(_ touch: Touch) -> CGSize {
        let dx = touch.location.x - touch.start.x
        let dy = touch.location.y - touch.start.y
        let length = (dx * dx + dy * dy).squareRoot()
        let scale = length > radius ? radius / length : 1
        return CGSize(width: dx * scale, height: dy * scale)
    }
}
