# robot_3d

3D-printed robot platform: build123d CAD, Bambu Lab X2D printer over LAN,
Swift printer-status apps, ESP32-C5 firmware.

## CAD and printing (cad/)

uv project — run everything with `uv run` from inside `cad/`.

- Experiments go in `cad/demo_NN/`; an ongoing build graduates to a named
  folder (e.g. `cad/robot_car/`) by renaming, not copying.
- Render a model and check it visually before slicing; run a design's
  PASS/FAIL check script, if it has one, before printing.
- Running clearance is 0.2 mm radial (calibrated — don't re-derive).
- `print_pipeline.py` subcommands: `slice [--supports]`, `verify`, `upload`,
  `print --ams-slot N | --trays 2,ext`, `status`.
- Always get the user's explicit go-ahead before starting a physical print.
- Credentials in `cad/.env` (gitignored, see `.env.example`) — never commit.
- `BED_TYPE` in print_pipeline.py must match the plate on the bed.
- AMS slots are 0-indexed: 0=black, 1=white, 2=dark blue, 3=green (PLA Basic).
- Slicing resolves Bambu profile inheritance locally; the Bambu Studio CLI
  doesn't, which drops the AMS load gcode and causes air prints.
- `--supports`: the filament→extruder map must be CLI args
  (`--filament-map 1,2 --filament-map-mode Manual`) — as profile keys they
  segfault the CLI. The prime tower must sit at X≥20.5 for the aux extruder.

## Swift apps (shared/BambuKit, macos/, ios/)

- `shared/BambuKit` (SwiftPM, macOS 14 + iOS 17) holds everything
  protocol-shaped: MQTT, TLS roots, SSDP discovery, chamber camera. Keep it
  UI-free; app targets hold only UI and config.
- macOS app is read-only (never sends print commands). `swift run PrinterStatus`
  with `--simulate`, `--dump`, `--discover`, or `--snapshot out.png` to verify UI.
- iOS app: `xcodegen generate`, then xcodebuild — see its README.
- Protocol and camera notes: `macos/RESEARCH.md`.

## ESP32-C5 firmware (esp32-c5/)

ESP-IDF v6.1 projects for the Seeed XIAO ESP32-C5, one folder each. From a
project folder: `source ~/.espressif/tools/activate_idf_v6.1.sh`, then
`idf.py build` and `idf.py -p /dev/cu.usbmodem* flash`.

- `sdkconfig.defaults` is the source of truth; `sdkconfig` and `build/` are generated.
- Shared code is ESP-IDF components in `esp32-c5/components/` (e.g. `pwm_led`);
  a project adds `set(EXTRA_COMPONENT_DIRS ../components)` and `PRIV_REQUIRES <name>`.
- Circuit diagrams: each project's `<project>.fzz` is the schematic's source. Edit it with
  the fritzing-format skill or Fritzing, then re-render and commit `<project>_schematic.png`
  (the only render kept). Third-party parts are downloaded (not committed) into
  `esp32-c5/fritzing-parts/`; its README has sources and fixes.
- XIAO pad labels (D0…) aren't GPIO numbers — check the pin map. Onboard user LED is GPIO 27, active-low.
- The serial port is exclusive: if a VS Code/Arduino monitor holds it, don't
  read it from a shell. Never toggle DTR/RTS — it resets the chip into download mode.
- VS Code: open `robot_3d.code-workspace`; the ESP-IDF extension acts on its active
  folder (first by default). Each project's settings pin `IDF_TARGET=esp32c5` —
  without it the extension configures the plain ESP32.
  Keep IntelliSense mode `linux-gcc-x86`, and keep `idf.port`, `idf.currentSetup`,
  OpenOCD and clangd paths out of tracked settings files.

## Conventions

- Generated outputs (STL, STEP, PNG, gcode, USD, build/) are gitignored; commit only source.
  Exception: Fritzing schematic PNGs next to their `.fzz`.
