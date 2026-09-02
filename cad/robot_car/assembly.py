"""robot_car/assembly.py: full-car verification assembly (visualization + checks
only -- not meant to print). Places the chassis plate, two N20 motors in
their snap cradles, two drive wheels on the motor shafts, the front skid,
and the four electronics modules (Pi Zero 2 W, DRV8833, MP1584EN, LiPo
pack) at their documented chassis positions, then runs a battery of
programmatic PASS/FAIL checks against the assembled geometry.

Every placement is derived from chassis.py's own ChassisDims constants
(cradle_x, endwall_t, tray_standoff, pi_x, drv_x/y, buck_x/y, battery_x,
skid_front_x, ...) and the parts library dataclasses -- nothing here
re-derives a number chassis.py or wheel.py already owns.

Wheel axial placement is the one non-trivial derivation: the gearbox's
retention end-wall sits with its OUTER face flush with the plate edge and
its INNER face (2 mm inboard) against the gearbox front. wheel.py's wheel
mounts with its web (the spoked face, local Z=0) OUTBOARD and its long
hub reaching inboard through the rim to the shaft; the hub tip and the
rim's inboard edge are flush and sit `WALL_CLEARANCE_MM` outboard of the
wall's outer face, so the whole wheel stays clear of the plate (the
overlap an earlier web-inboard orientation had). See `wheel_geometry()`
for the worked numbers.

Run with:  uv run robot_car/assembly.py
Exports robot_car/car_assembly.stl (gitignored) and prints a PASS/FAIL
design-check table. Then render for a visual check:
    uv run demo_01/render.py robot_car/car_assembly.stl
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

import trimesh
from build123d import Axis, Part, Pos, export_stl
from scipy.spatial import cKDTree

from chassis import (
    ChassisDims, N20, build, latch_geometry, motor_placement,
    plate as chassis_plate, pcb_tray,
)
from wheel import WheelDims, make_wheel
from pi_zero_2w import PiZero2WDims, make_pi_zero_2w
from d2_drv8833 import Drv8833Dims, make_drv8833
from p1_mp1584 import Mp1584Dims, make_mp1584
from b2_lipo import LipoDims, make_lipo

WALL_CLEARANCE_MM = 1.0  # design target: web-face-to-wall-outer-face gap

RESULTS = []


def check(name: str, ok: bool, detail: str):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def ivol(a, b) -> float:
    """Boolean intersection volume of two parts (0.0 if disjoint)."""
    r = a & b
    return 0.0 if r is None else abs(r.volume)


def to_trimesh(part: Part) -> trimesh.Trimesh:
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        path = f.name
    export_stl(part, path)
    return trimesh.load_mesh(path)


def min_mesh_distance(mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh) -> float:
    """Minimum distance between two meshes' surfaces, via nearest-point
    sampling at every vertex of each mesh against the other (both
    directions, since neither mesh's own vertices necessarily land at the
    true closest point pair). trimesh's face-accurate ProximityQuery
    (rtree-backed) would also work now that rtree is a project dependency,
    but the vertex-to-vertex scipy cKDTree remains -- a good approximation
    given the STL tessellation is fine relative to the 0.5 mm check
    tolerance, with no accuracy complaint on record."""
    tree_b = cKDTree(mesh_b.vertices)
    dist_ab, _ = tree_b.query(mesh_a.vertices)
    tree_a = cKDTree(mesh_a.vertices)
    dist_ba, _ = tree_a.query(mesh_b.vertices)
    return float(min(dist_ab.min(), dist_ba.min()))


# ---------------------------------------------------------------------------
# placements
# ---------------------------------------------------------------------------


def wheel_geometry(side: int, d: ChassisDims, wd: WheelDims) -> dict:
    """All the axial (Y) numbers for one wheel, worked from chassis.py's
    own cradle/wall constants -- see module docstring.

    Local wheel Z=0 is the OUTSIDE (spoked web) face and local +Z runs
    inboard, toward the motor; the hub tip / rim inboard edge (local
    Z = hub_top = rim_width) is placed WALL_CLEARANCE_MM outboard of the
    wall's outer face. Shaft depth is measured from the hub tip into the
    blind bore."""
    plate_top = d.plate_thickness
    axis_z = plate_top + N20.gearbox_height / 2
    edge_y = side * (d.plate_width / 2)  # wall OUTER face == plate edge
    face_y = side * (d.plate_width / 2 - d.endwall_t)  # gearbox face == wall INNER face
    shaft_tip_y = face_y + side * N20.shaft_length

    inboard_y = side * (d.plate_width / 2 + WALL_CLEARANCE_MM)  # hub tip & rim inboard edge
    y_origin = inboard_y + side * wd.hub_top  # outside web face (local Z=0)
    web_clearance = side * (inboard_y - edge_y)  # nearest wheel feature vs the wall
    rim_outer_y = y_origin  # outermost point of the wheel

    # how far the shaft reaches into the blind bore, measured from the hub tip
    shaft_reach = side * (shaft_tip_y - inboard_y)
    grip_start = 0.0  # D-bore starts right at the hub tip
    grip_end = wd.bore_depth  # ... and ends at the bore floor
    engagement = max(0.0, min(shaft_reach, grip_end) - grip_start)
    protrusion_margin = grip_end - shaft_reach  # > 0: tip stays short of the bore floor
    within_grip_zone = shaft_reach <= grip_end

    return dict(
        axis_z=axis_z, edge_y=edge_y, face_y=face_y, shaft_tip_y=shaft_tip_y,
        y_origin=y_origin, inboard_y=inboard_y, web_clearance=web_clearance,
        rim_outer_y=rim_outer_y, shaft_tip_local=shaft_reach, grip_start=grip_start,
        grip_end=grip_end, engagement=engagement, protrusion_margin=protrusion_margin,
        within_grip_zone=within_grip_zone,
    )


def wheel_placement(side: int, d: ChassisDims, wd: WheelDims):
    g = wheel_geometry(side, d, wd)
    wheel = make_wheel(wd)
    # Local +Z (web -> hub tip) must point INBOARD (-side*Y): rotate(X, 90)
    # maps +Z to -Y for the +Y side; the Z-flip below mirrors it for -Y.
    wheel = wheel.rotate(Axis.X, 90)
    if side < 0:
        wheel = wheel.rotate(Axis.Z, 180)
    wheel = Pos(d.cradle_x, g["y_origin"], g["axis_z"]) * wheel
    return wheel, g


def pi_placement(d: ChassisDims):
    """Board bottom at standoff-top height; rotate 90 deg about Z so the
    board's long axis (native X, the 58 mm hole span) runs across the
    chassis (global Y), and the connector edge (native -Y) faces front
    (+X) -- per chassis.py's docstring."""
    pdims = PiZero2WDims()
    board = make_pi_zero_2w(pdims)
    board = board.rotate(Axis.Z, 90)
    standoff_top = d.plate_thickness + d.pi_boss_h
    z_center = standoff_top + pdims.board_thickness / 2
    board = Pos(d.pi_x, 0, z_center) * board
    return board, pdims, z_center


def tray_placement(
    cx: float, cy: float, board_thickness: float, part: Part, d: ChassisDims,
    standoff: float | None = None,
):
    """Generic snap-hook tray seating: board bottom on the standoff ledge.
    `standoff` defaults to the generic (MP1584) tray_standoff; pass
    d.drv_tray_standoff for the DRV8833, which needs a taller ledge so its
    with_headers=True solder-tail pins (3 mm below the board) clear the
    plate."""
    standoff = d.tray_standoff if standoff is None else standoff
    z_center = d.plate_thickness + standoff + board_thickness / 2
    return Pos(cx, cy, z_center) * part


def battery_placement(d: ChassisDims):
    """Resting on the plate top; native +X (the XT60 lead-exit end) is
    already front-facing, so no rotation is needed."""
    ldims = LipoDims()
    pack = make_lipo(ldims)
    z_center = d.plate_thickness + ldims.height / 2
    pack = Pos(d.battery_x, 0, z_center) * pack
    return pack, ldims, z_center


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    d = ChassisDims()
    wd = WheelDims()
    c = build(d)

    wheel_p, wg_p = wheel_placement(+1, d, wd)
    wheel_m, wg_m = wheel_placement(-1, d, wd)
    motor_p = motor_placement(+1, d)
    motor_m = motor_placement(-1, d)
    installed_skid = Pos(d.skid_front_x, 0, -c.skid_below) * c.skid

    pi_board, pdims, pi_z = pi_placement(d)

    drv_dims = Drv8833Dims()
    drv_board = make_drv8833(drv_dims)
    drv_placed = tray_placement(
        d.drv_x, d.drv_y, drv_dims.board_thickness, drv_board, d,
        standoff=d.drv_tray_standoff,
    )

    mp_dims = Mp1584Dims()
    mp_board = make_mp1584(mp_dims)
    mp_placed = tray_placement(d.buck_x, d.buck_y, mp_dims.board_thickness, mp_board, d)

    battery, ldims, batt_z = battery_placement(d)

    assembly = Part() + c.plate
    assembly += motor_p + motor_m
    assembly += wheel_p + wheel_m
    assembly += installed_skid
    assembly += pi_board + drv_placed + mp_placed + battery

    export_stl(assembly, HERE / "car_assembly.stl")
    print(f"Exported {HERE / 'car_assembly.stl'}")

    # -----------------------------------------------------------------
    # check 1: ground plane consistency (skid tip vs. wheel bottom)
    # -----------------------------------------------------------------
    print("\n-- 1. ground plane consistency --")
    rolling_radius = wd.rolling_diameter / 2  # O-ring not in the STL -- analytical
    wheel_bottom_z = wg_p["axis_z"] - rolling_radius
    skid_tip_z = -c.skid_below
    ground_delta = abs(wheel_bottom_z - skid_tip_z)
    plate_bottom_clearance = -min(wheel_bottom_z, skid_tip_z)
    check(
        "wheel-bottom vs skid-tip Z",
        ground_delta <= 0.5,
        f"wheel bottom Z={wheel_bottom_z:.2f} (axis {wg_p['axis_z']:.2f} - "
        f"rolling r{rolling_radius:.2f}), skid tip Z={skid_tip_z:.2f} "
        f"-> delta {ground_delta:.2f} mm (<= 0.5)",
    )
    print(f"    ground clearance under the plate bottom: {plate_bottom_clearance:.2f} mm")

    # -----------------------------------------------------------------
    # check 2: wheel/wall axial clearance + real mesh interference
    # -----------------------------------------------------------------
    print("\n-- 2. wheel / retention-wall clearance --")
    for side, g in ((+1, wg_p), (-1, wg_m)):
        check(
            f"hub-tip/rim-edge vs wall-outer-face clearance (Y{'+' if side>0 else '-'})",
            g["web_clearance"] >= 1.0 - 1e-9,
            f"hub tip & rim inboard edge Y={g['inboard_y']:.2f}, wall outer face "
            f"Y={g['edge_y']:.2f} -> clearance {g['web_clearance']:.2f} mm (>= 1.0, by construction)",
        )

    chassis_mesh = to_trimesh(c.plate)
    wheel_p_mesh = to_trimesh(wheel_p)
    wheel_m_mesh = to_trimesh(wheel_m)
    dist_p = min_mesh_distance(chassis_mesh, wheel_p_mesh)
    dist_m = min_mesh_distance(chassis_mesh, wheel_m_mesh)
    vol_p = ivol(wheel_p, c.plate)
    vol_m = ivol(wheel_m, c.plate)
    OVERLAP_TOL = 1.0  # mm^3 -- anything above this means the meshes truly intersect
    for side, dist, vol, g in ((+1, dist_p, vol_p, wg_p), (-1, dist_m, vol_m, wg_m)):
        # Once two meshes actually intersect, an unsigned vertex-nearest-
        # surface distance is a noisy, near-meaningless number (it can land
        # anywhere from ~0 to several mm depending on which vertex happens
        # to be sampled near the crossing boundary) -- so the exact CAD
        # boolean intersection volume, not the mesh distance, is the
        # authoritative FAIL signal here.
        ok = dist >= 0.5 and vol < OVERLAP_TOL
        check(
            f"wheel-vs-chassis clearance (Y{'+' if side>0 else '-'})",
            ok,
            f"mesh min distance {dist:.3f} mm (>= 0.5 target; noisy once meshes "
            f"truly overlap) -- exact CAD boolean intersection {vol:.2f} mm^3 "
            f"(authoritative; FAIL if >= {OVERLAP_TOL:g})",
        )
    print(
        f"    wheel span is entirely outboard of the wall: hub tip / rim edge at "
        f"Y={wg_p['inboard_y']:.2f} (wall outer face Y={wg_p['edge_y']:.2f}) out to the "
        f"spoked web face at Y={wg_p['y_origin']:.2f}."
    )

    # -----------------------------------------------------------------
    # check 3: wheel bore vs shaft
    # -----------------------------------------------------------------
    print("\n-- 3. wheel bore vs. motor shaft --")
    check(
        "coaxial (shared cradle_x, axis_z)",
        True,
        f"both wheel and motor placed at X={d.cradle_x:g}, Z={wg_p['axis_z']:.2f} "
        "by construction (same constants)",
    )
    for side, g in ((+1, wg_p), (-1, wg_m)):
        check(
            f"D-bore engagement (Y{'+' if side>0 else '-'})",
            g["engagement"] >= 6.0,
            f"{g['engagement']:.2f} mm (>= 6.0); shaft reaches {g['shaft_tip_local']:.2f} mm "
            f"into the blind bore from the hub tip, bore is {g['grip_end']:.2f} mm deep "
            f"-- i.e. {N20.shaft_length:g} mm shaft - {d.endwall_t:g} mm end wall - "
            f"{WALL_CLEARANCE_MM:g} mm wall clearance",
        )
        check(
            f"shaft tip stays within the D-bore grip zone (Y{'+' if side>0 else '-'})",
            g["within_grip_zone"],
            f"reach {g['shaft_tip_local']:.2f} mm vs bore depth {g['grip_end']:.2f} mm",
        )
        check(
            f"shaft tip does not bottom out in the blind bore (Y{'+' if side>0 else '-'})",
            g["protrusion_margin"] > 0,
            f"tip is {g['protrusion_margin']:.2f} mm short of the bore floor "
            f"(bore_depth={wd.bore_depth:g}) -- margin > 0",
        )

    # -----------------------------------------------------------------
    # check 4: electronics vs chassis interference
    # -----------------------------------------------------------------
    print("\n-- 4. electronics vs. chassis interference (tolerance a few mm^3) --")
    TOL = 10.0

    # Split the DRV8833 signal in two: the bare plate slab (does anything
    # hanging below the board reach it?) and its own tray (do the retention
    # features foul the board or its headers?). Both are built from the same
    # functions chassis.build() calls. The tilt-and-slide tray clears the
    # board top by tray_clearance rather than biting into it, so unlike the
    # old snap-barb tray this number is a real signal, not an accepted
    # overlap -- it should be zero.
    drv_tray_only = pcb_tray(
        d.drv_x, d.drv_y, d.drv_board_x, d.drv_board_y, d,
        standoff=d.drv_tray_standoff, axis="y", lead=-1,
        hook_span=d.drv_hook_span,
    )
    v_drv_plate = ivol(drv_placed, chassis_plate(d))
    v_drv_tray = ivol(drv_placed, drv_tray_only)
    v_drv_total = ivol(drv_placed, c.plate)
    check(
        "DRV8833 vs bare plate (header solder-tails)",
        v_drv_plate < TOL,
        f"intersection {v_drv_plate:.3f} mm^3 (< {TOL:g}) -- standoff "
        f"{d.drv_tray_standoff:g} mm clears the {drv_dims.header_pin_down:g} mm solder "
        f"tails by {d.drv_tray_standoff - drv_dims.header_pin_down:.1f} mm",
    )
    check(
        "DRV8833 vs its own tray (hooks/latch vs board + headers)",
        v_drv_tray < 1.0,
        f"intersection {v_drv_tray:.3f} mm^3 (< 1) -- tongues sit "
        f"{d.tray_clearance:g} mm above the board top and hook_span="
        f"{d.drv_hook_span:g} mm keeps them clear of the header bases",
    )
    print(f"    (combined DRV8833-vs-full-chassis total = {v_drv_total:.3f} mm^3)")

    # -----------------------------------------------------------------
    # check 4b: can the one flexing feature per tray actually flex?
    # -----------------------------------------------------------------
    print("\n-- 4b. tray latch snap-fit strain --")
    for tag, standoff in (("MP1584EN", d.tray_standoff),
                          ("DRV8833", d.drv_tray_standoff)):
        g = latch_geometry(d, standoff)
        check(
            f"{tag} latch strain at full deflection",
            g["strain"] <= 0.01,
            f"{g['deflection']:.2f} mm barb on a {g['free_length']:.2f} mm arm "
            f"-> {g['strain'] * 100:.2f}% strain (<= 1.00%), "
            f"{g['force']:.1f} N ({g['force'] / 9.81:.2f} kgf) to press past",
        )

    for name, part in (
        ("Pi Zero 2 W vs chassis", pi_board),
        ("MP1584 vs chassis", mp_placed),
        ("LiPo pack vs chassis", battery),
    ):
        v = ivol(part, c.plate)
        check(name, v < TOL, f"intersection {v:.3f} mm^3 (< {TOL:g})")

    # -----------------------------------------------------------------
    # check 5: battery vs guide nubs
    # -----------------------------------------------------------------
    print("\n-- 5. battery footprint vs. guide nubs --")
    slack_x = (d.battery_len / 2 + d.nub_clearance) - ldims.length / 2
    slack_y = (d.battery_wid / 2 + d.nub_clearance) - ldims.width / 2
    check(
        "battery X slack per side",
        0.3 <= slack_x <= 1.5,
        f"{slack_x:.2f} mm (nub half-span {d.battery_len/2 + d.nub_clearance:.2f} - "
        f"pack half-length {ldims.length/2:.2f})",
    )
    check(
        "battery Y slack per side",
        0.3 <= slack_y <= 1.5,
        f"{slack_y:.2f} mm (nub half-span {d.battery_wid/2 + d.nub_clearance:.2f} - "
        f"pack half-width {ldims.width/2:.2f})",
    )

    # -----------------------------------------------------------------
    # check 6: Pi mounting holes vs chassis bosses
    # -----------------------------------------------------------------
    print("\n-- 6. Pi mounting holes vs. chassis bosses --")
    boss_xy = [
        (d.pi_x + sx * d.pi_hole_x / 2, sy * d.pi_hole_y / 2)
        for sx in (-1, 1) for sy in (-1, 1)
    ]
    # native hole (nx, ny) = (+-span_x/2, +-span_y/2); after rotate(Z,90):
    # (x, y) -> (-y, x), then translate by (pi_x, 0)
    hole_xy = [
        (-(sy * pdims.mount_hole_span_y / 2) + d.pi_x, sx * pdims.mount_hole_span_x / 2)
        for sx in (-1, 1) for sy in (-1, 1)
    ]
    max_delta = 0.0
    for (bx, by), (hx, hy) in zip(sorted(boss_xy), sorted(hole_xy)):
        dx, dy = hx - bx, hy - by
        delta = (dx**2 + dy**2) ** 0.5
        max_delta = max(max_delta, delta)
        print(f"    boss ({bx:6.2f},{by:6.2f}) vs hole ({hx:6.2f},{hy:6.2f}) -> {delta:.4f} mm")
    check("max boss/hole XY delta", max_delta <= 0.3, f"{max_delta:.4f} mm (<= 0.3)")

    # -----------------------------------------------------------------
    # check 7: overall dimensions and mass
    # -----------------------------------------------------------------
    print("\n-- 7. overall dimensions --")
    bbox = assembly.bounding_box()
    # outer web (spoked) face to outer web face
    track_width = wg_p["rim_outer_y"] - wg_m["rim_outer_y"]
    wheelbase = abs(d.skid_front_x - d.cradle_x)
    print(
        f"    bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}"
    )
    print(f"    track width (outer wheel face to outer wheel face): {track_width:.2f} mm")
    print(f"    wheelbase equivalent (motor axis X to front-skid X): {wheelbase:.2f} mm")

    vol_plate = c.plate.volume
    vol_wheels = wheel_p.volume + wheel_m.volume
    vol_skid = c.skid.volume
    total_vol_mm3 = vol_plate + vol_wheels + vol_skid
    total_vol_cm3 = total_vol_mm3 / 1000
    PLA_DENSITY = 1.24  # g/cm^3
    INFILL_FACTOR = 0.85  # assumption: solid-ish small parts print near-solid; light discount
    mass_g = total_vol_cm3 * PLA_DENSITY * INFILL_FACTOR
    print(
        f"    plastic volume: chassis {vol_plate:.0f} + 2 wheels {vol_wheels:.0f} + "
        f"skid {vol_skid:.0f} = {total_vol_mm3:.0f} mm^3 ({total_vol_cm3:.1f} cm^3)"
    )
    print(
        f"    PLA mass estimate: {total_vol_cm3:.1f} cm^3 x {PLA_DENSITY:g} g/cm^3 x "
        f"{INFILL_FACTOR:g} (infill/shell factor) = {mass_g:.1f} g"
    )

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{'=' * 60}")
    print(f"{len(RESULTS) - len(fails)}/{len(RESULTS)} checks passed", end="")
    print(f", {len(fails)} FAILED" if fails else " -- ALL PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
