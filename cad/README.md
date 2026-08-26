# CAD — parametric design and print pipeline

Parametric 3D models for the robot platform, built with
[build123d](https://build123d.readthedocs.io/) and printed on a Bambu Lab X2D
over the LAN. Python environment is managed with [uv](https://docs.astral.sh/uv/)
(`uv sync` to set up).

## Layout

- `demo_01/` — first experiment: a parametric washer (`washer.py`, outer
  diameter as the driving parameter) and an STL renderer (`render.py`) that
  produces PNG views for visual verification.
- `demo_02/` — printable ISO hex nut (`nut.py`, thread size string as the
  driving parameter, e.g. `M8`). Body dimensions come from bd_warehouse's
  ISO 4032 tables; the modeled internal thread gets a radial printing
  clearance (default 0.3 mm) so a steel bolt fits after printing in PLA.
  Also exports a half-section STL for inspecting the thread profile.
- `demo_03/` — involute spur gear (`gear.py`, module and tooth count as the
  driving parameters; defaults module 1, 20 teeth, 6 mm face width, 5 mm
  center bore). Uses py_gearworks, a local editable dependency from
  `~/Repos/py_gearworks`.
- `print_pipeline.py` — slice / verify / upload / print / status against the
  printer. Slicing runs Bambu Studio's CLI headlessly with the official X2D
  profiles (inheritance resolved locally — the CLI doesn't do it and silently
  drops the AMS filament-load start gcode, causing "air prints").
- `printer_status.py` — quick MQTT status check.

## Printer connection

Copy `.env.example` to `.env` and fill in the LAN access code from the
printer's touchscreen. The printer needs LAN-only mode + Developer Mode
enabled for third-party print starts, and a USB stick for file storage.

## Typical flow

```bash
uv run demo_01/washer.py 16              # generate STL
uv run print_pipeline.py slice demo_01/washer.stl
uv run print_pipeline.py verify demo_01/washer.gcode.3mf   # pre-flight checks + toolpath plot
uv run print_pipeline.py upload demo_01/washer.gcode.3mf
uv run print_pipeline.py print demo_01/washer.gcode.3mf --ams-slot 2
uv run print_pipeline.py status
```

`print` re-runs verification and refuses files that fail. `BED_TYPE` in
print_pipeline.py must match the plate on the bed (the X2D checks optically).
