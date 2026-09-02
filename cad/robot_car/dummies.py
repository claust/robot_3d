"""Printable stand-in dummies for the components not yet in hand: two N20
gearmotors (M2) and the two small PCBs (D2 DRV8833, P1 MP1584). Printed in
white from the aux nozzle so real parts and stand-ins can't be confused, they
let the first chassis print be dress-rehearsed — cradle snap fit, tray
snap-hook fit, wheel press-fit on the dummy shaft — before the real hardware
arrives.
The Pi Zero 2 W and B2 LiPo are real and mount as themselves; no dummies.

These take their dimensions from the reference models in cad/parts/ but are
print-adapted, not miniatures:

- N20 dummy: prints LYING DOWN on one can flat, with the shaft's D-flat
  facing the bed so the shaft prints as a clean horizontal half-round.
  (The first attempt printed the motor standing, rear-face-down: a 34 mm
  tower on a 10 x 12 mm base — it got knocked over at layer ~120, exactly
  like the first skid. Lying down the part is 12 mm tall and unshakable.)
  The D-flat and the can's 10 mm across-flats — the surfaces the wheel
  bore and the cradle actually grip — are exact. The rear face is
  flattened (no bearing boss, no solder tabs); M1.6 holes omitted.
  Handle the printed shaft gently; a Ø3 PLA pin takes wheel press-fits
  but not side-loads.
- DRV8833 dummy: bare 18.5 x 16 x 1.6 board with the IC bump. Header pins
  and holes omitted (a 1 mm hole / 0.64 mm pin doesn't print); the tray
  snap hooks grip the bare board edge exactly as they would the real PCB.
- MP1584 dummy: 22 x 17 x 1.6 board with inductor and trimpot bumps, whose
  heights matter for anything routed above the tray.

Each dummy carries a raised label (M2 / D2 / P1) so the white parts stay
identifiable once scattered on the bench.

Run with:  uv run robot_car/dummies.py
Exports dummies.stl (one plate: 2 motors + both boards) plus the individual
dummy_*.stl files (gitignored), in the cwd.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import (  # noqa: E402
    Align,
    Box,
    Cylinder,
    Part,
    Plane,
    Pos,
    Rot,
    Text,
    export_stl,
    extrude,
)

from d2_drv8833 import Drv8833Dims  # noqa: E402
from n20_motor import N20Dims  # noqa: E402
from p1_mp1584 import Mp1584Dims  # noqa: E402

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
LABEL_HEIGHT = 0.4  # raised text
PLATE_GAP = 12.0


def make_motor_dummy(d: N20Dims | None = None) -> Part:
    """N20 stand-in, printed LYING DOWN: built axis-up (Z=0 at the
    flattened rear can face), then rotated onto its -X can flat so the
    shaft runs horizontally with its D-flat facing the bed, plus a
    breakaway fin under the otherwise-floating shaft."""
    d = d or N20Dims()

    can = Cylinder(radius=d.can_diameter / 2, height=d.can_length, align=ALIGN_BOTTOM)
    can &= Box(
        d.gearbox_width, d.can_diameter + 2, d.can_length, align=ALIGN_BOTTOM
    )  # the two flats the cradle grips

    gearbox = Pos(0, 0, d.can_length) * Box(
        d.gearbox_width, d.gearbox_height, d.gearbox_length, align=ALIGN_BOTTOM
    )

    front_z = d.can_length + d.gearbox_length
    boss = Pos(0, 0, front_z) * Cylinder(
        radius=d.boss_diameter / 2, height=d.boss_length, align=ALIGN_BOTTOM
    )

    # Shaft with D-flat, dimensioned face-to-tip like the real part. The
    # flat faces -X: the same side as the can flat the motor lies on, so in
    # print orientation the flat is on the bed.
    shaft = Pos(0, 0, front_z) * Cylinder(
        radius=d.shaft_diameter / 2, height=d.shaft_length, align=ALIGN_BOTTOM
    )
    flat_depth = d.shaft_diameter - d.shaft_flat_across
    shaft -= Pos(-(d.shaft_diameter / 2 - flat_depth / 2), 0, front_z + d.boss_length) * Box(
        flat_depth,
        d.shaft_diameter,
        d.shaft_length - d.boss_length,
        align=ALIGN_BOTTOM,
    )

    motor = Part() + can + gearbox + boss + shaft

    # Lie the motor down for printing: rotate the axis from +Z onto the bed
    # so the -X side (can flat + shaft D-flat) faces down, then rest it on
    # the bed plane (shaft ends up at the low-X end).
    motor = Rot(0, -90, 0) * motor
    bb = motor.bounding_box()
    motor = Pos(-bb.min.X, 0, -bb.min.Z) * motor

    # Label on the upward-facing can flat, added AFTER the rotation so it
    # cannot end up mirrored (the first print's labels were unreadable for
    # exactly that reason).
    bb = motor.bounding_box()
    label = Plane.XY.offset(bb.max.Z) * Pos(bb.max.X - d.can_length / 2, 0) * Text(
        "M2", font_size=5
    )
    motor += extrude(label, amount=LABEL_HEIGHT)

    # Breakaway support fin under the shaft: lying on the can flat, the
    # shaft's underside floats (gearbox_width/2 - 1.0) = 4 mm above the bed
    # and printed as spaghetti without it. A 0.8 mm wall runs from the bed
    # to 0.2 mm below the D-flat (standard support z-gap) along the exposed
    # shaft; snap it off after printing — the gap keeps the press-fit flat
    # unscarred. The shaft tip is at x=0 in print orientation.
    axis_z = d.gearbox_width / 2
    flat_bottom_z = axis_z - (d.shaft_flat_across - d.shaft_diameter / 2)
    fin_len = d.shaft_length - d.boss_length - 0.3  # stop short of the boss face
    fin = Pos(fin_len / 2, 0, 0) * Box(
        fin_len, 0.8, flat_bottom_z - 0.2, align=ALIGN_BOTTOM
    )
    motor += fin
    return motor


def make_drv8833_dummy(d: Drv8833Dims | None = None) -> Part:
    d = d or Drv8833Dims()
    board = Box(d.board_length, d.board_width, d.board_thickness, align=ALIGN_BOTTOM)
    ic = Pos(0, 0, d.board_thickness) * Box(
        d.ic_size, d.ic_size, d.ic_height, align=ALIGN_BOTTOM
    )
    label = Plane.XY.offset(d.board_thickness) * Pos(0, -d.board_width / 4) * Text(
        "D2", font_size=4
    )
    return Part() + board + ic + extrude(label, amount=LABEL_HEIGHT)


def make_mp1584_dummy(d: Mp1584Dims | None = None) -> Part:
    d = d or Mp1584Dims()
    board = Box(d.board_length, d.board_width, d.board_thickness, align=ALIGN_BOTTOM)
    inductor = Pos(d.inductor_x, d.inductor_y, d.board_thickness) * Box(
        d.inductor_size, d.inductor_size, d.inductor_height, align=ALIGN_BOTTOM
    )
    trimpot = Pos(d.trimpot_x, d.trimpot_y, d.board_thickness) * Box(
        d.trimpot_length, d.trimpot_width, d.trimpot_height, align=ALIGN_BOTTOM
    )
    label = Plane.XY.offset(d.board_thickness) * Pos(-d.board_length / 4 - 1, 3) * Text(
        "P1", font_size=4
    )
    return Part() + board + inductor + trimpot + extrude(label, amount=LABEL_HEIGHT)


if __name__ == "__main__":
    motor = make_motor_dummy()
    drv = make_drv8833_dummy()
    buck = make_mp1584_dummy()

    for part, name in ((motor, "dummy_n20"), (drv, "dummy_drv8833"), (buck, "dummy_mp1584")):
        export_stl(part, f"{name}.stl")
        bb = part.bounding_box()
        print(f"{name}: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")

    # One combined plate: parts in a row along X, spacing computed from
    # each part's real bounding box. (The first plate hardcoded offsets
    # sized for the old STANDING motor orientation; the lying motors are
    # 34 mm long, overlapped each other and the D2 board, and the slicer
    # printed the union as one fused 48 mm brick.)
    plate = Part()
    x = 0.0
    for part in (motor, motor, drv, buck):
        bb = part.bounding_box()
        plate += Pos(x - bb.min.X, -(bb.min.Y + bb.max.Y) / 2, 0) * part
        x += bb.size.X + PLATE_GAP
    export_stl(plate, "dummies.stl")
    bb = plate.bounding_box()
    print(f"dummies plate: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
    print("Exported dummies.stl and individual dummy_*.stl files")
