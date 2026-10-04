"""Reference model of the XT60 connector pair: the male plug on the car's
harness pigtail (wiring: pack -> XT60 -> fuse -> switch, see
cad/robot_car/WIRING.md) and the female on the B2 pack's lead.

This is a *reference* part: it models the bought hardware so a holder can be
designed around it. It is not meant to be printed.

The car's male is a plain XT60 (not the sheathed XT60H) with one sleeve of
heat-shrink over each solder cup. Calipered on it: the housing is 15.7 x 8.1
and 16.4 long, rim to rear face, and each sleeve is about 5 across. A
moulded + and - stand proud of its two short ends near the wire end and
make it 16.1 wide there, over about 1 mm of its length (marks). The
female is taken to share the male's outline. Everything else is the Amass
XT60-M / XT60-F datasheet's (2021V1) where it gives it -- the female 21.30
long with its cups -- or read off that drawing at its scale (~27.8 px/mm):
cups 4.6 long, the female's nose 7.8 long on an 8.0 mm body, the keying
chamfers 3.0 x 3.0 at 45 deg on both corners of one 8.1 mm end, pin pitch
7.2.

Gender goes by the metal: the MALE has the pins, inside a shroud whose
outline is the housing's. The female's nose (the two socket tubes) goes into
that shroud, until the female's body face meets the male's rim. So the
male's front face is entirely covered by the mated female, and the male has
no other face that points forward.

Frame (both parts, mated): mating axis X, the male's rim on x = 0 with its
housing toward -X, the female toward +X. Lying flat: the 15.7 mm width
along Y, the 8.1 mm height along Z from z = 0, the chamfered end at -Y. By the
common RC convention the chamfered side is (+) and the square side (-);
the housings carry their own marks, which win.

Run with:  uv run parts/xt60.py   (exports xt60_pair.stl, gitignored)
"""

from dataclasses import dataclass

from build123d import Axis, Box, Cylinder, Part, Polyline, Pos, export_stl, extrude, make_face
from shapely.geometry import Polygon


@dataclass
class Xt60Dims:
    width: float = 15.7  # Y, calipered (datasheet 16.0)
    height: float = 8.1  # Z, calipered
    chamfer: float = 3.0  # both corners of the -Y end, 45 deg
    corner_r: float = 0.5  # est, the square end's corners
    pitch: float = 7.2  # pin centres, along Y, datasheet

    # male (pins): rim at x = 0, housing back to -housing_len
    male_len: float = 16.4  # housing, rim to rear face, calipered
    shroud_wall: float = 0.7
    shroud_depth: float = 8.0  # how far the female's nose goes in
    pin_d: float = 3.5
    pin_recess: float = 1.0  # pin tips stand this far back from the rim
    # the moulded + (chamfered end) and - (square end), near the wire end
    mark_h: float = 0.2  # proud of the end face: 16.1 across, calipered
    mark_len: float = 1.2  # along X, ~1 calipered
    mark_tall: float = 1.6  # along Z (est), centred on the pins
    mark_from_rear: float = 2.5  # centre to the rear face (est)

    # female (sockets): body face at x = 0 when mated, nose toward -X
    female_body_len: float = 8.0
    nose_len: float = 7.8
    nose_inset: float = 0.9  # nose outline = housing outline inset by this
    socket_d: float = 3.7

    cup_len: float = 4.6  # solder cups behind each housing
    cup_d: float = 4.3
    # pigtail: one heat-shrink sleeve over each cup and the wire's start
    shrink_d: float = 5.0  # calipered, about
    shrink_len: float = 10.0  # from the housing's rear face (est)
    wire_d: float = 3.4  # 14 AWG silicone

    @property
    def axis_z(self) -> float:
        return self.height / 2


def outline(d: Xt60Dims, inset: float = 0.0) -> Polygon:
    """The housing's YZ outline (chamfered end at -Y), optionally inset."""
    w, h, c = d.width / 2, d.height, d.chamfer
    p = Polygon([(w, 0), (-w + c, 0), (-w, c), (-w, h - c), (-w + c, h), (w, h)])
    return p.buffer(-inset, join_style="mitre") if inset else p


def yz_prism(poly: Polygon, x0: float, x1: float) -> Part:
    """Extrude a YZ polygon along X from x0 to x1."""
    pts = list(poly.exterior.coords)[:-1]
    face = make_face(Polyline(*[(0, y, z) for y, z in pts], close=True))
    return Pos(min(x0, x1), 0, 0) * extrude(face, amount=abs(x1 - x0), dir=(1, 0, 0))


def _x_cylinder(d_: float, x0: float, x1: float, y: float, z: float) -> Part:
    c = Cylinder(radius=d_ / 2, height=abs(x1 - x0)).rotate(Axis.Y, 90)
    return Pos((x0 + x1) / 2, y, z) * c


def _cups(d: Xt60Dims, x_face: float, direction: int) -> Part:
    """Two solder cups behind a housing face, the last 60 % cut open on top."""
    cups = Part()
    x_end = x_face + direction * d.cup_len
    for s in (-1, 1):
        y = s * d.pitch / 2
        cup = _x_cylinder(d.cup_d, x_face, x_end, y, d.axis_z)
        x_open = x_face + direction * 0.4 * d.cup_len
        cut = Pos((x_open + x_end) / 2 + direction * 0.5, y, d.axis_z + d.cup_d / 2) * Box(
            abs(x_end - x_open) + 1, d.cup_d + 1, d.cup_d)
        cup -= cut
        cup -= _x_cylinder(d.cup_d - 1.2, x_open, x_end + direction, y, d.axis_z)
        cups += cup
    return cups


def make_male(d: Xt60Dims | None = None) -> Part:
    """The male housing with its pins and solder cups (no wires)."""
    d = d or Xt60Dims()
    body = yz_prism(outline(d), -d.male_len, 0)
    body -= yz_prism(outline(d, d.shroud_wall), -d.shroud_depth, 0.1)
    for s in (-1, 1):
        body += _x_cylinder(d.pin_d, -d.shroud_depth - 0.1, -d.pin_recess, s * d.pitch / 2, d.axis_z)
        # the + / - mark on this short end, as a pad
        x = -d.male_len + d.mark_from_rear
        y = s * (d.width / 2 + d.mark_h / 2 - 0.01)
        body += Pos(x, y, d.axis_z) * Box(d.mark_len, d.mark_h + 0.02, d.mark_tall)
    return body + _cups(d, -d.male_len, -1)


def make_female(d: Xt60Dims | None = None) -> Part:
    """The female housing, nose into the male's shroud, in the mated frame."""
    d = d or Xt60Dims()
    body = yz_prism(outline(d), 0, d.female_body_len)
    nose = yz_prism(outline(d, d.nose_inset), -d.nose_len, 0.01)
    for s in (-1, 1):
        nose -= _x_cylinder(d.socket_d, -d.nose_len - 0.1, -1.0, s * d.pitch / 2, d.axis_z)
    return body + nose + _cups(d, d.female_body_len, +1)


def make_shrink(d: Xt60Dims, x_face: float, direction: int) -> list[Part]:
    """Heat-shrink sleeves over the two cups behind a housing face; [-Y, +Y]."""
    x_end = x_face + direction * d.shrink_len
    return [_x_cylinder(d.shrink_d, x_face, x_end, s * d.pitch / 2, d.axis_z) for s in (-1, 1)]


if __name__ == "__main__":
    d = Xt60Dims()
    pair = make_male(d) + make_female(d)
    export_stl(pair, "xt60_pair.stl")
    for name, part in (("male", make_male(d)), ("female", make_female(d))):
        bb = part.bounding_box()
        print(f"XT60 {name}: {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f} mm "
              f"(x {bb.min.X:+.1f}..{bb.max.X:+.1f})")
    print("Exported xt60_pair.stl")
