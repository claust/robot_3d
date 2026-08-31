"""demo_07: fidget gearbox — the demo_04 three-gear train with a sliding
smallest gear that clicks between an engaged and a disengaged position.

The z12 gear rides a one-piece carriage that slides 4 mm along the frame's
axis line. The frame's tail becomes an open two-rail fork; the carriage's
side walls wrap around the rail outer edges, thin hold-down strips pass
over the rail tops, and a solid pedestal rises through the gap between the
rails to carry the gear boss + snap post at the same height as the fixed
gears (GEAR_Z0 unchanged from demo_04). Two spring fingers in the carriage
bottom plate carry detent bumps that click into through-holes in the rails
at each end of the travel; the pedestal nose stopping 0.1 mm short of the
deck face guards against over-travel into a jammed mesh. A paddle with an
upturned lip at the carriage rear, below the plank, is the shift handle.

All parts print supportless, flat side down (the only bridges are the two
hold-down strips, ~4.4 mm span). Gears are identical to demo_04's.

Run with:  uv run fidget_gearbox.py [module] [z1] [z2] [z3] [face_width]
Exports per-part STL/STEP plus engaged/disengaged assemblies and sections.
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
    Pos,
    Rectangle,
    Sphere,
    export_step,
    export_stl,
    extrude,
    fillet,
)

# ---- driving parameters (identical to demo_04) -----------------------------
MODULE = 1.0
TEETH = (12, 20, 30)
FACE_WIDTH = 6.0
BACKLASH_COEFF = 0.15  # mesh_to backlash, in units of module

# ---- calibrated clearances (fit_test.py coupons, X2D, white PLA, 0.2 mm) ---
RUN_CLEARANCE = 0.2  # radial: gear bore on post; DO NOT re-derive
SLIDE_CLR = 0.2  # carriage sliding fits reuse the same calibrated value

LAYER_HEIGHT = 0.2

# ---- frame / post geometry (identical to demo_04 where shared) -------------
POST_D = 5.0
BORE_D = POST_D + 2 * RUN_CLEARANCE  # 5.4
FRAME_W = 20.0
RAIL_W = 4.0
ARM_W = 4.0
CROSS_W = 8.0
ARM_H = 3.0
FILLET_R = 1.5
BOSS_D = 8.0
BOSS_H = 1.0
GEAR_Z0 = ARM_H + BOSS_H  # 4.0, gear bottom face — unchanged from demo_04
AXIAL_PLAY = 0.3

LIP_PROTRUDE = 0.35
LIP_LAND = 0.4
LIP_TOP_R = 2.2
SLIT_W = 1.5
SLIT_DEPTH = 6.5

# ---- carriage / slide geometry ---------------------------------------------
TRAVEL = 4.0  # engaged -> disengaged slide distance
ENGAGE_BACKOFF = 0.1  # engaged center distance = mesh_to distance + this;
#                       the deck stop then sits exactly at the nominal mesh
#                       distance, so over-travel can never jam the teeth
VERT_PLAY = 0.2  # carriage vertical float (plate-to-plank / strip-to-rail)
PLATE_T = 2.0  # carriage bottom plate, below the plank
WALL_T = 2.0  # side walls wrapping the rail outer edges
STRIP_T = 0.4  # hold-down strips over the rail tops, 2 layers
CAR_X0, CAR_X1 = -12.0, 6.0  # carriage plate/walls span (gear axis at 0)
PED_X0 = -8.0  # pedestal rear; front is CAR_X1 (the stop nose)
BOSS2_H = 0.4  # boss height on the pedestal (pedestal top to GEAR_Z0)
PED_TOP = GEAR_Z0 - BOSS2_H  # 3.6 — also the strip top (they must fuse)
STRIP_Z0 = ARM_H + VERT_PLAY  # 3.2

# detent spring fingers in the carriage plate (one per side, under a rail)
KERF = 0.8  # slit width freeing each finger (wide enough not to fuse)
FING_Y0, FING_Y1 = 6.2, 9.4  # finger band; bump centered at y = +-8
FING_ROOT = 0.0  # fingers are cantilevered from here toward the tip
FING_TIP = -11.6  # free end, kerfed clear of the plate and paddle
FING_T = 1.4  # finger thinned from PLATE_T for compliance
BUMP_X = -10.5  # bump center, carriage-local
BUMP_R0, BUMP_R1 = 1.3, 0.4  # detent bump cone radii (base at finger top)
BUMP_ENGAGE = 0.4  # bump tip protrusion above the plank underside
HOLE_D = 2.4  # detent through-holes in the rails (leaves 0.8 rail walls)

# paddle handle at the carriage rear, below the plank
PAD_X0, PAD_HW = -21.0, 7.0  # paddle reaches back to here, half-width
LIP_WALL = 1.2  # upturned thumb lip at the paddle rear
LIP_TOP = 1.5  # lip top (must stay clear of the rails: it never goes
#                under them — max lip x at engaged is well behind the tail)

TAIL_MARGIN = 2.5  # rails extend this far past the disengaged carriage rear
RET_R0, RET_R1, RET_H = 1.0, 0.3, 0.3  # retention cones on the rail tops

# finger divots in the big gear's top face: fingertip recesses to crank it.
# Three at 120 deg keep the gear balanced when it spins fast.
DIVOT_N = 3
DIVOT_RPOS = 8.5  # divot centers, radius from the gear axis
DIVOT_DIA = 6.5
DIVOT_DEPTH = 1.8  # leaves face_width - 1.8 of floor under each divot


@dataclass
class FidgetGearbox:
    """All parts in engaged position plus the numbers the checks need."""

    module: float
    teeth: tuple
    face_width: float
    gears_pgw: list
    centers: list  # gear centers in ENGAGED position (z12 backed off)
    tip_radii: list
    gears: list  # build123d Parts, engaged position
    frame: Part = None
    carriage: Part = None  # without the detent bumps (they interfere by design)
    bumps: Part = None  # the two detent bump cones, separate for the checks
    rail_probe: Part = None
    post_probes: list = field(default_factory=list)
    dims: dict = field(default_factory=dict)

    @property
    def carriage_full(self) -> Part:
        return self.carriage + self.bumps


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    return Box(
        x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN)
    ).translate((x0, y0, z0))


def rrect(x0, x1, y0, y1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2) * Rectangle(x1 - x0, y1 - y0)


def build_gear_train(module, teeth, face_width, backlash):
    gears = [
        pgw.SpurGear(
            number_of_teeth=z, module=module, height=face_width, root_fillet=0.2
        )
        for z in teeth
    ]
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


def post_with_lip(cx, cy, base_z, dims):
    """Boss-less snap post identical to demo_04's, rising from base_z."""
    bottom = (Align.CENTER, Align.CENTER, Align.MIN)
    lip_r = dims["lip_r"]
    post = Cylinder(
        radius=POST_D / 2, height=dims["lip_land_z1"] - base_z, align=bottom
    ).translate((cx, cy, base_z))
    lip = (
        Cone(POST_D / 2, lip_r, LIP_PROTRUDE, align=bottom).translate(
            (cx, cy, dims["lip_z0"])
        )
        + Cylinder(radius=lip_r, height=LIP_LAND, align=bottom).translate(
            (cx, cy, dims["lip_land_z0"])
        )
        + Cone(lip_r, LIP_TOP_R, lip_r - LIP_TOP_R, align=bottom).translate(
            (cx, cy, dims["lip_land_z1"])
        )
    )
    slit = Box(
        POST_D + 2 * LIP_PROTRUDE + 1, SLIT_W, SLIT_DEPTH + 0.2, align=bottom
    ).translate((cx, cy, dims["post_top"] - SLIT_DEPTH))
    return post + lip, slit


def build(module=MODULE, teeth=TEETH, face_width=FACE_WIDTH) -> FidgetGearbox:
    gears_pgw, mesh_centers, gear_parts = build_gear_train(
        module, teeth, face_width, BACKLASH_COEFF
    )
    tip_radii = [g.addendum_radius for g in gears_pgw]

    # engaged z12 center: backed off from the pure mesh position so the
    # deck stop (at the nominal mesh distance) is an over-travel guard
    x_e = mesh_centers[0][0] - ENGAGE_BACKOFF
    centers = [(x_e, mesh_centers[0][1])] + mesh_centers[1:]
    gb = FidgetGearbox(
        module, teeth, face_width, gears_pgw, centers, tip_radii, []
    )

    gear_top = GEAR_Z0 + face_width
    lip_z0 = gear_top + AXIAL_PLAY
    lip_r = POST_D / 2 + LIP_PROTRUDE
    lip_land_z0 = lip_z0 + LIP_PROTRUDE
    lip_land_z1 = lip_land_z0 + LIP_LAND
    post_top = lip_land_z1 + (lip_r - LIP_TOP_R)

    gb.gears = [p.translate((0, 0, GEAR_Z0)) for p in gear_parts]
    gb.gears[0] = gb.gears[0].translate((-ENGAGE_BACKOFF, 0, 0))

    # finger divots in the big gear's top face (spherical caps, cut from
    # above: every divot surface faces upward, so nothing overhangs)
    a = DIVOT_DIA / 2
    sph_r = (a**2 + DIVOT_DEPTH**2) / (2 * DIVOT_DEPTH)
    cx3, cy3 = centers[-1]
    for k in range(DIVOT_N):
        ang = 2 * np.pi * k / DIVOT_N
        # rotate the cutter so the sphere mesh's pole singularity sits on
        # its equator, not at the divot floor (avoids degenerate STL facets)
        gb.gears[-1] -= (
            Sphere(radius=sph_r)
            .rotate(Axis.X, 90)
            .translate(
                (
                    cx3 + DIVOT_RPOS * np.cos(ang),
                    cy3 + DIVOT_RPOS * np.sin(ang),
                    gear_top - DIVOT_DEPTH + sph_r,
                )
            )
        )

    dims = dict(
        gear_top=gear_top,
        lip_z0=lip_z0,
        lip_r=lip_r,
        lip_land_z0=lip_land_z0,
        lip_land_z1=lip_land_z1,
        post_top=post_top,
        bore_r=BORE_D / 2,
        post_r=POST_D / 2,
        lip_interference=lip_r - BORE_D / 2,
        lip_deflection_len=SLIT_DEPTH,
        lip_flex_t=(POST_D - SLIT_W) / 2,
    )

    # ---- frame: deck ladder for z20/z30 + open two-rail fork for the slide -
    x_stop = x_e + CAR_X1 + ENGAGE_BACKOFF  # deck face; nose gap 0.1 engaged
    x_tail = x_e + CAR_X0 - TRAVEL - TAIL_MARGIN
    oy1 = FRAME_W / 2
    iy1 = oy1 - RAIL_W  # rail inner edge -> the fork void half-width
    rx1 = centers[-1][0] + CROSS_W / 2

    plan = (
        rrect(x_tail, rx1, -oy1, -iy1)
        + rrect(x_tail, rx1, iy1, oy1)
        # solid deck between the rails from the stop face to the z20 hub:
        # its front face is the carriage's over-travel hard stop
        + rrect(x_stop, centers[1][0], -iy1, iy1)
        + rrect(centers[1][0], rx1, -ARM_W / 2, ARM_W / 2)  # spine
    )
    for cx, cy in centers[1:]:
        plan += rrect(cx - CROSS_W / 2, cx + CROSS_W / 2, -oy1, oy1)
    # fillet every plan corner EXCEPT the deck-face/void corners: a concave
    # fillet there would bulge into the void and collide with the sliding
    # pedestal's nose corners
    verts = [
        v
        for v in plan.vertices()
        if not (abs(v.X - x_stop) < 0.01 and abs(abs(v.Y) - iy1) < 0.01)
    ]
    plan = fillet(verts, FILLET_R)
    frame = Part() + extrude(plan, amount=ARM_H)

    bottom = (Align.CENTER, Align.CENTER, Align.MIN)
    slits = []
    for cx, cy in centers[1:]:
        boss = Cylinder(radius=BOSS_D / 2, height=BOSS_H, align=bottom).translate(
            (cx, cy, ARM_H)
        )
        post, slit = post_with_lip(cx, cy, ARM_H, dims)
        frame += boss + post
        slits.append(slit)
        gb.post_probes.append(
            Cylinder(radius=POST_D / 2, height=face_width, align=bottom).translate(
                (cx, cy, GEAR_Z0)
            )
        )
    for slit in slits:
        frame -= slit

    # detent through-holes in the rails (engaged / disengaged bump positions)
    hole_xs = [x_e + BUMP_X, x_e + BUMP_X - TRAVEL]
    rail_yc = (iy1 + oy1) / 2  # 8.0, the finger/bump/hole centerline
    for hx in hole_xs:
        for sy in (rail_yc, -rail_yc):
            frame -= Cylinder(
                radius=HOLE_D / 2, height=ARM_H + 2, align=bottom
            ).translate((hx, sy, -1))

    # retention cones on the rail tops near the tail: the carriage clicks
    # over them once during assembly and cannot drift off the fork
    ret_x = x_tail + 1.0
    for sy in (rail_yc, -rail_yc):
        frame += Cone(RET_R0, RET_R1, RET_H, align=bottom).translate(
            (ret_x, sy, ARM_H)
        )
    gb.frame = frame
    gb.rail_probe = rbox(x_tail, rx1, -oy1, -iy1, 0, ARM_H) + rbox(
        x_tail, rx1, iy1, oy1, 0, ARM_H
    )

    # ---- carriage (built carriage-local: gear axis at x=0, then moved) -----
    wall_iy = oy1 + SLIDE_CLR  # 10.2
    wall_oy = wall_iy + WALL_T  # 12.2
    # pedestal stops short of the finger kerf band so the kerf cuts stay in
    # open air (no ceiling faces over the slits); guidance comes from the
    # walls, so the extra 0.5 mm to the rail inner faces is fine
    ped_hw = FING_Y0 - KERF - 0.1  # 5.3
    plate_z1 = -VERT_PLAY
    plate_z0 = plate_z1 - PLATE_T

    plan = rrect(CAR_X0, CAR_X1, -wall_oy, wall_oy) + rrect(
        PAD_X0, CAR_X0, -PAD_HW, PAD_HW
    )
    plan = fillet(plan.vertices(), FILLET_R)
    car = Part() + extrude(plan, amount=PLATE_T).translate((0, 0, plate_z0))

    # side walls wrapping the rail outer edges; their outer plan corners get
    # the same fillet as the plate so the wall base never overhangs it
    wall_plan = rrect(CAR_X0, CAR_X1, wall_iy, wall_oy) + rrect(
        CAR_X0, CAR_X1, -wall_oy, -wall_iy
    )
    wall_verts = [v for v in wall_plan.vertices() if abs(v.Y) > wall_oy - 0.01]
    wall_plan = fillet(wall_verts, FILLET_R)
    car += extrude(wall_plan, amount=PED_TOP - plate_z1).translate(
        (0, 0, plate_z1)
    )
    for sy in (1, -1):
        car += rbox(  # hold-down strip: wall -> over the rail -> pedestal
            PED_X0, CAR_X1, sy * (ped_hw - 0.8), sy * (wall_oy - FILLET_R),
            STRIP_Z0, PED_TOP,
        )
    car += rbox(PED_X0, CAR_X1, -ped_hw, ped_hw, plate_z1, PED_TOP)  # pedestal
    car += Cylinder(radius=BOSS_D / 2, height=BOSS2_H, align=bottom).translate(
        (0, 0, PED_TOP)
    )
    post, slit = post_with_lip(0, 0, PED_TOP, dims)
    car = car + post - slit
    car += rbox(  # upturned thumb lip at the paddle rear (inside the fillets)
        PAD_X0, PAD_X0 + LIP_WALL, -PAD_HW + 1.5, PAD_HW - 1.5, plate_z0,
        LIP_TOP,
    )

    # free the two detent spring fingers: side kerfs, a tip kerf separating
    # the finger from the plate/paddle junction, and a thinning cut on top
    for sy in (1, -1):
        for ky0, ky1 in ((FING_Y0 - KERF, FING_Y0), (FING_Y1, FING_Y1 + KERF)):
            car -= rbox(
                FING_TIP - KERF, FING_ROOT, sy * ky0, sy * ky1,
                plate_z0 - 0.1, plate_z1 + 0.1,
            )
        car -= rbox(  # tip kerf
            FING_TIP - KERF, FING_TIP, sy * (FING_Y0 - KERF),
            sy * (FING_Y1 + KERF), plate_z0 - 0.1, plate_z1 + 0.1,
        )
        car -= rbox(  # thin the finger from the top for compliance
            FING_TIP, FING_ROOT, sy * FING_Y0, sy * FING_Y1,
            plate_z0 + FING_T, plate_z1 + 0.1,
        )
    bump_h = BUMP_ENGAGE + VERT_PLAY + (PLATE_T - FING_T)  # tip at +0.4
    bumps = Part()
    for sy in (rail_yc, -rail_yc):
        # base sunk 0.1 into the finger so the union has no coplanar seam
        bumps += Cone(BUMP_R0, BUMP_R1, bump_h + 0.1, align=bottom).translate(
            (BUMP_X, sy, plate_z0 + FING_T - 0.1)
        )

    gb.carriage = car.translate((x_e, 0, 0))
    gb.bumps = bumps.translate((x_e, 0, 0))
    gb.post_probes.insert(
        0,
        Cylinder(radius=POST_D / 2, height=face_width, align=bottom).translate(
            (x_e, 0, GEAR_Z0)
        ),
    )

    dims.update(
        x_engaged=x_e,
        x_stop=x_stop,
        x_tail=x_tail,
        rx1=rx1,
        hole_xs=hole_xs,
        ret_x=ret_x,
        rail_yc=rail_yc,
        wall_iy=wall_iy,
        wall_oy=wall_oy,
        ped_hw=ped_hw,
        plate_z0=plate_z0,
        plate_z1=plate_z1,
        nose_gap=x_stop - (x_e + CAR_X1),
        arm_under_gear=GEAR_Z0 - ARM_H,
        strip_under_gear=GEAR_Z0 - PED_TOP,
        bump_tip_z=plate_z0 + FING_T + bump_h,
        finger_len=abs(BUMP_X - FING_ROOT),
        finger_t=FING_T,
        exterior=(x_tail, rx1, -oy1, oy1),
    )
    gb.dims = dims
    return gb


if __name__ == "__main__":
    module = float(sys.argv[1]) if len(sys.argv) > 1 else MODULE
    teeth = tuple(int(a) for a in sys.argv[2:5]) if len(sys.argv) > 4 else TEETH
    face_width = float(sys.argv[5]) if len(sys.argv) > 5 else FACE_WIDTH

    gb = build(module, teeth, face_width)
    d = gb.dims

    for z, (cx, cy), part in zip(teeth, gb.centers, gb.gears):
        stem = f"gear_z{z}"
        printable = part.translate((-cx, -cy, -GEAR_Z0))
        export_stl(printable, f"{stem}.stl")
        export_step(printable, f"{stem}.step")
        print(f"{stem}: center ({cx:.3f}, {cy:.3f}), bore {BORE_D:g} mm")

    export_stl(gb.frame, "frame.stl")
    export_step(gb.frame, "frame.step")

    car_print = gb.carriage_full.translate((-d["x_engaged"], 0, -d["plate_z0"]))
    export_stl(car_print, "carriage.stl")
    export_step(car_print, "carriage.step")

    assembly = Part() + gb.frame + gb.carriage_full
    for part in gb.gears:
        assembly += part
    export_stl(assembly, "assembly.stl")

    slid = Part() + gb.frame
    slid += gb.carriage_full.translate((-TRAVEL, 0, 0))
    slid += gb.gears[0].translate((-TRAVEL, 0, 0))
    for part in gb.gears[1:]:
        slid += part
    export_stl(slid, "assembly_disengaged.stl")

    x0, x1, y0, y1 = d["exterior"]
    sec_len = assembly & rbox(x0 - 25, x1 + 20, 0, y1 + 25, -5, d["post_top"] + 1)
    export_stl(sec_len, "section_length.stl")
    bx = d["hole_xs"][0]
    sec_slide = assembly & rbox(bx - 1.0, bx + 1.0, y0 - 10, y1 + 10, -5, 12)
    export_stl(
        sec_slide.rotate(Axis((0, 0, 0), (0, 0, 1)), -90), "section_slide.stl"
    )

    a12 = gb.centers[1][0] - gb.centers[0][0]
    tips = gb.tip_radii[0] + gb.tip_radii[1]
    print(f"Engaged center distance {a12:.3f} mm "
          f"(mesh_to + {ENGAGE_BACKOFF:g} backoff), travel {TRAVEL:g} mm, "
          f"disengaged tip gap {a12 + TRAVEL - tips:.2f} mm")
    print(f"Frame {x1 - x0:.1f} x {y1 - y0:.1f} mm, fork tail at x={x0:.1f}; "
          f"carriage nose gap to deck stop {d['nose_gap']:.2f} mm")
    print("Exported gears, frame, carriage, assembly(+disengaged), sections")
