"""Parametric involute spur gear built with py_gearworks (local editable dep).

Driving parameters are the gear module and tooth count; face width and the
center bore diameter can be overridden. The gear sits flat on the XY plane
(Z=0 = print bed) so it prints without supports.

Defaults: module 1, 20 teeth (pitch diameter 20 mm), 6 mm face width, 5 mm
center bore. The bore is a plain cylinder — add your own printing clearance to
its diameter if it must slip over a shaft (e.g. 5.3 mm for a 5 mm steel pin).

Run with:  uv run gear.py [module] [teeth] [face_width_mm] [bore_mm]
e.g.       uv run gear.py 1 20 6 5
"""

import sys

import py_gearworks as pgw
from build123d import Align, Cylinder, Part, export_step, export_stl


def make_gear(
    module: float = 1.0,
    teeth: int = 20,
    face_width: float = 6.0,
    bore_diameter: float = 5.0,
) -> Part:
    """Spur gear sitting flat on the XY plane (Z=0 is the print bed)."""
    gear = pgw.SpurGear(
        number_of_teeth=teeth,
        module=module,
        height=face_width,
        root_fillet=0.2,  # in units of module; eases FDM printing of the root
    )
    part = Part() + gear.build_part()
    if bore_diameter > 0:
        if bore_diameter >= 2 * gear.dedendum_radius:
            raise ValueError(
                f"bore {bore_diameter} mm reaches into the teeth "
                f"(root diameter {2 * gear.dedendum_radius:.2f} mm)"
            )
        part -= Cylinder(
            radius=bore_diameter / 2,
            height=face_width,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
    return part


if __name__ == "__main__":
    module = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    teeth = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    face_width = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
    bore = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0
    gear = make_gear(module, teeth, face_width, bore)

    stem = f"gear_m{module:g}_z{teeth}"
    export_stl(gear, f"{stem}.stl")
    export_step(gear, f"{stem}.step")

    bbox = gear.bounding_box()
    print(f"Spur gear: module {module:g}, {teeth} teeth, "
          f"pitch diameter {module * teeth:g} mm, bore {bore:g} mm")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {gear.volume:.1f} mm^3")
    print(f"Exported {stem}.stl and {stem}.step")
