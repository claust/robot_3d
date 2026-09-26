"""Reference model of the MP1584EN buck converter module (parts library
P1, see parts/p1.html).

This is a *reference* part — it models the bought hardware so a robot
chassis can be designed around it. It is not meant to be printed.

Board 22.5 x 17 mm, calipered on the car's boards (the seller lists 22).
Component positions are read off a photo of one of those boards (est):
the MP1584EN (SOP-8), the 4R7 shielded inductor, the SS34 Schottky diode
along one long edge at the IN end, a small SMD trimpot near the other long
edge at the OUT end, and a few 1206 caps and small passives. Four pads on
each short edge, in two 2.54 mm pairs, one pair at each corner: IN+/IN- on
one short edge, OUT+/OUT- on the other.

The car carries the boards COMPONENTS DOWN: the bare side is up, with a
2-pin male header soldered through every corner pad pair from that side
(plastic and collar on the bare side, pins up for Dupont housings, solder
joints among the components underneath). Whatever holds the board can
reach over its bare top anywhere clear of the corner headers; under it,
it has to miss the components.

Frames. make_mp1584() builds the COMPONENT side up, as the photo shows it:
PCB on the XY plane, origin at its centre, the 22.5 mm axis X with the IN
pads at -X, the diode's long edge at +Y. mounted=True returns the board
as the car carries it, flipped about X: bare side and headers up,
components down, IN still at -X, the diode edge at -Y.

Run with:  uv run parts/p1_mp1584.py
Exports p1_mp1584.stl and p1_mp1584.step (gitignored), mounted.
"""

from dataclasses import dataclass

from build123d import Align, Axis, Box, Cylinder, Part, Pos, export_step, export_stl

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_TOP = (Align.CENTER, Align.CENTER, Align.MAX)
ALIGN_CENTER = (Align.CENTER, Align.CENTER, Align.CENTER)


@dataclass
class Mp1584Dims:
    """All dimensions in mm, component-side frame (module docstring).
    Components are (x, y, size_x, size_y, height) -- est, read off a photo
    of the car's board -- unless noted."""

    board_length: float = 22.5  # X, calipered
    board_width: float = 17.0  # Y, calipered
    board_thickness: float = 1.6  # est, standard 1.6 mm PCB

    # pads: one 2.54 mm pair at each corner of both short edges
    pad_diameter: float = 1.2  # est
    pad_x: float = 9.75  # est, +-, pad centres from the board centre
    pad_ys: tuple = (6.74, 4.2, -4.46, -7.0)  # est

    diode: tuple = (-2.87, 6.4, 6.6, 2.6, 2.3)  # SS34, SMA, along the +Y edge
    ic: tuple = (-3.8, 0.5, 5.1, 6.0, 1.6)  # MP1584EN SOP-8, leads included
    inductor: tuple = (3.97, 1.86, 6.8, 7.0, 4.5)  # 4R7, height est
    trimpot: tuple = (4.18, -6.14, 4.5, 3.05, 2.0)  # small SMD, 0.85 from the -Y edge
    passives: tuple = (-4.5, -6.0, 6.5, 2.85, 0.8)  # C3/R3/R4/R5 strip along -Y
    cap_in: tuple = (-9.6, -0.3, 1.8, 3.2, 1.6)  # 1206 between the IN pads
    cap_out: tuple = (9.85, -0.8, 1.6, 3.3, 1.6)  # 1206 between the OUT pads

    # 2-pin male header on each pad pair, from the bare side
    header_base_h: float = 5.0  # est: collar + plastic above the bare side
    header_pin_up: float = 5.0  # est, above the plastic
    header_tail: float = 2.0  # est, below the component side with its solder
    dupont_h: float = 14.0  # est, a housing pushed on over the pins


def make_mp1584(dims: Mp1584Dims | None = None, with_headers: bool = False,
                with_dupont: bool = False, mounted: bool = False) -> Part:
    """Build the module (module docstring, Frames). with_headers adds the
    corner headers the car's boards carry; with_dupont a housing on each."""
    d = dims or Mp1584Dims()
    t = d.board_thickness
    board = Box(d.board_length, d.board_width, t, align=ALIGN_CENTER)
    for x, y, sx, sy, h in (d.diode, d.ic, d.inductor, d.trimpot, d.passives,
                            d.cap_in, d.cap_out):
        board += Pos(x, y, t / 2) * Box(sx, sy, h, align=ALIGN_BOTTOM)

    for x in (-d.pad_x, d.pad_x):  # -X: IN pads, +X: OUT pads
        for y in d.pad_ys:
            board -= Pos(x, y, 0) * Cylinder(radius=d.pad_diameter / 2, height=t * 2,
                                             align=ALIGN_CENTER)
        if not with_headers:
            continue
        for pair in (d.pad_ys[:2], d.pad_ys[2:]):
            yc = sum(pair) / 2
            bare = -t / 2
            board += Pos(x, yc, bare) * Box(2.54, 5.08, d.header_base_h, align=ALIGN_TOP)
            top = bare - d.header_base_h
            if with_dupont:
                board += Pos(x, yc, top) * Box(2.54, 5.08, d.dupont_h, align=ALIGN_TOP)
            for y in pair:  # through the pad hole, tail among the components
                board += Pos(x, y, t / 2 + d.header_tail) * Box(
                    0.64, 0.64, d.header_tail + t + d.header_base_h + d.header_pin_up,
                    align=ALIGN_TOP)

    return board.rotate(Axis.X, 180) if mounted else board


if __name__ == "__main__":
    module = make_mp1584(with_headers=True, mounted=True)
    export_stl(module, "p1_mp1584.stl")
    export_step(module, "p1_mp1584.step")

    d = Mp1584Dims()
    bbox = module.bounding_box()
    print("MP1584EN buck converter module reference model (P1), mounted")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    below = max(c[4] for c in (d.diode, d.ic, d.inductor, d.trimpot, d.passives,
                               d.cap_in, d.cap_out))
    print(f"Hangs {below:.1f} mm below the board (tallest component), "
          f"header tails {d.header_tail:.1f}")
    print("Exported p1_mp1584.stl and p1_mp1584.step")
