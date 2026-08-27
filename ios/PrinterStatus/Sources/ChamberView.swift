import SwiftUI

/// Heat as color: cool parts stay neutral gray, warming parts blend toward
/// orange, hot parts toward red. `max` sets the scale (nozzle 250, bed 100).
func heatColor(_ temp: Double, max maxTemp: Double) -> Color {
    let f = min(max((temp - 25) / (maxTemp - 25), 0), 1)
    let cool = (r: 0.58, g: 0.58, b: 0.62)
    let warm = (r: 1.00, g: 0.55, b: 0.15)
    let hot = (r: 0.95, g: 0.25, b: 0.10)
    let mix: (Double) -> (Double, Double, Double) = { t in
        t < 0.5
            ? (cool.r + (warm.r - cool.r) * t * 2, cool.g + (warm.g - cool.g) * t * 2,
               cool.b + (warm.b - cool.b) * t * 2)
            : (warm.r + (hot.r - warm.r) * (t - 0.5) * 2, warm.g + (hot.g - warm.g) * (t - 0.5) * 2,
               warm.b + (hot.b - warm.b) * (t - 0.5) * 2)
    }
    let (r, g, b) = mix(f)
    return Color(red: r, green: g, blue: b)
}

/// Hotend silhouette: heater block, tapering nozzle, tip.
struct NozzleShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        let blockH = rect.height * 0.52
        let taperH = rect.height * 0.30
        let tipW = rect.width * 0.16
        p.addRoundedRect(
            in: CGRect(x: rect.minX, y: rect.minY, width: rect.width, height: blockH),
            cornerSize: CGSize(width: 3, height: 3))
        var taper = Path()
        taper.move(to: CGPoint(x: rect.minX + rect.width * 0.08, y: rect.minY + blockH))
        taper.addLine(to: CGPoint(x: rect.maxX - rect.width * 0.08, y: rect.minY + blockH))
        taper.addLine(to: CGPoint(x: rect.midX + tipW / 2, y: rect.minY + blockH + taperH))
        taper.addLine(to: CGPoint(x: rect.midX - tipW / 2, y: rect.minY + blockH + taperH))
        taper.closeSubpath()
        p.addPath(taper)
        p.addRect(CGRect(x: rect.midX - tipW / 2, y: rect.minY + blockH + taperH,
                         width: tipW, height: rect.height - blockH - taperH))
        return p
    }
}

/// A fan drawn as spinning blades in a ring; rotation speed follows the PWM
/// percentage (still at 0%).
struct FanGlyph: View {
    let percent: Int
    let diameter: CGFloat
    let tint: Color
    let label: String

    var body: some View {
        VStack(spacing: 3) {
            TimelineView(.animation(minimumInterval: 1.0 / 30.0, paused: percent == 0)) { context in
                let t = context.date.timeIntervalSinceReferenceDate
                Image(systemName: "fanblades.fill")
                    .resizable()
                    .scaledToFit()
                    .padding(diameter * 0.16)
                    // 100% ≈ 1.5 revolutions per second
                    .rotationEffect(.degrees((t * Double(percent) * 5.4)
                        .truncatingRemainder(dividingBy: 360)))
                    .frame(width: diameter, height: diameter)
                    .overlay(Circle().strokeBorder(tint.opacity(0.4), lineWidth: 1.5))
            }
            .foregroundStyle(tint.opacity(percent == 0 ? 0.5 : 0.95))
            Text("\(percent)%")
                .font(.caption2)
                .foregroundStyle(tint)
                .monospacedDigit()
        }
        .accessibilityLabel("\(label): \(percent) percent")
    }
}

/// The machine, front view, drawn in the "Glow" style the macOS app grew
/// into: a dark chamber where every heated part glows with its temperature.
/// The only style the iOS app ships — on a phone one good rendering beats a
/// style picker.
struct ChamberView: View {
    let snapshot: PrinterSnapshot

    private var nozzles: [PrinterSnapshot.Nozzle] {
        snapshot.nozzles.sorted { $0.id > $1.id }  // Left first, as you face it
    }

    private let secondaryText = Color.white.opacity(0.55)

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Label("\(Int(snapshot.chamberCurrent.rounded()))°",
                      systemImage: "thermometer.medium")
                    .font(.caption)
                    .foregroundStyle(secondaryText)
                    .accessibilityLabel("Chamber \(Int(snapshot.chamberCurrent.rounded())) degrees")
                Spacer()
            }
            .padding(.horizontal, 14)
            .padding(.top, 12)

            // gantry with the toolhead: both nozzles and the part-cooling
            // fan ride one carriage on the real machine, so box them together
            Rectangle()
                .fill(secondaryText.opacity(0.35))
                .frame(height: 4)
                .padding(.horizontal, 44)
                .padding(.top, 8)
            HStack(alignment: .top, spacing: 16) {
                if let first = nozzles.first {
                    nozzleGlyph(first)
                }
                FanGlyph(percent: snapshot.partFanPercent, diameter: 24,
                         tint: secondaryText, label: "Part cooling fan")
                    .padding(.top, 12)
                ForEach(Array(nozzles.dropFirst())) { nozzle in
                    nozzleGlyph(nozzle)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(RoundedRectangle(cornerRadius: 10)
                .fill(Color.white.opacity(0.07)))
            .overlay(RoundedRectangle(cornerRadius: 10)
                .strokeBorder(.white.opacity(0.12), lineWidth: 1))
            .padding(.top, -1)

            Spacer(minLength: 8)

            // build plate
            VStack(spacing: 5) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(heatColor(snapshot.bedCurrent, max: 100).gradient)
                    .frame(height: 11)
                    .padding(.horizontal, 56)
                    .shadow(color: heatColor(snapshot.bedCurrent, max: 100)
                        .opacity(glowAmount(snapshot.bedCurrent, max: 100)),
                        radius: 10, y: -4)
                tempLabel(current: snapshot.bedCurrent, target: snapshot.bedTarget)
            }
            .padding(.bottom, 14)
        }
        .frame(height: 230)
        .frame(maxWidth: .infinity)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color.black.opacity(0.82)))
        .overlay(RoundedRectangle(cornerRadius: 14)
            .strokeBorder(.white.opacity(0.1), lineWidth: 1))
        // wall fans, placed where they sit on the real machine (front view):
        // aux part-cooling fan on the left wall, chamber exhaust fan on the
        // right inner liner behind the carbon filter
        .overlay(alignment: .leading) {
            FanGlyph(percent: snapshot.auxFanPercent, diameter: 26,
                     tint: secondaryText, label: "Aux part cooling fan")
                .padding(.leading, 12)
                .offset(y: 8)
        }
        .overlay(alignment: .trailing) {
            FanGlyph(percent: snapshot.chamberFanPercent, diameter: 32,
                     tint: secondaryText, label: "Chamber exhaust fan")
                .padding(.trailing, 12)
                .offset(y: 8)
        }
    }

    private func glowAmount(_ temp: Double, max maxTemp: Double) -> Double {
        min(max((temp - 30) / (maxTemp - 30), 0), 1) * 0.9
    }

    private func nozzleGlyph(_ nozzle: PrinterSnapshot.Nozzle) -> some View {
        let color = heatColor(nozzle.current, max: 250)
        return VStack(spacing: 5) {
            NozzleShape()
                .fill(color.gradient)
                .frame(width: 46, height: 58)
                .shadow(color: color.opacity(glowAmount(nozzle.current, max: 250)), radius: 12)
                .overlay(alignment: .top) {
                    if nozzles.count > 1 {
                        Text(nozzle.id == 1 ? "L" : "R")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.white.opacity(0.9))
                            .padding(.top, 7)
                    }
                }
                .overlay(alignment: .bottom) {
                    if nozzle.active && nozzle.target > 0 {
                        Circle().fill(.orange)
                            .frame(width: 5, height: 5)
                            .offset(y: 4)
                    }
                }
            tempLabel(current: nozzle.current, target: nozzle.target,
                      emphasized: nozzle.active)
        }
    }

    private func tempLabel(current: Double, target: Double, emphasized: Bool = true) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            Text("\(Int(current.rounded()))°")
                .font(.system(.callout, design: .rounded).weight(.semibold))
                .foregroundStyle(.white)
                .opacity(emphasized ? 1 : 0.55)
                .monospacedDigit()
            if target > 0 {
                Text("→\(Int(target.rounded()))°")
                    .font(.caption)
                    .foregroundStyle(secondaryText)
                    .monospacedDigit()
            }
        }
    }
}
