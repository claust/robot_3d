"""Reference model of the Yowoo "Graphene" 2S LiPo pack (parts library
B2, see parts/b2.html).

This is a *reference* part — it models the bought hardware so a robot
chassis can be designed around it. It is not meant to be printed.

Pack body caliper-measured 2026-08-30: 93.0 x 35.2 mm, height tapering
17.7 mm (lead-exit end) to 18.3 mm (far end) — modeled as a uniform box
at the 18.3 max since chassis fits care about the envelope. XT60 stub
size/position and the edge rounding remain "est".

Modeled as a parametric rounded box (soft LiPo packs are not sharp
rectangular prisms — all edges get a uniform fillet) plus a simple stub
block for the XT60 connector on one end wall. The pack also has a
JST-XH balance lead exiting the same end (not modeled — thin flying
wires, not a chassis-clearance concern).

Run with:  uv run parts/b2_lipo.py
Exports b2_lipo.stl and b2_lipo.step (gitignored).

Orientation: pack centered on the origin, long axis (93 mm) is X, the
XT60 connector exits the +X end wall on the pack's Z centerline.
"""

from dataclasses import dataclass

from build123d import Align, Box, Part, Pos, export_step, export_stl, fillet

ALIGN_CENTER = (Align.CENTER, Align.CENTER, Align.CENTER)


@dataclass
class LipoDims:
    """All dimensions in mm. Body measured 2026-08-30; XT60 stub and
    edge rounding still est."""

    length: float = 93.0  # X, measured
    width: float = 35.2  # Y, measured
    height: float = 18.3  # Z, measured max (tapers to 17.7 at lead end)
    edge_radius: float = 2.0  # est, soft-pack corner/edge rounding

    # XT60 connector stub, on the +X end wall (est size and position)
    xt60_width: float = 16.0  # Y
    xt60_height: float = 16.0  # Z
    xt60_depth: float = 8.0  # X, protrusion past the end wall


def make_lipo(dims: LipoDims | None = None) -> Part:
    """Build the pack centered on the origin."""
    d = dims or LipoDims()

    pack = Box(d.length, d.width, d.height, align=ALIGN_CENTER)
    pack = fillet(pack.edges(), d.edge_radius)

    xt60 = Pos(d.length / 2 + d.xt60_depth / 2, 0, 0) * Box(
        d.xt60_depth, d.xt60_width, d.xt60_height, align=ALIGN_CENTER
    )

    return pack + xt60


if __name__ == "__main__":
    pack = make_lipo()

    export_stl(pack, "b2_lipo.stl")
    export_step(pack, "b2_lipo.step")

    d = LipoDims()
    bbox = pack.bounding_box()
    print("Yowoo 2S LiPo pack reference model (B2) — body measured, XT60 est")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Pack body (measured): {d.length} x {d.width} x {d.height} mm, edge radius {d.edge_radius} mm (est)")
    print("Exported b2_lipo.stl and b2_lipo.step")
