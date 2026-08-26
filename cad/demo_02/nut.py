"""Parametric, printable ISO hex nut. The thread size string is the driving
parameter — body dimensions (width across flats, height) come from the ISO 4032
tables in bd_warehouse, and the internal thread is a real modeled ISO thread
from bd_warehouse.thread so it can be printed directly.

Printability:
- CLEARANCE (default 0.3 mm) is a *radial* clearance applied to the whole
  internal thread profile: every diameter (major/pitch/minor) is enlarged by
  2 x CLEARANCE. This compensates FDM inaccuracy (elephant foot, extrusion
  bulge) so an off-the-shelf steel bolt threads in after printing in PLA.
  0.2 mm is a snug fit, 0.3 mm an easy fit, 0.4 mm loose — tune per printer.
- The nut prints flat face down with no supports: the bottom face is flat
  (no washer-face chamfer), only the top corners carry the usual 30 degree
  cone chamfer. Internal thread overhangs are self-supporting at this size.

Run with:  uv run nut.py [size] [clearance_mm]
e.g.       uv run nut.py M8 0.3
"""

import sys
from math import radians, sqrt, tan

from bd_warehouse.fastener import HexNut
from bd_warehouse.thread import IsoThread
from build123d import (
    Align,
    Box,
    Cone,
    Cylinder,
    Part,
    Plane,
    RegularPolygon,
    export_step,
    export_stl,
    extrude,
)

CLEARANCE = 0.3  # mm radial thread clearance for FDM printing (see docstring)


def coarse_size(size: str) -> str:
    """Expand a bare size like 'M8' to bd_warehouse's 'M8-1.25' (coarse pitch)."""
    if "-" in size:
        return size
    for s in HexNut.sizes("iso4032"):
        if s.split("-")[0] == size:
            return s
    raise ValueError(f"Unknown thread size {size!r}; known: {HexNut.sizes('iso4032')}")


def make_nut(size: str = "M8", clearance: float = CLEARANCE) -> Part:
    """Hex nut for `size` (e.g. 'M8'), sitting flat on the XY plane (Z=0 = bed)."""
    size = coarse_size(size)
    major = float(size.split("-")[0][1:]) + 2 * clearance
    pitch = float(size.split("-")[1])

    # ISO 4032 body dimensions: s = width across flats, m = height
    data = HexNut(size=size, fastener_type="iso4032", simple=True).nut_data
    across_flats, height = float(data["s"]), float(data["m"])

    align = (Align.CENTER, Align.CENTER, Align.MIN)
    body = extrude(
        Plane.XY * RegularPolygon(across_flats / 2, 6, major_radius=False), height
    )

    # Conical 30-degree chamfer on the top corners only (bottom stays flat on
    # the bed). The cone meets the top face at ~0.95 x across-flats diameter.
    top_r = 0.475 * across_flats
    body &= Cone(
        bottom_radius=top_r + height * sqrt(3),  # 30 deg from the face plane
        top_radius=top_r,
        height=height,
        align=align,
    )

    body -= Cylinder(radius=major / 2, height=height, align=align)
    thread = IsoThread(
        major_diameter=major,
        pitch=pitch,
        length=height,
        external=False,
        end_finishes=("chamfer", "chamfer"),
    )
    return Part() + body + thread


if __name__ == "__main__":
    size = sys.argv[1] if len(sys.argv) > 1 else "M8"
    clearance = float(sys.argv[2]) if len(sys.argv) > 2 else CLEARANCE
    nut = make_nut(size, clearance)

    stem = f"nut_{size.lower().split('-')[0]}"
    export_stl(nut, f"{stem}.stl")
    export_step(nut, f"{stem}.step")

    # Half-section (Y < 0 removed, cut face towards the front view) for visual
    # inspection of the thread profile
    section = nut & Box(100, 100, 100, align=(Align.CENTER, Align.MIN, Align.MIN))
    export_stl(section, f"{stem}_section.stl")

    bbox = nut.bounding_box()
    print(f"{size} hex nut, {clearance} mm radial thread clearance")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {nut.volume:.1f} mm^3")
    print(f"Exported {stem}.stl, {stem}.step and {stem}_section.stl")
