"""Printable drive wheel for the N20 gearmotor (parts/n20_motor.py: Ø3 mm
output shaft, 0/-0.03, 2.5 mm D-flat, Ø4 x 0.7 mm front boss), sized for an
off-the-shelf O-ring tire (default: OD 60 / ID 40 mm, i.e. a 10 mm cord).

The tire drives the wheel geometry, not the other way around: the groove
ROOT diameter is oring_id x STRETCH, and the default geometry is a copy of
the ring's original wooden wheel, measured 2026-08-30: root Ø39 (ring seated
RELAXED), shoulder Ø46 (15% momentary stretch to install — proven
hand-mountable), round-bottomed seat ~3.5 mm deep. Retention comes from the
cord-matched arc cradling the ring, not from tension. Rolling diameter =
root + 2 x cord = Ø59. Run with different `oring_id` / `oring_cord` values
to fit a different O-ring.

The wheel is a hoop rim on a solid base (the "web") with a hub rising out of
the middle, printed with the web flat on the bed (Z=0) and the rim/hub open
side up:

- Z in [0, web_thickness]: a solid disc across the full diameter. This is
  both the printable base and the flat web that carries the hub load to the
  rim; sliced flat like this it is a single horizontal plane with nothing
  below it, so there are no overhangs to worry about.
- Z in [web_thickness, hub_top]: the hub stands on the web, motor side up
  (its tip is the first thing the motor shaft meets), inside an open hollow
  rim tube -- a vertical tube wall is self-supporting, so no overhangs here
  either.
- Z in [hub_top, rim_width]: at the wide (10 mm cord) end, `rim_width` no
  longer matches `hub_top` -- the rim simply continues on as a plain hollow
  tube past the hub tip, wider than the shaft/bore ever needs. Placing this
  extra length past the hub tip (rather than past the web on the *other*
  side, closer to how "outboard" reads literally) is a deliberate choice:
  the web has to be the very first, full-diameter layer for the "no
  overhangs" rule to hold -- anywhere else it would be an unsupported
  horizontal disc bridging across the open middle. The rim's ID (see
  `rim_wall_thickness`) stays far larger than the N20 gearbox's 10 x 12 mm
  footprint, so this extra tube can extend past the shaft tip without
  fouling the gearbox; it just means "outboard" here means "away from the
  web," not literally away from the motor -- worth double-checking against
  the actual chassis mount.

O-ring groove (`groove_profile`): default "round" is a circular-arc seat
matching the cord radius (+`groove_seat_clearance`), like the wooden
original, with 45-degree conical flares from the point where the arc's wall
would exceed printable overhang out to the rim surface -- the ring only
touches the arc, the flares just keep the groove's upper walls
self-supporting when printed axis-vertical. "v" keeps coupon rounds 1-2's
straight-walled V (walls ~40 deg from vertical). The shoulders either side
stay a plain cylinder so the wheel rolls fine bare, before a tire is
fitted. History: the original design buried the cord 0.6 x diameter, which
made a Ø52.6 shoulder = 32% install stretch -- physically impossible by
hand at a 10 mm cord (coupon round 1's finding).

Bore: a D-shaped through-hole sized for the N20 shaft (round + flat, both
grown by `bore_clearance` radially) sits under a Ø4.5 relief pocket that
gives 1 mm of axial clearance for the Ø4 boss, so the wheel's hub face can't
rub the gearbox front even if pressed fully home. This is a *press* fit --
FDM holes print undersized (elephant-foot / bridging), so unlike the
demo_04 running-fit coupon (0.2 mm radial clearance measured to spin
freely), a bore meant to grip the shaft wants only 0-0.05 mm of *nominal*
radial clearance in the model; dial the exact value in with a fit coupon
printed on your printer/filament before committing to a batch of wheels.
The shaft is only 10 mm long overall and the bore only ever engages
~8.5 mm of it (web_thickness + hub_protrusion) -- unaffected by rim_width.

Run with:  uv run wheel.py [oring_id_mm] [oring_cord_mm] [bore_clearance_mm]
e.g.       uv run wheel.py 40 10 0.05
"""

import sys
from dataclasses import dataclass
from math import atan, degrees

from build123d import (
    Align,
    Box,
    Cone,
    Cylinder,
    GeomType,
    Part,
    Pos,
    Torus,
    chamfer,
    export_step,
    export_stl,
)

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)

# Seated-fit factor: groove root = oring_id x STRETCH. Matched to the ring's
# original wooden wheel (root Ø39 for the ID-40 ring, i.e. the ring sits
# RELAXED and retention comes from the round groove cradling the cord, not
# from tension). Coupon rounds 1-2 taught us the binding constraint is the
# INSTALL stretch over the shoulder (wood: Ø46 = 15%, proven hand-mountable;
# our first 0.6-burial design: Ø52.6 = 32%, impossible by hand).
STRETCH = 0.975


@dataclass
class WheelDims:
    """All dimensions in mm."""

    oring_id: float = 40.0  # relaxed O-ring inner diameter
    oring_cord: float = 10.0  # O-ring cross-section (cord) diameter
    bore_clearance: float = 0.05  # radial, added to both the round bore and the flat
    # Groove burial as a fraction of the cord. Retention trades off against
    # INSTALLATION: the ring's ID must momentarily stretch over the shoulder
    # OD (root + 2 x depth), and stretching force scales with cord cross-
    # section — at a 10 mm cord, the original 0.6 burial made a Ø52.6
    # shoulder = 32% install stretch, not hand-mountable (found the hard way
    # on coupons P1-P3). Shallower groove + more seated stretch shifts the
    # grip to ring tension and keeps installation feasible.
    groove_depth_factor: float = 0.35  # wood-matched: 3.5 mm at the 10 mm cord

    # Groove profile: "round" = circular-arc seat matching the cord (like the
    # wooden wheel), with 45-degree flares from where the arc's wall would
    # exceed printable overhang out to the rim surface; "v" = the straight-
    # walled V used by coupon rounds 1-2.
    groove_profile: str = "round"
    groove_seat_clearance: float = 0.1  # radial slack of the arc seat vs the cord

    groove_shoulder_margin: float = 2.0  # plain rim shoulder left on each side of the groove
    rim_chamfer: float = 0.4  # eases the two outer tread edges
    min_rim_wall: float = 3.0  # radial rim wall thickness floor, under the groove root

    web_thickness: float = 2.5  # flat disc from hub to rim
    hub_diameter: float = 10.0
    hub_protrusion: float = 6.0  # hub rise above the web, motor side
    bore_chamfer: float = 0.3  # lead-in at the bore entry (top of the boss relief)

    # N20 output shaft (parts/n20_motor.py N20Dims), driving the bore shape
    shaft_diameter: float = 3.0  # 0/-0.03 on the seller drawing
    shaft_flat_across: float = 2.5  # 0/-0.1
    boss_diameter: float = 4.0  # front bearing boss the shaft exits through
    boss_length: float = 0.7
    boss_relief_diameter: float = 4.5  # clearance pocket so the boss can't rub
    boss_relief_depth: float = 1.0  # > boss_length, leaves axial clearance

    @property
    def seat_radius(self) -> float:
        """Radius of the round groove seat's arc (cord radius + slack)."""
        return self.oring_cord / 2 + self.groove_seat_clearance

    @property
    def flare_start_axial(self) -> float:
        """Axial offset from groove center where the arc reaches 45 deg."""
        return self.seat_radius * 0.7071

    @property
    def flare_start_radius(self) -> float:
        root_r = self.groove_root_diameter / 2
        return (root_r + self.seat_radius) - self.seat_radius * 0.7071

    @property
    def groove_width(self) -> float:
        if self.groove_profile == "round":
            flare_du = self.rim_shoulder_diameter / 2 - self.flare_start_radius
            return 2 * (self.flare_start_axial + flare_du)
        return self.oring_cord + 0.2

    @property
    def groove_depth(self) -> float:
        return self.groove_depth_factor * self.oring_cord

    @property
    def groove_root_diameter(self) -> float:
        """Groove floor diameter: the O-ring's ID stretched by STRETCH."""
        return self.oring_id * STRETCH

    @property
    def rim_shoulder_diameter(self) -> float:
        """OD of the plain (un-grooved) rim surface either side of the groove."""
        return self.groove_root_diameter + 2 * self.groove_depth

    @property
    def rolling_diameter(self) -> float:
        """Effective diameter the wheel rolls on with the tire fitted."""
        return self.groove_root_diameter + 2 * self.oring_cord

    @property
    def rim_width(self) -> float:
        """Axial rim/tread width: the groove plus a plain shoulder each side."""
        return max(
            self.groove_width + 2 * self.groove_shoulder_margin,
            self.hub_top,  # never shorter than the hub + web it has to carry
        )

    @property
    def rim_wall_thickness(self) -> float:
        # Radial wall left under the groove root, floored for structural sense.
        return max(self.min_rim_wall, self.groove_depth + 1.0)

    @property
    def hub_top(self) -> float:
        """Z of the hub tip (and the top of the through-bore), motor side."""
        return self.web_thickness + self.hub_protrusion

    @property
    def bore_engagement(self) -> float:
        """D-bore length that actually grips the shaft, between the two reliefs."""
        return self.hub_top - 2 * self.boss_relief_depth

    @property
    def groove_wall_angle_deg(self) -> float:
        """V-groove wall angle from vertical (0 deg = vertical, self-supporting)."""
        return degrees(atan((self.groove_width / 2) / self.groove_depth))


def make_wheel(d: WheelDims | None = None) -> Part:
    """Build the wheel with its web on the XY plane (Z=0 is the print bed)."""
    d = d or WheelDims()

    rim_radius = d.rim_shoulder_diameter / 2
    rim_inner_radius = rim_radius - d.rim_wall_thickness
    if rim_inner_radius <= d.hub_diameter / 2:
        raise ValueError(
            f"rim wall (inner radius {rim_inner_radius:.2f} mm) collides with "
            f"the hub (radius {d.hub_diameter / 2:.2f} mm) -- widen the O-ring "
            "ID or shrink the cord"
        )
    if 2 * d.boss_relief_depth >= d.hub_top:
        raise ValueError("boss_relief_depth (x2, one per face) must be less than the total bore depth")

    # Solid base: doubles as the web (Z 0..web_thickness) and the lower part
    # of the rim wall. A single flat disc -- flat on the bed, no overhangs.
    base = Cylinder(radius=rim_radius, height=d.web_thickness, align=ALIGN_BOTTOM)

    # Rim continues up as a plain hollow tube around an open middle.
    rim_upper_height = d.rim_width - d.web_thickness
    rim_upper = Cylinder(radius=rim_radius, height=rim_upper_height, align=ALIGN_BOTTOM)
    rim_upper -= Cylinder(
        radius=rim_inner_radius, height=rim_upper_height, align=ALIGN_BOTTOM
    )
    rim_upper = Pos(0, 0, d.web_thickness) * rim_upper

    # Hub stands on the web inside the open middle, motor side up.
    hub = Cylinder(radius=d.hub_diameter / 2, height=d.hub_protrusion, align=ALIGN_BOTTOM)
    hub = Pos(0, 0, d.web_thickness) * hub

    wheel = Part() + base + rim_upper + hub

    # Centered O-ring groove.
    half_width = d.groove_width / 2
    depth = d.groove_depth
    root_radius = rim_radius - depth
    groove_center_z = d.rim_width / 2
    if d.groove_profile == "round":
        # Circular-arc seat matching the cord (like the ring's original
        # wooden wheel): a torus cut whose tube cradles the cord, PLUS a
        # 45-degree conical flare on each side from where the arc's wall
        # would exceed printable overhang out to the rim surface. The ring
        # only ever touches the arc; the flares just make the groove's
        # upper walls self-supporting when printed axis-vertical.
        seat_r = d.seat_radius
        torus_major = root_radius + seat_r
        wheel -= Pos(0, 0, groove_center_z) * Torus(
            major_radius=torus_major, minor_radius=seat_r
        )
        u45 = d.flare_start_axial
        rho45 = d.flare_start_radius
        flare_du = rim_radius - rho45
        for side in (+1, -1):
            z0 = groove_center_z + (u45 if side > 0 else -(u45 + flare_du))
            slab = Pos(0, 0, z0) * Cylinder(
                radius=rim_radius + 1, height=flare_du, align=ALIGN_BOTTOM
            )
            if side > 0:
                cone = Cone(bottom_radius=rho45, top_radius=rim_radius,
                            height=flare_du, align=ALIGN_BOTTOM)
            else:
                cone = Cone(bottom_radius=rim_radius, top_radius=rho45,
                            height=flare_du, align=ALIGN_BOTTOM)
            wheel -= slab - Pos(0, 0, z0) * cone
    else:
        # Straight-walled V (coupon rounds 1-2): a cylinder slug minus an
        # "hourglass" pair of cones meeting at the root radius.
        cone_in = Cone(
            bottom_radius=rim_radius, top_radius=root_radius, height=half_width, align=ALIGN_BOTTOM
        )
        cone_in = Pos(0, 0, groove_center_z - half_width) * cone_in
        cone_out = Cone(
            bottom_radius=root_radius, top_radius=rim_radius, height=half_width, align=ALIGN_BOTTOM
        )
        cone_out = Pos(0, 0, groove_center_z) * cone_out
        bicone = cone_in + cone_out

        groove_slug = Pos(0, 0, groove_center_z - half_width) * Cylinder(
            radius=rim_radius, height=d.groove_width, align=ALIGN_BOTTOM
        )
        wheel -= groove_slug - bicone

    # Bore: a Ø4.5 boss-clearance relief on BOTH faces (the wheel mounts
    # web-face-to-motor, but the top-side relief is kept too so the part is
    # symmetric in function and the other orientation stays usable), with a
    # D-shaped press-fit hole for the shaft engaging the span between them.
    relief_top = Pos(0, 0, d.hub_top - d.boss_relief_depth) * Cylinder(
        radius=d.boss_relief_diameter / 2, height=d.boss_relief_depth, align=ALIGN_BOTTOM
    )
    relief_web = Cylinder(
        radius=d.boss_relief_diameter / 2, height=d.boss_relief_depth, align=ALIGN_BOTTOM
    )

    bore_round_radius = d.shaft_diameter / 2 + d.bore_clearance
    bore_flat_half = d.shaft_flat_across / 2 + d.bore_clearance
    bore_depth = d.hub_top - 2 * d.boss_relief_depth
    d_bore = Cylinder(radius=bore_round_radius, height=bore_depth, align=ALIGN_BOTTOM)
    flat_cut_depth = bore_round_radius - bore_flat_half
    d_bore -= Pos(bore_round_radius - flat_cut_depth / 2, 0, 0) * Box(
        flat_cut_depth, 2 * bore_round_radius, bore_depth, align=ALIGN_BOTTOM
    )
    d_bore = Pos(0, 0, d.boss_relief_depth) * d_bore

    wheel -= relief_top
    wheel -= relief_web
    wheel -= d_bore

    # Chamfer the bore entries (top of each relief) and the two outer tread
    # edges for print quality / easier shaft insertion.
    circles = wheel.edges().filter_by(GeomType.CIRCLE)

    def at(radius: float, z: float):
        return circles.filter_by(
            lambda e, radius=radius, z=z: (
                abs(e.radius - radius) < 1e-6 and abs(e.center().Z - z) < 1e-6
            )
        )

    entry_edge_top = at(d.boss_relief_diameter / 2, d.hub_top)
    entry_edge_web = at(d.boss_relief_diameter / 2, 0)
    rim_top_edge = at(rim_radius, d.rim_width)
    rim_bottom_edge = at(rim_radius, 0)
    wheel = chamfer(entry_edge_top + entry_edge_web, d.bore_chamfer)
    wheel = chamfer(rim_top_edge + rim_bottom_edge, d.rim_chamfer)

    return wheel


if __name__ == "__main__":
    oring_id = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
    oring_cord = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    bore_clearance = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05

    dims = WheelDims(oring_id=oring_id, oring_cord=oring_cord, bore_clearance=bore_clearance)
    wheel = make_wheel(dims)

    export_stl(wheel, "wheel.stl")
    export_step(wheel, "wheel.step")

    # Half-section (Y >= 0 kept, cut through the axis) to inspect the groove
    # and bore profile, same convention as demo_02/nut.py.
    section = wheel & Box(200, 200, 200, align=(Align.CENTER, Align.MIN, Align.MIN))
    export_stl(section, "wheel_section.stl")

    bbox = wheel.bounding_box()
    print(
        f"Drive wheel for O-ring ID {oring_id:g} x cord {oring_cord:g} mm "
        f"(stretched {(STRETCH - 1) * 100:.0f}% onto a {dims.groove_root_diameter:.2f} mm "
        "groove root)"
    )
    print(
        f"Rim shoulder OD {dims.rim_shoulder_diameter:.2f} mm, rim width {dims.rim_width:.2f} mm, "
        f"groove {dims.groove_width:.2f} mm wide x {dims.groove_depth:.2f} mm deep "
        + (f"(round seat R{dims.seat_radius:g} + 45 deg flares)"
           if dims.groove_profile == "round"
           else f"(V profile, {dims.groove_wall_angle_deg:.1f} deg wall from vertical)")
    )
    print(
        f"Effective rolling diameter with tire fitted: {dims.rolling_diameter:.2f} mm "
        "(use this for chassis skid height)"
    )
    print(
        f"Hub Ø{dims.hub_diameter:g} mm x {dims.hub_protrusion:g} mm; boss relief "
        f"Ø{dims.boss_relief_diameter:g} x {dims.boss_relief_depth:g} mm on BOTH faces "
        f"(mounts web-face-to-motor; top-side relief kept for the other orientation)"
    )
    print(
        f"D-bore Ø{2 * (dims.shaft_diameter / 2 + bore_clearance):.2f} mm "
        f"(flat {dims.shaft_flat_across + 2 * bore_clearance:.2f} mm) "
        f"x {dims.bore_engagement:.2f} mm engagement between the two reliefs, "
        f"{bore_clearance:g} mm radial clearance"
    )
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {wheel.volume:.1f} mm^3")
    print("Exported wheel.stl, wheel.step and wheel_section.stl")
