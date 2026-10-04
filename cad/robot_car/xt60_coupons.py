"""XT60 holder fit coupons: four copies of xt60_holder.py's holder, each on
a 2 mm slab that stands in for the motor lid's ceiling, differing only in
the channel's fit around the plug. Round 2:

    W  side fit 0.10, top fit 0.15     Y  side fit 0.10, top fit 0.30
    X  side fit 0.15, top fit 0.15     Z  side fit 0.15, top fit 0.30

Side fit is the gap on every face of the plug's outline, per side, around
the calipered 15.7 x 8.1 body (HolderDims.side_fit); top fit is the gap
from the plug's top to the lips (HolderDims.top_fit). Everything else is the
car's holder: the V-groove and lip, the grooves for the + / - marks, the
floor ledges and the crossbar clearance that keep the shroud free, the
latch arm, the channel floor, and the 1.2 mm gap over the ceiling with its
two plinths. Each prints upside down exactly as the lid will -- the
holder's top on the bed, the ceiling bridging the gap last -- so only the
lid's skirts and pad are missing. The letter stands on the slab.

Round 1 (S/T/U/V = side fit 0.00/0.05/0.10/0.15, green PLA Basic, X2D,
2026-10-03), before the floor ledges and the crossbar clearance: only V
took the plug, tight, and it bent the shroud's walls inward at the front
end -- pinched in the middle between the floor's sagging bridge and the
crossbar. The latch dropped behind the plug as it should.

Round 2 (W/X/Y/Z above, green PLA Basic, X2D, 2026-10-04), with the floor
ledges and the crossbar clearance: Z fits best, and side fit 0.15 / top fit
0.30 are the car's HolderDims.

Fitting: hold the male XT60 with its mating face toward the end where the
latch arm is rooted, and push it in rim first from the other end, the one
where the arm's tail is. The arm lifts and drops behind the plug's back
face with a click. Judge, per coupon:
- can you push it in by hand, and does the latch click down fully;
- seated, does it wiggle side to side or up and down;
- how hard is it to pull out forward by its rim -- unplugging the pack
  pulls that way, and only this friction resists it;
- lift the arm's tail with a fingernail and slide it back out;
- look along the slit under the holder: it should be open, not fused.

Run with:  uv run robot_car/xt60_coupons.py
Exports xt60_coupons.stl (print orientation), runs the PASS/FAIL checks and
renders xt60_coupons.png: the plate on the bed, and the car's holder in use
with the plug seated.
"""

import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build123d import Axis, Part, Plane, Pos, Text, export_stl, extrude  # noqa: E402

from chassis import ChassisDims, ivol, lid_dims  # noqa: E402
from xt60_holder import (  # noqa: E402
    HolderDims, make_holder, male_seated, rbox, shrink_seated,
)

FITS = (("W", 0.10, 0.15), ("X", 0.15, 0.15), ("Y", 0.10, 0.30), ("Z", 0.15, 0.30))
GAP = 5.0  # between coupons on the plate
FONT, FONT_SIZE, TEXT_HEIGHT = "Arial Black", 7.0, 0.6  # ~1.4 mm strokes


def coupon(h: HolderDims, cd: ChassisDims) -> Part:
    """The holder on its stand-in ceiling, in the holder frame."""
    ld = lid_dims(cd)
    frame, arm = make_holder(h, cd)
    ceiling = rbox(-2 * ld.lid_half_w, 0, -h.width / 2, h.width / 2, -ld.ceiling_t, 0.01)
    return frame + arm + ceiling


def for_print(part: Part, letter: str) -> Part:
    """Upside down, the holder's top on the bed, the letter on the slab."""
    flipped = part.rotate(Axis.Y, 180)
    bb = flipped.bounding_box()
    flipped = Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * flipped
    top = flipped.bounding_box().max.Z
    text = Text(letter, font_size=FONT_SIZE, font=FONT)
    return flipped + extrude(Plane.XY.offset(top - 0.01) * text, amount=TEXT_HEIGHT + 0.01)


def checks(h: HolderDims, cd: ChassisDims, part: Part, letter: str) -> bool:
    frame, _ = make_holder(h, cd)
    male = male_seated(h) + shrink_seated(h)
    v_seat = ivol(male, part)
    worst = max(ivol(Pos(dx, 0, 0) * male, frame) for dx in range(-30, 1, 2))
    ok = v_seat < 1e-3 and worst < 1e-3
    print(f"  [{'PASS' if ok else 'FAIL'}] {letter}: side fit {h.side_fit:.2f}, top fit "
          f"{h.top_fit:.2f} -- plug seated "
          f"{v_seat:.3f} mm^3, sliding in {worst:.3f} mm^3 against the frame")
    return ok


def render(cd: ChassisDims, plate: Part) -> None:
    import numpy as np
    from build123d import Box

    from xt60_twin import framed, mesh_of, render_stills, stage
    h = HolderDims()
    bb = plate.bounding_box()
    bed = Pos(0, 0, -0.5) * Box(90, 80, 1)
    # in use, beside the plate: the car's fit with the plug, the tail end toward the camera
    use = Pos(90, 0, 2.0) * (coupon(h, cd) + male_seated(h) + shrink_seated(h)).rotate(Axis.Z, 180)
    seated = [("coupon", mesh_of(Pos(90, 0, 2.0) * coupon(h, cd).rotate(Axis.Z, 180), 0.02), "holder"),
              ("male", mesh_of(Pos(90, 0, 2.0) * male_seated(h).rotate(Axis.Z, 180), 0.02), "xt60"),
              ("shrink", mesh_of(Pos(90, 0, 2.0) * shrink_seated(h).rotate(Axis.Z, 180), 0.02), "shrink")]
    statics = [("plate", mesh_of(plate, 0.02), "holder"), ("bed", mesh_of(bed), "floor")] + seated
    t1 = np.array([0, 0, bb.size.Z / 2])
    c = use.bounding_box().center()
    t2 = np.array([c.X, c.Y, c.Z])
    cams = [framed("on_bed", t1, (0.9, -1.2, 1.3), 40.0),
            framed("in_use", t2, (1.1, 0.6, 0.9), 19.0)]
    render_stills("xt60_coupons", stage(statics, [], cams), [c[0] for c in cams])


def main() -> None:
    cd = ChassisDims()
    plate, ok = Part(), True
    print("PASS/FAIL checks:")
    for i, (letter, side, top) in enumerate(FITS):
        h = replace(HolderDims(), side_fit=side, top_fit=top)
        part = coupon(h, cd)
        ok &= checks(h, cd, part, letter)
        col, row = i % 2, i // 2
        pitch = 2 * lid_dims(cd).lid_half_w + GAP
        plate += Pos((col - 0.5) * pitch, (0.5 - row) * pitch, 0) * for_print(part, letter)
    bb = plate.bounding_box()
    print(f"Solids: {len(plate.solids())} (expect {len(FITS)}); "
          f"{bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, {plate.volume / 1000:.1f} cm^3")
    export_stl(plate, HERE / "xt60_coupons.stl")
    print("Exported xt60_coupons.stl")
    render(cd, plate)
    print("ALL PASS" if ok and len(plate.solids()) == len(FITS) else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
