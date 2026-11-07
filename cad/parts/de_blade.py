"""Reference model of a double-edge safety razor blade, the cutter's knife.

This is a *reference* part: it models the bought blade so the disc's clips
can be designed around it. It is not meant to be printed.

Length, width and the outline's shape are the user's caliper readings and
comparison with the drawing in IS 7371:1982 Fig. 2 (2026-11-07). The centre
hole and the diamond's tip-to-tip size are calipered, both "about". Hole
spacing, slot width, slot length and thickness come from the standard.
Fields marked "est" are scaled from that drawing.

Frame: long axis along X, cutting edges along +-Y, origin at the centre of
the bottom face, top face at Z = thickness. The model is a plain prism with
square notches and no bevels, which is all a clearance check needs.

Run with:  uv run parts/de_blade.py   (exports de_blade.stl, gitignored)
"""

from dataclasses import dataclass

from build123d import (
    Circle, Part, Plane, Polygon, Pos, Rectangle, Sketch, export_stl, extrude,
)


@dataclass
class BladeDims:
    length: float = 42.9
    width: float = 22.0
    thickness: float = 0.10
    hole_pitch: float = 12.73  # standard, centre hole to each outer hole
    centre_hole_d: float = 5.0  # calipered, about
    diamond_tips: float = 6.3  # calipered, about, across Y
    diamond_x: float = 8.0  # est, across X, tip to tip if the sides ran straight
    slot_w: float = 2.13  # standard, 2.06 to 2.21
    slot_reach: float = 17.86  # standard minimum, centre to the slot's end
    narrow_start: float = 2.6  # est, where the slot leaves the centre hole
    narrow_end: float = 8.2  # est, where the slot widens into the first lobe
    lobe_inner: tuple = (8.2, 9.85)  # est, the lobe inside the diamond
    lobe_outer: tuple = (16.1, 17.5)  # est, the lobe outside it
    lobe_half_y: float = 3.0  # est
    shoulder_x: float = 18.5  # standard, centre to the notch at the end tab
    tab_half_y: float = 6.6  # standard, the end tab's half width


def cutout_sketch(b: BladeDims = BladeDims()) -> Sketch:
    s = Circle(b.centre_hole_d / 2)
    s += Rectangle(2 * b.slot_reach, b.slot_w)
    for side in (-1, 1):
        cx = side * b.hole_pitch
        s += Polygon((cx - b.diamond_x / 2, 0), (cx, b.diamond_tips / 2),
                     (cx + b.diamond_x / 2, 0), (cx, -b.diamond_tips / 2), align=None)
        for lo, hi in (b.lobe_inner, b.lobe_outer):
            s += Pos(side * (lo + hi) / 2, 0) * Rectangle(hi - lo, 2 * b.lobe_half_y)
    return s


def make_blade(b: BladeDims = BladeDims()) -> Part:
    outline = Rectangle(2 * b.shoulder_x, b.width) + Rectangle(b.length, 2 * b.tab_half_y)
    return extrude(Plane.XY * (outline - cutout_sketch(b)), amount=b.thickness)


if __name__ == "__main__":
    blade = make_blade()
    bb = blade.bounding_box()
    print(f"blade {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.2f} mm, "
          f"{blade.volume * 7.7e-3:.2f} g")
    export_stl(blade, "de_blade.stl")
