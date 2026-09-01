# Printer Status (iOS)

The macOS status app's iPhone sibling: live, read-only Bambu X2D status over
LAN MQTT, redesigned as a single scrolling column of cards — print progress,
the glowing chamber schematic, AMS trays, connection footer. It never sends
print commands.

The protocol layer (MQTT decode, TLS, SSDP discovery, simulator) comes from
[BambuKit](../../shared/BambuKit), the package the macOS app also depends
on, so protocol fixes land in both apps at once. The UI, credential storage
and the app shell are iOS-specific.

## Onboarding

On a first launch with no credentials the app offers to find the printer
itself: it sweeps the local subnet with directed SSDP `M-SEARCH` datagrams
and lists whatever answers, with the name, model and address already filled
in. Picking one leaves just the access code to type — that is a secret on
the printer's screen and the one thing discovery cannot supply. Manual
entry is one tap away, and the settings sheet has the same scan under
"Scan for printers" (handy when DHCP moves the printer: it refreshes the
address and serial and leaves the stored access code alone).

The sweep is unicast, which is what keeps it off the
`com.apple.developer.networking.multicast` entitlement — see the discovery
notes in [../../macos/RESEARCH.md](../../macos/RESEARCH.md). It does need
the Local Network permission, and iOS has no API to tell a refusal from an
empty network, so the empty state offers both explanations and a link into
Settings. Note that the *simulator* is not subject to that permission at
all — it uses the Mac's network — so the prompt only appears on a device.

The chamber camera works here too, as of the switch to the in-process
RTSPS client in BambuKit (`BambuCameraSource`) — the old macOS pane needed a
local ffmpeg subprocess, which iOS cannot spawn. Tapping the card opens a
full-screen view. The stream stops with the rest of the sources when the app
leaves the foreground.

**TLS posture, iOS vs macOS:** on macOS the MQTT session is chain-verified
against Bambu's pinned device-CA roots (NIOSSL, hostname check off since the
certificate names the serial). The iOS MQTT session is not: MQTTNIO compiles
NIOSSL out there, and its `TSTLSConfiguration` exposes no hook for a custom
trust evaluation, so the *default* Network.framework evaluation applies —
and that always uses the SSL policy, which the printer's certificate can
never pass (serial CN, no serverAuth EKU, over-long validity, all verified
live). The iOS MQTT session is therefore **encrypted but not
authenticated**, like the macOS `BAMBU_TLS_INSECURE` escape hatch: a MITM on
the local network could impersonate the printer and capture the access code.
Acceptable for a home LAN and read-only telemetry.

The camera connection *is* authenticated on both platforms, including iOS.
It does not go through MQTTNIO, so it can install a
`sec_protocol_options_set_verify_block` that pins Bambu's roots and
evaluates under a **basic X.509 policy** instead of the SSL one — which is
exactly the constraint the MQTT path cannot escape. Verified in the iOS
simulator against a live printer. That suggests the MQTT gap is closable the
same way if MQTTNIO is bypassed or taught to pass `NWProtocolTLS.Options`
through; worth revisiting, and worth confirming on a physical device first.

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
