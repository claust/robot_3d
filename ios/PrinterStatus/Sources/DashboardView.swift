import SwiftUI

/// The phone layout: one scrolling column of cards — status & progress,
/// the glowing chamber, AMS, then the connection footer. The macOS app's
/// two fixed columns assume a wide window; a phone wants everything
/// stacked, thumb-reachable, and readable at arm's length.
struct DashboardView: View {
    @ObservedObject var model: PrinterViewModel
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    statusCard
                    if !model.snapshot.alerts.isEmpty {
                        alertsCard
                    }
                    ChamberView(snapshot: model.snapshot)
                    amsCard
                    footerCard
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle(model.printerName ?? "Printer Status")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                    .accessibilityLabel("Printer settings")
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView(model: model)
            }
        }
    }

    // MARK: cards

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Circle()
                    .fill(stateColor)
                    .frame(width: 11, height: 11)
                Text(stateLabel)
                    .font(.headline)
                Spacer()
                if model.mode == .simulated {
                    Text("SIMULATED")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(Capsule().fill(Color(.tertiarySystemFill)))
                }
            }
            if !model.snapshot.jobName.isEmpty && model.snapshot.gcodeState != "IDLE" {
                Text(model.snapshot.jobName)
                    .font(.title3.weight(.semibold))
                    .lineLimit(2)
            }
            if let stage = model.snapshot.stageText {
                Text(stage)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            if model.snapshot.isPrinting || model.snapshot.gcodeState == "FINISH" {
                progressSection
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemGroupedBackground)))
    }

    private var progressSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color(.tertiarySystemFill))
                    Capsule().fill(stateColor.gradient)
                        .frame(width: max(10, geo.size.width * Double(model.snapshot.percent) / 100))
                        .animation(.easeInOut(duration: 0.5), value: model.snapshot.percent)
                }
            }
            .frame(height: 10)
            HStack {
                Text("\(model.snapshot.percent)%")
                    .font(.system(.title, design: .rounded).weight(.bold))
                    .monospacedDigit()
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Label("Layer \(model.snapshot.layer) / \(model.snapshot.totalLayers)",
                          systemImage: "square.3.layers.3d")
                    Label(remainingText, systemImage: "clock")
                }
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .monospacedDigit()
            }
        }
    }

    private var amsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("AMS", systemImage: "circle.grid.2x2")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                if let humidity = model.snapshot.amsHumidityPercent {
                    Label("\(humidity)%", systemImage: "humidity")
                        .accessibilityLabel("AMS humidity \(humidity) percent")
                }
                if let temp = model.snapshot.amsTemp {
                    Label("\(Int(temp.rounded()))°", systemImage: "thermometer.low")
                        .accessibilityLabel("AMS temperature \(Int(temp.rounded())) degrees")
                }
            }
            .font(.subheadline)
            .monospacedDigit()
            HStack(spacing: 0) {
                ForEach(model.snapshot.trays) { tray in
                    VStack(spacing: 6) {
                        ZStack {
                            Circle()
                                .fill(tray.isEmpty
                                    ? AnyShapeStyle(Color(.tertiarySystemFill))
                                    : AnyShapeStyle(color(fromRGBA: tray.colorHex)))
                                .frame(width: 52, height: 52)
                                .overlay(Circle().strokeBorder(.quaternary, lineWidth: 1))
                            if activeSlots.contains(tray.id) {
                                Circle()
                                    .strokeBorder(.orange, lineWidth: 2.5)
                                    .frame(width: 62, height: 62)
                            }
                        }
                        .frame(width: 62, height: 62)
                        Text(tray.isEmpty ? "—" : tray.type)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if tray.remainPercent >= 0 {
                            Text("\(tray.remainPercent)%")
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                                .monospacedDigit()
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemGroupedBackground)))
    }

    private var alertsCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(model.snapshot.alerts) { alert in
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red)
                    if let url = alert.wikiURL {
                        Link("HMS \(alert.code)", destination: url)
                            .font(.footnote.monospaced())
                    } else {
                        Text("HMS \(alert.code)")
                            .font(.footnote.monospaced())
                    }
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 14).fill(.red.opacity(0.12)))
    }

    private var footerCard: some View {
        VStack(spacing: 8) {
            HStack(spacing: 14) {
                Label(model.snapshot.speedLevelName, systemImage: "speedometer")
                if !model.snapshot.wifiSignal.isEmpty {
                    Label(model.snapshot.wifiSignal, systemImage: "wifi")
                }
                Spacer()
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            HStack(spacing: 8) {
                Circle()
                    .fill(model.isConnected ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                    .shadow(color: (model.isConnected ? Color.green : Color.red).opacity(0.8),
                            radius: 3)
                Text(model.connectionText)
                    .lineLimit(2)
                Spacer()
                if let updated = model.lastUpdate {
                    Text(updated.formatted(date: .omitted, time: .standard))
                        .monospacedDigit()
                }
            }
            .font(.caption2)
            .foregroundStyle(.tertiary)
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemGroupedBackground)))
    }

    // MARK: helpers

    private var activeSlots: Set<Int> {
        Set(model.snapshot.nozzles.compactMap { $0.active ? $0.amsSlot : nil })
    }

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
