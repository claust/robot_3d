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

The wheel is a hoop rim on a spoked base (the "web") with a long hub rising
out of the middle, printed with the web flat on the bed (Z=0) and the
rim/hub open side up. On the car the web is the OUTSIDE face -- spokes
showing -- and the hub reaches inboard through the rim to the motor shaft:

- Z in [0, web_thickness]: a disc across the full diameter, pierced by
  `spoke_count` windows between a solid ring around the hub and a solid
  ring under the rim wall -- `spoke_count` curved spokes carry the hub load
  to the rim (`web_windows`; 0 gives a solid disc). This is both the
  printable base and the flat web; sliced flat like this it is a single
  horizontal plane with nothing below it, and the windows are plain
  through-holes in it, so there are no overhangs or bridges to worry about.
- Z in [web_thickness, rim_width]: the hub stands on the web inside an
  open hollow rim tube, and runs the full rim width so its tip ends flush
  with the rim's inboard edge (`hub_top` == `rim_width`) -- the shaft is
  short, so the hub goes to meet it. Vertical tube and pillar walls are
  self-supporting, so no overhangs here either.

Why the web is outboard at all: the shaft reaches only ~8 mm past the plate
edge, and the rim must stay entirely outboard of the plate (its Ø46 would
foul the plate edge otherwise). With the web *inboard* the rim bowl pointed
outward and the outside face of the wheel was a hollow tube (prototype
wheels P7/P8). Putting the web outboard shows the spokes, and the extended
hub keeps the same shaft engagement inside the same envelope: the rim's
inboard edge (and the hub tip with it) sit where P7/P8's web face sat.

O-ring groove (`groove_profile`): default "round" is a circular-arc seat
matching the cord radius (+`groove_seat_clearance`), like the wooden
original, with 45-degree conical flares from the point where the arc's wall
would exceed printable overhang out to the rim surface -- the ring only
touches the arc, the flares just keep the groove's upper walls
self-supporting when printed axis-vertical. Printed as P7/P8 (2026-08-30)
it comes out looking round, not V-shaped -- leave it alone. "v" keeps
coupon rounds 1-2's straight-walled V (walls ~40 deg from vertical). The
shoulders either side stay a plain cylinder so the wheel rolls fine bare,
before a tire is fitted. History: the original design buried the cord 0.6 x diameter, which
made a Ø52.6 shoulder = 32% install stretch -- physically impossible by
hand at a 10 mm cord (coupon round 1's finding).

Bore: a BLIND D-shaped hole `bore_depth` deep from the hub tip, sized for
the N20 shaft (round + flat, both grown by `bore_clearance` radially), so
the outside face of the wheel is solid in the middle. The motor's Ø4 x 0.7
front boss never reaches the wheel (it sits inside the cradle's end wall),
so no boss relief. `bore_depth` is the shaft reach in the chassis mount
plus a millimetre, so the shaft never bottoms out and the wheel's axial
position is set by pushing it on, not by the bore floor. This is a *press*
fit --
FDM holes print undersized (elephant-foot / bridging), so it needs more
nominal clearance than a metal-machining intuition suggests, but less than
the demo_04 running-fit coupon (0.2 mm radial, measured to spin freely).
The value is no longer a guess: bore_coupons.py swept 0.00-0.20 on the
printer and 0.10 won -- firm push-on, seats fully, no rotational play --
while 0.15 and 0.20 dropped on loose. Shaft dimensions here are the
measured ones (Ø3.0, flat 2.45 across), not the drawing's.
The shaft is only 10 mm long overall; after the cradle's 2 mm end wall and
the 1 mm wall clearance, 7 mm of it enters the bore (assembly.py's
`wheel_geometry` works this out from the chassis constants).

Run with:  uv run wheel.py [oring_id_mm] [oring_cord_mm] [bore_clearance_mm]
e.g.       uv run wheel.py 40 10 0.10
"""

import sys
from dataclasses import dataclass
from math import atan, cos, degrees, radians, sin

from build123d import (
    Align,
    Box,
    Circle,
    Cone,
    Cylinder,
    GeomType,
    Part,
    Pos,
    Rot,
    Sketch,
    SlotArc,
    ThreePointArc,
    Torus,
    chamfer,
    export_step,
    export_stl,
    extrude,
    fillet,
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
    # Calibrated on the X2D in green PLA Basic (2026-09-02) with
    # bore_coupons.py: station B3 was the firm, no-play press fit; 0.15 and
    # 0.20 dropped on loose. Nominal 0.10 in the model comes out right
    # because FDM holes print undersized.
    bore_clearance: float = 0.10  # radial, added to both the round bore and the flat
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

    # Spoked web: `spoke_count` curved spokes between a solid ring around
    # the hub and a solid ring under the rim; 0 = the old solid disc. The
    # windows are through-holes in the web only (Z 0..web_thickness), i.e.
    # holes in the first layers -- nothing bridges over them.
    spoke_count: int = 5
    spoke_width: float = 3.0
    spoke_sweep_deg: float = 55.0  # angular lean hub-to-rim; 0 = straight radial
    hub_ring_width: float = 1.5  # solid web left around the hub, radially
    rim_ring_width: float = 1.0  # solid web left inside the rim wall, radially
    window_corner_radius: float = 1.2

    groove_shoulder_margin: float = 2.0  # plain rim shoulder left on each side of the groove
    rim_chamfer: float = 0.4  # eases the two outer tread edges
    min_rim_wall: float = 3.0  # radial rim wall thickness floor, under the groove root

    web_thickness: float = 2.5  # flat disc from hub to rim
    hub_diameter: float = 10.0
    bore_chamfer: float = 0.3  # lead-in at the bore entry (hub tip)
    # Blind D-bore depth from the hub tip. The chassis mount lets 7 mm of
    # shaft into the wheel (10 mm shaft - 2 mm end wall - 1 mm wall
    # clearance, see assembly.py wheel_geometry); +1 mm so the tip never
    # bottoms out. Fit per mm is the bore_coupons.py calibration.
    bore_depth: float = 8.0

    # N20 output shaft (parts/n20_motor.py N20Dims), driving the bore shape
    shaft_diameter: float = 3.0  # 0/-0.03 on the seller drawing
    shaft_flat_across: float = 2.45  # measured; drawing says 2.5, 0/-0.1
    boss_diameter: float = 4.0  # front bearing boss the shaft exits through
    boss_length: float = 0.7

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
            self.web_thickness + 4.0,  # sanity floor: some hub to hold on to
        )

    @property
    def rim_wall_thickness(self) -> float:
        # Radial wall left under the groove root, floored for structural sense.
        return max(self.min_rim_wall, self.groove_depth + 1.0)

    @property
    def hub_top(self) -> float:
        """Z of the hub tip (the bore entry), motor side: flush with the
        rim's inboard edge, so the hub reaches as far toward the shaft as
        the rim allows without getting to the wall first."""
        return self.rim_width

    @property
    def hub_protrusion(self) -> float:
        """Hub rise above the web."""
        return self.hub_top - self.web_thickness

    @property
    def bore_floor(self) -> float:
        """Z of the blind bore's floor."""
        return self.hub_top - self.bore_depth

    @property
    def groove_wall_angle_deg(self) -> float:
        """V-groove wall angle from vertical (0 deg = vertical, self-supporting)."""
        return degrees(atan((self.groove_width / 2) / self.groove_depth))

    @property
    def rim_inner_radius(self) -> float:
        return self.rim_shoulder_diameter / 2 - self.rim_wall_thickness

    @property
    def window_inner_radius(self) -> float:
        """Radial start of the web windows, outside the hub ring."""
        return self.hub_diameter / 2 + self.hub_ring_width

    @property
    def window_outer_radius(self) -> float:
        """Radial end of the web windows, inside the rim ring."""
        return self.rim_inner_radius - self.rim_ring_width


def web_windows(d: WheelDims) -> Sketch:
    """2D cutter for the spoked web: the annulus between the hub ring and
    the rim ring, minus `spoke_count` curved spokes, corners rounded.

    Each spoke is an arc slot leaning `spoke_sweep_deg` around the axis from
    hub to rim, all in the same sense, so the wheel reads as a turbine
    rather than a cartwheel. The slots overrun both rings so the boolean
    leaves clean intersections for the fillet.
    """
    r_in, r_out = d.window_inner_radius, d.window_outer_radius
    if r_out - r_in < 2 * d.window_corner_radius + 1.0:
        raise ValueError(
            f"no room for web windows between the hub ring (r{r_in:.2f}) and the "
            f"rim ring (r{r_out:.2f}) -- drop spoke_count to 0"
        )
    windows = Circle(r_out) - Circle(r_in)
    overrun = 1.0
    r0, r1 = r_in - overrun, r_out + overrun
    sweep = radians(d.spoke_sweep_deg)
    # The mid-point sits on the chord's angular midpoint at the mean radius,
    # which bows the spoke into a gentle S-free curve.
    p0 = (r0, 0.0)
    pm = ((r0 + r1) / 2 * cos(sweep / 2), (r0 + r1) / 2 * sin(sweep / 2))
    p1 = (r1 * cos(sweep), r1 * sin(sweep))
    spoke = SlotArc(ThreePointArc(p0, pm, p1), d.spoke_width)
    for i in range(d.spoke_count):
        windows -= Rot(0, 0, 360 * i / d.spoke_count) * spoke
    return fillet(windows.vertices(), d.window_corner_radius)


def d_bore_cutter(
    shaft_diameter: float, flat_across: float, clearance: float, depth: float
) -> Part:
    """Cutter solid for the D-shaped shaft bore.

    A cylinder of `shaft_diameter / 2 + clearance` with one side flattened
    to `flat_across / 2 + clearance` from the axis, sitting on Z=0 with the
    flat facing +X. `clearance` is radial and applies to both features, so
    the flat cut DEPTH stays constant while the flat itself moves outward.
    Shared with the bore fit coupons (bore_coupons.py) so a coupon result
    transfers to the wheel unchanged.
    """
    radius = shaft_diameter / 2 + clearance
    flat_half = flat_across / 2 + clearance
    bore = Cylinder(radius=radius, height=depth, align=ALIGN_BOTTOM)
    cut_depth = radius - flat_half
    if cut_depth <= 0:
        return bore  # clearance swallowed the flat -- a plain round hole
    return bore - Pos(radius - cut_depth / 2, 0, 0) * Box(
        cut_depth, 2 * radius, depth, align=ALIGN_BOTTOM
    )


def make_wheel(d: WheelDims | None = None) -> Part:
    """Build the wheel with its web on the XY plane (Z=0 is the print bed)."""
    d = d or WheelDims()

    rim_radius = d.rim_shoulder_diameter / 2
    rim_inner_radius = d.rim_inner_radius
    if rim_inner_radius <= d.hub_diameter / 2:
        raise ValueError(
            f"rim wall (inner radius {rim_inner_radius:.2f} mm) collides with "
            f"the hub (radius {d.hub_diameter / 2:.2f} mm) -- widen the O-ring "
            "ID or shrink the cord"
        )
    if d.bore_floor < 1.0:
        raise ValueError(
            f"bore_depth {d.bore_depth:g} leaves only {d.bore_floor:.2f} mm of floor "
            "under the blind bore -- it would break through the outside face"
        )

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

    # Spoked web: windows through the base between hub ring and rim ring.
    if d.spoke_count > 0:
        wheel -= extrude(web_windows(d), amount=d.web_thickness)

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

    # Bore: blind D-shaped press-fit hole from the hub tip down. Printed
    # hub-up, it is a vertical hole with its floor at the bottom -- nothing
    # to bridge.
    wheel -= Pos(0, 0, d.bore_floor) * d_bore_cutter(
        d.shaft_diameter, d.shaft_flat_across, d.bore_clearance, d.bore_depth
    )

    # Chamfer the bore entry (the D outline at the hub tip -- arc + flat,
    # so select by size, not by GeomType) and the two outer tread edges for
    # print quality / easier shaft insertion.
    bore_entry = wheel.edges().filter_by(
        lambda e: abs(e.center().Z - d.hub_top) < 1e-6
        and e.bounding_box().size.X < d.hub_diameter / 2
    )
    wheel = chamfer(bore_entry, d.bore_chamfer)

    circles = wheel.edges().filter_by(GeomType.CIRCLE)

    def at(radius: float, z: float):
        return circles.filter_by(
            lambda e, radius=radius, z=z: (
                abs(e.radius - radius) < 1e-6 and abs(e.center().Z - z) < 1e-6
            )
        )

    rim_top_edge = at(rim_radius, d.rim_width)
    rim_bottom_edge = at(rim_radius, 0)
    wheel = chamfer(rim_top_edge + rim_bottom_edge, d.rim_chamfer)

    return wheel


if __name__ == "__main__":
    oring_id = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
    oring_cord = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    bore_clearance = (
        float(sys.argv[3]) if len(sys.argv) > 3 else WheelDims().bore_clearance
    )

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
    if dims.spoke_count:
        print(
            f"Web: {dims.spoke_count} curved spokes {dims.spoke_width:g} mm wide, "
            f"{dims.spoke_sweep_deg:g} deg sweep, windows r{dims.window_inner_radius:.1f}"
            f"-r{dims.window_outer_radius:.1f}"
        )
    print(
        f"Effective rolling diameter with tire fitted: {dims.rolling_diameter:.2f} mm "
        "(use this for chassis skid height)"
    )
    print(
        f"Hub Ø{dims.hub_diameter:g} mm x {dims.hub_protrusion:.2f} mm above the web, tip "
        f"flush with the rim's inboard edge (mounts web/spokes OUTBOARD, hub to the motor)"
    )
    print(
        f"Blind D-bore Ø{2 * (dims.shaft_diameter / 2 + bore_clearance):.2f} mm "
        f"(flat {dims.shaft_flat_across + 2 * bore_clearance:.2f} mm) "
        f"x {dims.bore_depth:g} mm deep from the hub tip, {dims.bore_floor:.2f} mm floor, "
        f"{bore_clearance:g} mm radial clearance"
    )
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {wheel.volume:.1f} mm^3")
    print("Exported wheel.stl, wheel.step and wheel_section.stl")
