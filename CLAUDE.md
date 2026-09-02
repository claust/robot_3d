# robot_3d

3D-printed robot platform. Parametric CAD in Python (build123d), printed on a
Bambu Lab X2D over LAN. All code lives in `cad/`, a uv project — run
everything with `uv run` from inside `cad/`.

## Modeling

Parametric part scripts live in `cad/demo_NN/` folders (experiments) or a
named folder like `cad/robot_car/` (an ongoing build), and export STL + STEP
next to themselves. Always render a model and check it visually before
slicing, and run a design's own PASS/FAIL check script, where it has one,
before any print. Running clearances are calibrated at 0.2 mm radial — use
that value, don't re-derive it.

## Printing (print_pipeline.py)

```
uv run print_pipeline.py slice <model.stl>     # -> <model>.gcode.3mf
uv run print_pipeline.py slice <model.stl> --supports  # supports in white from the aux nozzle
uv run print_pipeline.py verify <file.gcode.3mf>  # pre-flight checks + toolpath PNG
uv run print_pipeline.py upload <file.gcode.3mf>  # FTPS to printer USB stick
uv run print_pipeline.py print <file.gcode.3mf> --ams-slot N  # MQTT start
uv run print_pipeline.py print <file.gcode.3mf> --trays 2,ext  # dual-filament start
uv run print_pipeline.py status
```

- Credentials come from `cad/.env` (gitignored; see `.env.example`). Never commit it.
- `print` auto-verifies and refuses failing files. Always get the user's explicit
  go-ahead before starting a physical print.
- `BED_TYPE` in print_pipeline.py must match the plate on the bed (X2D checks optically).
- AMS slots are 0-indexed: 0=black, 1=white, 2=dark blue, 3=green (PLA Basic).
- Slicing resolves Bambu profile inheritance locally — the Bambu Studio CLI does
  not, which silently drops the AMS load gcode and causes air prints.
- `--supports` slices two filaments (body + support) and maps support to the
  aux Bowden extruder. The filament→extruder map MUST be CLI args
  (`--filament-map 1,2 --filament-map-mode Manual`) — as process-profile keys
  they segfault the CLI (BambuStudio #9119). The prime tower must be moved
  inside the aux extruder's reachable area (X≥20.5), or the multi-extruder
  printable-area check rejects the gcode.
- `print --trays 2,ext` maps sliced filament order to trays: AMS slot number
  or `ext` = the aux nozzle's external spool (virtual tray 255 in vir_slot;
  sent as -1 in ams_mapping + ams_id 255 in ams_mapping2).

## Shared protocol layer (shared/BambuKit)

SwiftPM package both status apps depend on: MQTT session + report decode,
Bambu's TLS trust roots, SSDP discovery, the chamber camera, and the
simulated source. UI-free and declared for macOS 14 + iOS 17, so a
platform-only import fails to build here rather than in one app.
`swift build --package-path shared/BambuKit`,
`swift test --package-path shared/BambuKit` (SSDP parsing, subnet math,
camera trust plumbing).
Anything protocol-shaped belongs here, not in an app target.

`BambuCameraSource` decodes the RTSPS chamber stream in-process (RTSP via
`claust/IPCamKit`, our fork of steelbrain/IPCamKit pinned by revision —
upstream has no TLS and its Digest auth trips the printer, see that repo's
`PATCHES.md` — then VideoToolbox) and emits `CGImage`, so neither app needs
ffmpeg or a platform image type.
The printer omits its intermediate CA on the camera port but sends it on the
MQTT port, so `BambuDeviceCA` harvests it from a throwaway TLS handshake —
details in `macos/RESEARCH.md`.

## macOS status app (macos/PrinterStatus)

Swift Package (SwiftUI + MQTTNIO) showing live printer status in a small
window — read-only, never sends print commands. From `macos/PrinterStatus`:
`swift run PrinterStatus` (live), `--simulate` (fake data), `--dump`
(headless status to stdout), `--discover` (sweep the LAN for printers),
`--snapshot out.png` (render UI to PNG for verification). `./install.sh`
installs it to /Applications for Spotlight.
Protocol notes in `macos/RESEARCH.md`. Credentials resolve from BAMBU_* env
vars, then `~/Library/Application Support/PrinterStatus/config.env` (which
may hold a `BAMBU_ENV_FILE=` pointer), then `cad/.env` found by walking up.

## iOS status app (ios/PrinterStatus)

iPhone port of the macOS app; both take the protocol layer from
`shared/BambuKit` — UI and config are iOS-specific, and the two now share
the chamber camera too. From `ios/PrinterStatus`:
`xcodegen generate`, then build with xcodebuild for the simulator (see its
README). First launch offers network discovery (unicast SSDP sweep) to fill
in address and serial; credentials otherwise come from the in-app settings
sheet or `SIMCTL_CHILD_BAMBU_*` env vars. TestFlight releases: `Scripts/testflight.sh` locally, or the
manual `testflight-ios.yml` GitHub workflow (secrets: ASC_KEY_ID,
ASC_ISSUER_ID, ASC_KEY_P8, DEVELOPMENT_TEAM).

## Conventions

- Generated outputs (STL, STEP, PNG, gcode, USD) are gitignored; commit only source.
- New experiments go in `cad/demo_NN/` folders sharing the root uv environment.
- An experiment that turns into an ongoing build graduates to a named folder
  (`cad/robot_car/` was demo_06). Rename rather than copy — git keeps the
  history, and a copy just gives you two sources to fix. Scripts resolve
  paths from `__file__`, so a rename only costs the doc references.
