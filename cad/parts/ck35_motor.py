"""Reference model of the Canon CK35-H12CH-22V brushed DC motor (parts library M1).

This is a *reference* part — it models the real salvaged hardware so robot
frames can be designed around it. It is not meant to be printed.

Geometry is based on photos of the motor (label side, front mounting face,
rear endcap, side views):
- Round steel can with square vent windows in the wall (vents not modeled).
- FRONT: flat mounting face with a cone-shaped center bearing boss the
  working shaft exits through, plus six holes in three groups (1+2+3);
  the face is stamped "INCH", so the ~2.4 mm holes are likely tapped 4-40
  and the two ~3.0 mm holes plain (see FRONT_HOLES).
- REAR: crimped-on endcap that protrudes past the can rim, carrying the
  brush caps (modeled as four solder domes), two 100 nF disc capacitors
  and the black/white lead exit (radial, at the rim, on the hole-A side).
  A short stub shaft sticks out through a second cone boss.

Every dimension is parametric. The dataclass defaults are the original
photo-based ESTIMATES; MEASURED_DIMS holds the digital-caliper campaign of
2026-08-29 and overrides them. Still estimated: hole depth, edge rounding
radii, and the rear-cluster positions (capacitor/solder angles).

Run with:  uv run parts/ck35_motor.py
Exports ck35_motor.stl and ck35_motor.step (gitignored).

Orientation: motor axis along Z. Z=0 is the FRONT mounting face, the can
extends up in +Z, the working shaft points down in -Z. That way a mounting
plate sketched on the XY plane meets the motor face directly.
"""

from dataclasses import dataclass
from math import cos, radians, sin

from build123d import (
    Align,
    Axis,
    Cone,
    Cylinder,
    Part,
    Pos,
    Rot,
    Sphere,
    export_step,
    export_stl,
    fillet,
)

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_TOP = (Align.CENTER, Align.CENTER, Align.MAX)


@dataclass
class Ck35Dims:
    """All dimensions in mm. Defaults are photo-based ESTIMATES."""

    can_diameter: float = 35.5  # "35 mm class" can; measure across the can
    can_length: float = 30.0  # front face to can rim, rear cap excluded
    can_front_edge_radius: float = 1.0  # rounding of the front face rim (est)

    # Working shaft (long end, points -Z / "down" in the model)
    shaft_diameter: float = 2.0
    shaft_length: float = 12.0  # protrusion past the front face (tip at -shaft_length)

    # Cone-shaped bearing boss on the front face — same base/top diameters
    # as the rear one, but shorter (1.6 vs 2.2 measured)
    front_boss_base_diameter: float = 7.9
    front_boss_top_diameter: float = 5.0
    front_boss_height: float = 2.5

    mount_hole_depth: float = 3.0
    # Radius of the bolt circle all six front holes sit on (photo estimate)
    mount_hole_pitch_radius: float = 13.5

    # Rear endcap: crimped on, protrudes past the can rim; brush caps,
    # capacitors and lead exit sit on/above it
    rear_cap_diameter: float = 34.0
    rear_cap_height: float = 2.0  # protrusion past the can rim
    rear_cap_edge_radius: float = 1.2  # rounding of the lid's top rim (est)
    rear_parts_height: float = 5.0  # keep-out above the cap (caps + wires)

    # Cone-shaped bearing boss in the middle of the rear lid ("small cap")
    rear_boss_base_diameter: float = 7.9
    rear_boss_top_diameter: float = 5.0
    rear_boss_height: float = 2.5

    # Stub shaft (short end, +Z, pulley/flywheel/sensor side)
    stub_diameter: float = 2.0
    stub_length: float = 5.0  # protrusion past the rear cap

    # Rear lid detail (positions/sizes are photo ESTIMATES):
    # two ceramic disc capacitors lying flat on the lid,
    capacitor_diameter: float = 10.0
    capacitor_thickness: float = 3.0  # height above the lid surface
    capacitor_pitch_radius: float = 7.0  # disc center from motor axis
    # four solder domes on the brush caps,
    solder_diameter: float = 4.0
    solder_pitch_radius: float = 9.0
    # and the black/white lead pair exiting radially at the rim, at the
    # same angle as front hole A (+Y)
    wire_bundle_diameter: float = 3.5
    wire_exit_length: float = 6.0  # protrusion past the can wall


# Front-face holes as (label, angle_deg, diameter) on the common bolt
# circle (angle 0 = +X, CCW; wire exit up = +Y). Labels match the
# hole-mapping diagram: A = the single hole, B1-B2 = the pair, C1-C3 = the
# triple. From the straight-on face photo the six holes sit on a ~30° grid.
# The face is stamped "INCH": the ~2.4 mm holes are likely tapped 4-40
# (minor 2.39 mm) rather than M3 (minor 2.46 mm). Per user: B2 and C2 (the
# diametrically opposite pair on the horizontal axis) are the big ~3.0 mm
# holes, the other four are ~2.4 mm (likely tapped).
FRONT_HOLES: list[tuple[str, float, float]] = [
    ("A", 90, 2.4),
    ("B1", 330, 2.4),
    ("B2", 0, 3.0),
    ("C1", 150, 2.4),
    ("C2", 180, 3.0),
    ("C3", 210, 2.4),
]

# Caliper campaign of 2026-08-29 (dimension names L*/D* refer to the
# side-view drawing used during measuring). These override the estimate
# defaults above.
MEASURED_DIMS: dict[str, float] = {
    "can_diameter": 34.3,  # caliper, 2026-08-29
    "can_length": 27.6,  # caliper, 2026-08-29
    "shaft_diameter": 2.0,  # caliper, 2026-08-29
    # 9.0 mm measured from the front cone top, plus the 1.6 mm front cone
    "shaft_length": 10.6,
    # derived: L3 32.9 face-to-cone-top minus 2.2 cone minus 27.6 can.
    # (The earlier 29.8 "can incl lid" reading was off by ~0.9 and is
    # discarded — every other measurement closes on this value.)
    "rear_cap_height": 3.1,
    "rear_boss_base_diameter": 7.9,  # caliper, 2026-08-29
    "rear_boss_top_diameter": 5.0,  # caliper (approximate), 2026-08-29
    "rear_boss_height": 2.2,  # derived: L10 5.6 lid-to-stub-tip minus L6 3.4
    # derived: 34.5 cone-top-to-cone-top minus 32.9 face-to-rear-cone-top;
    # cones share diameters but NOT heights
    "front_boss_height": 1.6,
    "front_boss_base_diameter": 7.9,  # same as rear per user, 2026-08-29
    # 34.3/2 - 3.1 edge-to-edge - 1.2 hole radius; edge distance ~3.1 mm
    # measured on all holes, 2026-08-29
    "mount_hole_pitch_radius": 12.85,
    "rear_parts_height": 3.0,  # capacitors above rear lid, caliper (rough), 2026-08-29
    "rear_cap_diameter": 32.6,  # caliper, 2026-08-29
    "capacitor_diameter": 10.0,  # caliper, 2026-08-29
    "capacitor_thickness": 1.5,  # height above lid, caliper (approx), 2026-08-29
    # disc centers roughly midway between shaft and lid rim, fully clear of
    # the center cone (inner edge past the 3.95 cone base), per user 2026-08-29
    "capacitor_pitch_radius": 9.2,
    "wire_bundle_diameter": 1.5,  # height above lid, caliper (approx), 2026-08-29
    "front_boss_top_diameter": 5.0,  # same as rear per user, 2026-08-29
    "stub_diameter": 2.0,  # caliper, 2026-08-29
    "stub_length": 5.6,  # caliper (L10, lid surface to stub tip), 2026-08-29
}


def make_motor(dims: Ck35Dims | None = None, rear_keepout: bool = False) -> Part:
    """Build the motor with its front mounting face on the XY plane (Z=0).

    With rear_keepout=True, a solid cylinder replaces the rear-end detail to
    reserve space for the capacitors and lead wires in assembly checks.
    """
    d = dims or Ck35Dims(**MEASURED_DIMS)

    can = Cylinder(radius=d.can_diameter / 2, height=d.can_length, align=ALIGN_BOTTOM)
    can = fillet(can.edges().group_by(Axis.Z)[0], d.can_front_edge_radius)

    front_boss = Cone(
        bottom_radius=d.front_boss_top_diameter / 2,
        top_radius=d.front_boss_base_diameter / 2,
        height=d.front_boss_height,
        align=ALIGN_TOP,
    )
    working_shaft = Cylinder(
        radius=d.shaft_diameter / 2, height=d.shaft_length, align=ALIGN_TOP
    )

    cap = Cylinder(
        radius=d.rear_cap_diameter / 2, height=d.rear_cap_height, align=ALIGN_BOTTOM
    )
    cap = fillet(cap.edges().group_by(Axis.Z)[-1], d.rear_cap_edge_radius)
    rear_cap = Pos(0, 0, d.can_length) * cap
    rear_boss = Pos(0, 0, d.can_length + d.rear_cap_height) * Cone(
        bottom_radius=d.rear_boss_base_diameter / 2,
        top_radius=d.rear_boss_top_diameter / 2,
        height=d.rear_boss_height,
        align=ALIGN_BOTTOM,
    )
    stub_shaft = Pos(0, 0, d.can_length + d.rear_cap_height) * Cylinder(
        radius=d.stub_diameter / 2, height=d.stub_length, align=ALIGN_BOTTOM
    )

    lid_top = d.can_length + d.rear_cap_height

    # Two disc capacitors lying flat on the lid, roughly opposite each other
    capacitors = [
        Pos(side * d.capacitor_pitch_radius, 0, lid_top)
        * Cylinder(
            radius=d.capacitor_diameter / 2,
            height=d.capacitor_thickness,
            align=ALIGN_BOTTOM,
        )
        for side in (-1, 1)
    ]

    # Four solder domes on the brush caps, between the capacitors
    solder = [
        Pos(
            d.solder_pitch_radius * cos(radians(ang)),
            d.solder_pitch_radius * sin(radians(ang)),
            lid_top,
        )
        * Sphere(radius=d.solder_diameter / 2)
        for ang in (45, 135, 225, 315)
    ]

    # Lead pair exiting radially over the lid rim at hole A's angle (+Y)
    wire_exit = Pos(
        0, (d.can_diameter / 2 + d.wire_exit_length) / 2, lid_top
    ) * Rot(90, 0, 0) * Cylinder(
        radius=d.wire_bundle_diameter / 2,
        height=d.can_diameter / 2 + d.wire_exit_length,
    )

    motor = (
        can + front_boss + working_shaft + rear_cap + rear_boss + stub_shaft
    )
    for extra in (*capacitors, *solder, wire_exit):
        motor += extra

    if rear_keepout:
        motor += Pos(0, 0, d.can_length) * Cylinder(
            radius=d.rear_cap_diameter / 2,
            height=d.rear_cap_height + d.rear_parts_height,
            align=ALIGN_BOTTOM,
        )

    for _label, angle_deg, diameter in FRONT_HOLES:
        angle = radians(angle_deg)
        x = d.mount_hole_pitch_radius * cos(angle)
        y = d.mount_hole_pitch_radius * sin(angle)
        motor -= Pos(x, y, 0) * Cylinder(
            radius=diameter / 2, height=d.mount_hole_depth, align=ALIGN_BOTTOM
        )

    return motor


if __name__ == "__main__":
    motor = make_motor()

    export_stl(motor, "ck35_motor.stl")
    export_step(motor, "ck35_motor.step")

    bbox = motor.bounding_box()
    print("Canon CK35-H12CH-22V reference model")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    if MEASURED_DIMS:
        print(f"Caliper-measured: {', '.join(sorted(MEASURED_DIMS))}")
    else:
        print("WARNING: all dimensions are still photo-based estimates")
    print("Exported ck35_motor.stl and ck35_motor.step")
