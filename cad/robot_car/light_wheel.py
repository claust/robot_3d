"""Light Ø80 lawn wheel for the N20 gearmotor, 30 mm across the tread.

Hub -> spokes -> inner rim (the car side) -> thin bars across the tread ->
outer rim (the far side, no spokes). The bars are the only thing that
touches the ground: grass pushes up between them and they bite. They
stand proud of both rims as cleats, or stay flush and carry spikes.

Ø80 at the bar or spike tips is the diameter that levels the plate on the
bought swivel caster on a hard floor (assembly.py check 1: the caster
stands 10.5 mm below a Ø59 wheel's contact, and the axle is at Z=9).
Nothing on the car reaches past the plate edge inside a Ø84 disc at the
wheel position except the motor shaft, so the chassis needs no change.

Layout (wheel frame: Z=0 is the INNER face, toward the car, and the print
bed; +Z runs outward across the tread):

- hub: Ø`hub_diameter` x `hub_length`; the shaft enters from the bed side
  into wheel.py's blind D-bore (`d_bore_cutter`, the 0.10 mm press fit
  from bore_coupons.py), `bore_depth` deep. The bore's blind end is a
  Ø3.2 ceiling -- a bridge too short to matter.
- spokes: `spoke_count` spokes `spoke_height` tall, hub to inner rim,
  roots rounded.
- inner rim: `rim_t` radial x `inner_rim_height`, outer face at
  `rim_diameter`, on the bed with the spokes.
- bars: `bar_count` bars `bar_t` thick (measured in the print slice),
  rooted in the rims' inner face, running the full tread width. The
  pattern is the design choice -- see `bars`.
- outer rim: like the inner rim, `outer_rim_height` tall, at the top of
  the print. It rests on the bar ends, so the bars are spaced to leave it
  no bridge longer than `max_bridge`.

Every horizontal slice of the wheel is supported by the one below it,
apart from those short bridges under the outer rim. Slanted bars lean at
most `bar_lean_deg` and spike flanks slope at 45 degrees or steeper.

Run with:  uv run robot_car/light_wheel.py [variant ...] [--plate]
Writes light_wheel_<variant>.stl (gitignored) and prints mass per variant;
--plate also lays them out 2 x 2 in light_wheel_plate.stl (a name given
twice lays out two copies).
"""

import sys
from dataclasses import dataclass, replace
from math import cos, degrees, pi, radians, sin, tan

from build123d import (
    Align,
    Circle,
    Cylinder,
    Part,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Sketch,
    SlotArc,
    ThreePointArc,
    Vector,
    chamfer,
    export_stl,
    extrude,
    fillet,
    loft,
)

from wheel import d_bore_cutter

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
PLA_DENSITY = 1.24  # g/cm^3, PLA Basic


@dataclass
class LightWheelDims:
    """All dimensions in mm."""

    outer_diameter: float = 80.0  # bar or spike tips: levels the plate on the caster
    tread_width: float = 30.0  # inner rim's car-side face to outer rim's far face

    rim_diameter: float = 76.0  # both rims' outer face; cleat bars stand 2 mm proud
    rim_t: float = 2.0  # radial
    inner_rim_height: float = 4.0  # carries the spokes
    outer_rim_height: float = 2.5

    bar_style: str = "straight"  # straight | chevron | helix | spikes
    bar_count: int = 24
    bar_t: float = 1.0  # across the bar, in the horizontal print slice
    bar_lean_deg: float = 30.0  # chevron, helix: bar angle from the axis; < 0 mirrors
    max_bridge: float = 9.0  # longest span the outer rim may bridge between bar ends
    # spikes: pyramids on flush bars, rows staggered bar to bar
    spike_base_w: float = 2.6  # round the wheel
    spike_base_h: float = 7.0  # across the tread; >= 2 x length + tip keeps 45 deg
    spike_tip: float = 0.6  # flat at the tip, square

    spoke_style: str = "straight"  # straight | curved
    spoke_count: int = 6
    spoke_width: float = 2.4
    spoke_height: float = 4.0
    spoke_sweep_deg: float = 50.0  # curved: lean hub-to-rim; < 0 mirrors
    spoke_root_radius: float = 1.5

    hub_diameter: float = 10.0
    hub_length: float = 10.0
    bore_depth: float = 8.0  # wheel.py WheelDims: 7 mm of shaft + 1
    bore_clearance: float = 0.10  # bore_coupons.py winner
    bore_chamfer: float = 0.4  # on the bed face: also eats the elephant foot
    shaft_diameter: float = 3.0
    shaft_flat_across: float = 2.45

    @property
    def tip_radius(self) -> float:
        return self.outer_diameter / 2

    @property
    def rim_outer_radius(self) -> float:
        return self.rim_diameter / 2

    @property
    def rim_inner_radius(self) -> float:
        return self.rim_diameter / 2 - self.rim_t

    @property
    def hub_radius(self) -> float:
        return self.hub_diameter / 2


# --- 2D helpers --------------------------------------------------------------


def ring(r_in: float, r_out: float) -> Sketch:
    return Circle(r_out) - Circle(r_in)


def bar(p0: tuple[float, float], p1: tuple[float, float], w: float,
        overrun: float = 0.0) -> Sketch:
    """A straight bar `w` wide from p0 to p1, extended by `overrun` past
    both ends so it fuses into whatever it joins."""
    a, b = Vector(*p0, 0), Vector(*p1, 0)
    u = (b - a).normalized()
    mid = (a + b) / 2
    angle = Vector(1, 0, 0).get_signed_angle(u, Vector(0, 0, 1))
    return Pos(mid.X, mid.Y) * Rot(0, 0, angle) * Rectangle((b - a).length + 2 * overrun, w)


def arc_bar(r0: float, r1: float, sweep_deg: float, w: float) -> Sketch:
    """A curved bar from radius r0 at angle 0 to radius r1 at `sweep_deg`,
    bowed through the mean radius at half the sweep."""
    s = radians(sweep_deg)
    rm = (r0 + r1) / 2
    return SlotArc(ThreePointArc((r0, 0), (rm * cos(s / 2), rm * sin(s / 2)),
                                 (r1 * cos(s), r1 * sin(s))), w)


def polar_copies(shape, n: int):
    out = None
    for i in range(n):
        c = Rot(0, 0, 360 * i / n) * shape
        out = c if out is None else out + c
    return out


def windows_of(r_in: float, r_out: float, solid: Sketch, root_radius: float) -> Sketch:
    """The openings between `solid` members inside the ring r_in..r_out,
    corners rounded so each member meets its rims with a root radius."""
    windows = ring(r_in, r_out) - solid
    out = Sketch()
    for face in windows.faces():
        try:
            out += fillet(face.vertices(), root_radius)
        except ValueError:  # OCC's 2D fillet gives up on some arc/line corners
            out += fillet(face.vertices(), root_radius / 2)
    return out


# --- tread ---------------------------------------------------------------------


def tread_bar(d: LightWheelDims, z0: float, z1: float, turn0: float, turn1: float,
              r1: float) -> Part:
    """One bar from z0 to z1, its slice turning from `turn0` to `turn1`
    degrees about the axis on the way up. The slice is a radial rectangle
    from the rims' inner face out to r1."""
    r0 = d.rim_inner_radius
    slice_ = Pos((r0 + r1) / 2, 0) * Rectangle(r1 - r0, d.bar_t)
    if turn0 == turn1:
        return Rot(0, 0, turn0) * Pos(0, 0, z0) * extrude(slice_, z1 - z0)
    steps = max(2, int(abs(turn1 - turn0) / 4) + 1)  # a section every ~4 deg
    sections = [
        Pos(0, 0, z0 + (z1 - z0) * i / steps)
        * Rot(0, 0, turn0 + (turn1 - turn0) * i / steps) * slice_
        for i in range(steps + 1)
    ]
    # ruled: flat facets between sections. OCC cannot fuse smooth lofted
    # bars to each other reliably and returns nothing.
    return loft(sections, ruled=True)


def spike(d: LightWheelDims, z: float) -> Part:
    """A pyramid spike on the +X bar, centred at height z: base on the bar
    (sunk 0.5 mm into it), flat square tip at `outer_diameter`."""
    r0, r1 = d.rim_outer_radius - 0.5, d.tip_radius
    if (d.spike_base_h - d.spike_tip) / 2 < r1 - r0 - 0.5:
        raise ValueError("spike flank flatter than 45 degrees -- raise spike_base_h")

    def section(r: float, w: float, h: float):
        return Plane(origin=(r, 0, z), x_dir=(0, 1, 0), z_dir=(1, 0, 0)) * Rectangle(w, h)

    return loft([section(r0, d.spike_base_w, d.spike_base_h),
                 section(r1, d.spike_tip, d.spike_tip)])


def bars(d: LightWheelDims) -> Part:
    """The bars across the tread, rim to rim.

    - straight: paddles along the axis -- the most bite either way, but
      on a hard floor the wheel rolls from bar to bar.
    - chevron: a V across the tread, tractor-tyre style. The wheels on
      the car's two sides face opposite ways, so each side needs the
      other's mirror image for the Vs to point the same way (`mirrored`).
    - helix: every bar slanted the same way; the slant also braces the
      outer rim against twisting relative to the inner one.
    - spikes: straight bars flush with the rims, each carrying pyramid
      spikes, rows staggered bar to bar.
    Every style's bars end at the outer rim once per pitch.
    """
    W, n = d.tread_width, d.bar_count
    r_mid = (d.rim_inner_radius + d.tip_radius) / 2
    turn = degrees(W * tan(radians(d.bar_lean_deg)) / r_mid)  # over the full width
    tip = d.tip_radius
    if d.bar_style == "straight":
        one = tread_bar(d, 0, W, 0, 0, tip)
    elif d.bar_style == "chevron":
        one = tread_bar(d, 0, W / 2, 0, turn / 2, tip) + tread_bar(d, W / 2, W, turn / 2, 0, tip)
    elif d.bar_style == "helix":
        one = tread_bar(d, 0, W, 0, turn, tip)
    elif d.bar_style == "spikes":
        flush = tread_bar(d, 0, W, 0, 0, d.rim_outer_radius)
        rows = (W / 3, 2 * W / 3), (W / 2,)
        out = None
        for i in range(n):
            row = flush + sum((spike(d, z) for z in rows[i % 2]), Part())
            row = Rot(0, 0, 360 * i / n) * row
            out = row if out is None else out + row
        return out
    else:
        raise ValueError(f"unknown bar_style {d.bar_style!r}")
    out = polar_copies(one, n)
    if out.volume < 0.8 * n * one.volume:
        raise RuntimeError(f"{d.bar_style} bar union lost bars")
    return out


def outer_rim_bridge(d: LightWheelDims) -> float:
    """Span the outer rim bridges between neighbouring bar ends."""
    r_mid = d.rim_outer_radius - d.rim_t / 2
    return 2 * pi * r_mid / d.bar_count - d.bar_t


def tread(d: LightWheelDims) -> Part:
    span = outer_rim_bridge(d)
    if span > d.max_bridge:
        raise ValueError(f"outer rim would bridge {span:.1f} mm between bars "
                         f"(max {d.max_bridge:g}) -- raise bar_count")
    inner = extrude(ring(d.rim_inner_radius, d.rim_outer_radius), d.inner_rim_height)
    outer = Pos(0, 0, d.tread_width - d.outer_rim_height) * extrude(
        ring(d.rim_inner_radius, d.rim_outer_radius), d.outer_rim_height)
    return inner + outer + bars(d)


# --- spokes, hub ---------------------------------------------------------------


def spoke_web(d: LightWheelDims) -> Part:
    r_h, r_r = d.hub_radius, d.rim_inner_radius
    ov = 1.0
    if d.spoke_style == "straight":
        spoke = bar((r_h, 0), (r_r, 0), d.spoke_width, ov)
    elif d.spoke_style == "curved":
        spoke = arc_bar(r_h - ov, r_r + ov, d.spoke_sweep_deg, d.spoke_width)
    else:
        raise ValueError(f"unknown spoke_style {d.spoke_style!r}")
    windows = windows_of(r_h, r_r, polar_copies(spoke, d.spoke_count), d.spoke_root_radius)
    return extrude(ring(r_h, r_r) - windows, d.spoke_height)


def make_light_wheel(d: LightWheelDims | None = None) -> Part:
    """Build the wheel inner face down on Z=0 (the print bed)."""
    d = d or LightWheelDims()
    if d.hub_length - d.bore_depth < 1.0:
        raise ValueError("the blind bore would break through the hub's far end")

    hub = Cylinder(d.hub_radius, d.hub_length, align=ALIGN_BOTTOM)
    wheel = Part() + hub + spoke_web(d) + tread(d)

    wheel -= d_bore_cutter(d.shaft_diameter, d.shaft_flat_across,
                           d.bore_clearance, d.bore_depth)
    bore_entry = wheel.edges().filter_by(
        lambda e: abs(e.center().Z) < 1e-6
        and Vector(e.center().X, e.center().Y).length < d.hub_radius / 2)
    return chamfer(bore_entry, d.bore_chamfer)


def mirrored(d: LightWheelDims) -> LightWheelDims:
    """The mirror image of `d`: bars and spokes lean the other way. The
    D-bore is symmetric about its flat, so it fits the same shaft."""
    return replace(d, bar_lean_deg=-d.bar_lean_deg, spoke_sweep_deg=-d.spoke_sweep_deg)


VARIANTS: dict[str, LightWheelDims] = {
    "A": LightWheelDims(bar_style="straight", spoke_style="straight"),
    "B": LightWheelDims(bar_style="chevron", spoke_style="curved", spoke_count=5),
    "C": LightWheelDims(bar_style="helix", spoke_style="straight"),
    "D": LightWheelDims(bar_style="spikes", rim_diameter=74.0,
                        spoke_style="curved", spoke_count=5),
}
VARIANTS["B-mirror"] = mirrored(VARIANTS["B"])  # B for the car's right side


def mass_g(part: Part) -> float:
    return part.volume / 1000 * PLA_DENSITY


if __name__ == "__main__":
    plate = "--plate" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(VARIANTS)
    pitch = max(VARIANTS[n].outer_diameter for n in names) + 6.0
    plate_part, built = Part(), {}
    for i, name in enumerate(names):  # a name given twice lays out two copies
        d = VARIANTS[name]
        if name in built:
            plate_part += Pos((i % 2 - 0.5) * pitch, (0.5 - i // 2) * pitch, 0) * built[name]
            continue
        wheel = built[name] = make_light_wheel(d)
        export_stl(wheel, f"light_wheel_{name}.stl")
        plate_part += Pos((i % 2 - 0.5) * pitch, (0.5 - i // 2) * pitch, 0) * wheel
        print(f"{name}: {d.bar_count} {d.bar_style} bars, {d.spoke_count} "
              f"{d.spoke_style} spokes, outer rim bridges {outer_rim_bridge(d):.1f} mm -- "
              f"{wheel.volume:.0f} mm^3, {mass_g(wheel):.1f} g solid PLA, "
              f"valid={wheel.is_valid}, solids={len(wheel.solids())}")
    if plate:
        export_stl(plate_part, "light_wheel_plate.stl")
        print(f"Plate: {len(plate_part.solids())} wheels, "
              f"{mass_g(plate_part):.1f} g -> light_wheel_plate.stl")
