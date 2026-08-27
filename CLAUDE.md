# robot_3d

3D-printed robot platform. Parametric CAD in Python (build123d), printed on a
Bambu Lab X2D over LAN. All code lives in `cad/`, a uv project — run
everything with `uv run` from inside `cad/`.

## Modeling

- `demo_01/washer.py <outer_diameter_mm>` — example parametric part; exports STL + STEP.
- `demo_01/render.py <model.stl>` — renders iso/top/front PNGs for visual verification.
  Always render and check before slicing.
- `demo_02/nut.py [size] [clearance_mm]` — printable ISO hex nut (bd_warehouse);
  also exports a half-section STL to inspect the thread profile.
- `demo_03/gear.py [module] [teeth] [face_width] [bore]` — involute spur gear
  (py_gearworks, local editable checkout at ~/Repos/py_gearworks).
- `demo_04/fit_test.py [clearance_mm]` — post/washer coupons that calibrate
  running clearances by hand-feel. 0.2 mm radial is the calibrated value.
- `demo_04/gearbox.py [module] [z1] [z2] [z3] [face_width]` — three-gear train
  on an open frame; center distances come from py_gearworks' `mesh_to()`,
  never hand-computed. Exports each part plus assembly and section STLs.
- `demo_04/assembly_check.py [steps]` — automated PASS/FAIL design checks
  (interference, clearances, mesh sweep, snap strain, sliceability incl. a
  mesh overhang scan). Run it before slicing; exit 0 only if all pass.

## Printing (print_pipeline.py)

```
uv run print_pipeline.py slice <model.stl>     # -> <model>.gcode.3mf
uv run print_pipeline.py verify <file.gcode.3mf>  # pre-flight checks + toolpath PNG
uv run print_pipeline.py upload <file.gcode.3mf>  # FTPS to printer USB stick
uv run print_pipeline.py print <file.gcode.3mf> --ams-slot N  # MQTT start
uv run print_pipeline.py status
```

- Credentials come from `cad/.env` (gitignored; see `.env.example`). Never commit it.
- `print` auto-verifies and refuses failing files. Always get the user's explicit
  go-ahead before starting a physical print.
- `BED_TYPE` in print_pipeline.py must match the plate on the bed (X2D checks optically).
- AMS slots are 0-indexed: 0=black, 1=white, 2=dark blue, 3=green (PLA Basic).
- Slicing resolves Bambu profile inheritance locally — the Bambu Studio CLI does
  not, which silently drops the AMS load gcode and causes air prints.

## macOS status app (macos/PrinterStatus)

Swift Package (SwiftUI + MQTTNIO) showing live printer status in a small
window — read-only, never sends print commands. From `macos/PrinterStatus`:
`swift run PrinterStatus` (live), `--simulate` (fake data), `--dump`
(headless status to stdout), `--snapshot out.png` (render UI to PNG for
verification). `./install.sh` installs it to /Applications for Spotlight.
Protocol notes in `macos/RESEARCH.md`. Credentials resolve from BAMBU_* env
vars, then `~/Library/Application Support/PrinterStatus/config.env` (which
may hold a `BAMBU_ENV_FILE=` pointer), then `cad/.env` found by walking up.

## Conventions

- Generated outputs (STL, STEP, PNG, gcode) are gitignored; commit only source.
- New experiments go in `cad/demo_NN/` folders sharing the root uv environment.
