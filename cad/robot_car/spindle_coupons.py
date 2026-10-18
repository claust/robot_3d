"""Mower spindle test kit: fit coupons for the 6000 bearings
(parts/bearing_6000.py, 10 x 26 x 8) and a spindle you can spin by hand.

One plate, eight parts:

- Four fit fobs, A-D. Each is a seat ring for a bearing and, on the same
  fob, a short axle pin. The step is radial clearance in mm, applied to both
  (positive = looser):

      A  0.00   ring bore Ø26.00   pin Ø10.00
      B  0.05   ring bore Ø26.10   pin Ø9.90
      C  0.10   ring bore Ø26.20   pin Ø9.80
      D  0.15   ring bore Ø26.30   pin Ø9.70

- The tower: a tube with a bearing seat at each end, on a square flange
  that stands in for the car's plate. The lower bearing presses in from the
  flange side until it is flush with the flange's underside. The upper one
  presses in from the top onto a ledge and ends flush with the tube's top.
  Both seats come off the printer in one part, so they line up.
- The rotor: an Ø80 disc, a hub boss and the axle, printed in one piece
  standing on the disc. The boss's top land is small enough to touch only
  the lower bearing's inner ring.
- Two washers. One sits on the upper bearing's inner ring, and a piece of
  1.75 mm filament through the cross hole above it carries the rotor.

The tower's seats and the rotor's axle are drawn at SpindleDims'
clearances. The number on the tower's flange and on the disc is that
clearance in hundredths of a mm.

RESULT, round 1 (dark blue PLA Basic, X2D, 2026-10-12): ring B is a nice
tight fit, so seat_clearance stays 0.05 and the round-1 tower is the
car's. Pin A is too tight and B-D are too loose, so the axle's fit lies
between 0.00 and 0.05.

Round 2: three pin coupons that split the A-B gap, printed alone (the
`pins` plate) or beside a new rotor at axle_clearance (the `rotor` plate):

      E  0.015   pin Ø9.97
      F  0.025   pin Ø9.95
      G  0.035   pin Ø9.93

RESULT, round 2 (dark blue, 2026-10-12): E still a bit loose, and A, a
tight push, is the better grip. The axle now has two sizes. Inside the
lower bearing, next to the disc where any play shows most at the rim, it
is A's Ø10.00 (press_clearance) and presses in. Above that it is E's Ø9.97
(axle_clearance), so it slides through the lower bearing on the way in and
into the upper one. A little play at the top, 32 mm away, tilts the disc by
next to nothing.

Assembly: press both bearings into the tower. Slide the rotor's axle up
through the lower bearing and on through the upper one, drop a washer over
the axle, push filament through the cross hole and trim it to ~3 mm each
side. The pin leaves 0.3 mm of end play.

What to judge on the fobs:
- Ring: press a bearing in with your thumb, or in a vise if it won't
  start. The right fit needs deliberate force, sits flush, and doesn't rock
  when you push on the bearing's edge. Push it out again from the other
  side with a socket that bears on the outer ring.
- Pin: slide a bearing onto it. A tight push is the press fit for the
  lower bearing; sliding on without force and without rattle is the fit
  for the rest of the axle, which has to pass through the lower bearing to
  reach the upper one.

Spin test: hold the tower (or screw the flange to a board that overhangs a
table edge) and flick the disc. It should run on, without scraping, and
without a visible wobble at the rim. The axle stub above the pin is for the
motor coupler later. A drill can grip it for a speed test, held lightly so
it doesn't bend the axle.

Frame for the assembled spindle: axis along Z, Z=0 at the underside of
the tower's flange, which is also the lower bearing's bottom face. The disc
hangs below Z=0.

Run with:  uv run robot_car/spindle_coupons.py [kit | pins | rotor]
Runs the PASS/FAIL checks on the assembled spindle, then exports one plate
in print orientation: `kit` (default) is round 1, spindle_coupons.stl,
rendered with the spindle cut in half as spindle_coupons.png; `pins` is
round 2's pins alone, spindle_pins.stl; `rotor` is the rotor with them,
spindle_rotor.stl.
"""

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import (  # noqa: E402
    Align, Axis, Box, Circle, Cone, Cylinder, Part, Plane, Polygon, Pos, Rot, Text,
    export_stl, extrude, fillet,
)

from bearing_6000 import BearingDims, make_inner, make_outer  # noqa: E402
from chassis import ChassisDims, ivol  # noqa: E402

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
FITS = (("A", 0.00), ("B", 0.05), ("C", 0.10), ("D", 0.15))
FINE_PINS = (("E", 0.015), ("F", 0.025), ("G", 0.035))
FONT, TEXT_HEIGHT = "Arial Black", 0.6
MIN_STROKE = 0.8  # two 0.4 mm extrusions; thinner text prints illegibly


@dataclass
class SpindleDims:
    """All dimensions in mm."""

    bearing: BearingDims = field(default_factory=BearingDims)
    seat_clearance: float = 0.05  # radial, bearing OD in its seat (ring B)
    axle_clearance: float = 0.015  # radial, axle above the lower bearing (pin E)
    press_clearance: float = 0.0  # radial, axle inside the lower bearing (pin A)
    wall: float = 3.0  # tube wall around a seat
    span: float = 40.0  # lower bearing's bottom face to upper bearing's top face
    bore_d: float = 23.0  # tube bore between the seats; the upper bearing's ledge
    mouth_chamfer: float = 0.5
    flange: float = 48.0  # square
    flange_t: float = 3.0
    flange_r: float = 4.0
    hole_d: float = 3.4  # M3 clearance
    hole_pitch: float = 38.0
    disc_d: float = 80.0
    disc_t: float = 2.0
    hub_d: float = 24.0  # boss foot on the disc
    land_d: float = 13.0  # boss top and washer OD: inner ring only
    boss_h: float = 6.0  # disc top to the lower bearing; clears the car's plate
    washer_t: float = 2.0
    washer_play: float = 0.2  # radial, washer bore over the axle
    pin_hole_d: float = 2.0  # for 1.75 mm filament
    pin_d: float = 1.75
    axial_play: float = 0.3
    stub: float = 15.0  # axle above the cross hole
    tip_chamfer: float = 0.5
    fob_bar: float = 10.0  # ring to pin pad, carries the letter
    fob_pad_d: float = 18.0
    fob_t: float = 2.0
    fob_pin_h: float = 10.0  # above the pad; the bearing is 8 wide

    @property
    def seat_d(self) -> float:
        return self.bearing.od + 2 * self.seat_clearance

    @property
    def axle_d(self) -> float:
        return self.bearing.bore - 2 * self.axle_clearance

    @property
    def tower_od(self) -> float:
        return self.seat_d + 2 * self.wall

    @property
    def pin_z(self) -> float:
        """Centre of the cross hole."""
        return self.span + self.washer_t + self.axial_play + self.pin_hole_d / 2

    @property
    def axle_top(self) -> float:
        return self.pin_z + self.pin_hole_d / 2 + self.stub

    @property
    def disc_top(self) -> float:
        return -self.boss_h


def label(text: str, size: float):
    """Text face, refusing strokes too thin to print (2 x area / perimeter)."""
    face = Text(text, font_size=size, font=FONT)
    area = sum(f.area for f in face.faces())
    perimeter = sum(e.length for e in face.edges())
    if 2 * area / perimeter < MIN_STROKE:
        raise ValueError(f"label {text!r} strokes under {MIN_STROKE} mm -- raise the size")
    return face


def raised(text: str, size: float, x: float, y: float, z: float) -> Part:
    return extrude(Plane.XY.offset(z - 0.01) * Pos(x, y) * label(text, size),
                   amount=TEXT_HEIGHT + 0.01)


def hundredths(c: float) -> str:
    """0.05 -> "05", 0.025 -> "2.5"."""
    v = round(c * 100, 3)
    return f"{v:02.0f}" if v == int(v) else f"{v:g}"


def tube(r_out: float, r_in: float, h: float, z0: float = 0.0) -> Part:
    return Pos(0, 0, z0) * (Cylinder(r_out, h, align=ALIGN_BOTTOM)
                            - Cylinder(r_in, h, align=ALIGN_BOTTOM))


def mouth(r: float, c: float, z: float, up: bool) -> Part:
    """45 deg chamfer cutter opening a bore of radius r at height z, the wide
    end at z, narrowing into the part (up=True: the part is above z)."""
    e = 0.01
    if up:
        return Pos(0, 0, z - e) * Cone(r + c + e, r, c + e, align=ALIGN_BOTTOM)
    return Pos(0, 0, z - c) * Cone(r, r + c + e, c + e, align=ALIGN_BOTTOM)


def tip_cutter(r: float, c: float, z: float) -> Part:
    """45 deg chamfer cutter for the top edge of a pin of radius r ending at z."""
    block = Pos(0, 0, z - c) * Cylinder(r + 1, c + 0.01, align=ALIGN_BOTTOM)
    return block - Pos(0, 0, z - c) * Cone(r, r - c, c, align=ALIGN_BOTTOM)


def teardrop(d: float, length: float) -> Part:
    """Horizontal hole along X with a 45 deg peak on top, printable unsupported."""
    r = d / 2
    s = r * math.sqrt(0.5)
    profile = Circle(r) + Polygon((-s, s), (s, s), (0, r * math.sqrt(2)))
    return extrude(Plane.YZ.offset(-length / 2) * profile, amount=length)


def make_tower(s: SpindleDims) -> Part:
    b = s.bearing
    r_seat = s.seat_d / 2
    flange = Box(s.flange, s.flange, s.flange_t, align=ALIGN_BOTTOM)
    tower = fillet(flange.edges().filter_by(Axis.Z), s.flange_r)
    for sx in (-1, 1):
        for sy in (-1, 1):
            tower -= Pos(sx * s.hole_pitch / 2, sy * s.hole_pitch / 2, 0) * Cylinder(
                s.hole_d / 2, s.flange_t, align=ALIGN_BOTTOM)
    tower += Cylinder(s.tower_od / 2, s.span, align=ALIGN_BOTTOM)
    tower += raised(hundredths(s.seat_clearance), 7.0, 0,
                    (s.tower_od / 2 + s.flange / 2) / 2, s.flange_t)
    return tower - tower_bore(s)


def tower_bore(s: SpindleDims) -> Part:
    """Everything cut out of the tower: both bearing seats and the bore
    between them, Z=0 at the lower seat's mouth."""
    b = s.bearing
    r_seat = s.seat_d / 2
    bore = Cylinder(s.bore_d / 2, s.span, align=ALIGN_BOTTOM)
    bore += Cylinder(r_seat, b.width, align=ALIGN_BOTTOM)
    # The lower seat's ceiling is a 45 deg cone, not a flat ledge: a flat
    # ceiling would print as rings hanging in the air. The bearing is
    # pressed flush with the seat's mouth and doesn't reach the cone.
    bore += Pos(0, 0, b.width) * Cone(r_seat, s.bore_d / 2, r_seat - s.bore_d / 2,
                                      align=ALIGN_BOTTOM)
    bore += Pos(0, 0, s.span - b.width) * Cylinder(r_seat, b.width, align=ALIGN_BOTTOM)
    bore += mouth(r_seat, s.mouth_chamfer, 0, up=True)
    bore += mouth(r_seat, s.mouth_chamfer, s.span, up=False)
    return bore


def make_rotor(s: SpindleDims) -> Part:
    disc_bottom = s.disc_top - s.disc_t
    rotor = Pos(0, 0, disc_bottom) * Cylinder(s.disc_d / 2, s.disc_t, align=ALIGN_BOTTOM)
    rotor += Pos(0, 0, s.disc_top) * Cone(s.hub_d / 2, s.land_d / 2, s.boss_h,
                                          align=ALIGN_BOTTOM)
    r = s.axle_d / 2
    rotor += Pos(0, 0, s.disc_top) * Cylinder(r, s.axle_top - s.disc_top, align=ALIGN_BOTTOM)
    rotor -= tip_cutter(r, s.tip_chamfer, s.axle_top)
    rotor += Cylinder(s.bearing.bore / 2 - s.press_clearance, s.bearing.width,
                      align=ALIGN_BOTTOM)
    rotor -= Pos(0, 0, s.pin_z) * teardrop(s.pin_hole_d, s.axle_d + 2)
    rotor += raised(hundredths(s.axle_clearance), 8.0, 0, -s.disc_d / 2 + 10, s.disc_top)
    return rotor


def make_washer(s: SpindleDims) -> Part:
    return tube(s.land_d / 2, s.axle_d / 2 + s.washer_play, s.washer_t, s.span)


def make_pin(s: SpindleDims) -> Part:
    """The filament pin, resting in the bottom of the cross hole."""
    z = s.pin_z - (s.pin_hole_d - s.pin_d) / 2
    return Pos(0, 0, z) * Rot(0, 90, 0) * Cylinder(s.pin_d / 2, s.axle_d + 6)


def bearings(s: SpindleDims) -> list[tuple[Part, Part]]:
    """(outer, inner) for the lower and the upper bearing, in place."""
    b = s.bearing
    return [(Pos(0, 0, z) * make_outer(b), Pos(0, 0, z) * make_inner(b))
            for z in (0.0, s.span - b.width)]


def make_fob(s: SpindleDims, letter: str, c: float) -> Part:
    """Seat ring at the origin, axle pin on a pad toward -Y, letter between."""
    b = s.bearing
    r_seat = b.od / 2 + c
    r_out = r_seat + s.wall
    pad_y = -(r_out + s.fob_bar + s.fob_pad_d / 2)
    fob = Cylinder(r_out, b.width, align=ALIGN_BOTTOM)
    y0 = -(r_out - 1)  # the bar runs from inside the ring's wall to the pad's centre
    fob += Pos(0, (y0 + pad_y) / 2, 0) * Box(14, y0 - pad_y, s.fob_t, align=ALIGN_BOTTOM)
    fob += Pos(0, pad_y, 0) * Cylinder(s.fob_pad_d / 2, s.fob_t, align=ALIGN_BOTTOM)
    r_pin = b.bore / 2 - c
    pin = Cylinder(r_pin, s.fob_pin_h, align=ALIGN_BOTTOM)
    pin -= tip_cutter(r_pin, s.tip_chamfer, s.fob_pin_h)
    fob += Pos(0, pad_y, s.fob_t) * pin
    fob -= Cylinder(r_seat, b.width, align=ALIGN_BOTTOM)
    fob -= mouth(r_seat, s.mouth_chamfer, 0, up=True)
    fob -= mouth(r_seat, s.mouth_chamfer, b.width, up=False)
    fob += raised(letter, 8.0, 0, -(r_out + s.fob_bar / 2), s.fob_t)
    return fob


def make_pin_coupon(s: SpindleDims, letter: str, c: float) -> Part:
    """An axle pin on a pad, with its letter on a tab toward +Y."""
    r_pin = s.bearing.bore / 2 - c
    tab = s.fob_bar + s.fob_pad_d / 2
    coupon = Cylinder(s.fob_pad_d / 2, s.fob_t, align=ALIGN_BOTTOM)
    coupon += Pos(0, tab / 2, 0) * Box(14, tab, s.fob_t, align=ALIGN_BOTTOM)
    pin = Cylinder(r_pin, s.fob_pin_h, align=ALIGN_BOTTOM)
    pin -= tip_cutter(r_pin, s.tip_chamfer, s.fob_pin_h)
    coupon += Pos(0, 0, s.fob_t) * pin
    coupon += raised(letter, 8.0, 0, s.fob_pad_d / 2 + s.fob_bar / 2, s.fob_t)
    return coupon


def build_plate(s: SpindleDims) -> tuple[Part, list[Part]]:
    """Round 1: every part in print orientation, laid out on one plate."""
    parts = [
        Pos(-60, 40, s.boss_h + s.disc_t) * make_rotor(s),
        Pos(10, 48, 0) * make_tower(s),
        Pos(47, 62, -s.span) * make_washer(s),
        Pos(47, 42, -s.span) * make_washer(s),
    ]
    pitch = s.tower_od + 4
    for i, (letter, c) in enumerate(FITS):
        parts.append(Pos((i - 1.5) * pitch - 30, -22, 0) * make_fob(s, letter, c))
    return fuse(parts), parts


def build_round2_plate(s: SpindleDims, rotor: bool) -> tuple[Part, list[Part]]:
    """Round 2: the fine pin coupons, with the rotor beside them if asked."""
    parts = [Pos(0, 0, s.boss_h + s.disc_t) * make_rotor(s)] if rotor else []
    for i, (letter, c) in enumerate(FINE_PINS):
        parts.append(Pos(s.disc_d / 2 + 16 + i * 22, -10, 0) * make_pin_coupon(s, letter, c))
    return fuse(parts), parts


def fuse(parts: list[Part]) -> Part:
    plate = Part()
    for p in parts:
        plate += p
    return plate


def check(ok: bool, text: str) -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    return ok


def checks(s: SpindleDims, plate: Part, parts: list[Part]) -> bool:
    b = s.bearing
    tower, rotor, washer, pin = make_tower(s), make_rotor(s), make_washer(s), make_pin(s)
    (lo_out, lo_in), (hi_out, hi_in) = bearings(s)
    eps = 1e-3
    ok = True

    v = ivol(lo_out, tower) + ivol(hi_out, tower)
    ok &= check(v < eps, f"both bearings sit in the tower's Ø{s.seat_d:.2f} seats, "
                f"{v:.3f} mm^3 overlap")
    ledge = (b.od - s.bore_d) / 2
    ok &= check(ledge >= 1.0 and s.bore_d > b.inner_land_d + 2,
                f"the upper bearing's ledge is {ledge:.2f} mm wide and clears the "
                f"inner ring by {(s.bore_d - b.inner_land_d) / 2:.2f} mm")
    wall = (s.tower_od - s.seat_d) / 2
    ok &= check(wall >= 2.5, f"tube wall around the seats {wall:.2f} mm")

    turning = rotor + washer + pin
    v = sum(ivol(turning, p) for p in (tower, lo_out, hi_out))
    ok &= check(v < eps, f"rotor, washer and pin clear the tower and both outer rings, "
                f"{v:.3f} mm^3")
    v = ivol(rotor, lo_in) + ivol(rotor, hi_in) + ivol(washer, rotor)
    ok &= check(v < eps, f"the axle, Ø{b.bore - 2 * s.press_clearance:.2f} in the lower "
                f"bearing and Ø{s.axle_d:.2f} above, meets both inner rings and passes the "
                f"washer, {v:.3f} mm^3")
    margin = (b.inner_land_d - s.land_d) / 2
    ok &= check(margin >= 0.5 and s.land_d > b.bore + 2,
                f"boss land and washer (Ø{s.land_d:g}) touch only the inner rings, "
                f"{margin:.2f} mm inside their faces")
    gap = (s.pin_z - s.pin_hole_d / 2) - (s.span + s.washer_t)
    ok &= check(abs(gap - s.axial_play) < 1e-6 and gap > 0,
                f"cross hole {gap:.2f} mm above the washer (the rotor's end play)")
    plate_t = ChassisDims().plate_thickness
    ok &= check(s.boss_h >= plate_t + 2,
                f"disc {s.boss_h - plate_t:.1f} mm below the car's {plate_t:g} mm plate "
                f"when the flange sits on it")
    ok &= check(s.disc_d / 2 > s.flange / 2 * math.sqrt(2),
                f"Ø{s.disc_d:g} disc reaches past the flange's corners, so the "
                f"spin test shows wobble at the rim")

    n = len(plate.solids())
    bb = plate.bounding_box()
    ok &= check(n == len(parts), f"plate: {n} separate solids (expect {len(parts)})")
    ok &= check(bb.size.X <= 240 and bb.size.Y <= 240 and abs(bb.min.Z) < 1e-6,
                f"plate {bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.1f} mm, "
                "flat on the bed")
    return ok


def render(s: SpindleDims, plate: Part) -> None:
    import numpy as np

    from xt60_twin import framed, mesh_of, render_stills, stage

    bb = plate.bounding_box()
    bed = Pos(bb.center().X, bb.center().Y, -0.5) * Box(bb.size.X + 20, bb.size.Y + 20, 1)
    statics = [("plate", mesh_of(plate, 0.02), "holder"), ("bed", mesh_of(bed), "floor")]

    # The assembled spindle, cut along X = 0 (the +X half kept), off to the side.
    at = Pos(250, 0, 60)
    keep = Box(400, 400, 400, align=(Align.MIN, Align.CENTER, Align.CENTER))
    pieces = [(make_tower(s), "holder"), (make_rotor(s), "battery"),
              (make_washer(s), "xt60"), (make_pin(s), "red")]
    for outer, inner in bearings(s):
        pieces += [(outer, "motor"), (inner, "motor")]
    for i, (p, look) in enumerate(pieces):
        statics.append((f"cut{i}", mesh_of(at * (p & keep), 0.02), look))

    cams = [framed("on_bed", np.array([bb.center().X, bb.center().Y, 10]),
                   (0.6, -1.0, 1.1), 125.0),
            framed("section", np.array([270, 0, 70]), (-1.0, -0.35, 0.25), 52.0)]
    render_stills("spindle_coupons", stage(statics, [], cams), [c[0] for c in cams])


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("plate", nargs="?", choices=("kit", "pins", "rotor"), default="kit")
    which = ap.parse_args().plate

    s = SpindleDims()
    if which == "kit":
        plate, parts = build_plate(s)
        print("Fit fobs (radial clearance; ring bore / pin):")
        for letter, c in FITS:
            print(f"  {letter}  {c:.3f}   Ø{s.bearing.od + 2 * c:.2f} / "
                  f"Ø{s.bearing.bore - 2 * c:.2f}")
    else:
        plate, parts = build_round2_plate(s, rotor=which == "rotor")
        print("Pin coupons (radial clearance; pin):")
        for letter, c in FINE_PINS:
            print(f"  {letter}  {c:.3f}   Ø{s.bearing.bore - 2 * c:.2f}")
    print(f"Tower seats Ø{s.seat_d:.2f}, bearings {s.span - s.bearing.width:g} mm apart "
          f"(centre to centre); rotor axle Ø{s.bearing.bore - 2 * s.press_clearance:.2f} in the "
          f"lower bearing, Ø{s.axle_d:.2f} above; disc Ø{s.disc_d:g} x {s.disc_t:g}")
    print("PASS/FAIL checks:")
    ok = checks(s, plate, parts)
    print(f"Volume {plate.volume / 1000:.1f} cm^3")
    name = {"kit": "spindle_coupons", "pins": "spindle_pins", "rotor": "spindle_rotor"}[which]
    export_stl(plate, HERE / f"{name}.stl")
    print(f"Exported {name}.stl")
    if which == "kit":
        render(s, plate)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
