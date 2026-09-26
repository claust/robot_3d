"""robot_car: the chassis plate for the two-motor robot car.

One flat part, 130 x 94 x 3 mm (X x Y x Z), corner radius 6 mm, printed flat
side down with no supports. +X is FRONT, -X is REAR. The plate is centred
on the origin in X and Y; the bottom face is Z=0, the top face is Z =
plate_thickness (3 mm) and every feature grows up from there. ChassisDims
holds every number; this docstring says what each feature is and why.

LAYOUT

- Motors (M2 N20, two): one cradle per side at X=-31, output shafts
  pointing out past the plate edge. A rigid U-channel holds the gearbox
  and can, both sitting directly on the plate; an end wall at the plate
  edge, slotted for the Ø4 boss, takes the axial load where the gearbox
  face lands. A separately printed lid (motor_lid, exported as
  motor_lid.stl -- print two) slides on from inboard along dovetail rails
  on the outside of the channel walls, stops on the end wall, and clicks
  into a detent recess in each rail. Its centre pad presses 0.30 mm down
  on the motor's top, so the motor is clamped, not just fenced in. The lid
  ends before the can's rear face, leaving the solder tabs and wires free.
  The geometry is lid_coupons.py's (lid E: rail clearance 0.10, preload
  0.30). The motor's M1.6 bracket holes are not used.
- Raspberry Pi Zero 2 W (C1), front area: four bosses with Ø2.2 pilots for
  self-tapping M2.5 screws, on the 58 x 23 mm hole rectangle, board long
  axis across the car, connector edge facing front.
- Motor driver (D2 DRV8833), rear left: its own tilt-and-slide tray,
  drv_tray (see PCB TRAYS).
- Buck converter (P1 MP1584EN), mid right: the generic tilt-and-slide tray,
  pcb_tray. A Ø4 zip-tie hole past its +X short edge is the strain relief
  for the power leads.
- Battery (B2 2S LiPo, 93 x 35.2 mm calipered), centre: four L-shaped guide
  nubs hug its corners at 0.5 mm clearance, and one pair of 25 x 3 mm slots
  takes the 21 mm hook-and-loop strap. The XT60 lead exits at +X, toward
  the buck and the Pi.
- Skid: a Ø10 hole on the centreline at the front (X=55) and another at the
  rear (X=-58). The skid is a separate part that push-snaps up through
  either hole from underneath, on four slit prongs.
- Identity text engraved, mirrored, into the underside.

DESIGN RULES

- The lids slide on over the battery bay, so they go on before the
  battery and a motor comes out with the battery removed.
- The cradles sit at X=-31 so the lid skirts clear the DRV8833 tray behind
  them (0.5 mm). The tray can't move back: it already reaches the rear
  plate edge.
- Plate width 94 mm is set by the motors and the battery. Every motor
  dimension hangs off the plate edge, and the battery can't move out of the
  way in X or Z, so the edge is what keeps the N20's can and its rear
  solder tabs (which point at the pack and carry wires) clear of the pack.
  At 94 mm the can clears by 3.4 mm and the tabs by 0.9 mm.
- The motor's gearbox face lands 2 mm inboard of the plate edge, against
  the inside of the end wall, so the wall stands fully on the plate.
- The driver and buck sit off the centreline because the battery and the
  cradles leave no room there; the Pi sits at X=48 so the 93 mm pack fits
  behind it.
- Nothing may stick out past the plate edge: build() clips every added
  feature to the plate outline. A Ø10 hole placed exactly tangent to the
  plate edge meshes non-manifold, so every hole keeps real wall to the edge.
- Where a tray and a battery guide nub collide, the nub is trimmed by the
  tray's built geometry. The trays locate a board to a tenth of a mm; the
  nubs only fence a soft pack.
- Overlaps are checked on BUILT geometry (exact boolean volume), never on
  plan-view rectangles, and the motor bodies are checked against their
  neighbours, not just the cradles. The only intended overlap is each
  lid's pad pressing on its motor, checked against a range
  (overlap_check). The strap slots are in the check too: nothing may
  stand over the strap's path.
- Underside text is Arial Black 8 mm, 0.9 mm deep. It prints against the
  textured PEI sheet, which grains the plate face and the letter floors
  alike, so legibility comes from stroke width and depth.
- Strap slot: one 25 x 3 mm slot per side for the 21 mm strap, spanning X
  -25..0 between the cradles and the buck tray, 1 mm off the pack's side.
  The cradles stand in line with the slots, 0.4 mm past their outer
  edge.

PCB TRAYS

Both boards stand 7.0 mm off the plate on a tilt-and-slide tray: tilt the
board ~15 deg, tuck one long edge under two fixed 45 deg tongues, rotate it
down until the one flexing latch on the opposite edge clicks over. Press
the latch back with a fingernail to lift it out. Only the latch flexes.
A snap arm's travel grows with the square of its length, and the 7 mm
standoff is what gives the latch a ~9 mm arm: 0.4-0.5 mm of barb travel
stays under 1% strain in PLA at 2-3 N of finger force (latch_geometry,
cantilever). A short rigid post of the same height can't deflect 0.6 mm
without breaking, which is why the other retention points are rigid. The
standoff also clears the DRV8833's 3 mm header solder tails and leaves
room for wiring under both boards.

The DRV8833 (18.5 x 15.6 mm calipered, 1.6 mm thick) has straight pin
headers soldered pins-up along both short ends. They cover the board top
edge to edge there, so nothing reaches over the board except the two
tongues and the latch, all in the clear middle band of the long sides.
drv_tray differs from pcb_tray in three ways:
- The latch is PRELOADED (drv_latch_geometry). Its lower 45 deg face
  would cut 0.30 mm into the seated board's top edge, so the arm stays
  bent and presses the board down and against the tongue columns. The
  board can't rattle against a spring that is already leaning on it.
- The corners are end stops flush with the board top, over a 0.6 mm shelf
  that clears the header solder pads. End fit 0.05 mm per end.
- The tongues' 45 deg undersides start right at the seated board's edge,
  0.10 mm above it.
- The latch arm is 0.8 x 7 mm with a 1 mm radius on both sides of its
  root. It bends across the print layers and stays bent under the preload,
  so it is kept thin (strain scales with thickness for a given bend: 0.83%
  peak on insertion) and made wide to keep the clamping force (1.4 N).
  The radius removes the sharp corner at the plate where a square-rooted
  arm snaps off.
End fit and preload are coupon C of drv_coupons.py: no wiggle, and the
board still pops out by hand.

Run with:  uv run chassis.py [plate_length] [plate_width] [wheel_diameter]
Exports (gitignored): chassis.stl/.step, skid.stl/.step, and
chassis_assembly.stl (chassis + two reference N20 motors + the skid, all in
installed position, for visual verification only -- not meant to print).
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from build123d import (
    Align,
    Axis,
    Box,
    Cone,
    Cylinder,
    Part,
    Plane,
    Pos,
    Rectangle,
    Text,
    Wedge,
    chamfer,
    export_step,
    export_stl,
    extrude,
    fillet,
    mirror,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "parts"))
from n20_motor import N20Dims, make_motor  # noqa: E402

from lid_coupons import LidDims, lid_for_print, make_cradle, make_lid  # noqa: E402

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_TOP = (Align.CENTER, Align.CENTER, Align.MAX)


@dataclass
class ChassisDims:
    # ---- plate ---------------------------------------------------------
    plate_length: float = 130.0  # X
    plate_width: float = 94.0  # Y -- keeps the motors clear of the battery
    plate_thickness: float = 3.0
    corner_radius: float = 6.0
    wheel_diameter: float = 59.0  # rolling Ø of the wood-copy wheel (root 39 + 2 x cord 10); drives skid only

    # ---- N20 motor cradle + slide-on lid (one each per side) -----------
    # The cradle and lid geometry is lid_coupons.py's (lid_dims); these are
    # the numbers the car sets on it.
    cradle_x: float = -31.0  # lid skirt 0.5 mm clear of the DRV8833 tray
    channel_clearance: float = 0.2  # radial fit around the 10 mm can flats
    wall_t: float = 3.0
    # 1 mm of bare can left inboard of the channel and the lid: the rear
    # solder tabs sit on the can's rear FACE and reach 2.5 mm further
    # inboard, so they and their wires stay completely free.
    tail_exposed: float = 1.0
    endwall_t: float = 2.0
    endwall_slot_w: float = 4.5  # clears the Ø4 boss, open at the top
    lid_rail_clearance: float = 0.10  # lid_coupons.py lid E
    lid_pad_preload: float = 0.30  # lid_coupons.py lid E

    # ---- C1 Raspberry Pi Zero 2 W mount ---------------------------------
    pi_x: float = 48.0
    pi_hole_y: float = 58.0
    pi_hole_x: float = 23.0
    pi_board_y: float = 65.0  # footprint, for the overlap check
    pi_board_x: float = 30.0
    pi_boss_d: float = 5.5
    pi_boss_h: float = 5.0
    pi_pilot_d: float = 2.2

    # ---- tilt-and-slide PCB trays (D2 DRV8833, P1 MP1584EN) ------------
    # The standoff is what makes the latch work: it sets the arm's free
    # length, and a snap arm this short has no other way to earn travel.
    # 7.0 mm also clears the DRV8833's 3.0 mm header solder tails by 4.0 mm
    # and leaves room to route wiring under both boards.
    tray_standoff: float = 7.0  # board stands this high off the plate
    tray_board_t: float = 1.6
    tray_snap_hook_w: float = 3.0  # corner feature footprint, square
    tray_clearance: float = 0.15  # vertical, board top to hook underside
    tray_fit: float = 0.25  # in-plane, per side, board edge to post face
    # extra in-plane slack on the FIXED-hook edge only: rotating the board
    # down sweeps its leading top corner outward by board_t * sin(tilt),
    # ~0.4 mm at a 15 deg tilt, and it needs somewhere to go.
    tray_lead_slack: float = 0.5
    tray_hook_capture: float = 1.2  # fixed tongue reach over the board top
    # The one flexing feature. 0.4 mm of engagement costs 0.86% strain on a
    # 9.15 mm arm at 2.7 N -- see latch_geometry().
    tray_latch_barb: float = 0.4
    tray_latch_w: float = 4.0
    tray_latch_t: float = 1.2

    # Kept per-tray because only the DRV8833 has anything below its board
    # (with_headers=True solder tails, 3.0 mm down).
    drv_tray_standoff: float = 7.0

    # d2_drv8833.py's soldered header bases run 15.24 mm along Y at both X
    # ends of the board, so tongues at the board corners land on plastic,
    # not on the PCB. 3.0 mm puts both of them in the 13 mm-wide clear band
    # between the two rows.
    drv_hook_span: float = 3.0

    drv_x: float = -54.0
    drv_y: float = 29.0  # clears the battery guide nub, >= 1 mm to the plate edge
    drv_board_x: float = 18.5  # calipered
    drv_board_y: float = 15.6  # calipered

    # drv_tray. The seated board rests against the tongue side; every other
    # number is a gap to that. End fit and preload are drv_coupons.py's C.
    drv_end_fit: float = 0.05  # per end, 18.5 mm axis
    drv_lead_slack: float = 0.30  # tilt sweep room, 1.6 * sin(10 deg) = 0.28
    drv_latch_fit: float = 0.10  # latch face to board edge, board seated
    drv_latch_preload: float = 0.30
    drv_latch_barb: float = 0.9
    # The arm bends across the print layers, PLA's weak direction, and stays
    # bent by the preload whenever a board is in. Thin keeps the strain
    # down (it scales with thickness for a given bend), wide gives back the
    # clamping force, and the root radius on both sides removes the sharp
    # corner at the plate where a break starts.
    drv_latch_t: float = 0.8
    drv_latch_w: float = 7.0
    drv_latch_root_r: float = 1.0
    drv_tongue_clearance: float = 0.10
    # Corner shelf under the board: the header solder pads (Ø~1.7) sit
    # 1.45 mm in from both edges, so 0.6 mm is what clears them.
    drv_corner_ledge: float = 0.6
    drv_corner_wall: float = 1.5
    drv_corner_arm: float = 3.0

    buck_x: float = 13.0
    buck_y: float = -27.8  # 0.2 mm clear of the battery envelope
    buck_board_x: float = 22.0
    buck_board_y: float = 17.0  # the two 22 mm long edges stay open

    # ---- B2 LiPo strap bay (calipered) ----------------------------------
    battery_x: float = -16.0
    battery_len: float = 93.0  # X, calipered body length
    battery_wid: float = 35.2  # Y, calipered body width
    battery_h: float = 18.3  # thickest end -- for reference/docstring only
    nub_clearance: float = 0.5  # per side, footprint-to-nub
    nub_h: float = 3.0
    nub_arm: float = 6.0
    nub_t: float = 2.0
    # One slot per side, sized for the 21 mm hook-and-loop strap.
    strap_slot_len: float = 25.0
    strap_slot_wid: float = 3.0
    # slot Y = wid/2 + this: 1 mm off the pack's side, and 0.4 mm short of
    # the motor cradles' inboard ends, which stand in line with the slots
    strap_y_offset: float = 2.5
    strap_stations: tuple = (-12.5,)

    # ---- underside identity engraving -----------------------------------
    # Mirrored text cut into the bottom face, centred between the two skid
    # sockets and inboard of the strap slots;
    # readable when the robot is flipped over.
    label_lines: tuple = ("DELECTOSOFT", "© 2026  PROTO-02")
    # It prints against the textured PEI sheet, which stipples the plate
    # face and the letter floors with the same grain, so legibility comes
    # from stroke width and depth: Arial Black's strokes are ~1.7 mm wide at
    # this size, and 0.9 mm deep gives a real shadow line.
    label_font: str = "Arial Black"
    label_font_size: float = 8.0
    label_line_spacing: float = 11.0
    label_depth: float = 0.9  # of 3.0 mm plate -> 2.1 mm left under the text
    # Centred: the widest line spans X +-39.5,
    # which clears both skid-hole rims (X -63..-53 and 50..60) and sits
    # well inside the strap slots at |Y| >= 20.1.
    label_x: float = 0.0
    label_y: float = 0.0

    # ---- skid mounting holes + skid part ---------------------------------
    skid_front_x: float = 55.0
    skid_rear_x: float = -58.0  # at -60 the Ø10 hole would be tangent to
    # the plate edge, a degenerate boolean OCCT meshes as a non-manifold STL
    skid_hole_d: float = 10.0
    skid_post_d: float = 10.0
    skid_hole_clearance: float = 0.2  # radial, straight shank only
    skid_foot_d: float = 14.0
    skid_barb_interference: float = 0.15  # radial -- the snap value validated
    # on demo_04; much more and the skid can't be pushed in by hand
    skid_barb_h: float = 2.0
    skid_shoulder_d: float = 16.0
    skid_shoulder_h: float = 0.5  # flat land; a 45 deg cone leads up to it
    skid_slit_w: float = 2.0
    skid_slit_depth_below_barb: float = 12.0  # long slender prongs (demo_04
    # scaling); short prongs are too rigid to snap

    # ---- misc -------------------------------------------------------------
    zip_tie_hole_d: float = 4.0


N20 = N20Dims()


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Box(
        x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN)
    ).translate((x0, y0, z0))


def ivol(a: Part, b: Part) -> float:
    """Exact CAD boolean intersection volume of two BUILT parts (0.0 if
    disjoint) -- the same authoritative overlap signal assembly.py's own
    `ivol` uses for its electronics-vs-chassis checks. overlap_check() uses
    it to test real geometry (tray snap hooks, guide-nub arms,
    boolean-subtraction remnants, true Z extent) instead of an
    approximate plan-view rectangle, which either badly over-approximates
    a sparse multi-armed shape like the guide nubs (a single bounding
    rect spans the gaps between arms) or is Z-blind (flags features that
    only overlap in plan view but sit at different heights)."""
    r = a & b
    return 0.0 if r is None else abs(r.volume)


def plate_plan(d: ChassisDims):
    plan = Rectangle(d.plate_length, d.plate_width)
    return fillet(plan.vertices(), d.corner_radius)


def plate(d: ChassisDims) -> Part:
    return Part() + extrude(plate_plan(d), amount=d.plate_thickness)


def plate_footprint_prism(d: ChassisDims) -> Part:
    """The plate's own rounded-rect outline, extruded tall in both Z
    directions -- used to clip every added feature so nothing (a tray hook,
    a guide-nub arm, ...) can ever stick out past the plate's edge, however
    tight an individual placement margin turns out to be."""
    return Pos(0, 0, -20) * extrude(plate_plan(d), amount=60)


# ---------------------------------------------------------------------------
# motor cradle
# ---------------------------------------------------------------------------


def channel_barb(wall_face_x, tip_dir, y_center, z_center, overhang,
                 length) -> Part:
    """A small diamond-section ridge (45 deg both faces) poking `overhang`
    mm out from a vertical wall face, running `length` mm along Y. Prints
    without support: both the top and bottom faces slope at 45 deg -- the
    upper slope is the insertion ramp, the lower one the retention face.
    The tray latches carry these."""
    oh = overhang
    height = 2 * oh  # symmetric diamond -> exactly 45 deg both sides
    w = Wedge(length, oh, height, 0, height / 2, length, height / 2)
    w = w.rotate(Axis.Z, 90 if tip_dir < 0 else -90)
    x = wall_face_x + tip_dir * oh / 2
    return Pos(x, y_center, z_center) * w


def lid_dims(d: ChassisDims) -> LidDims:
    """lid_coupons.py's cradle and lid, with the car's numbers."""
    return LidDims(
        plate_t=d.plate_thickness, channel_clearance=d.channel_clearance,
        wall_t=d.wall_t, tail_exposed=d.tail_exposed, endwall_t=d.endwall_t,
        endwall_slot_w=d.endwall_slot_w, rail_clearance=d.lid_rail_clearance,
        pad_preload=d.lid_pad_preload, label="",
    )


def _to_side(part: Part, d: ChassisDims, side: int) -> Part:
    """Coupon frame (channel along +Y, plate edge at y=edge_y) -> the car,
    at the +Y (side=+1) or -Y (side=-1) plate edge."""
    y = d.plate_width / 2 - lid_dims(d).edge_y
    if side < 0:
        part = part.rotate(Axis.Z, 180)
    return Pos(d.cradle_x, side * y, 0) * part


def motor_cradle(d: ChassisDims, side: int) -> Part:
    """One cradle (side=+1 -> +Y edge, side=-1 -> -Y edge): a rigid
    U-channel with a dovetail rail along the outside of each wall and an
    end wall at the plate edge."""
    return _to_side(make_cradle(lid_dims(d)), d, side)


def motor_lid(d: ChassisDims, side: int) -> Part:
    """The slide-on lid, seated on its cradle."""
    return _to_side(make_lid(lid_dims(d)), d, side)


def motor_placement(side: int, d: ChassisDims):
    """Location of the reference N20 motor (its own frame) for `side`."""
    plate_top = d.plate_thickness
    axis_z = plate_top + N20.gearbox_height / 2
    face_y = side * (d.plate_width / 2 - d.endwall_t)
    motor = make_motor(N20)
    motor = motor.rotate(Axis.X, 90)
    if side < 0:
        motor = motor.rotate(Axis.Z, 180)
    motor = Pos(d.cradle_x, face_y, axis_z) * motor
    return motor


# ---------------------------------------------------------------------------
# Raspberry Pi mount
# ---------------------------------------------------------------------------


def pi_mount(d: ChassisDims) -> Part:
    plate_top = d.plate_thickness
    mount = Part()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = d.pi_x + sx * d.pi_hole_x / 2
            y = sy * d.pi_hole_y / 2
            boss = Pos(x, y, plate_top) * Cylinder(
                radius=d.pi_boss_d / 2, height=d.pi_boss_h, align=ALIGN_BOTTOM
            )
            boss -= Pos(x, y, plate_top + d.pi_boss_h) * Cylinder(
                radius=d.pi_pilot_d / 2, height=d.pi_boss_h + 0.5, align=ALIGN_TOP
            )
            mount += boss
    return mount


# ---------------------------------------------------------------------------
# generic tilt-and-slide PCB tray (DRV8833, MP1584EN)
#
# Assembly: hold the board at ~15 deg, tuck its LEADING edge under the two
# fixed 45 deg tongues, then rotate it down flat. The trailing edge cams
# the single latch outward on the way past and the barb closes over the
# board top. Removal is the reverse -- press the latch back with a
# fingernail and lift that edge.
#
# Only the latch flexes. A snap arm this short has almost no travel in
# it, so the design spends its one flexing feature where it must and makes
# the other three rigid (module docstring, PCB TRAYS).
# ---------------------------------------------------------------------------


def latch_geometry(d: ChassisDims, standoff=None) -> dict:
    """Working numbers for one tray latch, so the arm is sized by
    arithmetic rather than by eye. Standard cantilever snap-fit relations
    for a constant rectangular section:

        permissible deflection  y = eps * L^2 / (1.5 * t)
        deflection force        F = b * t^3 * E * y / (4 * L^3)

    with L the free length from the plate to the barb, t the thickness in
    the bending direction and b the width. PLA is taken at E = 3000 MPa
    (printed, not datasheet bulk) and a 1% permissible strain, which is
    conservative for a part assembled a handful of times."""
    standoff = d.tray_standoff if standoff is None else standoff
    board_top = d.plate_thickness + standoff + d.tray_board_t
    barb_z = board_top + d.tray_clearance + d.tray_latch_barb  # widest point
    return dict(
        board_top=board_top, barb_z=barb_z,
        **cantilever(barb_z - d.plate_thickness, d.tray_latch_t,
                     d.tray_latch_w, d.tray_latch_barb),
    )


def cantilever(L, t, b, y, root_r=0.0) -> dict:
    """The snap-fit relations in latch_geometry's docstring, for an arm of
    free length L, thickness t and width b deflected by y. With root_r the
    arm has a concave radius that size on both sides where it meets the
    plate; the beam is then integrated numerically, and `strain` is the
    peak along the arm (just above the radius, not at the plate)."""
    E_PLA = 3000.0  # MPa, printed
    EPS_PERM = 0.01  # 1% strain
    x = np.linspace(0.0, L, 4001)
    fillet = np.where(
        x < root_r, root_r - np.sqrt(np.clip(root_r ** 2 - (root_r - x) ** 2, 0, None)), 0.0
    )
    tx = t + 2 * fillet
    I = b * tx ** 3 / 12
    compliance = np.trapezoid((L - x) ** 2 / (E_PLA * I), x)  # tip mm per N
    force = y / compliance
    strain = (force * (L - x) * (tx / 2) / (E_PLA * I)).max()
    return dict(
        free_length=L, deflection=y, permissible=y * EPS_PERM / strain,
        strain=strain, force=force,
    )


def drv_latch_geometry(d: ChassisDims) -> dict:
    """The DRV8833 latch is PRELOADED: its barb's lower 45 deg face passes
    drv_latch_preload below the seated board's top corner, so the arm
    stays bent by that much and pushes the board down and against the
    tongue side. The board can't wiggle away from a spring that is already
    leaning on it -- the gap-based latch above can only stop it escaping.

    `gap` is the latch face to the seated board edge. Insertion deflects
    the arm by barb - gap (the tip has to clear the board edge); at rest it
    keeps `preload`, and the barb tip reaches `reach` over the board."""
    board_top = d.plate_thickness + d.drv_tray_standoff + d.tray_board_t
    gap = d.drv_lead_slack + d.drv_latch_fit
    barb, pre = d.drv_latch_barb, d.drv_latch_preload
    barb_z = board_top + barb - gap - pre
    L = barb_z - d.plate_thickness
    t, b, r = d.drv_latch_t, d.drv_latch_w, d.drv_latch_root_r
    rest = cantilever(L, t, b, pre, r)
    return dict(
        board_top=board_top, barb_z=barb_z, gap=gap, reach=barb - gap - pre,
        rest_strain=rest["strain"], rest_force=rest["force"],
        **cantilever(L, t, b, barb - gap, r),
    )


def pcb_tray(cx, cy, board_x, board_y, d: ChassisDims, standoff=None,
             axis="x", lead=1, hook_span=None) -> Part:
    """`axis` is the capture axis -- the one the fixed hooks and the latch
    face each other across; the board's other two edges stay open for
    wiring. `lead` picks which end of that axis carries the FIXED hooks
    (+1 or -1), so the latch always ends up on the opposite, accessible
    side. `standoff` defaults to the generic (MP1584) tray height.

    `hook_span` is how far the fixed tongues sit from the board centre
    along the OTHER axis; it defaults to the board corners. Pass a smaller
    value when something stands on the board there -- the tongues are the
    only feature that reaches over the board top, so they are the only
    ones a tall component can foul.

    Built in a canonical frame -- capture axis along X, fixed hooks at +X
    -- then rotated into place, so there is one piece of geometry to reason
    about instead of four mirrored variants."""
    standoff = d.tray_standoff if standoff is None else standoff
    plate_top = d.plate_thickness
    board_bot = plate_top + standoff
    board_top = board_bot + d.tray_board_t
    w, fit, slack = d.tray_snap_hook_w, d.tray_fit, d.tray_lead_slack
    cap = d.tray_hook_capture

    # canonical bx is the board dimension ALONG the capture axis
    bx, by = (board_x, board_y) if axis == "x" else (board_y, board_x)
    lead_face = bx / 2 + slack  # fixed-hook posts stand off by the tilt slack
    trail_face = -bx / 2 - fit  # latch/locator posts sit snug
    hook_top = board_top + d.tray_clearance + cap + 0.8
    post_top = board_top + 0.6  # plain locators: no overhang, no lead-in

    span = by / 2 if hook_span is None else hook_span
    tray = Part()
    for sx in (+1, -1):
        for sy in (+1, -1):
            px = lead_face if sx > 0 else trail_face
            top = hook_top if sx > 0 else post_top
            tray += Pos(px, sy * by / 2, plate_top) * Box(
                w, w, top - plate_top, align=ALIGN_BOTTOM
            )
    # A tongue moved inboard of the corner (hook_span) needs its own column
    # to stand on; without it the tongue floats at board height with
    # nothing below it to print onto.
    # When hook_span is the default the column coincides with the corner
    # post and the union changes nothing.
    for sy in (+1, -1):
        tray += Pos(lead_face, sy * span, plate_top) * Box(
            w, w, hook_top - plate_top, align=ALIGN_BOTTOM
        )

    # Clear the board's own volume out of everything above the ledge, so
    # each corner block becomes an L-bracket hugging two board edges. The
    # tongues are added AFTER this cut -- overhanging the board is their job.
    tray -= rbox(trail_face, lead_face, -by / 2 - fit, by / 2 + fit,
                 board_bot, board_top + 50)

    # fixed hooks: a tongue over the board top, its underside chamfered to
    # 45 deg so it prints unsupported AND guides the board in as it rotates
    # down. The chamfer eats the whole overhang, so the tongue reaches its
    # full `cap` only at the top -- the retention face is that 45 deg slope.
    for sy in (+1, -1):
        z0 = board_top + d.tray_clearance
        tongue = rbox(
            lead_face - cap, lead_face + w / 2,
            sy * span - w / 2, sy * span + w / 2,
            z0, z0 + cap + 0.8,
        )
        bottom = tongue.edges().group_by(Axis.Z)[0]
        tray += chamfer(bottom.sort_by(Axis.X)[0], cap)

    # the one flexing feature: a plain constant-section arm rising from the
    # plate at the trailing edge centre, with a 45/45 diamond barb on its
    # inner face. Free-standing on all sides -- the corner posts are out at
    # +-by/2, so nothing stiffens it.
    g = latch_geometry(d, standoff)
    tray += rbox(
        trail_face - d.tray_latch_t, trail_face,
        -d.tray_latch_w / 2, d.tray_latch_w / 2,
        plate_top, g["barb_z"] + d.tray_latch_barb + 0.4,
    )
    tray += channel_barb(trail_face, +1, 0, g["barb_z"],
                         overhang=d.tray_latch_barb, length=d.tray_latch_w)

    if axis == "y":
        tray = tray.rotate(Axis.Z, 90 if lead > 0 else -90)
    elif lead < 0:
        tray = tray.rotate(Axis.Z, 180)
    return Pos(cx, cy, 0) * tray


def drv_tray(d: ChassisDims, placed=True) -> Part:
    """The DRV8833 tray (module docstring, PCB TRAYS). Same tilt-and-slide as pcb_tray --
    two fixed tongues on one long side, one latch on the other -- but
    nothing reaches over the board anywhere except those three, because
    the soldered header strips cover the board top edge to edge along both
    short ends. The corners are flush end stops with a small shelf under
    the board, and the latch is preloaded (drv_latch_geometry).

    placed=False returns it in its canonical frame, board centred on the
    origin: capture axis along X with the tongues at +X, 18.5 mm axis along
    Y. drv_coupons.py prints it that way."""
    standoff = d.drv_tray_standoff
    plate_top = d.plate_thickness
    board_bot = plate_top + standoff
    board_top = board_bot + d.tray_board_t
    bx, by = d.drv_board_y, d.drv_board_x
    w, cap = d.tray_snap_hook_w, d.tray_hook_capture
    span = d.drv_hook_span

    lead_face = bx / 2 + d.drv_lead_slack
    trail_face = -bx / 2 - d.drv_latch_fit
    end_face = by / 2 + d.drv_end_fit
    pocket = rbox(trail_face, lead_face, -end_face, end_face,
                  plate_top, board_top + 50)

    # corner end stops: an L of wall round each corner, flush with the
    # board top, and a drv_corner_ledge square shelf under the corner itself
    wall, arm, e = d.drv_corner_wall, d.drv_corner_arm, d.drv_corner_ledge
    corners = Part()
    for sx, face in ((+1, lead_face), (-1, trail_face)):
        for sy in (+1, -1):
            x0, x1 = sorted((face - sx * arm, face + sx * wall))
            y0, y1 = sorted((sy * (end_face - arm), sy * (end_face + wall)))
            corners += rbox(x0, x1, y0, y1, plate_top, board_top)
    corners -= pocket
    for sx, face in ((+1, lead_face), (-1, trail_face)):
        for sy in (+1, -1):
            x0, x1 = sorted((face, face - sx * e))
            y0, y1 = sorted((sy * end_face, sy * (end_face - e)))
            corners += rbox(x0, x1, y0, y1, plate_top, board_bot)

    # fixed tongues, as pcb_tray's: the column is also the board's shelf on
    # this side, and the 45 deg underside starts right at the board edge
    z0 = board_top + d.drv_tongue_clearance
    tray = corners
    for sy in (+1, -1):
        column = Pos(lead_face, sy * span, plate_top) * Box(
            w, w, z0 + cap + 0.8 - plate_top, align=ALIGN_BOTTOM
        )
        tray += column - Pos(0, 0, board_bot - plate_top) * pocket
        tongue = rbox(lead_face - cap, lead_face + w / 2,
                      sy * span - w / 2, sy * span + w / 2, z0, z0 + cap + 0.8)
        bottom = tongue.edges().group_by(Axis.Z)[0]
        tray += chamfer(bottom.sort_by(Axis.X)[0], cap)

    g = drv_latch_geometry(d)
    lw, r = d.drv_latch_w, d.drv_latch_root_r
    tray += rbox(
        trail_face - d.drv_latch_t, trail_face, -lw / 2, lw / 2,
        plate_top, g["barb_z"] + d.drv_latch_barb + 0.4,
    )
    # concave root radius on both faces: a block beside the arm's foot with
    # a Y-axis cylinder taken out of it
    for x_face, out in ((trail_face, +1), (trail_face - d.drv_latch_t, -1)):
        x0, x1 = sorted((x_face, x_face + out * r))
        block = rbox(x0, x1, -lw / 2, lw / 2, plate_top, plate_top + r)
        tray += block - Pos(x_face + out * r, 0, plate_top + r) * Cylinder(
            radius=r, height=lw + 1, rotation=(90, 0, 0)
        )
    tray += channel_barb(trail_face, +1, 0, g["barb_z"],
                         overhang=d.drv_latch_barb, length=d.drv_latch_w)

    if not placed:
        return tray
    # tongues on the battery side (-Y), latch outboard where a finger reaches
    return Pos(d.drv_x, d.drv_y, 0) * tray.rotate(Axis.Z, -90)


# ---------------------------------------------------------------------------
# battery bay: guide nubs + strap slots (slots returned separately, they
# cut the plate rather than add to it)
# ---------------------------------------------------------------------------


def battery_nubs(d: ChassisDims) -> Part:
    """Four L-shaped corner guides. Each L HUGS its corner of the pack: both
    arms run inward along the pack's edges from the corner, and each arm's
    thickness sits outboard of the clearance line, so the inner faces form a
    clean nub_clearance-wide box around the footprint."""
    plate_top = d.plate_thickness
    half_x = d.battery_len / 2 + d.nub_clearance
    half_y = d.battery_wid / 2 + d.nub_clearance
    nubs = Part()
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx = d.battery_x + sx * half_x  # inner corner of the guide, in X
            by = sy * half_y                # ... and in Y
            # Both arms run past the corner by nub_t so they share a corner
            # block and fuse into one L, rather than meeting at a single
            # point and staying two disjoint bars.
            xi, xo = bx - sx * d.nub_arm, bx + sx * d.nub_t
            yi, yo = by - sy * d.nub_arm, by + sy * d.nub_t
            # arm along the pack's LONG edge: inward in X, thickness outward in Y
            nubs += rbox(min(xi, xo), max(xi, xo), min(by, yo), max(by, yo),
                         plate_top, plate_top + d.nub_h)
            # arm along the pack's SHORT edge: inward in Y, thickness outward in X
            nubs += rbox(min(bx, xo), max(bx, xo), min(yi, yo), max(yi, yo),
                         plate_top, plate_top + d.nub_h)
    return nubs


def strap_slots(d: ChassisDims) -> Part:
    plate_top = d.plate_thickness
    slot_y = d.battery_wid / 2 + d.strap_y_offset
    cutter = Part()
    for x in d.strap_stations:
        for sy in (-1, 1):
            cutter += Pos(x, sy * slot_y, -0.5) * Box(
                d.strap_slot_len,
                d.strap_slot_wid,
                d.plate_thickness + 1,
                align=ALIGN_BOTTOM,
            )
    return cutter


# ---------------------------------------------------------------------------
# skid: separate part, printed dome-down, snaps up through a plate hole
# ---------------------------------------------------------------------------


def skid_below_plate(d: ChassisDims) -> float:
    return d.wheel_diameter / 2 - N20.gearbox_height / 2 - d.plate_thickness


def build_skid(d: ChassisDims) -> Part:
    below = skid_below_plate(d)
    shank_d = d.skid_hole_d - 2 * d.skid_hole_clearance
    # Ø6 tip flat: bed contact for printing tip-down (a Ø3 flat + brim let
    # the post snap off at the barb, twice) and a broader floor-contact
    # patch in use.
    tip_flat_d, tip_flat_h = 6.0, 0.4
    foot_h = 3.0
    neck_h = 2.0

    z0 = 0.0
    z1 = z0 + tip_flat_h
    z2 = z1 + foot_h
    z3 = z2 + neck_h  # post begins, diameter = shank_d
    z_shoulder_top = below  # plate bottom lands here
    z_shoulder_bot = z_shoulder_top - d.skid_shoulder_h
    z_plate_top = z_shoulder_top + d.plate_thickness
    barb_r = d.skid_hole_d / 2 + d.skid_barb_interference
    z_barb0 = z_plate_top
    barb_ramp = d.skid_barb_h * 0.4  # retention ramp, <45 deg from vertical
    barb_land = d.skid_barb_h * 0.2
    barb_lead_in = barb_r - shank_d / 2  # taper back to shank dia -> self-supporting
    z_barb1 = z_barb0 + barb_ramp + barb_land + barb_lead_in
    z_top = z_barb1

    skid = Part()
    skid += Cylinder(radius=tip_flat_d / 2, height=tip_flat_h, align=ALIGN_BOTTOM)
    skid += Pos(0, 0, z1) * Cone(
        tip_flat_d / 2, d.skid_foot_d / 2, foot_h, align=ALIGN_BOTTOM
    )
    skid += Pos(0, 0, z2) * Cone(
        d.skid_foot_d / 2, shank_d / 2, neck_h, align=ALIGN_BOTTOM
    )
    # shoulder (bears on the plate underside): a 45-degree cone up from the
    # shank to the shoulder diameter, then a short flat land. A plain
    # cylinder would leave a 3.2 mm mid-air overhang, which prints as
    # spaghetti.
    cone_h = (d.skid_shoulder_d - shank_d) / 2
    skid += Pos(0, 0, z_shoulder_top - d.skid_shoulder_h - cone_h) * Cone(
        shank_d / 2, d.skid_shoulder_d / 2, cone_h, align=ALIGN_BOTTOM
    )
    skid += Pos(0, 0, z_shoulder_top - d.skid_shoulder_h) * Cylinder(
        radius=d.skid_shoulder_d / 2, height=d.skid_shoulder_h, align=ALIGN_BOTTOM
    )
    # straight shank through the plate hole
    skid += Pos(0, 0, z3) * Cylinder(
        radius=shank_d / 2, height=z_shoulder_bot - z3, align=ALIGN_BOTTOM
    )
    skid += Pos(0, 0, z_shoulder_top) * Cylinder(
        radius=shank_d / 2, height=z_plate_top - z_shoulder_top, align=ALIGN_BOTTOM
    )
    # barb: a shallow retention ramp up to barb_r (<45 deg from vertical, so
    # it needs no support), a short land, then a taper back down to the
    # shank diameter (a shrinking radius as Z increases is always
    # self-supporting) -- same shouldered-cone idea as gearbox.py's post
    # lip. It flexes via a slit cut through it afterwards.
    skid += Pos(0, 0, z_barb0) * Cone(
        shank_d / 2, barb_r, barb_ramp, align=ALIGN_BOTTOM
    )
    skid += Pos(0, 0, z_barb0 + barb_ramp) * Cylinder(
        radius=barb_r, height=barb_land, align=ALIGN_BOTTOM
    )
    skid += Pos(0, 0, z_barb0 + barb_ramp + barb_land) * Cone(
        barb_r, shank_d / 2, barb_lead_in, align=ALIGN_BOTTOM
    )
    # flex slits: a CROSS (two perpendicular slits) making four slender
    # quarter-prongs -- compliant, and self-centering on insertion.
    slit_z0 = z_barb0 - d.skid_slit_depth_below_barb
    slit_h = z_top - slit_z0 + 0.5
    slit = Box(d.skid_hole_d + 2, d.skid_slit_w, slit_h, align=ALIGN_BOTTOM)
    skid -= slit.translate((0, 0, slit_z0))
    skid -= slit.rotate(Axis.Z, 90).translate((0, 0, slit_z0))

    return skid, below


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------


@dataclass
class Chassis:
    dims: ChassisDims
    plate: Part
    skid: Part
    skid_below: float
    lids: list  # [+Y, -Y], seated; separate printed parts
    footprints: dict = field(default_factory=dict)


def label_engraving(d: ChassisDims) -> Part:
    """Identity text cut into the bottom face, mirrored in X so it reads
    correctly when viewed from below (robot flipped over)."""
    n = len(d.label_lines)
    text = None
    for i, line in enumerate(d.label_lines):
        y = ((n - 1) / 2 - i) * d.label_line_spacing
        t = Pos(0, y) * Text(line, font_size=d.label_font_size,
                             font=d.label_font)
        text = t if text is None else text + t
    text = mirror(text, Plane.YZ)  # readable from underneath
    prism = extrude(text, amount=d.label_depth)  # z 0..depth, cut from the bottom
    return Pos(d.label_x, d.label_y, 0) * prism


def build(d: ChassisDims) -> Chassis:
    plate_top = d.plate_thickness
    cradle_p = motor_cradle(d, +1)
    cradle_m = motor_cradle(d, -1)
    # Capture axis per tray = across the edges that DON'T carry wiring.
    # DRV8833: its short X-ends carry the headers, so it captures along Y,
    # hooks on the battery side and the latch outboard where a finger can
    # reach it (drv_tray).
    # MP1584: its 22 mm long edges stay open, so it captures along X with
    # the latch forward, into clear plate.
    drv = drv_tray(d)
    buck_tray = pcb_tray(d.buck_x, d.buck_y, d.buck_board_x, d.buck_board_y, d,
                         axis="x", lead=-1)
    nubs = battery_nubs(d)
    # Both trays reach into a battery guide-nub arm.
    # Trim whatever nub material actually collides with each tray's BUILT
    # envelope, rather than hand-deriving which arm and how much. The trays
    # win: they locate a board to 0.25 mm, the nubs only fence a soft pack.
    nubs -= drv
    nubs -= buck_tray

    body = plate(d)
    body += cradle_p
    body += cradle_m
    body += pi_mount(d)
    body += drv
    body += buck_tray
    body += nubs

    # safety net: nothing added above may stick out past the plate's own
    # edge, however tight an individual placement margin is
    body &= plate_footprint_prism(d)

    body -= strap_slots(d)
    for x in (d.skid_front_x, d.skid_rear_x):
        body -= Pos(x, 0, -0.5) * Cylinder(
            radius=d.skid_hole_d / 2, height=d.plate_thickness + 1, align=ALIGN_BOTTOM
        )
    # zip-tie hole past the MP1584 board's +X short edge, away from the
    # battery bay, keeping >=4 mm of plate on every side (between the long
    # edge and the plate edge there is only 0.2 mm, which prints as an open
    # notch). The DRV8833 has none: its open edges face the cradle on one
    # side and the rear plate edge on the other.
    zip_x = d.buck_x + d.buck_board_x / 2 + 4.5
    zip_y = -(d.plate_width / 2) + 4.5 + d.zip_tie_hole_d / 2  # 4.5 mm edge wall
    body -= Pos(zip_x, zip_y, -0.5) * Cylinder(
        radius=d.zip_tie_hole_d / 2, height=d.plate_thickness + 1, align=ALIGN_BOTTOM
    )

    body -= label_engraving(d)

    skid, below = build_skid(d)
    lids = [motor_lid(d, +1), motor_lid(d, -1)]

    # Footprints are real BUILT Part envelopes, not nominal rectangles (a
    # rectangle either badly over-approximates the sparse, multi-armed
    # guide-nub shape, or misses a boolean-subtraction remnant's true
    # material extent, or is Z-blind).
    # cradle/tray envelopes are the actual built Parts (post projections
    # and true Z extent included for free). The battery envelope is the
    # nominal pack volume (its own footprint x battery_h) unioned with the
    # post-trim guide nubs. pi_board is a thin proxy slab at the board's
    # actual rest height (on top of the mounting bosses) over the nominal
    # board rectangle -- the Pi board itself isn't built in this file, only
    # its mounting bosses, so there is no better BUILT envelope to use.
    battery_env = nubs + rbox(
        d.battery_x - d.battery_len / 2, d.battery_x + d.battery_len / 2,
        -d.battery_wid / 2, d.battery_wid / 2,
        plate_top, plate_top + d.battery_h,
    )
    pi_env = rbox(
        d.pi_x - d.pi_board_x / 2, d.pi_x + d.pi_board_x / 2,
        -d.pi_board_y / 2, d.pi_board_y / 2,
        plate_top + d.pi_boss_h, plate_top + d.pi_boss_h + d.tray_board_t,
    )

    # The motor BODIES, not just their cradles: what a cradle holds has to
    # clear its neighbours too (the battery above all -- see DESIGN RULES).
    footprints = {
        "cradle+Y": cradle_p,
        "cradle-Y": cradle_m,
        "motor+Y": motor_placement(+1, d),
        "motor-Y": motor_placement(-1, d),
        "lid+Y": lids[0],
        "lid-Y": lids[1],
        "pi_board": pi_env,
        "drv8833": drv,
        "mp1584": buck_tray,
        "battery": battery_env,
        # a cut, not a feature: nothing may stand over the strap's path
        "strap_slots": strap_slots(d),
    }

    return Chassis(d, body, skid, below, lids, footprints)


def connectivity_check(body: Part) -> bool:
    """The plate plus everything standing on it must be ONE solid. A
    feature that ends up disconnected -- a hook tongue whose post moved out
    from under it, say -- shows up here as a second solid, which is exactly
    what it becomes on the bed: a shape the printer starts extruding in
    mid-air. print_lint catches the same thing from the mesh side, but this
    runs on the CAD, before anything is exported."""
    n = len(body.solids())
    ok = n == 1
    print(f"\n[{'PASS' if ok else 'FAIL'}] plate is one connected solid "
          f"({n} solid{'' if n == 1 else 's'}{'' if ok else ' -- something floats'})")
    return ok


def overlap_check(footprints: dict) -> bool:
    """`footprints[name]` is a BUILT Part (or a close proxy for pi_board --
    see build()). Two features conflict iff their exact CAD boolean
    intersection volume (ivol(), the same authoritative signal
    assembly.py's own checks use) is at or above OVERLAP_TOL -- a tiny
    positive volume from coincident/tangent faces is numerical noise, not
    a real conflict.

    A pair that is MEANT to interfere gets an expected range in EXPECTED
    rather than an exemption, and a range fails in both directions -- too
    little means the clamp has no grip, too much means something is fouling
    that should not be."""
    # each lid's pad presses lid_pad_preload into its motor's top by design
    # (~34 mm^3 at 0.30). The lower bound catches a pad that doesn't reach,
    # the upper bound interference that is not the pad at all.
    EXPECTED = {
        ("motor+Y", "lid+Y"): (10.0, 60.0),
        ("motor-Y", "lid-Y"): (10.0, 60.0),
    }
    OVERLAP_TOL = 1.0  # mm^3

    names = list(footprints)
    all_ok = True
    print("\n-- footprint overlap check (BUILT-geometry boolean volume) --")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            vol = ivol(footprints[a], footprints[b])
            band = EXPECTED.get((a, b)) or EXPECTED.get((b, a))
            if band:
                ok = band[0] <= vol <= band[1]
                detail = (f"designed clamp {vol:.3f} mm^3, "
                          f"expected {band[0]:g}-{band[1]:g}")
            else:
                ok = vol < OVERLAP_TOL
                detail = f"intersection {vol:.3f} mm^3, < {OVERLAP_TOL:g}"
            all_ok &= ok
            print(f"[{'PASS' if ok else 'FAIL'}] {a:10s} vs {b:10s}  ({detail})")
    return all_ok


if __name__ == "__main__":
    d = ChassisDims()
    if len(sys.argv) > 1:
        d.plate_length = float(sys.argv[1])
    if len(sys.argv) > 2:
        d.plate_width = float(sys.argv[2])
    if len(sys.argv) > 3:
        d.wheel_diameter = float(sys.argv[3])

    here = Path(__file__).parent
    c = build(d)

    export_stl(c.plate, here / "chassis.stl")
    export_step(c.plate, here / "chassis.step")
    export_stl(c.skid, here / "skid.stl")
    export_step(c.skid, here / "skid.step")
    # the two lids are identical; print two of this one, ceiling down
    lid = lid_for_print(make_lid(lid_dims(d)), lid_dims(d))
    export_stl(lid, here / "motor_lid.stl")
    export_step(lid, here / "motor_lid.step")

    assembly = Part() + c.plate
    assembly += motor_placement(+1, d)
    assembly += motor_placement(-1, d)
    assembly += c.lids[0] + c.lids[1]
    installed_skid = Pos(d.skid_front_x, 0, -c.skid_below) * c.skid
    assembly += installed_skid
    export_stl(assembly, here / "chassis_assembly.stl")

    ok = overlap_check(c.footprints)
    ok &= connectivity_check(c.plate)

    print(f"\nPlate: {d.plate_length:g} x {d.plate_width:g} x {d.plate_thickness:g} mm, "
          f"corner r{d.corner_radius:g}")
    print(f"Wheel diameter {d.wheel_diameter:g} mm -> skid reaches {c.skid_below:.2f} mm "
          f"below the plate bottom")
    print("\nLayout (center X, center Y):")
    print(f"  motor cradles      : X={d.cradle_x:g}  Y=+-{d.plate_width/2:g} (edge)")
    print(f"  Pi Zero 2W mount   : X={d.pi_x:g}  Y=0")
    print(f"  DRV8833 tray       : X={d.drv_x:g}  Y={d.drv_y:g}")
    print(f"  MP1584EN tray      : X={d.buck_x:g}  Y={d.buck_y:g}")
    print(f"  battery bay        : X={d.battery_x:g}  Y=0")
    print(f"  front skid hole    : X={d.skid_front_x:g}  Y=0")
    print(f"  rear skid hole     : X={d.skid_rear_x:g}  Y=0")

    print("\nExported chassis.stl/.step, skid.stl/.step, motor_lid.stl/.step "
          "(print two), chassis_assembly.stl")
    sys.exit(0 if ok else 1)
