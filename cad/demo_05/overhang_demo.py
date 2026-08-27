"""Support-demo bracket: one arm that needs support, one that doesn't.

A vertical post carries two horizontal arms at the same height:

- The +X arm is a flat-bottomed cantilever floating above the bed, with a
  drop lip at its tip. Its underside is a pure 90-degree overhang that
  cannot print in air -- the slicer must generate support underneath it.
- The -X arm is identical but backed by a 45-degree gusset down to the
  post, so it prints support-free. Side by side on the finished part the
  two undersides show exactly what support buys us.

The body is meant to print in dark blue PLA with the support printed in
white PLA from the auxiliary nozzle, so the support interface shows up
clearly and is easy to inspect after breaking the support away.

Run with:  uv run overhang_demo.py [arm_length_mm]
"""

import sys

from build123d import (
    Align,
    Box,
    Part,
    Plane,
    Polyline,
    Pos,
    export_step,
    export_stl,
    extrude,
    make_face,
)


def make_overhang_demo(
    arm_length: float = 15.0,
    arm_width: float = 12.0,
    arm_thickness: float = 4.0,
    post_height: float = 18.0,
    post_side: float = 10.0,
    lip_drop: float = 3.0,
) -> Part:
    """Build the bracket sitting on the XY plane (Z=0 is the print bed)."""
    if arm_length > post_height:
        raise ValueError(
            "arm_length must fit a 45-degree gusset on the post "
            "(arm_length <= post_height)"
        )

    align = (Align.CENTER, Align.CENTER, Align.MIN)
    arm_tip = post_side / 2 + arm_length

    post = Box(post_side, arm_width, post_height + arm_thickness, align=align)
    arms = Pos(0, 0, post_height) * Box(
        2 * arm_tip, arm_width, arm_thickness, align=align
    )

    # 45-degree gusset filling the corner under the -X arm, out to its tip.
    gusset_profile = Plane.XZ * make_face(
        Polyline(
            (-post_side / 2, post_height),
            (-arm_tip, post_height),
            (-post_side / 2, post_height - arm_length),
            close=True,
        )
    )
    gusset = extrude(gusset_profile, amount=arm_width / 2, both=True)

    # Drop lip at the +X tip: deepens the unsupported pocket so a stray
    # bridge cannot fake its way across, and gives support something to do.
    lip = Pos(arm_tip - 1.5, 0, post_height - lip_drop) * Box(
        3.0, arm_width, lip_drop + arm_thickness, align=align
    )

    return post + arms + gusset + lip


if __name__ == "__main__":
    arm_length = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
    part = make_overhang_demo(arm_length)

    export_stl(part, "overhang_demo.stl")
    export_step(part, "overhang_demo.step")

    bbox = part.bounding_box()
    print(f"Overhang demo bracket, arm length {arm_length} mm")
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {part.volume:.1f} mm^3")
    print("Exported overhang_demo.stl and overhang_demo.step")
