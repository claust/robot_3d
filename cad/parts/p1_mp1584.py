"""Reference model of the MP1584EN buck converter module (parts library
P1, see parts/p1.html).

This is a *reference* part — it models the bought hardware so a robot
chassis can be designed around it. It is not meant to be printed.

Board is 22 x 17 mm, confirmed by the seller's dimensioned photo
(parts/photos/p1-mp1584-dimensions.jpg): four unplated corner pads per
side — IN+/IN- on one 17 mm edge, OUT+/OUT- on the opposite 17 mm edge,
each edge carrying two closely-spaced pairs (one pair near each corner).
Exact pad pitch/inset is not dimensioned and is marked "est".

Visible components, per the dimensioned photo and parts/p1.html: the
MP1584EN itself (SOP-8), a shielded power inductor marked 4R7, an SS34
Schottky diode (not modeled — outside this task's component list), and
the blue multi-turn trimpot. Component sizes and on-board positions are
not dimensioned anywhere and are all marked "est".

Total stack height matters for the chassis clip cradle: with the default
dimensions below, the tallest component is the trimpot at 5.0 mm above
the top face, so the max envelope is board_thickness (1.6) + 5.0 =
**6.6 mm** from the PCB bottom to the top of the trimpot.

Run with:  uv run parts/p1_mp1584.py
Exports p1_mp1584.stl and p1_mp1584.step (gitignored).

Orientation: PCB on the XY plane, top (component) face at +Z, origin at
the PCB center. The 22 mm IN/OUT-pad axis is X, the 17 mm pad-edge axis
is Y. IN pads on the -X edge, OUT pads on the +X edge.
"""

from dataclasses import dataclass

from build123d import Align, Box, Cylinder, Part, Pos, export_step, export_stl

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_CENTER = (Align.CENTER, Align.CENTER, Align.CENTER)


@dataclass
class Mp1584Dims:
    """All dimensions in mm, from parts/p1.html and the dimensioned photo
    unless marked est."""

    board_length: float = 22.0  # X, IN/OUT pad axis
    board_width: float = 17.0  # Y, pad-edge axis
    board_thickness: float = 1.6  # est, standard 1.6 mm PCB

    # Four unplated pads per side edge, two pairs per edge (est spacing)
    pad_diameter: float = 1.2  # est
    pad_inset: float = 1.5  # est, edge to pad center
    pad_pair_spacing: float = 2.0  # est, gap within a pair
    pad_pair_offset: float = 5.5  # est, pair center from board Y center

    # Shielded power inductor (4R7 / 4.7 uH), est size and position
    inductor_size: float = 7.0  # X and Y
    inductor_height: float = 4.0
    inductor_x: float = 5.0  # est
    inductor_y: float = 2.0  # est

    # MP1584EN SOP-8, est size and position
    ic_length: float = 5.0  # X
    ic_width: float = 4.0  # Y
    ic_height: float = 1.5
    ic_x: float = -4.0  # est
    ic_y: float = 3.0  # est

    # Multi-turn trimpot, est size and position — the tallest component
    trimpot_length: float = 6.7  # X
    trimpot_width: float = 4.5  # Y
    trimpot_height: float = 5.0
    trimpot_x: float = 0.0  # est
    trimpot_y: float = -5.0  # est


def make_mp1584(dims: Mp1584Dims | None = None) -> Part:
    """Build the module with its PCB centered on the origin, top face +Z."""
    d = dims or Mp1584Dims()

    board = Box(
        d.board_length, d.board_width, d.board_thickness, align=ALIGN_CENTER
    )

    top_face = d.board_thickness / 2

    inductor = Pos(d.inductor_x, d.inductor_y, top_face) * Box(
        d.inductor_size, d.inductor_size, d.inductor_height, align=ALIGN_BOTTOM
    )
    ic = Pos(d.ic_x, d.ic_y, top_face) * Box(
        d.ic_length, d.ic_width, d.ic_height, align=ALIGN_BOTTOM
    )
    trimpot = Pos(d.trimpot_x, d.trimpot_y, top_face) * Box(
        d.trimpot_length, d.trimpot_width, d.trimpot_height, align=ALIGN_BOTTOM
    )

    board += inductor + ic + trimpot

    edge_x = d.board_length / 2 - d.pad_inset
    for edge_sign in (-1, 1):  # -X: IN pads, +X: OUT pads
        x = edge_sign * edge_x
        for pair_sign in (-1, 1):
            pair_y = pair_sign * d.pad_pair_offset
            for y in (pair_y - d.pad_pair_spacing / 2, pair_y + d.pad_pair_spacing / 2):
                board -= Pos(x, y, 0) * Cylinder(
                    radius=d.pad_diameter / 2,
                    height=d.board_thickness * 2,
                    align=ALIGN_CENTER,
                )

    return board


if __name__ == "__main__":
    module = make_mp1584()

    export_stl(module, "p1_mp1584.stl")
    export_step(module, "p1_mp1584.step")

    d = Mp1584Dims()
    bbox = module.bounding_box()
    print("MP1584EN buck converter module reference model (P1)")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    max_height = d.board_thickness + max(d.inductor_height, d.ic_height, d.trimpot_height)
    print(f"Max stack height (PCB bottom to tallest component): {max_height:.2f} mm")
    print("Exported p1_mp1584.stl and p1_mp1584.step")
