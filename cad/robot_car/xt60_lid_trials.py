"""XT60 holder lid trials: the real right-motor lid with the holder, printed
twice at two pad preloads, to try on the car.

    K  pad preload 0.30 (lid E's)       L  pad preload 0.20

RESULT (green PLA Basic, X2D, 2026-10-04): K fits better, so the holder
lid keeps lid E's 0.30 mm preload -- the car's lid_dims, unchanged.

The holder's frame stands on the lid over its two skirts and clears the
rest of the ceiling (xt60_holder.py), so the ceiling still bows over the
motor -- but its skirts can no longer splay outward, so the lid is stiffer
than lid E and its 0.30 mm preload may clamp too hard to slide on. Each
lid's letter is engraved in its pad face, as lid E's was. The channel fit
is the car's (xt60_coupons.py round 2, coupon Z).

Trying them: take the plain lid off the right motor, slide the trial lid
on from inboard until it clicks into its detent, then check:
- does it slide on by hand, and click into the detent;
- does it hold the motor -- no wobble when you rock the motor or the wheel;
- does it come back off by sliding it inboard;
- with the XT60 in the holder, plug and unplug the pack once.

Run with:  uv run robot_car/xt60_lid_trials.py
Exports xt60_lid_trials.stl (print orientation), runs the PASS/FAIL checks
and renders xt60_lid_trials.png.
"""

import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build123d import Part, Pos, export_stl  # noqa: E402

from chassis import ChassisDims, ivol, lid_dims  # noqa: E402
from lid_coupons import lid_for_print, make_cradle, motor_placement, tips  # noqa: E402
from xt60_holder import HolderDims, make_holder_lid  # noqa: E402

TRIALS = (("K", 0.30), ("L", 0.20))
GAP = 6.0  # between the lids on the plate


def checks(h: HolderDims, cd: ChassisDims, ld, lid: Part) -> bool:
    ok = True

    def report(name, passed, detail=""):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {ld.label}: {name}  {detail}")

    cradle, motor = make_cradle(ld), motor_placement(ld)
    body = lid - tips(ld)
    worst = max(ivol(Pos(0, dy, 0) * (body if dy else lid), cradle) for dy in (0.0, -3.0, -12.0, -22.0))
    report("clear of the cradle, seated and sliding on", worst < 1e-6, f"{worst:.3f} mm^3 at worst")
    v = ivol(lid, motor)
    report("pad presses into the motor", v > 0, f"{v:.2f} mm^3 overlap")
    bow = ld.pad_preload - ld.rail_clearance * (2 ** 0.5 - 1)
    report("ceiling bows clear of the frame", bow + 0.5 < h.gap,
           f"bow {bow:.2f} + bridge sag 0.5 < gap {h.gap:.1f} mm")
    return ok


def main() -> None:
    cd, h = ChassisDims(), HolderDims()
    plate, ok, x = Part(), True, 0.0
    print("PASS/FAIL checks:")
    for letter, preload in TRIALS:
        ld = replace(lid_dims(cd), pad_preload=preload, label=letter)
        lid = make_holder_lid(h, cd, ld)
        ok &= checks(h, cd, ld, lid)
        printed = lid_for_print(lid, ld)
        bb = printed.bounding_box()
        plate += Pos(x - bb.min.X, -bb.center().Y, 0) * printed
        x += bb.size.X + GAP
    bb = plate.bounding_box()
    plate = Pos(-bb.center().X, 0, 0) * plate
    print(f"Solids: {len(plate.solids())} (expect {len(TRIALS)}); "
          f"{bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, {plate.volume / 1000:.1f} cm^3")
    export_stl(plate, HERE / "xt60_lid_trials.stl")
    print("Exported xt60_lid_trials.stl")
    render(plate)
    print("ALL PASS" if ok and len(plate.solids()) == len(TRIALS) else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


def render(plate: Part) -> None:
    import numpy as np
    from build123d import Box

    from xt60_twin import framed, mesh_of, render_stills, stage
    bb = plate.bounding_box()
    bed = Pos(0, 0, -0.5) * Box(90, 60, 1)
    statics = [("plate", mesh_of(plate, 0.02), "holder"), ("bed", mesh_of(bed), "floor")]
    t = np.array([0, 0, bb.size.Z / 2])
    cams = [framed("pads_up", t, (0.9, -1.2, 1.4), 32.0), framed("other_side", t, (-1.0, 1.1, 0.8), 32.0)]
    render_stills("xt60_lid_trials", stage(statics, [], cams), [c[0] for c in cams])


if __name__ == "__main__":
    main()
