"""Clearance fit-test coupons: a tab (base plate with a round post) and a
washer that should slip over the post. Both parts sit side by side in one STL
so they print in a single job; press the washer onto the post afterwards to
judge the running fit.

The post is 5 mm diameter (the planned gear-post size for demo_04) and the
washer bore is post + 2 x CLEARANCE. The measured feel (too tight / snug /
spins free / sloppy) calibrates every running clearance in the demo_04
gear-box design.

Run with:  uv run fit_test.py [clearance_mm]
e.g.       uv run fit_test.py 0.3
"""

import sys

from build123d import Align, Box, Cylinder, Part, export_step, export_stl

# Calibrated on the X2D in white PLA Basic (2026-08-26): 0.3 mm printed
# visibly sloppy; 0.2 mm gives a free-moving running fit with slight wobble.
CLEARANCE = 0.2  # mm radial clearance between post and washer bore

POST_DIAMETER = 5.0  # matches the planned demo_04 gear posts
POST_HEIGHT = 6.0  # matches the gear face width
BASE_SIZE = 15.0
BASE_HEIGHT = 3.0
WASHER_OUTER = 12.0
WASHER_HEIGHT = 3.0
GAP = 8.0  # spacing between the two parts on the plate


def make_tab() -> Part:
    """Base plate with a centered round post, flat on the bed."""
    bottom = (Align.CENTER, Align.CENTER, Align.MIN)
    base = Box(BASE_SIZE, BASE_SIZE, BASE_HEIGHT, align=bottom)
    post = Cylinder(radius=POST_DIAMETER / 2, height=POST_HEIGHT, align=bottom).translate(
        (0, 0, BASE_HEIGHT)
    )
    return base + post


def make_washer(clearance: float = CLEARANCE) -> Part:
    """Washer whose bore is the post diameter plus 2 x clearance."""
    bottom = (Align.CENTER, Align.CENTER, Align.MIN)
    ring = Cylinder(radius=WASHER_OUTER / 2, height=WASHER_HEIGHT, align=bottom)
    bore = Cylinder(
        radius=POST_DIAMETER / 2 + clearance, height=WASHER_HEIGHT, align=bottom
    )
    return ring - bore


if __name__ == "__main__":
    clearance = float(sys.argv[1]) if len(sys.argv) > 1 else CLEARANCE

    offset = (BASE_SIZE + WASHER_OUTER) / 2 + GAP
    combo = Part() + make_tab() + make_washer(clearance).translate((offset, 0, 0))

    export_stl(combo, "fit_test.stl")
    export_step(combo, "fit_test.step")

    bbox = combo.bounding_box()
    print(f"Fit test: {POST_DIAMETER:g} mm post, "
          f"{POST_DIAMETER + 2 * clearance:g} mm washer bore "
          f"({clearance:g} mm radial clearance)")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print("Exported fit_test.stl and fit_test.step")
