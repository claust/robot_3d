"""The cutter's rotor: the printed axle and disc, with two double-edge razor
blades (parts/de_blade.py) clicked onto the disc's top face.

- Blades: opposite each other with their long axes radial, centre holes at
  r 37. Either long edge can face the direction of travel, so a blade can be
  turned over when one edge is dull. The edges run parallel to the radius,
  11 mm off it, so the leading edge is swept back and slices whichever way the
  disc turns.
- Seat: a round peg in the blade's centre hole and a diamond peg in its inner
  diamond, joined by a low ridge in the slot between them. Each peg has a lip
  one printed layer above the disc, wider across the blade than the hole. The
  slot lets the blade's two halves spread, so pressing the blade on opens it
  over the lips and it closes behind them. 0.20 past the hole's edge holds it
  securely and flat; 0.30 leaves it under tension and not flat.
- Disc: Ø80 x 3. It prints flat on the bed, axle up, like spindle_coupons.py's
  rotor.
- Height: three cross holes for the filament pin, 6 mm apart. The pin rests
  on the washer on the upper bearing, so a higher hole lowers the disc: by 0,
  6 or 12 mm. The axle top comes down with it, and the hub's sleeve and slots
  on canon_mount.py still fit over the pin as they are.
- Axle: Ø10.00 (press_clearance) from the disc up to where the lower bearing
  sits with the disc lowered 12, then Ø9.97 (axle_clearance) above it, so
  the press fit holds at all three heights.

Assembly: slide the axle up through both bearings, pushing hard for the last
part, until the wanted hole is just above the upper bearing's washer. Push a
20 mm filament pin through it, then press the blades on, wearing gloves.

Frame: the spindle's, Z=0 at the lower bearing's bottom face with the disc at
its highest. +Z is up.

Run with:  uv run robot_car/blade_disc.py [--no-render]
Exports blade_disc.stl (print orientation) and renders blade_disc.png, runs
the PASS/FAIL checks.
"""

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import (  # noqa: E402
    Box, Cone, Cylinder, Part, Plane, Polygon, Pos, Rot, export_stl, extrude,
)

from canon_mount import MountDims, make_hub, make_long_pin  # noqa: E402
from de_blade import BladeDims, make_blade  # noqa: E402
from spindle_coupons import (  # noqa: E402
    ALIGN_BOTTOM, SpindleDims, bearings, ivol, make_rotor, make_tower, make_washer, teardrop,
)

BLADE = BladeDims()
SPINDLE = SpindleDims(disc_t=3.0)
MOUNT = MountDims()
HOLE_R = 37.0  # disc axis to the blade's centre hole
DROPS = (0.0, 6.0, 12.0)  # how far each cross hole lowers the disc
PRESS_TOP = SPINDLE.bearing.width + max(DROPS)
LIP_OVERLAP = 0.20  # lip past the hole's edge
GAP = 0.2  # one layer, for the 0.10 blade
LIP_H = 0.4
TAPER_H = 0.8  # the lead-in above each lip
PEG_CLEAR = 0.1  # peg to the hole's edge, across the blade
RIDGE_W = 1.8  # in the 2.06-2.21 slot
RIDGE_RISE = GAP + LIP_H


def cyl(r: float, h: float, z: float) -> Part:
    return Pos(0, 0, z) * Cylinder(r, h, align=ALIGN_BOTTOM)


def rhombus(half_x: float, half_y: float, h: float, x: float, z: float) -> Part:
    plan = Polygon((half_x, 0), (0, half_y), (-half_x, 0), (0, -half_y), align=None)
    return Pos(x, 0, z) * extrude(Plane.XY * plan, amount=h)


def round_peg(z: float) -> Part:
    r = BLADE.centre_hole_d / 2
    rl = r + LIP_OVERLAP
    peg = cyl(r - PEG_CLEAR, GAP, z) + cyl(rl, LIP_H, z + GAP)
    return peg + Pos(0, 0, z + GAP + LIP_H) * Cone(rl, rl - TAPER_H, TAPER_H, align=ALIGN_BOTTOM)


def diamond_peg(z: float) -> Part:
    """Stays clear of the diamond's sloped sides; only the lip's tips, across
    the blade, reach past it."""
    x = -BLADE.hole_pitch
    tip = BLADE.diamond_tips / 2
    hy = tip - PEG_CLEAR
    hx = BLADE.diamond_x / 2 * hy / tip
    peg = rhombus(hx, hy, GAP, x, z)
    peg += rhombus(hx, tip + LIP_OVERLAP, LIP_H, x, z + GAP)
    plan = Polygon((hx, 0), (0, tip + LIP_OVERLAP), (-hx, 0), (0, -(tip + LIP_OVERLAP)), align=None)
    return peg + Pos(x, 0, z + GAP + LIP_H) * extrude(Plane.XY * plan, amount=TAPER_H, taper=45)


def blade_seat(z: float) -> Part:
    """One blade's pegs and ridge, its centre hole on +X at HOLE_R."""
    seat = round_peg(z) + diamond_peg(z)
    seat += Pos(-BLADE.hole_pitch / 2, 0, z) * Box(BLADE.hole_pitch, RIDGE_W, RIDGE_RISE, align=ALIGN_BOTTOM)
    return Pos(HOLE_R, 0, 0) * seat


def make_blade_rotor(s: SpindleDims = SPINDLE) -> Part:
    rotor = make_rotor(s)
    rotor += Cylinder(s.bearing.bore / 2 - s.press_clearance, PRESS_TOP, align=ALIGN_BOTTOM)
    for d in DROPS[1:]:
        rotor -= Pos(0, 0, s.pin_z + d) * teardrop(s.pin_hole_d, s.axle_d + 2)
    seat = blade_seat(s.disc_top)
    return rotor + seat + Rot(0, 0, 180) * seat


def blades(s: SpindleDims = SPINDLE) -> list[Part]:
    one = Pos(HOLE_R, 0, s.disc_top) * make_blade(BLADE)
    return [one, Rot(0, 0, 180) * one]


def check(good: bool, text: str) -> bool:
    print(f"  [{'PASS' if good else 'FAIL'}] {text}")
    return good


def checks(rotor: Part) -> bool:
    s, ok, eps = SPINDLE, True, 1e-3
    tower, washer = make_tower(s), make_washer(s)
    (lo_out, lo_in), (hi_out, hi_in) = bearings(s)
    hub, pin = make_hub(MOUNT), make_long_pin(MOUNT)
    two = blades(s)
    ok &= check(len(rotor.solids()) == 1, "rotor is one solid")
    for d in DROPS:
        low = Pos(0, 0, -d) * rotor
        v = sum(ivol(low, p) for p in (tower, lo_out, hi_out, washer, pin))
        ok &= check(v < eps, f"disc down {d:g}: rotor clears the tower, outer rings, washer and pin, {v:.3f} mm^3")
        v = ivol(low, hub)
        ok &= check(v < eps, f"disc down {d:g}: axle sits in the hub's sleeve, {v:.3f} mm^3")
        hole_lo = s.pin_z - s.pin_hole_d / 2
        bore_ok = ivol(low, Pos(0, 0, s.pin_z - 0.5) * Rot(0, 90, 0) * Cylinder(0.5, s.axle_d - 1)) < eps
        ok &= check(bore_ok, f"disc down {d:g}: a hole lines up {hole_lo - s.span - s.washer_t:.1f} mm above the washer")
        ok &= check(d + s.bearing.width <= PRESS_TOP, f"disc down {d:g}: Ø10.00 fills the lower bearing")
        tube_gap = s.boss_h + d
        ok &= check(tube_gap >= 6, f"disc down {d:g}: disc top {tube_gap:g} mm under the plate")
    top_wall = s.axle_top - (s.pin_z + max(DROPS) + s.pin_hole_d / 2)
    ok &= check(top_wall >= 2.5, f"{top_wall:.1f} mm of axle above the top hole")
    gap = DROPS[1] - s.pin_hole_d
    ok &= check(gap >= 3, f"{gap:.1f} mm of axle between holes")
    v = sum(ivol(rotor, b) for b in two)
    ok &= check(v < eps, f"blades lie flat, under the lips, {v:.4f} mm^3")
    ok &= check(GAP >= BLADE.thickness + 0.05, f"{GAP} mm under the lips for the {BLADE.thickness} blade")
    inner = HOLE_R - BLADE.length / 2
    ok &= check(inner > SPINDLE.hub_d / 2 + 1, f"blades' inner ends at r {inner:.1f} clear the boss (r {s.hub_d / 2:g})")
    lip_r = HOLE_R + BLADE.centre_hole_d / 2 + LIP_OVERLAP
    ok &= check(lip_r < s.disc_d / 2, f"the round lip (r {lip_r:.1f}) stays on the Ø{s.disc_d:g} disc")
    tip = HOLE_R + BLADE.length / 2
    edge = math.hypot(HOLE_R + BLADE.shoulder_x, BLADE.width / 2)
    ok &= check(tip < 66, f"blunt end tabs reach r {tip:.2f}, under the plate")
    print(f"  sharp edges end at r {edge:.1f}, cut Ø{2 * edge:.0f}; each edge runs "
          f"{math.degrees(math.asin(BLADE.width / 2 / edge)):.0f} to "
          f"{math.degrees(math.asin(BLADE.width / 2 / (s.disc_d / 2))):.0f} deg off radial, swept back")
    return ok


def render(rotor: Part) -> None:
    import numpy as np

    from xt60_twin import framed, mesh_of, render_stills, stage
    statics = [("rotor", mesh_of(rotor, 0.02), "holder")]
    statics += [(f"blade{i}", mesh_of(b, 0.02), "motor") for i, b in enumerate(blades())]
    cams = [framed("whole", np.array([0, 0, 15.0]), (0.6, -0.9, 0.7), 68.0),
            framed("top", np.array([0, 0, 40.0]), (0.35, -0.3, 0.1), 26.0)]
    render_stills("blade_disc", stage(statics, [], cams), [c[0] for c in cams])


def main() -> None:
    s = SPINDLE
    rotor = make_blade_rotor()
    ok = checks(rotor)
    print(f"Rotor volume {rotor.volume / 1000:.1f} cm^3")
    export_stl(Pos(0, 0, s.boss_h + s.disc_t) * rotor, HERE / "blade_disc.stl")
    print("Exported blade_disc.stl")
    if "--no-render" not in sys.argv:
        render(rotor)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
