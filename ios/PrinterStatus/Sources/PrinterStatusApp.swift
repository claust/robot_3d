import SwiftUI

@main
struct PrinterStatusApp: App {
    @StateObject private var model = PrinterViewModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            DashboardView(model: model)
        }
        .onChange(of: scenePhase) { _, phase in
            // Sockets do not survive backgrounding; reconnect on return
            // instead of waking up to a half-dead MQTT session.
            switch phase {
            case .active: model.setActive(true)
            case .background: model.setActive(false)
            default: break
            }
        }
    }
}
