"""demo_04: three-gear train on an open frame — no lid, no bottom plate.

Driving parameters are the gear module and the three tooth counts; everything
else (post positions, frame footprint) is derived. Center distances come from
py_gearworks' mesh_to() machinery (involute mesh distance including backlash),
never hand-computed.

Parts (all print supportless, flat side down):
- three spur gears (bore = post diameter + 2 x 0.2 mm calibrated running fit)
- frame: a perimeter ring around the gear tips, a low spine plus cross arms
  running from the ring edges in under the gears (1 mm below the gear faces),
  and a friction boss + slotted snap post at each gear center. The post lips
  click a pressed-on gear in place while letting it spin; the gears stay
  fully visible and touchable from the top and sides.

Run with:  uv run gearbox.py [module] [z1] [z2] [z3] [face_width]
Exports per-part STL/STEP plus assembly and section STLs for rendering.
"""

import sys
from dataclasses import dataclass, field

import numpy as np
import py_gearworks as pgw
from build123d import (
    Align,
    Axis,
    Box,
    Cone,
    Cylinder,
    Part,
    export_step,
    export_stl,
)

# ---- driving parameters ----------------------------------------------------
MODULE = 1.0
TEETH = (12, 20, 30)
FACE_WIDTH = 6.0
BACKLASH_COEFF = 0.15  # mesh_to backlash, in units of module (0.15 mm here)

# ---- calibrated clearances (fit_test.py coupons, X2D, white PLA, 0.2 mm) ---
RUN_CLEARANCE = 0.2  # radial: gear bore on post; DO NOT re-derive

LAYER_HEIGHT = 0.2

# ---- frame / post geometry -------------------------------------------------
POST_D = 5.0
BORE_D = POST_D + 2 * RUN_CLEARANCE  # 5.4
RING_W = 4.0  # perimeter ring cross-section
RING_H = 4.0
ARM_W = 4.0  # spine + cross arms under the gears
ARM_H = 3.0
BOSS_D = 8.0  # friction pad under each gear, < smallest root diameter
BOSS_H = 1.0
GEAR_Z0 = ARM_H + BOSS_H  # 4.0, gear bottom face
AXIAL_PLAY = 0.3  # gear axial float between boss and lip
TIP_GAP = 1.5  # gear tip to ring inner face

# snap lip on the post: gear bore (r 2.7) clicks over it and is retained
LIP_PROTRUDE = 0.35  # radial beyond post surface -> lip r 2.85
LIP_LAND = 0.4  # cylindrical land, 2 layers
LIP_TOP_R = 2.2  # radius at post tip after 45 deg lead-in chamfer
SLIT_W = 1.5  # slot through post top so the halves can flex
SLIT_DEPTH = 6.5


@dataclass
class Gearbox:
    """All parts in assembled position plus the numbers the checks need."""

    module: float
    teeth: tuple
    face_width: float
    gears_pgw: list  # py_gearworks SpurGear objects, meshed
    centers: list  # (x, y) gear/post centers
    tip_radii: list
    gears: list  # build123d Parts, assembled position (bottom at GEAR_Z0)
    frame: Part = None
    ring_probe: Part = None  # perimeter ring only, for clearance measurements
    post_probes: list = field(default_factory=list)  # bare post cylinders
    dims: dict = field(default_factory=dict)


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Box(
        x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN)
    ).translate((x0, y0, z0))


def build_gear_train(module, teeth, face_width, backlash):
    gears = [
        pgw.SpurGear(
            number_of_teeth=z, module=module, height=face_width, root_fillet=0.2
        )
        for z in teeth
    ]
    # py_gearworks meshing machinery: places each gear at the involute mesh
    # distance (incl. backlash) and clocks its teeth into the neighbor.
    gears[1].mesh_to(gears[0], target_dir=pgw.RIGHT, backlash=backlash)
    gears[2].mesh_to(gears[1], target_dir=pgw.RIGHT, backlash=backlash)

    centers = [tuple(np.ravel(g.gearcore.transform.center)[:2]) for g in gears]
    parts = []
    for g, (cx, cy) in zip(gears, centers):
        p = Part() + g.build_part()
        p -= Cylinder(
            radius=BORE_D / 2,
            height=face_width + 1,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        ).translate((cx, cy, -0.5))
        parts.append(p)
    return gears, centers, parts


def build(module=MODULE, teeth=TEETH, face_width=FACE_WIDTH) -> Gearbox:
    gears_pgw, centers, gear_parts = build_gear_train(
        module, teeth, face_width, BACKLASH_COEFF
    )
    tip_radii = [g.addendum_radius for g in gears_pgw]
    gb = Gearbox(module, teeth, face_width, gears_pgw, centers, tip_radii, [])

    gear_top = GEAR_Z0 + face_width
    lip_z0 = gear_top + AXIAL_PLAY  # lip underside chamfer starts here
    lip_r = POST_D / 2 + LIP_PROTRUDE
    lip_land_z0 = lip_z0 + LIP_PROTRUDE  # 45 deg chamfer rise
    lip_land_z1 = lip_land_z0 + LIP_LAND
    post_top = lip_land_z1 + (lip_r - LIP_TOP_R)  # 45 deg top lead-in

    # ring inner rectangle around the gear tips
    ix0 = min(c[0] - r for c, r in zip(centers, tip_radii)) - TIP_GAP
    ix1 = max(c[0] + r for c, r in zip(centers, tip_radii)) + TIP_GAP
    iy1 = max(abs(c[1]) + r for c, r in zip(centers, tip_radii)) + TIP_GAP
    iy0 = -iy1
    ox0, ox1 = ix0 - RING_W, ix1 + RING_W
    oy0, oy1 = iy0 - RING_W, iy1 + RING_W

    gb.gears = [p.translate((0, 0, GEAR_Z0)) for p in gear_parts]

    # ---- frame -------------------------------------------------------------
    ring = rbox(ox0, ox1, oy0, oy1, 0, RING_H) - rbox(
        ix0, ix1, iy0, iy1, -1, RING_H + 1
    )
    frame = Part() + ring
    # spine ties the three hubs together (mesh distances stay rigid) and runs
    # ring-to-ring; a cross arm at each hub spans the other way. All of it
    # sits ARM_H high: 1 mm below the gear undersides, invisible from above.
    frame += rbox(ox0, ox1, -ARM_W / 2, ARM_W / 2, 0, ARM_H)
    bottom = (Align.CENTER, Align.CENTER, Align.MIN)
    for cx, cy in centers:
        frame += rbox(cx - ARM_W / 2, cx + ARM_W / 2, oy0, oy1, 0, ARM_H)
        # hub pad so the boss underside is fully supported (no overhang)
        frame += rbox(
            cx - BOSS_D / 2, cx + BOSS_D / 2, cy - BOSS_D / 2, cy + BOSS_D / 2,
            0, ARM_H,
        )
        boss = Cylinder(radius=BOSS_D / 2, height=BOSS_H, align=bottom).translate(
            (cx, cy, ARM_H)
        )
        post = Cylinder(
            radius=POST_D / 2, height=lip_land_z1 - ARM_H, align=bottom
        ).translate((cx, cy, ARM_H))
        lip = (
            Cone(POST_D / 2, lip_r, LIP_PROTRUDE, align=bottom).translate(
                (cx, cy, lip_z0)
            )
            + Cylinder(radius=lip_r, height=LIP_LAND, align=bottom).translate(
                (cx, cy, lip_land_z0)
            )
            + Cone(lip_r, LIP_TOP_R, lip_r - LIP_TOP_R, align=bottom).translate(
                (cx, cy, lip_land_z1)
            )
        )
        frame += boss + post + lip
        gb.post_probes.append(
            Cylinder(
                radius=POST_D / 2, height=face_width, align=bottom
            ).translate((cx, cy, GEAR_Z0))
        )
    for cx, cy in centers:  # slit after all posts are fused
        frame -= Box(
            POST_D + 2 * LIP_PROTRUDE + 1, SLIT_W, SLIT_DEPTH + 0.2, align=bottom
        ).translate((cx, cy, post_top - SLIT_DEPTH))
    gb.frame = frame
    gb.ring_probe = ring

    gb.dims = dict(
        gear_top=gear_top,
        lip_z0=lip_z0,
        lip_r=lip_r,
        lip_land_z0=lip_land_z0,
        lip_land_z1=lip_land_z1,
        post_top=post_top,
        interior=(ix0, ix1, iy0, iy1),
        exterior=(ox0, ox1, oy0, oy1),
        bore_r=BORE_D / 2,
        post_r=POST_D / 2,
        arm_under_gear=GEAR_Z0 - ARM_H,  # vertical gap arms to gear faces
        # snap metadata for assembly_check
        lip_interference=lip_r - BORE_D / 2,  # radial, per side
        lip_deflection_len=SLIT_DEPTH,
        lip_flex_t=(POST_D - SLIT_W) / 2,
    )
    return gb


if __name__ == "__main__":
    module = float(sys.argv[1]) if len(sys.argv) > 1 else MODULE
    teeth = (
        tuple(int(a) for a in sys.argv[2:5]) if len(sys.argv) > 4 else TEETH
    )
    face_width = float(sys.argv[5]) if len(sys.argv) > 5 else FACE_WIDTH

    gb = build(module, teeth, face_width)

    for z, (cx, cy), part in zip(teeth, gb.centers, gb.gears):
        stem = f"gear_z{z}"
        printable = part.translate((-cx, -cy, -GEAR_Z0))
        export_stl(printable, f"{stem}.stl")
        export_step(printable, f"{stem}.step")
        print(f"{stem}: center ({cx:.3f}, {cy:.3f}), bore {BORE_D:g} mm")

    export_stl(gb.frame, "frame.stl")
    export_step(gb.frame, "frame.step")

    assembly = Part() + gb.frame
    for part in gb.gears:
        assembly += part
    export_stl(assembly, "assembly.stl")

    ox0, ox1, oy0, oy1 = gb.dims["exterior"]
    big = 5
    sec_posts = assembly & rbox(
        ox0 - big, ox1 + big, 0, oy1 + big, -1, gb.dims["post_top"] + 1
    )
    export_stl(sec_posts, "section_posts.stl")
    sec_hub = assembly & rbox(
        ox0 - big, gb.centers[1][0], oy0 - big, oy1 + big, -1,
        gb.dims["post_top"] + 1,
    )
    export_stl(
        sec_hub.rotate(Axis((0, 0, 0), (0, 0, 1)), -90), "section_hub.stl"
    )

    d = gb.dims
    print(f"Center distances: "
          f"{gb.centers[1][0] - gb.centers[0][0]:.3f}, "
          f"{gb.centers[2][0] - gb.centers[1][0]:.3f} mm (via mesh_to)")
    print(f"Frame exterior: {ox1 - ox0:.1f} x {oy1 - oy0:.1f} mm, "
          f"ring {RING_H:g} mm tall, posts to {d['post_top']:.1f} mm")
    print("Exported gears, frame.stl, assembly.stl, "
          "section_posts.stl, section_hub.stl")
