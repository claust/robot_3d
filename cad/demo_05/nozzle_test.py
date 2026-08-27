"""Minimal dual-nozzle control coupon: the overhang bracket, shrunk.

Smallest part that still forces both nozzles to print: a short post with a
stubby cantilever whose underside must be supported (white, aux nozzle)
while the body prints blue from the AMS. Run before any real support job to
prove the filament->extruder mapping end to end.

Run with:  uv run nozzle_test.py
"""

from build123d import export_step, export_stl

from overhang_demo import make_overhang_demo

if __name__ == "__main__":
    part = make_overhang_demo(
        arm_length=8.0,
        arm_width=8.0,
        arm_thickness=2.4,
        post_height=8.0,
        post_side=6.0,
        lip_drop=2.0,
    )

    export_stl(part, "nozzle_test.stl")
    export_step(part, "nozzle_test.step")

    bbox = part.bounding_box()
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {part.volume:.1f} mm^3")
    print("Exported nozzle_test.stl and nozzle_test.step")
