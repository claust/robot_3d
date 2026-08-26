import AppKit
import Foundation
import SwiftUI

// `--dump` runs headless: connect, print one decoded snapshot, exit.
// `--snapshot <out.png>` renders the dashboard with simulated data to a PNG.
// Both exist so the app can be verified without opening a window.
if CommandLine.arguments.contains("--dump") {
    runDump()
} else if let idx = CommandLine.arguments.firstIndex(of: "--snapshot"),
          idx + 1 < CommandLine.arguments.count {
    let style: TempVisualStyle? = CommandLine.arguments
        .firstIndex(of: "--style")
        .flatMap { i in
            i + 1 < CommandLine.arguments.count
                ? TempVisualStyle.allCases.first {
                    $0.rawValue.lowercased() == CommandLine.arguments[i + 1].lowercased()
                }
                : nil
        }
    let path = CommandLine.arguments[idx + 1]
    Task { @MainActor in
        await renderSnapshot(to: path, style: style)
    }
    RunLoop.main.run()  // renderSnapshot exits the process when done
} else {
    PrinterStatusApp.main()
}

struct PrinterStatusApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = PrinterViewModel(
        forceSimulate: CommandLine.arguments.contains("--simulate"))

    var body: some Scene {
        Window("Printer Status", id: "main") {
            DashboardView(model: model)
        }
        .windowResizability(.contentSize)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // When run as a bare executable (swift run), make sure we behave
        // like a normal windowed app and come to the front.
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}

@MainActor
func renderSnapshot(to path: String, style: TempVisualStyle? = nil) async {
    let model = PrinterViewModel(forceSimulate: true)
    // let a few simulated reports arrive
    try? await Task.sleep(for: .seconds(3))
    let renderer = ImageRenderer(content: DashboardView(model: model, forcedStyle: style)
        .background(Color(nsColor: .windowBackgroundColor)))
    renderer.scale = 2
    guard let cgImage = renderer.cgImage else {
        print("Render failed")
        exit(1)
    }
    let url = URL(fileURLWithPath: path) as CFURL
    guard let dest = CGImageDestinationCreateWithURL(url, "public.png" as CFString, 1, nil) else {
        print("Cannot write \(path)")
        exit(1)
    }
    CGImageDestinationAddImage(dest, cgImage, nil)
    CGImageDestinationFinalize(dest)
    print("Wrote \(path)")
    exit(0)
}

func runDump() {
    guard let config = PrinterConfig.load() else {
        print("No credentials: set BAMBU_* env vars or provide cad/.env")
        exit(1)
    }
    var merged: [String: Any] = [:]
    let done = DispatchSemaphore(value: 0)
    let source = BambuMQTTSource(config: config)
    source.onStatus = { text, _ in print("status: \(text)") }
    source.onReport = { report in
        deepMerge(&merged, report)
        // wait until the full pushall (with gcode_state) has arrived
        if merged["gcode_state"] != nil { done.signal() }
    }
    source.start()
    if done.wait(timeout: .now() + 20) == .timedOut {
        print("Timed out waiting for a report")
        source.stop()
        exit(1)
    }
    // give a second for a few more deltas, then decode
    Thread.sleep(forTimeInterval: 1.5)
    let snapshot = PrinterSnapshot.decode(from: merged)
    source.stop()

    print("state:      \(snapshot.gcodeState)")
    print("job:        \(snapshot.jobName)")
    print("progress:   \(snapshot.percent)%  layer \(snapshot.layer)/\(snapshot.totalLayers)  \(snapshot.remainingMinutes) min left")
    if let stage = snapshot.stageText { print("stage:      \(stage)") }
    for nozzle in snapshot.nozzles {
        let active = nozzle.active ? " (active)" : ""
        let slot = nozzle.amsSlot.map { "  AMS slot \($0)" } ?? ""
        print("nozzle \(nozzle.name):  \(nozzle.current)° → \(nozzle.target)°\(active)  ⌀\(nozzle.diameter) \(nozzle.type)\(slot)")
    }
    print("bed:        \(snapshot.bedCurrent)° → \(snapshot.bedTarget)°")
    print("chamber:    \(snapshot.chamberCurrent)°")
    if let humidity = snapshot.amsHumidityPercent, let temp = snapshot.amsTemp {
        print("AMS:        humidity \(humidity)%  temp \(temp)°")
    }
    for tray in snapshot.trays {
        print("  slot \(tray.id): \(tray.isEmpty ? "empty" : tray.type)  #\(tray.colorHex)  remain \(tray.remainPercent)%")
    }
    print("fans:       part \(snapshot.partFanPercent)%  aux \(snapshot.auxFanPercent)%  chamber \(snapshot.chamberFanPercent)%")
    print("speed:      \(snapshot.speedLevelName) (\(snapshot.speedMagnitude)%)   wifi \(snapshot.wifiSignal)")
    for alert in snapshot.alerts { print("HMS:        \(alert.code)") }
    exit(0)
}
