import BambuKit
import SwiftUI
// UIApplication (for the jump into iPhone Settings) comes in through
// SwiftUI today; import it explicitly rather than relying on that.
import UIKit

/// First run: sweep the network, pick the printer that answers, type the one
/// credential SSDP can't tell us (the access code). Manual entry stays one
/// tap away for a printer on another subnet, or a network that blocks the
/// sweep.
struct OnboardingView: View {
    @ObservedObject var model: PrinterViewModel
    @Environment(\.dismiss) private var dismiss

    @StateObject private var scanner = PrinterScanner()
    @State private var selected: DiscoveredPrinter?
    @State private var showManualEntry = false

    var body: some View {
        NavigationStack {
            PrinterScanList(scanner: scanner) { printer in
                scanner.cancel()  // nothing left to look for
                selected = printer
            }
            .safeAreaInset(edge: .top) { header }
            .safeAreaInset(edge: .bottom) { footer }
            .navigationTitle("Find your printer")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Not now") { finish() }
                }
            }
            .navigationDestination(item: $selected) { printer in
                AccessCodeView(printer: printer, model: model, onConnected: finish)
            }
            .navigationDestination(isPresented: $showManualEntry) {
                ManualEntryView(model: model, onSaved: finish)
            }
        }
        .onAppear { scanner.scan() }
        .onDisappear { scanner.cancel() }
    }

    private var header: some View {
        VStack(spacing: 6) {
            Text("Printer Status looks for Bambu printers on the Wi-Fi this "
                + "iPhone is joined to.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
                .padding(.bottom, 8)
        }
        .frame(maxWidth: .infinity)
        .background(.bar)
    }

    private var footer: some View {
        VStack(spacing: 10) {
            Button {
                scanner.scan()
            } label: {
                Label("Scan again", systemImage: "arrow.clockwise")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(scanner.isScanning)

            Button("Enter details manually") { showManualEntry = true }
                .font(.subheadline)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(.bar)
    }

    /// Onboarding is offered once. Dismissing it — with or without a
    /// printer — leaves the app in simulate mode and the settings sheet as
    /// the way back in, rather than reopening this on every launch.
    private func finish() {
        UserDefaults.standard.set(true, forKey: SettingsKey.onboardingShown)
        dismiss()
    }
}

/// The scan results themselves: used by onboarding, and by the settings
/// sheet's "Scan for printers".
struct PrinterScanList: View {
    @ObservedObject var scanner: PrinterScanner
    var onSelect: (DiscoveredPrinter) -> Void

    var body: some View {
        List {
            if !scanner.printers.isEmpty {
                Section("Printers found") {
                    ForEach(scanner.printers) { printer in
                        Button { onSelect(printer) } label: { row(printer) }
                            .buttonStyle(.plain)
                    }
                }
            }
            if scanner.isScanning {
                Section {
                    HStack(spacing: 12) {
                        ProgressView()
                        Text(scanner.printers.isEmpty
                            ? "Scanning your network…"
                            : "Still scanning…")
                            .foregroundStyle(.secondary)
                    }
                }
            } else if scanner.hasFinishedEmpty {
                Section { emptyState }
            }
        }
    }

    private func row(_ printer: DiscoveredPrinter) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "printer.fill")
                .font(.title3)
                .foregroundStyle(.tint)
            VStack(alignment: .leading, spacing: 2) {
                Text(printer.displayName)
                    .font(.headline)
                Text(printer.modelName.isEmpty
                    ? printer.ip
                    : "\(printer.modelName) · \(printer.ip)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.tertiary)
        }
        .contentShape(Rectangle())
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(emptyTitle)
                .font(.headline)
            Text(emptyAdvice)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            // iOS has no API for reading the Local Network grant, so a
            // refusal and an empty network look identical from here — offer
            // the Settings trip either way.
            if case .completed = scanner.lastOutcome {
                Button("Open iPhone Settings") {
                    guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
                    UIApplication.shared.open(url)
                }
                .font(.subheadline)
            }
        }
        .padding(.vertical, 4)
    }

    private var emptyTitle: String {
        if case .noLocalNetwork = scanner.lastOutcome { return "Not on Wi-Fi" }
        return "No printers answered"
    }

    private var emptyAdvice: String {
        switch scanner.lastOutcome {
        case .noLocalNetwork:
            return "This iPhone has no Wi-Fi or Ethernet connection. Join the "
                + "network your printer is on and scan again."
        case .completed(_, let truncated) where truncated:
            return "This network is too large to scan completely, so the printer "
                + "may simply be outside the range that was checked. Entering its "
                + "IP address manually always works."
        default:
            return "Check that the printer is powered on and on this Wi-Fi network, "
                + "and that Printer Status is allowed to find devices on the local "
                + "network in iPhone Settings › Privacy & Security › Local Network."
        }
    }
}

/// Step two: the access code, which is a secret on the printer's screen and
/// so is the one thing discovery cannot supply.
private struct AccessCodeView: View {
    let printer: DiscoveredPrinter
    @ObservedObject var model: PrinterViewModel
    var onConnected: () -> Void

    @State private var accessCode = ""
    @State private var saveError: String?
    @FocusState private var codeFocused: Bool

    var body: some View {
        Form {
            Section {
                LabeledContent("Printer", value: printer.displayName)
                if !printer.modelName.isEmpty {
                    LabeledContent("Model", value: printer.modelName)
                }
                LabeledContent("Address", value: printer.ip)
                LabeledContent("Serial", value: printer.serial)
                    .font(.callout.monospaced())
            } header: {
                Text("Discovered")
            }

            Section {
                SecureField("Access code", text: $accessCode)
                    .focused($codeFocused)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .onSubmit(connect)
            } header: {
                Text("Access code")
            } footer: {
                Text("On the printer: Settings › Network › LAN Only Mode. "
                    + "It is stored in this iPhone's Keychain and only ever sent "
                    + "to the printer.")
            }

            Section {
                Button("Connect", action: connect)
                    .disabled(accessCode.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .navigationTitle(printer.displayName)
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { codeFocused = true }
        .alert("Couldn't save", isPresented: Binding(
            get: { saveError != nil },
            set: { if !$0 { saveError = nil } }
        )) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(saveError ?? "")
        }
    }

    private func connect() {
        let code = accessCode.trimmingCharacters(in: .whitespaces)
        guard !code.isEmpty else { return }
        guard PrinterConfig.save(ip: printer.ip, serial: printer.serial, accessCode: code) else {
            saveError = "The Keychain rejected the write, so the access code is "
                + "not stored. Try again."
            return
        }
        model.reloadConfig()
        onConnected()
    }
}

/// The escape hatch: a printer on another subnet, or a network where the
/// sweep is blocked. Same three fields as the settings sheet.
private struct ManualEntryView: View {
    @ObservedObject var model: PrinterViewModel
    var onSaved: () -> Void

    @State private var ip = ""
    @State private var serial = ""
    @State private var accessCode = ""
    @State private var saveError: String?

    var body: some View {
        Form {
            Section {
                // not .decimalPad: in comma-decimal locales it has no "."
                // key, which makes a dotted IPv4 address untypeable
                TextField("192.168.1.…", text: $ip)
                    .keyboardType(.numbersAndPunctuation)
                    .autocorrectionDisabled()
                TextField("Serial number", text: $serial)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.characters)
                SecureField("Access code", text: $accessCode)
            } header: {
                Text("Printer")
            } footer: {
                Text("On the printer: Settings › Network shows the IP address and "
                    + "the LAN access code; the serial is under Settings › Device.")
            }

            Section {
                Button("Save", action: save)
                    .disabled([ip, serial, accessCode]
                        .contains { $0.trimmingCharacters(in: .whitespaces).isEmpty })
            }
        }
        .navigationTitle("Enter details")
        .navigationBarTitleDisplayMode(.inline)
        .alert("Couldn't save", isPresented: Binding(
            get: { saveError != nil },
            set: { if !$0 { saveError = nil } }
        )) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(saveError ?? "")
        }
    }

    private func save() {
        guard PrinterConfig.save(ip: ip, serial: serial, accessCode: accessCode) else {
            saveError = "The Keychain rejected the write, so the access code is "
                + "not stored. Try again."
            return
        }
        model.reloadConfig()
        onSaved()
    }
}
