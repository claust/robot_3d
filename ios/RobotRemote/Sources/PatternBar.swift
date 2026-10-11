import RobotLink
import SwiftUI

/// The preset patterns: a button for each, and the calibration sheet. While
/// one runs, the row turns into its progress and a Stop button.
struct PatternBar: View {
    var link: CarLink
    @AppStorage("pattern.straight") private var straight = 1.0
    @AppStorage("pattern.corners") private var corners = 1.0
    @AppStorage("pattern.circleSize") private var circleSize = 1.0
    @AppStorage("pattern.circleLength") private var circleLength = 1.0
    @State private var calibrating = false

    var body: some View {
        Group {
            if let run = link.pattern {
                HStack(spacing: 16) {
                    ProgressView(timerInterval: run.period, countsDown: false) {
                        Text("Driving \(run.pattern.name)")
                    } currentValueLabel: {
                        Text(timerInterval: run.period, countsDown: true)
                            .monospacedDigit()
                    }
                    Button(role: .destructive, action: link.stopPattern) {
                        Label("Stop", systemImage: "stop.fill")
                            .frame(maxHeight: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                }
            } else {
                HStack(spacing: 10) {
                    ForEach(DrivePattern.allCases) { pattern in
                        Button {
                            link.drive(pattern, calibration: calibration)
                        } label: {
                            VStack(spacing: 4) {
                                Image(systemName: pattern.symbol)
                                    .font(.title3)
                                Text(pattern.title)
                                    .font(.caption)
                            }
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                        }
                        .accessibilityLabel("Drive \(pattern.name)")
                    }
                    Button {
                        calibrating = true
                    } label: {
                        Image(systemName: "slider.horizontal.3")
                            .font(.title3)
                            .frame(maxHeight: .infinity)
                    }
                    .accessibilityLabel("Calibrate patterns")
                }
                .buttonStyle(.bordered)
                .disabled(!link.isConnected)
            }
        }
        .frame(height: 56)
        .sensoryFeedback(trigger: link.pattern) { _, run in
            run == nil ? .stop : .start
        }
        .sheet(isPresented: $calibrating) {
            CalibrationSheet(
                straight: $straight, corners: $corners,
                circleSize: $circleSize, circleLength: $circleLength)
        }
    }

    private var calibration: DrivePattern.Calibration {
        DrivePattern.Calibration(
            straight: straight, corners: corners, circleSize: circleSize, circleLength: circleLength)
    }
}

private extension DrivePattern {
    var title: String {
        switch self {
        case .square: "Square"
        case .circle: "Circle"
        case .figureEight: "Eight"
        }
    }

    var name: String {
        switch self {
        case .square: "a square"
        case .circle: "a circle"
        case .figureEight: "an eight"
        }
    }

    var symbol: String {
        switch self {
        case .square: "square"
        case .circle: "circle"
        case .figureEight: "infinity"
        }
    }
}

/// One correction per kind of move.
private struct CalibrationSheet: View {
    @Binding var straight: Double
    @Binding var corners: Double
    @Binding var circleSize: Double
    @Binding var circleLength: Double
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    factor("Straight", $straight,
                           hint: "Raise it if the square's sides come out shorter than 40 cm.")
                    factor("Corners", $corners,
                           hint: "Lower it if the square's corners turn more than 90°, raise it if less.")
                    factor("Circle size", $circleSize,
                           hint: "Lower it if the circle comes out wider than 40 cm.")
                    factor("Circle length", $circleLength,
                           hint: "Raise it if the circle stops short of where it started.")
                } footer: {
                    Text("The car has no wheel sensors, so it times each move. Get the circle's size right before its length.")
                }
                Section {
                    Button("Reset to 100%") {
                        straight = 1
                        corners = 1
                        circleSize = 1
                        circleLength = 1
                    }
                }
            }
            .navigationTitle("Calibrate patterns")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDetents([.large])
    }

    private func factor(_ title: String, _ value: Binding<Double>, hint: String) -> some View {
        Stepper(value: value, in: DrivePattern.Calibration.range, step: 0.02) {
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(title)
                    Spacer()
                    Text(value.wrappedValue, format: .percent.precision(.fractionLength(0)))
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                }
                Text(hint)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }
}
