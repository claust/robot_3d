import RobotLink
import SwiftUI

@main
struct RobotRemoteApp: App {
    @State private var link = CarLink(simulated: Self.simulated)
    @Environment(\.scenePhase) private var scenePhase

    /// The Simulator has no Bluetooth, so it always gets the simulated car.
    /// On a phone, launch with `--simulate` for the same.
    private static var simulated: Bool {
        #if targetEnvironment(simulator)
        true
        #else
        ProcessInfo.processInfo.arguments.contains("--simulate")
        #endif
    }

    var body: some Scene {
        WindowGroup {
            DriveView(link: link)
                .onAppear { link.start() }
        }
        .onChange(of: scenePhase) { _, phase in
            // In the background the app can't keep its 20 Hz stream going,
            // so let go of the car outright rather than leave the Pi's
            // watchdog to notice.
            switch phase {
            case .active: link.start()
            case .background: link.stop()
            default: break
            }
        }
    }
}
