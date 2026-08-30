"""Reference model of the DRV8833 dual H-bridge driver module (parts
library D2, see parts/d2.html).

This is a *reference* part — it models the bought hardware so a robot
chassis can be designed around it. It is not meant to be printed.

Board is 18.5 x 16 mm (per the listing and parts/d2.html), with two loose
6-pin 2.54 mm header strips that ship unsoldered — solder before use. The
pinout photo (parts/photos/d2-drv8833-pinout.jpg) confirms two 6-pin rows
running along the two opposite 16 mm edges. Hole pitch (2.54 mm) is fixed
by the header standard; the exact inset from the edge is not dimensioned
anywhere and is marked "est". The DRV8833 IC footprint/position is also
"est" — a small block standing in for the chip near the board center.

Because the header pins are usually soldered on before the board is used,
`with_headers` (default True) adds the worst-case envelope: a 2.54 mm
pitch pin-header strip per row — plastic base 2.5 mm tall sitting on the
board, pins reaching 6 mm above the base and 3 mm below the board
(solder tails). The chassis should be designed around this default,
larger envelope unless the board is known to be used bare.

Run with:  uv run parts/d2_drv8833.py
Exports d2_drv8833.stl and d2_drv8833.step (gitignored).

Orientation: PCB on the XY plane, top (component) face at +Z, origin at
the PCB center. The 18.5 mm axis is X, the 16 mm header-row axis is Y.
"""

from dataclasses import dataclass

from build123d import Align, Box, Cylinder, Part, Pos, export_step, export_stl

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_TOP = (Align.CENTER, Align.CENTER, Align.MAX)
ALIGN_CENTER = (Align.CENTER, Align.CENTER, Align.CENTER)


@dataclass
class Drv8833Dims:
    """All dimensions in mm, from parts/d2.html unless marked est."""

    board_length: float = 18.5  # X
    board_width: float = 16.0  # Y
    board_thickness: float = 1.6  # est, standard 1.6 mm PCB

    # Two 6-pin 2.54 mm header rows, one on each 16 mm (Y) edge
    header_pin_count: int = 6
    header_pitch: float = 2.54
    header_hole_diameter: float = 1.0  # est
    header_inset: float = 1.5  # est, edge to hole center

    # DRV8833 IC, near board center (est size and position)
    ic_size: float = 3.0
    ic_height: float = 1.0

    # Optional soldered pin-header variant — the worst-case envelope
    with_headers: bool = True
    header_base_height: float = 2.5  # plastic base, sits on the board
    header_pin_up: float = 6.0  # above the base top
    header_pin_down: float = 3.0  # below the board (solder tails)
    header_pin_size: float = 0.64  # est, standard 0.025" square pin
    header_row_width: float = 2.5  # est, base width across the single row


def _header_row_x_positions(d: Drv8833Dims) -> list[float]:
    span = (d.header_pin_count - 1) * d.header_pitch
    start = -span / 2
    return [start + i * d.header_pitch for i in range(d.header_pin_count)]


def make_drv8833(dims: Drv8833Dims | None = None) -> Part:
    """Build the module with its PCB centered on the origin, top face +Z."""
    d = dims or Drv8833Dims()

    board = Box(
        d.board_length, d.board_width, d.board_thickness, align=ALIGN_CENTER
    )

    top_face = d.board_thickness / 2
    bottom_face = -d.board_thickness / 2
    row_x = d.board_length / 2 - d.header_inset
    pin_ys = _header_row_x_positions(d)  # despite the name, these run along Y

    ic = Pos(0, 0, top_face) * Box(
        d.ic_size, d.ic_size, d.ic_height, align=ALIGN_BOTTOM
    )
    board += ic

    for row_sign in (-1, 1):
        x = row_sign * row_x
        for y in pin_ys:
            board -= Pos(x, y, 0) * Cylinder(
                radius=d.header_hole_diameter / 2,
                height=d.board_thickness * 2,
                align=ALIGN_CENTER,
            )

    if d.with_headers:
        row_span = (d.header_pin_count - 1) * d.header_pitch
        base_length = row_span + d.header_pitch  # est, a bit of margin
        headers = Part()
        for row_sign in (-1, 1):
            x = row_sign * row_x
            headers += Pos(x, 0, top_face) * Box(
                d.header_row_width,
                base_length,
                d.header_base_height,
                align=ALIGN_BOTTOM,
            )
            for y in pin_ys:
                pin_bottom = bottom_face - d.header_pin_down
                pin_top = top_face + d.header_base_height + d.header_pin_up
                headers += Pos(x, y, pin_bottom) * Box(
                    d.header_pin_size,
                    d.header_pin_size,
                    pin_top - pin_bottom,
                    align=ALIGN_BOTTOM,
                )
        board += headers

    return board


if __name__ == "__main__":
    module = make_drv8833()

    export_stl(module, "d2_drv8833.stl")
    export_step(module, "d2_drv8833.step")

    d = Drv8833Dims()
    bbox = module.bounding_box()
    print("DRV8833 dual H-bridge driver module reference model (D2)")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"with_headers={d.with_headers}")
    if d.with_headers:
        max_height = (
            d.board_thickness / 2
            + d.header_base_height
            + d.header_pin_up
        )
        min_z = -(d.board_thickness / 2 + d.header_pin_down)
        print(f"Header envelope: {min_z:.2f} to {max_height:.2f} mm (Z)")
    print("Exported d2_drv8833.stl and d2_drv8833.step")
