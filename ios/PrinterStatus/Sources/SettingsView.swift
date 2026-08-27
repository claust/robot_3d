import SwiftUI

/// Where the phone gets its credentials: the values that live in `cad/.env`
/// on the Mac are typed in once here. IP and serial persist in
/// UserDefaults, the access code in the Keychain.
struct SettingsView: View {
    @ObservedObject var model: PrinterViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var ip = UserDefaults.standard.string(forKey: SettingsKey.ip) ?? ""
    @State private var serial = UserDefaults.standard.string(forKey: SettingsKey.serial) ?? ""
    @State private var accessCode = Keychain.accessCode ?? ""

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
                    TextField("192.168.1.…", text: $ip)
                        .keyboardType(.decimalPad)
                        .textContentType(.URL)
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
                    Button("Save") {
                        PrinterConfig.save(ip: ip, serial: serial, accessCode: accessCode)
                        model.reloadConfig()
                        dismiss()
                    }
                }
            }
        }
    }
}
