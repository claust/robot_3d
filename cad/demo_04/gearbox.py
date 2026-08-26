"""demo_04: three-gear train in a snap-together two-part enclosure.

Driving parameters are the gear module and the three tooth counts; everything
else (post positions, enclosure footprint, lid) is derived. Center distances
come from py_gearworks' mesh_to() machinery (involute mesh distance including
backlash), never hand-computed.

Parts (all print supportless, flat side down):
- three spur gears (bore = post diameter + 2 x 0.2 mm calibrated running fit)
- base: plate + perimeter wall + friction bosses + slotted snap posts whose
  lips click a pressed-on gear in place while letting it spin
- lid: prints upside down; a locating lip drops inside the wall and four
  cantilever arms snap over 45 degree chamfered bumps on the wall exterior.
  All snap retention faces are 45 degrees so no orientation needs supports.

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
    Polyline,
    export_step,
    export_stl,
    extrude,
    make_face,
)

# ---- driving parameters ----------------------------------------------------
MODULE = 1.0
TEETH = (12, 20, 30)
FACE_WIDTH = 6.0
BACKLASH_COEFF = 0.15  # mesh_to backlash, in units of module (0.15 mm here)

# ---- calibrated clearances (fit_test.py coupons, X2D, white PLA, 0.2 mm) ---
RUN_CLEARANCE = 0.2  # radial: gear bore on post; DO NOT re-derive
SNAP_CLEARANCE = 0.15  # radial per side: static/snap fits (lid onto base)

LAYER_HEIGHT = 0.2

# ---- base / post geometry --------------------------------------------------
POST_D = 5.0
BORE_D = POST_D + 2 * RUN_CLEARANCE  # 5.4
BASE_T = 3.0
BOSS_D = 8.0  # friction pad under each gear, < smallest root diameter
BOSS_H = 1.0
GEAR_Z0 = BASE_T + BOSS_H  # 4.0, gear bottom face
AXIAL_PLAY = 0.3  # gear axial float between boss and lip

# snap lip on the post: gear bore (r 2.7) clicks over it and is retained
LIP_PROTRUDE = 0.35  # radial beyond post surface -> lip r 2.85
LIP_LAND = 0.4  # cylindrical land, 2 layers
LIP_TOP_R = 2.2  # radius at post tip after 45 deg lead-in chamfer
SLIT_W = 1.5  # slot through post top so the halves can flex
SLIT_DEPTH = 6.5

# ---- enclosure -------------------------------------------------------------
WALL_T = 2.0
TIP_GAP = 1.5  # gear tip to inner wall
CEIL_CLEARANCE = 1.0  # above post tip
LID_T = 2.0
LID_LIP_T = 1.2  # locating lip inside the wall
LID_LIP_H = 1.5

# ---- snap arms (lid) over wall bumps (base) --------------------------------
ARM_T = 1.3
ARM_W = 12.0
ARM_GAP = SNAP_CLEARANCE  # arm inner face to wall outer face
BUMP_P = 0.55  # bump protrusion from wall outer face
BUMP_W = 8.0
BUMP_TOP_Z = 4.6  # flat top (up-facing, printable); 45 deg chamfer below
BUMP_LAND = 0.2
NOTCH_W = BUMP_W + 0.6  # window in the arm, side clearance 0.3 per side
FINGER_D = 20.0  # hole in the lid over the largest gear


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
    base: Part = None
    lid: Part = None  # assembled orientation
    wall_probe: Part = None  # wall only, for clearance measurements
    post_probes: list = field(default_factory=list)  # bare post cylinders
    dims: dict = field(default_factory=dict)


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Box(
        x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN)
    ).translate((x0, y0, z0))


def side_prism(pts_yz, side, x_center, width) -> Part:
    """Prism from a (y, z) profile on the +Y side, mirrored for side=-1."""
    pts = [(0, side * y, z) for y, z in pts_yz]
    face = make_face(Polyline(*pts, close=True))
    return extrude(face, amount=width / 2, both=True).translate((x_center, 0, 0))


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
    ceil_z = post_top + CEIL_CLEARANCE  # wall top = lid underside
    lid_top = ceil_z + LID_T

    # interior rectangle around the gear tips, then the wall outside it
    ix0 = min(c[0] - r for c, r in zip(centers, tip_radii)) - TIP_GAP
    ix1 = max(c[0] + r for c, r in zip(centers, tip_radii)) + TIP_GAP
    iy1 = max(abs(c[1]) + r for c, r in zip(centers, tip_radii)) + TIP_GAP
    iy0 = -iy1
    ox0, ox1 = ix0 - WALL_T, ix1 + WALL_T
    oy0, oy1 = iy0 - WALL_T, iy1 + WALL_T
    w_out = oy1  # outer wall face on the +Y side

    gb.gears = [p.translate((0, 0, GEAR_Z0)) for p in gear_parts]

    # ---- base --------------------------------------------------------------
    plate = rbox(ox0, ox1, oy0, oy1, 0, BASE_T)
    wall = rbox(ox0, ox1, oy0, oy1, BASE_T, ceil_z) - rbox(
        ix0, ix1, iy0, iy1, BASE_T - 1, ceil_z + 1
    )
    base = plate + wall
    bottom = (Align.CENTER, Align.CENTER, Align.MIN)
    for cx, cy in centers:
        boss = Cylinder(radius=BOSS_D / 2, height=BOSS_H, align=bottom).translate(
            (cx, cy, BASE_T)
        )
        post = Cylinder(
            radius=POST_D / 2, height=lip_land_z1 - BASE_T, align=bottom
        ).translate((cx, cy, BASE_T))
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
        base += boss + post + lip
        gb.post_probes.append(
            Cylinder(
                radius=POST_D / 2, height=face_width, align=bottom
            ).translate((cx, cy, GEAR_Z0))
        )
    for cx, cy in centers:  # slit after all posts are fused
        base -= Box(
            POST_D + 2 * LIP_PROTRUDE + 1, SLIT_W, SLIT_DEPTH + 0.2, align=bottom
        ).translate((cx, cy, post_top - SLIT_DEPTH))

    # snap bumps on the wall exterior: flat top (printable upright), 45 deg
    # chamfered underside that mates the 45 deg notch floor in the lid arm
    arm_xc = [ox0 + 0.25 * (ox1 - ox0), ox0 + 0.75 * (ox1 - ox0)]
    bump_cham_z = BUMP_TOP_Z - BUMP_LAND - BUMP_P  # chamfer meets wall here
    bump_pts = [
        (w_out - 0.2, BUMP_TOP_Z),
        (w_out + BUMP_P, BUMP_TOP_Z),
        (w_out + BUMP_P, BUMP_TOP_Z - BUMP_LAND),
        (w_out - 0.2, bump_cham_z - 0.2),  # 45 deg continues into the wall
    ]
    for side in (+1, -1):
        for xc in arm_xc:
            base += side_prism(bump_pts, side, xc, BUMP_W)
    gb.base = base
    gb.wall_probe = wall

    # ---- lid (assembled orientation; flipped for printing) -----------------
    lid = rbox(
        ox0 - ARM_GAP - ARM_T,
        ox1 + ARM_GAP + ARM_T,
        oy0 - ARM_GAP - ARM_T,
        oy1 + ARM_GAP + ARM_T,
        ceil_z,
        lid_top,
    )
    lid += rbox(
        ix0 + SNAP_CLEARANCE,
        ix1 - SNAP_CLEARANCE,
        iy0 + SNAP_CLEARANCE,
        iy1 - SNAP_CLEARANCE,
        ceil_z - LID_LIP_H,
        ceil_z,
    ) - rbox(
        ix0 + SNAP_CLEARANCE + LID_LIP_T,
        ix1 - SNAP_CLEARANCE - LID_LIP_T,
        iy0 + SNAP_CLEARANCE + LID_LIP_T,
        iy1 - SNAP_CLEARANCE - LID_LIP_T,
        ceil_z - LID_LIP_H - 1,
        ceil_z + 1,
    )
    lid -= Cylinder(radius=FINGER_D / 2, height=LID_T + 1, align=bottom).translate(
        (centers[2][0], centers[2][1], ceil_z - 0.5)
    )

    arm_in = w_out + ARM_GAP
    arm_tip_z = bump_cham_z - 0.65
    # notch floor: 45 deg plane 0.1 below the bump chamfer plane, so the two
    # 45 deg faces mate on lift; flat ceiling faces up in print orientation
    notch_floor_at_arm_in = bump_cham_z + ARM_GAP - 0.1
    notch_pts = [
        (arm_in - 0.2, notch_floor_at_arm_in - 0.2),
        (arm_in + BUMP_P - ARM_GAP + 0.1, notch_floor_at_arm_in + BUMP_P - ARM_GAP + 0.1),
        (arm_in + BUMP_P - ARM_GAP + 0.1, BUMP_TOP_Z + 0.2),
        (arm_in - 0.2, BUMP_TOP_Z + 0.2),
    ]
    tip_cham_pts = [  # 45 deg lead-in on the arm tip inner edge
        (arm_in - 0.1, arm_tip_z + 0.65),
        (arm_in - 0.1, arm_tip_z - 0.1),
        (arm_in + 0.65, arm_tip_z - 0.1),
    ]
    for side in (+1, -1):
        for xc in arm_xc:
            lid += rbox(
                xc - ARM_W / 2,
                xc + ARM_W / 2,
                min(side * arm_in, side * (arm_in + ARM_T)),
                max(side * arm_in, side * (arm_in + ARM_T)),
                arm_tip_z,
                lid_top,
            )
            lid -= side_prism(notch_pts, side, xc, NOTCH_W)
            lid -= side_prism(tip_cham_pts, side, xc, ARM_W + 0.2)
    gb.lid = lid

    gb.dims = dict(
        gear_top=gear_top,
        lip_z0=lip_z0,
        lip_r=lip_r,
        lip_land_z0=lip_land_z0,
        lip_land_z1=lip_land_z1,
        post_top=post_top,
        ceil_z=ceil_z,
        lid_top=lid_top,
        interior=(ix0, ix1, iy0, iy1),
        exterior=(ox0, ox1, oy0, oy1),
        w_out=w_out,
        arm_xc=arm_xc,
        arm_in=arm_in,
        arm_tip_z=arm_tip_z,
        bump_cham_z=bump_cham_z,
        bore_r=BORE_D / 2,
        post_r=POST_D / 2,
        # snap metadata for assembly_check
        lip_interference=lip_r - BORE_D / 2,  # radial, per side
        lip_deflection_len=SLIT_DEPTH,
        lip_flex_t=(POST_D - SLIT_W) / 2,
        arm_deflection=(w_out + BUMP_P) - (w_out + ARM_GAP),
        arm_flex_len=ceil_z - BUMP_TOP_Z,
        arm_flex_t=ARM_T,
    )
    return gb


def lid_print_orientation(gb: Gearbox) -> Part:
    """Lid flipped upside down, top face on the bed at z=0."""
    return gb.lid.rotate(Axis((0, 0, 0), (1, 0, 0)), 180).translate(
        (0, 0, gb.dims["lid_top"])
    )


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

    export_stl(gb.base, "base.stl")
    export_step(gb.base, "base.step")
    lid_print = lid_print_orientation(gb)
    export_stl(lid_print, "lid.stl")
    export_step(lid_print, "lid.step")

    assembly = Part() + gb.base + gb.lid
    for part in gb.gears:
        assembly += part
    export_stl(assembly, "assembly.stl")

    ox0, ox1, oy0, oy1 = gb.dims["exterior"]
    big = 5
    sec_posts = assembly & rbox(
        ox0 - big, ox1 + big, 0, oy1 + big, -1, gb.dims["lid_top"] + 1
    )
    export_stl(sec_posts, "section_posts.stl")
    sec_snap = assembly & rbox(
        ox0 - big, gb.dims["arm_xc"][0], oy0 - big, oy1 + big, -1,
        gb.dims["lid_top"] + 1,
    )
    export_stl(
        sec_snap.rotate(Axis((0, 0, 0), (0, 0, 1)), -90), "section_snap.stl"
    )

    d = gb.dims
    print(f"Center distances: "
          f"{gb.centers[1][0] - gb.centers[0][0]:.3f}, "
          f"{gb.centers[2][0] - gb.centers[1][0]:.3f} mm (via mesh_to)")
    print(f"Base exterior: {ox1 - ox0:.1f} x {oy1 - oy0:.1f} mm, "
          f"wall top {d['ceil_z']:.1f}, lid top {d['lid_top']:.1f} mm")
    print("Exported gears, base.stl, lid.stl (print orientation), "
          "assembly.stl, section_posts.stl, section_snap.stl")
