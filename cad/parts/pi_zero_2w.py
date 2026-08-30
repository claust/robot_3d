"""Reference model of the Raspberry Pi Zero 2 W (parts library C1).

This is a *reference* part — it models the bought hardware so a robot
chassis can be designed around it. It is not meant to be printed.

Geometry is the well-documented public Pi Zero footprint: 65 x 30 x 1.4 mm
PCB, 3.0 mm corner radius, four Ø2.75 mm mounting holes on a 58 x 23 mm
rectangle (3.5 mm in from each edge — the standard Raspberry Pi Zero hole
pattern, unchanged since the original Zero).

Everything past the bare PCB outline and mounting holes is a simplified
envelope block, not a real connector shape, and its position along the
board edge is estimated from photos of the board rather than measured —
all marked "est":
- 40-pin GPIO header strip along one long edge (+Y).
- On the opposite long edge (-Y): mini-HDMI, micro-USB OTG, and micro-USB
  power connectors, left to right in that order, at their approximate
  standard Zero positions.
- microSD slot on one short edge (-X), modeled on the bottom face since
  that's where it sits on the real board.
- RP3A0 SiP (the Pi Zero 2 W's processor package) as a block near center.

Run with:  uv run parts/pi_zero_2w.py
Exports pi_zero_2w.stl and pi_zero_2w.step (gitignored).

Orientation: PCB on the XY plane, top (component) face at +Z, origin at
the PCB center. Long axis (65 mm) is X, short axis (30 mm) is Y. The GPIO
header is on the +Y edge, the AV/USB connectors on the -Y edge, the
microSD slot on the -X edge.
"""

from dataclasses import dataclass

from build123d import Align, Axis, Box, Cylinder, Part, Pos, export_step, export_stl, fillet

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_TOP = (Align.CENTER, Align.CENTER, Align.MAX)
ALIGN_CENTER = (Align.CENTER, Align.CENTER, Align.CENTER)


@dataclass
class PiZero2WDims:
    """All dimensions in mm. Values not on the public Zero footprint
    drawing (i.e. everything but the board outline and mounting holes)
    are marked est."""

    # PCB
    board_length: float = 65.0  # X
    board_width: float = 30.0  # Y
    board_thickness: float = 1.4  # Z
    corner_radius: float = 3.0

    # Mounting holes: 58 x 23 mm rectangle, 3.5 mm in from each edge
    mount_hole_diameter: float = 2.75
    mount_hole_span_x: float = 58.0
    mount_hole_span_y: float = 23.0

    # 40-pin GPIO header, along the +Y long edge (est overall envelope)
    gpio_length: float = 51.0  # X
    gpio_depth: float = 5.0  # Y, inset from the edge
    gpio_height: float = 8.5  # Z, above the top face

    # AV/USB connectors on the -Y long edge (est size and position)
    conn_depth: float = 5.0  # Y, straddling the board edge
    conn_height: float = 3.0  # Z, above the top face
    hdmi_width: float = 7.5  # X
    hdmi_x: float = -23.0  # est, near the left end
    usb_otg_width: float = 7.5  # X
    usb_otg_x: float = 0.0  # est, mid-board
    usb_pwr_width: float = 8.0  # X
    usb_pwr_x: float = 23.0  # est, near the right end

    # RP3A0 SiP, near center (est position/size)
    soc_size: float = 10.0  # X and Y
    soc_height: float = 1.2  # Z, above the top face

    # microSD slot, on the -X short edge, bottom side (est size/position)
    sd_length_x: float = 15.0  # mostly inboard, overhangs the edge a little
    sd_width_y: float = 12.0
    sd_height: float = 2.0  # below the bottom face
    sd_overhang: float = 2.0  # est, how far it pokes past the board edge


def make_pi_zero_2w(dims: PiZero2WDims | None = None) -> Part:
    """Build the board with its PCB centered on the origin, top face +Z."""
    d = dims or PiZero2WDims()

    board = Box(
        d.board_length, d.board_width, d.board_thickness, align=ALIGN_CENTER
    )
    board = fillet(board.edges().filter_by(Axis.Z), d.corner_radius)

    top_face = d.board_thickness / 2
    bottom_face = -d.board_thickness / 2
    edge_pos_y = d.board_width / 2
    edge_neg_y = -d.board_width / 2
    edge_neg_x = -d.board_length / 2

    gpio = Pos(0, edge_pos_y - d.gpio_depth / 2, top_face) * Box(
        d.gpio_length, d.gpio_depth, d.gpio_height, align=ALIGN_BOTTOM
    )

    connectors = Part()
    for width, x in (
        (d.hdmi_width, d.hdmi_x),
        (d.usb_otg_width, d.usb_otg_x),
        (d.usb_pwr_width, d.usb_pwr_x),
    ):
        connectors += Pos(x, edge_neg_y, top_face) * Box(
            width, d.conn_depth, d.conn_height, align=ALIGN_BOTTOM
        )

    soc = Pos(0, 0, top_face) * Box(
        d.soc_size, d.soc_size, d.soc_height, align=ALIGN_BOTTOM
    )

    sd_center_x = edge_neg_x + d.sd_length_x / 2 - d.sd_overhang
    sd_slot = Pos(sd_center_x, 0, bottom_face) * Box(
        d.sd_length_x, d.sd_width_y, d.sd_height, align=ALIGN_TOP
    )

    board += gpio + connectors + soc + sd_slot

    for x_sign in (-1, 1):
        for y_sign in (-1, 1):
            board -= Pos(
                x_sign * d.mount_hole_span_x / 2,
                y_sign * d.mount_hole_span_y / 2,
                0,
            ) * Cylinder(
                radius=d.mount_hole_diameter / 2,
                height=d.board_thickness * 2,
                align=ALIGN_CENTER,
            )

    return board


if __name__ == "__main__":
    board = make_pi_zero_2w()

    export_stl(board, "pi_zero_2w.stl")
    export_step(board, "pi_zero_2w.step")

    d = PiZero2WDims()
    bbox = board.bounding_box()
    print("Raspberry Pi Zero 2 W reference model (C1)")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    top_stack = d.board_thickness / 2 + max(d.gpio_height, d.conn_height, d.soc_height)
    print(f"PCB {d.board_length}x{d.board_width}x{d.board_thickness} mm, top stack to {top_stack:.2f} mm above center")
    print("Exported pi_zero_2w.stl and pi_zero_2w.step")
