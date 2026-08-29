import BambuKit
import SwiftUI

/// Where the phone gets its credentials: found by scanning the network, or
/// typed in from the values that live in `cad/.env` on the Mac. IP and
/// serial persist in UserDefaults, the access code in the Keychain.
struct SettingsView: View {
    @ObservedObject var model: PrinterViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var ip = UserDefaults.standard.string(forKey: SettingsKey.ip) ?? ""
    @State private var serial = UserDefaults.standard.string(forKey: SettingsKey.serial) ?? ""
    @State private var accessCode = Keychain.accessCode ?? ""
    @State private var saveError: String?
    @State private var showScan = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Data source", selection: $model.mode) {
                        ForEach(PrinterViewModel.Mode.allCases) { m in
                            Text(m.rawValue).tag(m)
                        }
                    }
                    .pickerStyle(.segmented)
                    .disabled(!model.hasCredentials)
                } header: {
                    Text("Mode")
                } footer: {
                    if !model.hasCredentials {
                        Text("Enter the printer details below to enable live mode.")
                    }
                }

                Section {
                    Button {
                        showScan = true
                    } label: {
                        Label("Scan for printers", systemImage: "dot.radiowaves.left.and.right")
                    }
                } footer: {
                    Text("Fills in the address and serial from whatever answers "
                        + "on this network. The access code still has to be typed.")
                }

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
                    Text("On the printer: Settings → Network → LAN Only Mode shows "
                        + "the access code; the serial is under Settings → Device. "
                        + "The phone must be on the same network as the printer.")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                }
            }
            .sheet(isPresented: $showScan) {
                ScanSheet { printer in
                    // A rediscovered printer may have moved: take the new
                    // address and serial, and leave the access code alone —
                    // it does not change with the lease.
                    ip = printer.ip
                    serial = printer.serial
                    showScan = false
                }
            }
            .alert("Couldn't save", isPresented: Binding(
                get: { saveError != nil },
                set: { if !$0 { saveError = nil } }
            )) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(saveError ?? "")
            }
        }
    }

    /// All three fields, or none: a partial config would silently land the
    /// app in simulate mode with no explanation. All-empty is legitimate —
    /// it clears the printer and returns to simulated data.
    private func save() {
        let ip = ip.trimmingCharacters(in: .whitespaces)
        let serial = serial.trimmingCharacters(in: .whitespaces)
        let accessCode = accessCode.trimmingCharacters(in: .whitespaces)
        let filled = [ip, serial, accessCode].filter { !$0.isEmpty }.count
        guard filled == 0 || filled == 3 else {
            saveError = "Fill in all three printer fields, or clear all of "
                + "them to use simulated data."
            return
        }
        guard PrinterConfig.save(ip: ip, serial: serial, accessCode: accessCode) else {
            saveError = "The Keychain rejected the write, so the access code "
                + "is not stored. Try saving again."
            return
        }
        model.reloadConfig()
        dismiss()
    }
}

/// The settings-sheet wrapper around `PrinterScanList` — picking a printer
/// here fills the form in rather than connecting straight away.
private struct ScanSheet: View {
    var onSelect: (DiscoveredPrinter) -> Void

    @StateObject private var scanner = PrinterScanner()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            PrinterScanList(scanner: scanner, onSelect: onSelect)
                .navigationTitle("Scan")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Scan again") { scanner.scan() }
                            .disabled(scanner.isScanning)
                    }
                }
        }
        .onAppear { scanner.scan() }
        .onDisappear { scanner.cancel() }
    }
}
