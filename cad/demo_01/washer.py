"""Parametric washer, lying flat on the print bed (easy to print, no supports).

The single driving parameter is the outer diameter; hole size and thickness
default to sensible proportions but can be overridden.

Run with:  uv run washer.py [outer_diameter_mm]
"""

import sys

from build123d import Align, Cylinder, Part, export_step, export_stl


def make_washer(
    outer_diameter: float = 20.0,
    inner_diameter: float | None = None,
    thickness: float | None = None,
) -> Part:
    """Build a washer sitting flat on the XY plane (Z=0 is the print bed)."""
    if inner_diameter is None:
        inner_diameter = outer_diameter / 2
    if thickness is None:
        thickness = outer_diameter / 10
    if inner_diameter >= outer_diameter:
        raise ValueError("inner_diameter must be smaller than outer_diameter")

    align = (Align.CENTER, Align.CENTER, Align.MIN)
    ring = Cylinder(radius=outer_diameter / 2, height=thickness, align=align)
    hole = Cylinder(radius=inner_diameter / 2, height=thickness, align=align)
    return ring - hole


if __name__ == "__main__":
    outer_diameter = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    washer = make_washer(outer_diameter)

    export_stl(washer, "washer.stl")
    export_step(washer, "washer.step")

    bbox = washer.bounding_box()
    print(f"Washer with outer diameter {outer_diameter} mm")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {washer.volume:.1f} mm^3")
    print("Exported washer.stl and washer.step")
