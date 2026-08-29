import AppKit
import BambuKit
import Foundation
import ImageIO
import SwiftUI

// `--dump` runs headless: connect, print one decoded snapshot, exit.
// `--discover` sweeps the LAN for printers and prints what answers.
// `--snapshot <out.png>` renders the dashboard with simulated data to a PNG.
// All three exist so the app can be verified without opening a window.
if CommandLine.arguments.contains("--dump") {
    runDump()
} else if CommandLine.arguments.contains("--discover") {
    runDiscover()
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
    let live = CommandLine.arguments.contains("--live")
    Task { @MainActor in
        await renderSnapshot(to: path, style: style, live: live)
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
                .navigationTitle(model.printerName ?? "Printer Status")
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
func renderSnapshot(to path: String, style: TempVisualStyle? = nil, live: Bool = false) async {
    let model = PrinterViewModel(forceSimulate: !live)
    if live {
        // wait for a full status report and the first camera frame
        for _ in 0..<40 where model.lastUpdate == nil || model.cameraFrame == nil {
            try? await Task.sleep(for: .seconds(0.5))
        }
    } else {
        // let a few simulated reports arrive
        try? await Task.sleep(for: .seconds(3))
    }
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
    guard CGImageDestinationFinalize(dest) else {
        print("Failed to write \(path)")
        exit(1)
    }
    print("Wrote \(path)")
    exit(0)
}

func runDump() {
    guard let config = PrinterConfig.load() else {
        print("No credentials: set BAMBU_* env vars or provide cad/.env")
        exit(1)
    }
    // Reports arrive on the MQTT client's thread while this thread waits,
    // so all access to the accumulated state goes through a lock.
    let lock = NSLock()
    var merged: [String: Any] = [:]
    var deviceName: String?
    let done = DispatchSemaphore(value: 0)
    let names = PrinterNameSource(ip: config.ip)
    names.onName = { name in
        lock.lock()
        deviceName = name
        lock.unlock()
    }
    names.start()
    let source = BambuMQTTSource(config: config)
    source.onStatus = { text, _ in print("status: \(text)") }
    source.onReport = { report in
        lock.lock()
        deepMerge(&merged, report)
        // wait until the full pushall (with gcode_state) has arrived
        let complete = merged["gcode_state"] != nil
        lock.unlock()
        if complete { done.signal() }
    }
    source.start()
    if done.wait(timeout: .now() + 20) == .timedOut {
        print("Timed out waiting for a report")
        source.stop()
        exit(1)
    }
    // give a second for a few more deltas, then decode a stable copy
    Thread.sleep(forTimeInterval: 1.5)
    lock.lock()
    let stableState = merged
    let stableName = deviceName
    lock.unlock()
    let snapshot = PrinterSnapshot.decode(from: stableState)
    source.stop()
    names.stop()

    if let stableName { print("printer:    \(stableName)") }
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

/// Headless SSDP sweep — the same code path the iOS onboarding screen runs,
/// where its results can be checked against a printer you can walk over to.
func runDiscover() {
    let discovery = PrinterDiscovery()
    discovery.onPrinter = { printer in
        print("found \(printer.displayName)  \(printer.ip)  serial \(printer.serial)  "
            + "model \(printer.modelName)  firmware \(printer.version)")
    }
    discovery.onFinished = { printers, outcome in
        switch outcome {
        case .noLocalNetwork:
            print("no Ethernet or Wi-Fi address — nothing was probed")
            exit(1)
        case .completed(let hosts, let truncated):
            print("probed \(hosts) hosts\(truncated ? " (subnet clamped)" : "")"
                + " — \(printers.count) printer(s)")
            exit(printers.isEmpty ? 1 : 0)
        }
    }
    discovery.start()
    RunLoop.main.run()  // the callbacks exit the process
}
