"""Reference model of the mower spindle's ball bearing: a shielded 6000-size
deep-groove bearing, 10 bore x 26 OD x 8 wide.

This is a *reference* part: it models the bought hardware so the spindle
tower and its axle can be designed around it. It is not meant to be printed.

Bore, outside diameter and width are the user's caliper readings
(2026-10-12). The rest is "est": the 6000 catalogue size, not measured.
The inner ring's face ends at inner_land_d; between that and outer_land_d
a shield closes the gap, set in a little from each face and fixed to the
outer ring. Only the inner ring turns, so anything that spins with the axle
may touch the inner ring's face and nothing else.

Frame: axis along Z, origin at the centre of the bottom face, top face at
Z = width.

Run with:  uv run parts/bearing_6000.py   (exports bearing_6000.stl, gitignored)
"""

from dataclasses import dataclass

from build123d import Align, Cylinder, Part, Pos, export_stl

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass
class BearingDims:
    bore: float = 10.0
    od: float = 26.0
    width: float = 8.0
    inner_land_d: float = 14.8  # est, outside of the inner ring's face
    outer_land_d: float = 22.6  # est, inside of the outer ring's face
    shield_gap: float = 0.3  # est, shield bore to the inner ring
    shield_t: float = 0.3  # est
    shield_inset: float = 0.2  # est, shield below each ring face


def _tube(od: float, id_: float, h: float, z0: float = 0.0) -> Part:
    tube = Cylinder(od / 2, h, align=ALIGN_BOTTOM) - Cylinder(id_ / 2, h, align=ALIGN_BOTTOM)
    return Pos(0, 0, z0) * tube


def make_inner(d: BearingDims | None = None) -> Part:
    """The inner ring, the part that turns with the axle."""
    d = d or BearingDims()
    return _tube(d.inner_land_d, d.bore, d.width)


def make_outer(d: BearingDims | None = None) -> Part:
    """The outer ring with both shields: everything that stays still."""
    d = d or BearingDims()
    outer = _tube(d.od, d.outer_land_d, d.width)
    shield_id = d.inner_land_d + 2 * d.shield_gap
    for z in (d.shield_inset, d.width - d.shield_inset - d.shield_t):
        outer += _tube(d.outer_land_d + 0.01, shield_id, d.shield_t, z)
    return outer


if __name__ == "__main__":
    d = BearingDims()
    bearing = make_outer(d) + make_inner(d)
    export_stl(bearing, "bearing_6000.stl")
    print(f"6000 bearing {d.bore:g} x {d.od:g} x {d.width:g} mm, "
          f"{bearing.volume / 1000:.2f} cm^3 -- exported bearing_6000.stl")
