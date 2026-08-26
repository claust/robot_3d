import SwiftUI

struct DashboardView: View {
    @ObservedObject var model: PrinterViewModel
    @AppStorage("tempVisualStyle") private var tempStyleRaw = TempVisualStyle.glow.rawValue
    private let forcedStyle: TempVisualStyle?

    init(model: PrinterViewModel, forcedStyle: TempVisualStyle? = nil) {
        self.model = model
        self.forcedStyle = forcedStyle
    }

    private var tempStyle: TempVisualStyle {
        forcedStyle ?? TempVisualStyle(rawValue: tempStyleRaw) ?? .glow
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            header
            if model.snapshot.isPrinting || model.snapshot.gcodeState == "FINISH" {
                progressSection
            }
            if tempStyle == .cards {
                temperatureGrid
            } else {
                PrinterSchematicView(snapshot: model.snapshot, style: tempStyle)
            }
            amsSection
            if !model.snapshot.alerts.isEmpty {
                alertsSection
            }
            Divider()
            footer
        }
        .padding(16)
        .frame(width: 380)
        .fixedSize(horizontal: false, vertical: true)
    }

    // MARK: sections

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Circle()
                    .fill(stateColor)
                    .frame(width: 10, height: 10)
                Text(stateLabel)
                    .font(.headline)
                Spacer()
                Picker("", selection: $model.mode) {
                    ForEach(PrinterViewModel.Mode.allCases) { m in
                        Text(m.rawValue).tag(m)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 150)
                .disabled(!model.hasCredentials)
                .help(model.hasCredentials ? "Data source" : "cad/.env not found — simulation only")
            }
            if !model.snapshot.jobName.isEmpty && model.snapshot.gcodeState != "IDLE" {
                Text(model.snapshot.jobName)
                    .font(.title3.weight(.semibold))
                    .lineLimit(1)
            }
            if let stage = model.snapshot.stageText {
                Text(stage)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var progressSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color(nsColor: .quaternarySystemFill))
                    Capsule().fill(stateColor.gradient)
                        .frame(width: max(8, geo.size.width * Double(model.snapshot.percent) / 100))
                        .animation(.easeInOut(duration: 0.5), value: model.snapshot.percent)
                }
            }
            .frame(height: 8)
            HStack {
                Text("\(model.snapshot.percent)%")
                    .font(.system(.title2, design: .rounded).weight(.bold))
                    .monospacedDigit()
                Spacer()
                Label("Layer \(model.snapshot.layer) / \(model.snapshot.totalLayers)",
                      systemImage: "square.3.layers.3d")
                    .monospacedDigit()
                Spacer()
                Label(remainingText, systemImage: "clock")
                    .monospacedDigit()
            }
            .font(.callout)
        }
    }

    private var temperatureGrid: some View {
        Grid(horizontalSpacing: 10, verticalSpacing: 10) {
            GridRow {
                ForEach(orderedNozzles) { nozzle in
                    tempCard(
                        title: "\(nozzle.name) nozzle",
                        icon: nozzle.active ? "flame.fill" : "flame",
                        highlight: nozzle.active && nozzle.target > 0,
                        current: nozzle.current, target: nozzle.target,
                        subtitle: "⌀\(nozzle.diameter)"
                    )
                }
            }
            GridRow {
                tempCard(title: "Bed", icon: "rectangle.bottomhalf.filled",
                         highlight: model.snapshot.bedTarget > 0,
                         current: model.snapshot.bedCurrent,
                         target: model.snapshot.bedTarget, subtitle: nil)
                tempCard(title: "Chamber", icon: "cube",
                         highlight: false,
                         current: model.snapshot.chamberCurrent,
                         target: nil, subtitle: nil)
            }
        }
    }

    private var orderedNozzles: [PrinterSnapshot.Nozzle] {
        // show Left before Right, matching how you face the printer
        model.snapshot.nozzles.sorted { $0.id > $1.id }
    }

    private func tempCard(title: String, icon: String, highlight: Bool,
                          current: Double, target: Double?, subtitle: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .foregroundStyle(highlight ? .orange : .secondary)
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let subtitle {
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text("\(Int(current.rounded()))°")
                    .font(.system(.title3, design: .rounded).weight(.semibold))
                    .monospacedDigit()
                if let target, target > 0 {
                    Text("→ \(Int(target.rounded()))°")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .monospacedDigit()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8)
            .fill(Color(nsColor: .quaternarySystemFill)))
        .overlay(RoundedRectangle(cornerRadius: 8)
            .strokeBorder(highlight ? Color.orange.opacity(0.5) : .clear, lineWidth: 1))
    }

    private var amsSection: some View {
        HStack(spacing: 14) {
            ForEach(model.snapshot.trays) { tray in
                VStack(spacing: 3) {
                    ZStack {
                        Circle()
                            .fill(color(fromRGBA: tray.colorHex))
                            .frame(width: 22, height: 22)
                            .overlay(Circle().strokeBorder(.quaternary, lineWidth: 1))
                        if activeSlots.contains(tray.id) {
                            Circle()
                                .strokeBorder(.orange, lineWidth: 2)
                                .frame(width: 28, height: 28)
                        }
                    }
                    .frame(width: 28, height: 28)
                    Text(tray.isEmpty ? "—" : tray.type)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    if tray.remainPercent >= 0 {
                        Text("\(tray.remainPercent)%")
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                            .monospacedDigit()
                    }
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("AMS")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let humidity = model.snapshot.amsHumidityPercent {
                    Label("\(humidity)%", systemImage: "humidity")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                if let temp = model.snapshot.amsTemp {
                    Label("\(Int(temp.rounded()))°", systemImage: "thermometer.low")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.horizontal, 2)
    }

    private var activeSlots: Set<Int> {
        Set(model.snapshot.nozzles.compactMap { $0.active ? $0.amsSlot : nil })
    }

    private var alertsSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(model.snapshot.alerts) { alert in
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red)
                    if let url = alert.wikiURL {
                        Link("HMS \(alert.code)", destination: url)
                            .font(.caption.monospaced())
                    } else {
                        Text("HMS \(alert.code)")
                            .font(.caption.monospaced())
                    }
                }
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 8).fill(.red.opacity(0.1)))
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 12) {
                Label("\(model.snapshot.partFanPercent)%", systemImage: "fan")
                    .help("Part cooling fan")
                Label("\(model.snapshot.auxFanPercent)%", systemImage: "fan.desk")
                    .help("Aux fan")
                Label("\(model.snapshot.chamberFanPercent)%", systemImage: "wind")
                    .help("Chamber fan")
                Spacer()
                Label(model.snapshot.speedLevelName, systemImage: "speedometer")
                if !model.snapshot.wifiSignal.isEmpty {
                    Label(model.snapshot.wifiSignal, systemImage: "wifi")
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            HStack(spacing: 8) {
                Text(model.connectionText)
                Spacer()
                if let updated = model.lastUpdate {
                    Text("Updated \(updated.formatted(date: .omitted, time: .standard))")
                }
                Menu {
                    Picker("Temperature style", selection: $tempStyleRaw) {
                        ForEach(TempVisualStyle.allCases) { style in
                            Text(style.rawValue).tag(style.rawValue)
                        }
                    }
                } label: {
                    Image(systemName: "paintpalette")
                }
                .menuStyle(.borderlessButton)
                .fixedSize()
                .help("Temperature display style")
            }
            .font(.caption2)
            .foregroundStyle(.tertiary)
        }
    }

    // MARK: helpers

    private var stateColor: Color {
        switch model.snapshot.gcodeState {
        case "RUNNING", "PREPARE", "SLICING": return .green
        case "PAUSE": return .yellow
        case "FAILED": return .red
        case "FINISH": return .blue
        default: return model.isConnected ? .gray : .red
        }
    }

    private var stateLabel: String {
        switch model.snapshot.gcodeState {
        case "RUNNING": return "Printing"
        case "PREPARE": return "Preparing"
        case "SLICING": return "Slicing"
        case "PAUSE": return "Paused"
        case "FINISH": return "Finished"
        case "FAILED": return "Failed"
        case "IDLE": return "Idle"
        default: return model.isConnected ? model.snapshot.gcodeState.capitalized : "Offline"
        }
    }

    private var remainingText: String {
        let minutes = model.snapshot.remainingMinutes
        if minutes <= 0 { return "—" }
        if minutes < 60 { return "\(minutes) min" }
        return "\(minutes / 60) h \(minutes % 60) min"
    }

    private func color(fromRGBA hex: String) -> Color {
        guard hex.count == 8, let value = UInt32(hex, radix: 16) else { return .gray }
        return Color(red: Double((value >> 24) & 0xFF) / 255,
                     green: Double((value >> 16) & 0xFF) / 255,
                     blue: Double((value >> 8) & 0xFF) / 255,
                     opacity: Double(value & 0xFF) / 255)
    }
}
