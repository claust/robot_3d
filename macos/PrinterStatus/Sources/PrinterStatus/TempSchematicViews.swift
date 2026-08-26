import SwiftUI

/// Alternative renderings of the temperature section: a schematic of the
/// real machine — two nozzles above the build plate, chamber around them.
enum TempVisualStyle: String, CaseIterable, Identifiable {
    case cards = "Cards"
    case schematic = "Schematic"
    case glow = "Glow"
    case isometric = "Isometric"
    var id: String { rawValue }
}

/// Heat as color: cool parts stay neutral gray, warming parts blend toward
/// orange, hot parts toward red. `max` sets the scale (nozzle 250, bed 100).
func heatColor(_ temp: Double, max maxTemp: Double) -> Color {
    let f = min(max((temp - 25) / (maxTemp - 25), 0), 1)
    let cool = (r: 0.58, g: 0.58, b: 0.62)
    let warm = (r: 1.00, g: 0.55, b: 0.15)
    let hot = (r: 0.95, g: 0.25, b: 0.10)
    let mix: (Double) -> (Double, Double, Double) = { t in
        t < 0.5
            ? (cool.r + (warm.r - cool.r) * t * 2, cool.g + (warm.g - cool.g) * t * 2, cool.b + (warm.b - cool.b) * t * 2)
            : (warm.r + (hot.r - warm.r) * (t - 0.5) * 2, warm.g + (hot.g - warm.g) * (t - 0.5) * 2, warm.b + (hot.b - warm.b) * (t - 0.5) * 2)
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

struct PrinterSchematicView: View {
    let snapshot: PrinterSnapshot
    let style: TempVisualStyle

    var body: some View {
        switch style {
        case .isometric:
            IsometricTempView(snapshot: snapshot)
        case .glow:
            ChamberSchematicView(snapshot: snapshot, darkChamber: true)
        default:
            ChamberSchematicView(snapshot: snapshot, darkChamber: false)
        }
    }
}

// MARK: - Schematic / Glow (front view inside the chamber)

struct ChamberSchematicView: View {
    let snapshot: PrinterSnapshot
    let darkChamber: Bool

    private var nozzles: [PrinterSnapshot.Nozzle] {
        snapshot.nozzles.sorted { $0.id > $1.id }  // Left first
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Label("\(Int(snapshot.chamberCurrent.rounded()))°",
                      systemImage: "thermometer.medium")
                    .font(.caption)
                    .foregroundStyle(secondaryText)
                    .help("Chamber temperature")
                Spacer()
            }
            .padding(.horizontal, 12)
            .padding(.top, 10)

            // gantry with the two toolheads
            Rectangle()
                .fill(secondaryText.opacity(0.35))
                .frame(height: 4)
                .padding(.horizontal, 20)
                .padding(.top, 6)
            HStack(alignment: .top, spacing: 34) {
                ForEach(nozzles) { nozzle in
                    nozzleGlyph(nozzle)
                }
            }
            .padding(.top, -1)

            Spacer(minLength: 6)

            // build plate
            VStack(spacing: 4) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(heatColor(snapshot.bedCurrent, max: 100).gradient)
                    .frame(height: 10)
                    .padding(.horizontal, 34)
                    .shadow(color: darkChamber ? heatColor(snapshot.bedCurrent, max: 100).opacity(glowAmount(snapshot.bedCurrent, max: 100)) : .clear,
                            radius: 10, y: -4)
                tempLabel(current: snapshot.bedCurrent, target: snapshot.bedTarget)
            }
            .padding(.bottom, 10)
        }
        .frame(height: 186)
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(darkChamber ? AnyShapeStyle(Color.black.opacity(0.82))
                                  : AnyShapeStyle(Color(nsColor: .quaternarySystemFill))))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(.quaternary, lineWidth: 1))
    }

    private var secondaryText: Color {
        darkChamber ? Color.white.opacity(0.55) : Color.secondary
    }

    private func glowAmount(_ temp: Double, max maxTemp: Double) -> Double {
        min(max((temp - 30) / (maxTemp - 30), 0), 1) * 0.9
    }

    private func nozzleGlyph(_ nozzle: PrinterSnapshot.Nozzle) -> some View {
        let color = heatColor(nozzle.current, max: 250)
        return VStack(spacing: 4) {
            NozzleShape()
                .fill(color.gradient)
                .frame(width: 42, height: 54)
                .shadow(color: darkChamber ? color.opacity(glowAmount(nozzle.current, max: 250)) : .clear,
                        radius: 12)
                .overlay(alignment: .top) {
                    Text(nozzle.id == 1 ? "L" : "R")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.white.opacity(0.9))
                        .padding(.top, 6)
                }
                .overlay(alignment: .bottom) {
                    if nozzle.active && nozzle.target > 0 {
                        Circle().fill(.orange)
                            .frame(width: 5, height: 5)
                            .offset(y: 4)
                            .help("Active nozzle")
                    }
                }
            tempLabel(current: nozzle.current,
                      target: nozzle.target,
                      emphasized: nozzle.active)
        }
    }

    private func tempLabel(current: Double, target: Double, emphasized: Bool = true) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            Text("\(Int(current.rounded()))°")
                .font(.system(.callout, design: .rounded).weight(.semibold))
                .foregroundStyle(darkChamber ? .white : Color.primary)
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

// MARK: - Isometric (plate in perspective)

struct IsometricTempView: View {
    let snapshot: PrinterSnapshot

    private var nozzles: [PrinterSnapshot.Nozzle] {
        snapshot.nozzles.sorted { $0.id > $1.id }
    }

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            let bedColor = heatColor(snapshot.bedCurrent, max: 100)

            ZStack {
                // build plate in perspective
                PlateShape()
                    .fill(bedColor.opacity(0.30).gradient)
                    .overlay(PlateShape().stroke(bedColor, lineWidth: 1.5))
                    .frame(width: w * 0.66, height: h * 0.34)
                    .position(x: w * 0.46, y: h * 0.72)

                // nozzle shadows on the plate
                ForEach(Array(nozzles.enumerated()), id: \.element.id) { index, _ in
                    Ellipse()
                        .fill(.black.opacity(0.18))
                        .frame(width: 30, height: 8)
                        .position(x: nozzleX(index, w), y: h * 0.66)
                }

                // nozzles hovering above
                ForEach(Array(nozzles.enumerated()), id: \.element.id) { index, nozzle in
                    let color = heatColor(nozzle.current, max: 250)
                    NozzleShape()
                        .fill(color.gradient)
                        .frame(width: 36, height: 48)
                        .overlay(alignment: .top) {
                            Text(nozzle.id == 1 ? "L" : "R")
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(.white.opacity(0.9))
                                .padding(.top, 4)
                        }
                        .position(x: nozzleX(index, w), y: h * 0.30)
                }

                // temperature callouts
                calloutLabel(title: "Left", current: nozzles.first?.current ?? 0,
                             target: nozzles.first?.target ?? 0,
                             active: nozzles.first?.active ?? false)
                    .position(x: w * 0.13, y: h * 0.22)
                calloutLabel(title: "Right", current: nozzles.last?.current ?? 0,
                             target: nozzles.last?.target ?? 0,
                             active: nozzles.last?.active ?? false)
                    .position(x: w * 0.85, y: h * 0.22)
                calloutLabel(title: "Bed", current: snapshot.bedCurrent,
                             target: snapshot.bedTarget, active: true)
                    .position(x: w * 0.82, y: h * 0.74)
                calloutLabel(title: "Chamber", current: snapshot.chamberCurrent,
                             target: 0, active: false)
                    .position(x: w * 0.16, y: h * 0.88)
            }
        }
        .frame(height: 200)
        .background(RoundedRectangle(cornerRadius: 10)
            .fill(Color(nsColor: .quaternarySystemFill)))
        .overlay(RoundedRectangle(cornerRadius: 10)
            .strokeBorder(.quaternary, lineWidth: 1))
    }

    private func nozzleX(_ index: Int, _ w: CGFloat) -> CGFloat {
        w * (index == 0 ? 0.38 : 0.55)
    }

    private func calloutLabel(title: String, current: Double, target: Double,
                              active: Bool) -> some View {
        VStack(spacing: 1) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text("\(Int(current.rounded()))°")
                    .font(.system(.callout, design: .rounded).weight(.semibold))
                    .opacity(active ? 1 : 0.6)
                    .monospacedDigit()
                if target > 0 {
                    Text("→\(Int(target.rounded()))°")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .monospacedDigit()
                }
            }
        }
    }
}

/// Build plate as a parallelogram, giving a cheap perspective effect.
struct PlateShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        let skew = rect.width * 0.22
        p.move(to: CGPoint(x: rect.minX, y: rect.maxY))
        p.addLine(to: CGPoint(x: rect.maxX - skew, y: rect.maxY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.minX + skew, y: rect.minY))
        p.closeSubpath()
        return p
    }
}
