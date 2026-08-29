"""Reference model of the N20 micro metal gearmotor (parts library M2).

This is a *reference* part — it models the bought hardware (6 V, 1:100
batch) so robot frames can be designed around it. It is not meant to be
printed.

Geometry comes from the seller's dimension drawing
(parts/photos/m2-n20-dimensions.png):
- FRONT: 10 x 12 mm gearbox bracket, Ø4 x 0.7 boss, Ø3 (0/-0.03) x 10 mm
  output shaft with a 2.5 (0/-0.1) D-flat, and two M1.6 tapped holes
  (2.1 mm deep) on the vertical centerline, 9 mm apart. The two hatched
  circles on the face are the gearbox assembly screw heads (flush, not
  modeled); the two small plain circles are rivets (not modeled).
- BODY: gearbox stack 9 mm long, then the motor can — a Ø12 cylinder
  flattened to 10 mm across, 15 mm long.
- REAR: Ø5 x 1.2 mm bearing boss, plus two solder-tab terminals
  (0.3 thick, 1.5 wide, reaching 2.5 mm past the rear face) 7.3±0.3 mm
  apart on the tall axis, (-) top / (+) bottom.

Dimensions not on the drawing are marked "est" and stay parametric:
bracket corner rounding, terminal hole, D-flat length (drawn running the
whole exposed shaft).

Run with:  uv run parts/n20_motor.py
Exports n20_motor.stl and n20_motor.step (gitignored).

Orientation: motor axis along Z, matching the CK35 convention. Z=0 is the
FRONT gearbox face, the body extends up in +Z, the output shaft points
down in -Z; the 12 mm bracket axis is Y, the 10 mm axis (and the can
flats) is X. A mounting plate sketched on the XY plane meets the gearbox
face directly.
"""

from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    Box,
    Cylinder,
    Part,
    Plane,
    Pos,
    export_step,
    export_stl,
    fillet,
)

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_TOP = (Align.CENTER, Align.CENTER, Align.MAX)


@dataclass
class N20Dims:
    """All dimensions in mm, from the seller drawing unless marked est."""

    # Gearbox bracket (front block)
    gearbox_width: float = 10.0  # X, across the can flats
    gearbox_height: float = 12.0  # Y, the mounting-hole axis
    gearbox_length: float = 9.0
    gearbox_corner_radius: float = 0.6  # bracket edge rounding (est)

    # Front bearing boss the shaft exits through
    boss_diameter: float = 4.0
    boss_length: float = 0.7

    # Output shaft, dimensioned from the gearbox face (boss included)
    shaft_diameter: float = 3.0  # 0/-0.03 on the drawing
    shaft_length: float = 10.0  # face to tip
    shaft_flat_across: float = 2.5  # 0/-0.1; flat depth = 3.0 - 2.5
    shaft_flat_length: float = 9.3  # drawn over the whole exposed shaft (est)

    # Two M1.6 tapped holes on the vertical centerline
    mount_hole_diameter: float = 1.6
    mount_hole_depth: float = 2.1
    mount_hole_spacing: float = 9.0  # center to center

    # Motor can: Ø12 cylinder flattened to the gearbox width
    can_diameter: float = 12.0
    can_length: float = 15.0

    # Rear bearing boss
    rear_boss_diameter: float = 5.0
    rear_boss_length: float = 1.2

    # Solder-tab terminals on the rear face, on the tall (Y) axis
    terminal_spacing: float = 7.3  # ±0.3, center to center
    terminal_reach: float = 2.5  # rear face to tab tip
    terminal_width: float = 1.5
    terminal_thickness: float = 0.3
    terminal_hole_diameter: float = 0.8  # wire hole in the tab (est)


def make_motor(dims: N20Dims | None = None) -> Part:
    """Build the motor with its gearbox face on the XY plane (Z=0)."""
    d = dims or N20Dims()

    gearbox = Box(
        d.gearbox_width, d.gearbox_height, d.gearbox_length, align=ALIGN_BOTTOM
    )
    gearbox = fillet(
        gearbox.edges().filter_by(Axis.Z), d.gearbox_corner_radius
    )

    boss = Cylinder(radius=d.boss_diameter / 2, height=d.boss_length, align=ALIGN_TOP)

    shaft = Cylinder(radius=d.shaft_diameter / 2, height=d.shaft_length, align=ALIGN_TOP)
    # D-flat: shave the +X side of the shaft down to shaft_flat_across,
    # over the flat_length nearest the tip
    flat_depth = d.shaft_diameter - d.shaft_flat_across
    shaft -= Pos(
        d.shaft_diameter / 2 - flat_depth / 2, 0, -d.shaft_length
    ) * Box(
        flat_depth,
        d.shaft_diameter,
        d.shaft_flat_length,
        align=ALIGN_BOTTOM,
    )

    can = Cylinder(radius=d.can_diameter / 2, height=d.can_length, align=ALIGN_BOTTOM)
    can &= Box(d.gearbox_width, d.can_diameter, d.can_length, align=ALIGN_BOTTOM)
    can = Pos(0, 0, d.gearbox_length) * can

    rear_face = d.gearbox_length + d.can_length
    rear_boss = Pos(0, 0, rear_face) * Cylinder(
        radius=d.rear_boss_diameter / 2, height=d.rear_boss_length, align=ALIGN_BOTTOM
    )

    # Terminal tabs stand on edge (thickness along Y), sticking out past
    # the rear face, (-) at +Y and (+) at -Y
    terminals = Part()
    for side in (-1, 1):
        tab = Pos(0, side * d.terminal_spacing / 2, rear_face) * Box(
            d.terminal_width,
            d.terminal_thickness,
            d.terminal_reach,
            align=ALIGN_BOTTOM,
        )
        tab -= Pos(
            0, side * d.terminal_spacing / 2, rear_face + d.terminal_reach * 0.6
        ) * Plane.XZ * Cylinder(
            radius=d.terminal_hole_diameter / 2, height=d.terminal_thickness * 3
        )
        terminals += tab

    motor = gearbox + boss + shaft + can + rear_boss + terminals

    for side in (-1, 1):
        motor -= Pos(0, side * d.mount_hole_spacing / 2, 0) * Cylinder(
            radius=d.mount_hole_diameter / 2,
            height=d.mount_hole_depth,
            align=ALIGN_BOTTOM,
        )

    return motor


if __name__ == "__main__":
    motor = make_motor()

    export_stl(motor, "n20_motor.stl")
    export_step(motor, "n20_motor.step")

    d = N20Dims()
    bbox = motor.bounding_box()
    print("N20 micro gearmotor reference model (M2)")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    expected_z = d.shaft_length + d.gearbox_length + d.can_length + d.terminal_reach
    print(f"Expected Z extent (shaft+gearbox+can+terminals): {expected_z:.2f}")
    print("Exported n20_motor.stl and n20_motor.step")
