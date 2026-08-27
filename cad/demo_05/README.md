# demo_05 — supports from the auxiliary nozzle

Prints a part that needs support, with the support material coming from the
X2D's auxiliary nozzle (external spool, white PLA) while the body prints
from the AMS (dark blue PLA). No filament ever changes mid-print: each
nozzle keeps its material, so support costs no purge waste.

## Parts

- `overhang_demo.py [arm_length_mm]` — the demo bracket. Two identical arms
  on one post: one backed by a 45° gusset (prints support-free), one a pure
  90° cantilever with a drop lip (impossible without support). The printed
  part contrasts a designed-away overhang with a supported one.
- `nozzle_test.py` — the same bracket shrunk to a ~20-minute coupon. Run
  this first on any new dual-nozzle configuration to prove the
  filament→extruder mapping end to end before committing to a long print.

## Workflow

```
uv run nozzle_test.py                     # or overhang_demo.py
uv run ../demo_01/render.py nozzle_test.stl   # visual check before slicing
cd .. && uv run print_pipeline.py slice demo_05/nozzle_test.stl --supports
uv run print_pipeline.py verify demo_05/nozzle_test.gcode.3mf
uv run print_pipeline.py upload demo_05/nozzle_test.gcode.3mf
uv run print_pipeline.py print demo_05/nozzle_test.gcode.3mf --trays 2,ext
```

`--trays 2,ext` maps sliced filament 1 → AMS slot 2 (blue) and filament 2 →
the external spool on the aux nozzle. The `verify` step checks, among other
things, that every aux-nozzle move stays inside its reachable area and that
per-tool extrusion matches the slicer's own estimate.

## How support-on-second-nozzle works

Support placement is computed by the slicer, not the model: any face flatter
than `support_threshold_angle` (Bambu default 30° from horizontal) gets
support grown under it, minus short bridges (≤ ~10 mm print unsupported).
Three settings route that support to the other nozzle:

- `support_filament = 2` and `support_interface_filament = 2` in the process
  profile — filament indices are 1-based; 0 means "same as model".
- `--filament-map 1,2 --filament-map-mode Manual` on the Bambu Studio CLI —
  filament 1 → left (AMS, direct-drive) extruder, filament 2 → aux (Bowden)
  extruder.

To control *where* supports go from code, the options are (in increasing
effort): tune `support_threshold_angle`; switch `support_type` to
`normal(manual)` and ship a support-enforcer mesh (`subtype =
"support_enforcer"` in the 3mf's model_settings.config); or design the
overhang away entirely with 45° chamfers/gussets like the demo's left arm.

## Hard-won lessons (each cost a failed slice or print)

1. **Never disable the prime tower on a dual-nozzle print.** Our first
   coupon air-printed: with ~60 tool changes and no tower, the parked
   nozzle oozes out its melt and restarts dry every layer, so *both*
   filaments starve — gcode, temps and E-values were all correct. Shrink it
   instead: `--set prime_tower_width=15`.
2. **`filament_map` must be CLI arguments, not profile keys.** Injected into
   the process JSON it segfaults the CLI (BambuStudio issue #9119, still
   present in 02.08.02.61).
3. **Move the prime tower into the shared reachable area.** The aux extruder
   only reaches X ≥ 20.5 mm; the default tower position is outside that,
   and slicing fails with "gcode unprintable, error_code = 1". The pipeline
   parks it at (180, 180).
4. **`--export-3mf` needs an absolute path**, or export dies with "Unable to
   open the file ....tmp".
5. **External spool = virtual tray 255.** The printer's `vir_slot` status
   lists two virtual trays (254 and 255); 255 is the aux nozzle's spool.
   On MQTT print start, an external filament is `-1` in `ams_mapping` and
   `{"ams_id": 255, "slot_id": 0}` in `ams_mapping2`.
6. **White-on-blue is a visibility demo, not a release agent.** PLA fuses to
   PLA, so the standard 0.2 mm breakaway gap stays. For glass-smooth
   undersides, put a non-bonding material (PETG under PLA) on the aux spool
   and set the support z-gap to 0.
