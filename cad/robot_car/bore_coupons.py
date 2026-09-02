"""D-bore fit coupons for the N20 output shaft (parts library M2).

wheel.py's hub carries a D-shaped press-fit bore, but its dimensions come
from the seller's drawing, not from the shafts we actually have. Measured on
the arrived motors (2026-09-02): Ø3.0 shaft, flat 2.45 across. A first
reading of that flat came out at 2.6 -- take the SMALLER one. A caliper
across a D can only over-read (tilt the jaws, or miss the flat's deepest
line, and you measure into the round), so the minimum reading is the true
across-flat, and 2.45 also sits inside the drawing's 2.5 mm 0/-0.1 band
where 2.6 does not. Printing a full wheel per guess costs an hour and 20 g
each, so this plate isolates just the bore: five hubs, identical to the
wheel's in every dimension that matters to the fit, differing only in
clearance.

    B1  0.00   bore Ø3.00, flat 2.45   -- nominal, interference once printed
    B2  0.05   bore Ø3.10, flat 2.55   -- the old default
    B3  0.10   bore Ø3.20, flat 2.65   -- WINNER, now wheel.py's default
    B4  0.15   bore Ø3.30, flat 2.75   -- loose
    B5  0.20   bore Ø3.40, flat 2.85   -- demo_04's calibrated RUNNING fit

RESULT (green PLA Basic, X2D, 2026-09-02): B3 is a firm push-on with no
play; B4 and B5 are visibly too large. wheel.py's `bore_clearance` is now
0.10 and its shaft dimensions are the measured ones. Reprint this plate
only if the printer, nozzle or filament changes.

Clearance is radial and applies to both the round and the flat, exactly as
wheel.py applies it, so the flat's cut depth is the same at every station
(0.20 mm) and only its distance from the axis changes. B5 is included as the
known-loose end of the scale: at demo_04's measured running clearance the
round can't grip, so whatever drive it still has comes from the flat alone --
a useful reading on how much the D is doing on its own.

Each station reproduces the wheel hub, and in particular the length of
shaft the wheel ACTUALLY grips. That is not the hub's full bore: in the
assembled robot the wheel's web sits 3 mm outboard of the gearbox face (2 mm
end wall + 1 mm WALL_CLEARANCE_MM), so of the shaft's 10 mm only 7 mm
reaches the wheel, and 1 mm of that is swallowed by the web-side boss
relief. Engagement is 6.00 mm -- assembly.py's own number, imported here
rather than copied, so this plate stays honest if the chassis moves.

A station is therefore 2.5 mm web + 7.5 mm hub = 10 mm tall, with the
D-bore running Z 1.0-7.0 and a Ø4.5 relief above it. Seat the plate flat on
the gearbox face and the shaft slides 7 of its 10 mm in, grips over exactly
the 6 mm the wheel will, and its tip comes out FLUSH with the hub tip --
that flush tip is the "fully home" indicator. Entry chamfers 0.3 mm, and the
print orientation matches the wheel's (bore vertical, flat facing +X) so the
hole distorts on the printer the way the wheel's will. Stations sit 18 mm
apart on a common web, motor hanging below the plate, and carry raised
labels (0.6 mm) either side of the hub: station number above, clearance in
hundredths of a millimetre below (B3 / "10" = 0.10 mm).

What to feel for: push each station onto the shaft by hand, no vice. Right
is a firm push-on that needs deliberate force, goes fully home (shaft tip
flush with the hub tip), and shows no rotational play when you twist the
plate against a held motor. Too tight = won't start without cracking the
hub; too loose = drops on, or twists with a click of backlash before the
flat catches. Report the winning clearance back into wheel.py's
`bore_clearance`.

Worth noting while testing: that web-side Ø4.5 relief costs a millimetre of
grip for nothing in the current assembly -- the motor's Ø4 boss is 3 mm away
at the wall, nowhere near the wheel. Deleting it would buy 7 mm of
engagement instead of 6. Left alone for now (it is also the bore's lead-in
chamfer), but if the winning fit turns out marginal, that is the first
knob.

Measure two or three shafts before trusting one number -- the drawing's
0/-0.1 band on the flat is a whole step of this sweep, and a unit at 2.4
behaves differently from one at 2.5. The bore flat is cut to the measured
2.45 plus the station's clearance, so a slightly fatter shaft just presses
0.05 into the PLA, which is fine on a flat that only has to key the wheel
against rotation.

Run with:  uv run demo_06/bore_coupons.py [shaft_dia] [flat_across]
e.g.       uv run demo_06/bore_coupons.py 3.0 2.45
Exports bore_coupons.stl and bore_coupons.step into the cwd.
"""

import sys

from build123d import (
    Align,
    Box,
    Cylinder,
    FontStyle,
    GeomType,
    Part,
    Plane,
    Pos,
    Text,
    chamfer,
    export_step,
    export_stl,
    extrude,
)

from assembly import wheel_geometry
from chassis import ChassisDims
from n20_motor import N20Dims
from wheel import ALIGN_BOTTOM, WheelDims, d_bore_cutter

# Shaft as MEASURED on the motors on hand (2026-09-02). The flat read 2.6 on
# a first pass and 2.45 on a second -- the smaller reading wins (a caliper
# across a D over-reads when it misses the deepest line) and agrees with the
# drawing's 2.5 mm 0/-0.1.
SHAFT_DIAMETER = 3.0
SHAFT_FLAT_ACROSS = 2.45

CLEARANCES = (0.0, 0.05, 0.10, 0.15, 0.20)  # radial, applied to round + flat
PITCH = 18.0  # station spacing; > the Ø12 motor can so units clear each other
PLATE_WIDTH = 28.0
LABEL_OFFSET_Y = 9.0  # label strips either side of the Ø10 hub
TEXT_HEIGHT = 0.6  # raised above the web face

# Labels are BOLD at 8 mm, and short (station "B3" over clearance in
# hundredths, "10"), because round 1 printed at 4.5 mm regular and came out
# illegible: those glyph strokes are ~0.37 mm wide, under a single 0.4 mm
# extrusion, so the slicer drops or blobs them. Bold at 8 mm gives ~1.0 mm
# strokes (2.5 extrusions). MIN_STROKE_WIDTH enforces it -- keep labels to
# two characters so they still fit inside PITCH.
RELIEF_DIAMETER = 4.5  # the printed coupon's boss relief, see station_grip
FONT = "Arial"
FONT_STYLE = FontStyle.BOLD
FONT_SIZE = 8.0
NOZZLE_WIDTH = 0.4
MIN_STROKE_WIDTH = 2 * NOZZLE_WIDTH


def label(text: str):
    """Text face for a coupon label, refusing strokes too thin to print.

    Stroke width is estimated as 2 x area / perimeter, which for glyph
    strokes (long thin faces) converges on the stroke's own width.
    """
    face = Text(text, font_size=FONT_SIZE, font=FONT, font_style=FONT_STYLE)
    area = sum(f.area for f in face.faces())
    perimeter = sum(e.length for e in face.edges())
    stroke = 2 * area / perimeter
    if stroke < MIN_STROKE_WIDTH:
        raise ValueError(
            f"label {text!r} has ~{stroke:.2f} mm strokes, under the "
            f"{MIN_STROKE_WIDTH:.2f} mm floor -- it will print illegibly; "
            "raise FONT_SIZE or use a bolder face"
        )
    if face.bounding_box().size.X > PITCH:
        raise ValueError(f"label {text!r} is wider than the {PITCH:g} mm pitch")
    return face


def station_grip(d: WheelDims) -> tuple[float, float, float]:
    """(bore start Z, engagement, hub top Z) for one station.

    The first two come straight from assembly.py's wheel_geometry -- the
    length of shaft the mounted wheel really grips, once the end wall and
    WALL_CLEARANCE_MM have eaten into the shaft's 10 mm. The hub top is set
    to the shaft length so a fully seated coupon shows the shaft tip flush
    with the hub tip.
    """
    g = wheel_geometry(1, ChassisDims(), d)
    hub_top = N20Dims().shaft_length
    # Pinned to the geometry PRINTED on 2026-09-02 (wheel then had a 1 mm
    # web-side Ø4.5 boss relief in front of the D-bore). The wheel has since
    # gone spokes-out with a blind bore straight from the hub tip, so
    # assembly.py now reports grip_start 0 / 7 mm; the calibrated 0.10 mm
    # clearance carries over unchanged -- it is a per-mm fit, not a length.
    grip_start, engagement = 1.0, g["engagement"] - 1.0
    if grip_start + engagement > hub_top:
        raise ValueError("D-bore runs past the shaft tip -- check assembly.py")
    if engagement <= 0:
        raise ValueError("assembly reports no D-bore engagement at all")
    return grip_start, engagement, hub_top


def make_coupons(
    shaft_diameter: float = SHAFT_DIAMETER,
    flat_across: float = SHAFT_FLAT_ACROSS,
    clearances: tuple[float, ...] = CLEARANCES,
) -> tuple[Part, WheelDims]:
    """One web plate carrying a labelled hub per clearance value."""
    d = WheelDims(shaft_diameter=shaft_diameter, shaft_flat_across=flat_across)
    grip_start, engagement, hub_top = station_grip(d)

    if d.hub_diameter >= PLATE_WIDTH - 2 * (LABEL_OFFSET_Y - FONT_SIZE / 2):
        raise ValueError("hub overlaps the label strips -- widen PLATE_WIDTH")
    if PITCH <= d.hub_diameter:
        raise ValueError("stations would merge -- raise PITCH")

    length = len(clearances) * PITCH
    plate = Box(length, PLATE_WIDTH, d.web_thickness, align=ALIGN_BOTTOM)

    xs = [(i - (len(clearances) - 1) / 2) * PITCH for i in range(len(clearances))]

    for x in xs:
        plate += Pos(x, 0, d.web_thickness) * Cylinder(
            radius=d.hub_diameter / 2,
            height=hub_top - d.web_thickness,
            align=ALIGN_BOTTOM,
        )

    for x, clearance in zip(xs, clearances):
        # Ø4.5 relief below the D-bore (the wheel's web-side boss relief,
        # here taking the motor's Ø4 x 0.7 front boss so the plate seats flat
        # on the gearbox face) and above it (free space for the shaft past
        # the engagement length, ending flush with the hub tip).
        for z0, z1 in ((0.0, grip_start), (grip_start + engagement, hub_top)):
            plate -= Pos(x, 0, z0) * Cylinder(
                radius=RELIEF_DIAMETER / 2,
                height=z1 - z0,
                align=ALIGN_BOTTOM,
            )
        plate -= Pos(x, 0, grip_start) * d_bore_cutter(
            shaft_diameter, flat_across, clearance, engagement
        )

    # Chamfer every bore entry at once (all reliefs share radius and Z).
    circles = plate.edges().filter_by(GeomType.CIRCLE)

    def at(radius: float, z: float):
        return circles.filter_by(
            lambda e, radius=radius, z=z: (
                abs(e.radius - radius) < 1e-6 and abs(e.center().Z - z) < 1e-6
            )
        )

    entries = at(RELIEF_DIAMETER / 2, 0) + at(RELIEF_DIAMETER / 2, hub_top)
    plate = chamfer(entries, d.bore_chamfer)

    # Station number above the hub, clearance in hundredths of a mm below,
    # both raised off the web.
    for i, (x, clearance) in enumerate(zip(xs, clearances), start=1):
        for line, y in ((f"B{i}", LABEL_OFFSET_Y), (f"{clearance * 100:02.0f}", -LABEL_OFFSET_Y)):
            placed = Plane.XY.offset(d.web_thickness) * Pos(x, y) * label(line)
            plate += extrude(placed, amount=TEXT_HEIGHT)

    return plate, d


if __name__ == "__main__":
    shaft_diameter = float(sys.argv[1]) if len(sys.argv) > 1 else SHAFT_DIAMETER
    flat_across = float(sys.argv[2]) if len(sys.argv) > 2 else SHAFT_FLAT_ACROSS

    plate, d = make_coupons(shaft_diameter, flat_across)
    grip_start, engagement, hub_top = station_grip(d)

    print(
        f"D-bore fit coupons for a Ø{shaft_diameter:g} mm shaft with a "
        f"{flat_across:g} mm flat, hub Ø{d.hub_diameter:g} mm x {hub_top:g} mm tall"
    )
    print(
        f"  D-bore Z {grip_start:.2f}-{grip_start + engagement:.2f} = "
        f"{engagement:.2f} mm engagement (assembly.py's figure for the mounted "
        f"wheel); {hub_top - N20Dims().boss_length:.2f} of the shaft's "
        f"{N20Dims().shaft_length:g} mm sits inside the coupon, tip flush with the "
        "hub tip"
    )
    for i, clearance in enumerate(CLEARANCES, start=1):
        bore = shaft_diameter + 2 * clearance
        flat = flat_across + 2 * clearance
        wall = (d.hub_diameter - bore) / 2
        print(
            f"  B{i}: clearance {clearance:.2f} -> bore Ø{bore:.2f}, "
            f"flat {flat:.2f} across, hub wall {wall:.2f} mm"
        )

    export_stl(plate, "bore_coupons.stl")
    export_step(plate, "bore_coupons.step")

    # Half-section through the bore axes to inspect the reliefs and chamfers.
    section = plate & Box(400, 400, 400, align=(Align.CENTER, Align.MIN, Align.MIN))
    export_stl(section, "bore_coupons_section.stl")

    bbox = plate.bounding_box()
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {plate.volume / 1000:.2f} cm^3")
    print("Exported bore_coupons.stl, bore_coupons.step and bore_coupons_section.stl")
