# Printer Status (iOS)

The macOS status app's iPhone sibling: live, read-only Bambu X2D status over
LAN MQTT, redesigned as a single scrolling column of cards — print progress,
the glowing chamber schematic, AMS trays, connection footer. It never sends
print commands.

The protocol layer (MQTT decode, TLS, SSDP name lookup, simulator) is shared
with `macos/PrinterStatus` — see `project.yml`, which compiles those files
straight out of the macOS package. The UI, credential storage and the app
shell are iOS-specific.

What the macOS app has that this one doesn't: the chamber camera. That pane
rides on a local ffmpeg subprocess transcoding the printer's RTSPS stream,
and iOS apps cannot spawn subprocesses; a native RTSPS/H.264 client is the
future fix.

## Build & run (simulator)

Requires Xcode and [XcodeGen](https://github.com/yonaskolb/XcodeGen)
(`brew install xcodegen`). The `.xcodeproj` is generated, not committed:

```sh
xcodegen generate
xcodebuild -project PrinterStatus.xcodeproj -scheme PrinterStatus \
  -sdk iphonesimulator -destination 'name=iPhone 17 Pro' \
  -derivedDataPath build build
xcrun simctl install booted build/Build/Products/Debug-iphonesimulator/PrinterStatus.app
xcrun simctl launch booted dk.delectosoft.printerstatus
```

With no credentials the app starts in Simulate mode. Credentials come from
the in-app settings sheet (IP + serial in UserDefaults, access code in the
Keychain) — or from `BAMBU_*` environment variables, which is how the
simulator can be pointed at the real printer:

```sh
SIMCTL_CHILD_BAMBU_PRINTER_IP=… SIMCTL_CHILD_BAMBU_PRINTER_SERIAL=… \
SIMCTL_CHILD_BAMBU_ACCESS_CODE=… \
xcrun simctl launch booted dk.delectosoft.printerstatus
```

## TestFlight

Same shape as the MeTube repo's pipeline: a manual GitHub workflow
(`.github/workflows/testflight-ios.yml`) or a local script.

```sh
Scripts/testflight.sh              # archive → export → validate → upload
Scripts/testflight.sh --validate   # same, minus the upload
Scripts/testflight.sh --archive    # just produce build-archive/PrinterStatus.ipa
```

The build number is the git commit count; `MARKETING_VERSION` in
`project.yml` stays hand-owned. Credentials resolve from the environment,
then `.testflight.env` (copy `.testflight.env.example`); the
`AuthKey_<KEYID>.p8` lives in `~/.private_keys/`.

The GitHub workflow needs four repo secrets — `ASC_KEY_ID`, `ASC_ISSUER_ID`,
`ASC_KEY_P8` (the .p8, base64-encoded), `DEVELOPMENT_TEAM` — and is started
from the Actions tab or `gh workflow run testflight-ios.yml --ref master`.

One-time setup (all already done for the MeTube app, so mostly reusable):

1. An App Store Connect API key with the **Admin** role (App Manager cannot
   mint distribution certificates for cloud signing).
2. The app record in App Store Connect: *Apps → + → New App*, platform iOS,
   bundle ID `dk.delectosoft.printerstatus`. Records cannot be created from
   the command line; the bundle ID itself is registered automatically by
   `xcodebuild -allowProvisioningUpdates` on the first archive.
3. Yourself as an internal tester under *TestFlight → Internal Testing*,
   and the TestFlight app on the phone. Internal builds skip Beta App
   Review and appear minutes after processing.
