"""demo_06: platform plate for the first two-motor robot-car prototype.

One flat part, 130 x 80 x 3 mm (X x Y x Z), corner radius 6 mm, printed flat
side down with no supports. +X is FRONT, -X is REAR. The plate is centered
on the origin in X and Y; the bottom face is Z=0, the top face is Z =
plate_thickness (3 mm by default) and every feature below grows up from
there.

Layout (see ChassisDims for the authoritative numbers; this is the plan):
- Two M2 N20 gearmotor snap cradles, rear area, one per side (+-Y), output
  shafts pointing outward past the plate edge so the wheels clear the plate.
  U-channel walls hold the motor can/gearbox; small chamfered lips snap over
  the can's round section (only the can is round -- the gearbox bracket is
  square and doesn't need a lip). A low cross rib marks the can/gearbox
  step, and an end wall with a slot for the Ø4 boss/shaft gives axial
  retention where the gearbox face lands. The two M1.6 bracket holes on the
  motor are NOT modeled -- mounting is snap-only; they remain a fallback if
  the snap cradle ever needs a screwed-down backup.
- C1 Raspberry Pi Zero 2 W mount, front area: four self-tapping-screw
  bosses on the documented 58 x 23 mm hole rectangle, board long axis (65 mm)
  across the chassis (Y). The connector edge (mini-HDMI + both micro-USB)
  faces front (+X).
- D2 DRV8833 driver tray and P1 MP1584EN buck tray: shallow four-post clip
  trays (board rests on a 2 mm ledge, snap lips at the post tops), each
  with its long header/IO edges left open for wiring.
- B2 LiPo strap-down bay: guide nubs mark the (calipered) 93 x 35.2 mm
  footprint with clearance, plus two pairs of 12 x 3 mm hook-and-loop strap
  slots. The pack's lead-exit (+X, XT60) end faces the buck/Pi side.
- Front skid boss (+X) and an alternate rear skid boss (-X, centerline,
  behind the cradles) -- both a plain Ø10 through hole. The skid itself is
  a separate printed part (skid.py-style single build here) that push-snaps
  in from underneath and is exported standalone.
- One Ø4 zip-tie hole beyond the MP1584 tray's open edge for strain relief
  (see deviation 7 -- there isn't a clean spot for a second one).

DEVIATIONS FROM THE ORIGINAL BRIEF (see the final report for the why):
1. N20 body length: parts/n20_motor.py's N20Dims gives gearbox_length=9 mm
   and can_length=15 mm (24 mm body), not the "9 + 26 = 36 mm" the brief
   estimated. The cradle length is derived from the actual dataclass, not
   the hand estimate.
2. The motor's gearbox front face sits 2 mm inboard of the literal plate
   edge (flush with the *inside* of the retention end-wall), not flush with
   the plate edge itself -- a wall standing exactly on the edge would have
   no plate material under half of it. The 0.7 mm boss + 10 mm shaft still
   clear the edge by a wide margin.
3. Raspberry Pi mount moved from X=42 to X=48 (still "front area") to open
   enough rear-of-Pi room for the calipered 93 mm-long battery -- see the
   footprint-corridor arithmetic in the report.
4. DRV8833 and MP1584 trays are off the Y=0 centerline (the battery,
   35.2 mm wide, and the motor cradles, which start at |Y|=20, leave only
   a sliver of centerline room). Both trays are still on centerline in X
   intent ("rear center" / "mid front"); they're just pushed sideways
   enough to clear the battery and, for the DRV8833, the cradle too.
5. Battery strap-slot X stations are ~13 mm apart, not "~45 mm" -- the
   available corridor between the cradle, the relocated driver trays and
   the battery's own footprint is only ~29 mm wide. See the report.
6. wheel_diameter default is 59 mm -- the wood-copy wheel's rolling
   diameter (groove root 39 + 2 x 10 mm cord; earlier revisions used the
   45 mm placeholder, then 62) -- and the skid post is Ø10, not Ø8 -- widened
   for stiffness now that the post is ~22 mm of exposed length below the
   plate. Both plate skid holes are Ø10 to match.
7. The rear skid hole moved from X=-60 to X=-58 (still "on centerline,
   behind the cradles"): at exactly X=-60 the Ø10 hole is tangent to the
   plate's straight edge, a boolean-degenerate case OCCT meshes as a
   non-manifold STL. Only the MP1584 tray got a zip-tie hole -- DRV8833's
   open (16 mm) edges face straight into the cradle on one side and the
   rear plate edge on the other, with no room left for a clean hole; the
   brief allows skipping it ("if it complicates anything").
8. Pi board footprint check note: with the Pi's mounting rectangle spanning
   nearly the full plate width (58 mm of 80 mm), a battery any longer than
   about 94 mm literally cannot avoid it on a 130 mm-long plate regardless
   of X placement -- see the corridor arithmetic in the report for why
   Pi/battery/tray positions all had to move together.
9. Full-car assembly verification (assembly.py) found real conflicts, fixed
   here: (a) d2_drv8833.py's default with_headers=True envelope has
   soldered-header solder tails reaching 3.0 mm below the board, but the
   generic 2.0 mm tray_standoff let them poke ~1 mm into the plate -- the
   DRV8833 tray now gets its own drv_tray_standoff=3.5 mm (tails clear by
   0.5 mm) with drv_tray_post_h raised by the same +1.5 mm so the post
   height above the board is unchanged. p1_mp1584.py has every component on
   the board's top face (inductor, IC, trimpot) and only cuts pad holes
   straight through -- nothing hangs below -- so the MP1584 tray is
   unchanged at 2.0 mm. (b) Tray corner posts project tray_post_w/2
   (1.5 mm) beyond the nominal board rectangle; at the original drv_y=26.5
   this put the DRV8833 tray's posts ~16 mm^3 into one LiPo guide-nub arm's
   built envelope. Fixed by moving the tray +2.5 mm in Y (drv_y=29.0, still
   >=1 mm clear of the plate edge) and boolean-subtracting the tray's own
   built geometry from the nubs so whatever residual overlap remains is
   trimmed away exactly, rather than guessing at a nub-arm length. (c)
   overlap_check() previously compared nominal board/battery rectangles,
   which is exactly how (b) went unnoticed. It now runs real CAD boolean
   intersection volume (like assembly.py's `ivol`) between each feature's
   actual BUILT geometry -- tray Parts (posts included), cradle Parts, and
   a battery envelope Part (the nominal pack volume unioned with the
   post-trim guide nubs) -- instead of approximate 2D rectangles, since a
   plan-view-only rectangle either badly over-approximates a sparse shape
   like the guide nubs (false positives against far-away features) or
   under-approximates a boolean-subtraction remnant's true material extent
   (a false positive right at the DRV8833/nub trim boundary). Hardening
   this way surfaced one more genuine conflict past the DRV8833 one: the
   MP1584 tray's post projection was 0.10 mm into the battery envelope at
   the original buck_y=-27.5, so buck_y also moved, to -27.8 (0.2 mm clear
   of the battery envelope and 0.2 mm clear of the zip-tie hole's plate-
   edge tangency -- see deviation 7 for why exact tangency is a problem).

Run with:  uv run chassis.py [plate_length] [plate_width] [wheel_diameter]
Exports (gitignored): chassis.stl/.step, skid.stl/.step, and
chassis_assembly.stl (chassis + two reference N20 motors + the skid, all in
installed position, for visual verification only -- not meant to print).
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

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

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
ALIGN_TOP = (Align.CENTER, Align.CENTER, Align.MAX)


@dataclass
class ChassisDims:
    # ---- plate ---------------------------------------------------------
    plate_length: float = 130.0  # X
    plate_width: float = 80.0  # Y
    plate_thickness: float = 3.0
    corner_radius: float = 6.0
    wheel_diameter: float = 59.0  # rolling Ø of the wood-copy wheel (root 39 + 2 x cord 10); drives skid only

    # ---- N20 motor snap cradle (one instance, mirrored for +-Y) --------
    cradle_x: float = -35.0
    channel_clearance: float = 0.2  # radial fit around the 10 mm can flats
    wall_t: float = 3.0
    wall_h: float = 10.0  # < can_diameter on purpose -- lips cover the rest
    tail_exposed: float = 6.0  # mm of can left sticking out for the wires
    endwall_t: float = 2.0
    endwall_h: float = 8.0
    endwall_slot_w: float = 4.5  # clears the Ø4 boss, open at the top
    lip_overhang: float = 0.8  # per side, 45 deg both faces (see docstring)
    lip_len: float = 3.0
    rib_h: float = 2.0
    rib_len: float = 2.5

    # ---- C1 Raspberry Pi Zero 2 W mount ---------------------------------
    pi_x: float = 48.0
    pi_hole_y: float = 58.0
    pi_hole_x: float = 23.0
    pi_board_y: float = 65.0  # footprint, for the overlap check
    pi_board_x: float = 30.0
    pi_boss_d: float = 5.5
    pi_boss_h: float = 5.0
    pi_pilot_d: float = 2.2

    # ---- shallow snap-clip PCB trays (D2 DRV8833, P1 MP1584EN) ---------
    # tray_standoff/tray_post_h are the MP1584 tray's numbers -- p1_mp1584.py
    # puts every component (inductor, IC, trimpot) on the top face and cuts
    # its pad holes straight through, nothing hangs below the board, so a
    # 2.0 mm standoff is fine as-is.
    tray_standoff: float = 2.0  # board stands this high off the plate
    tray_post_h: float = 6.0  # total post height incl. standoff
    tray_post_w: float = 3.0
    tray_lip_overhang: float = 0.6
    tray_board_t: float = 1.6

    # DRV8833 only: d2_drv8833.py's with_headers=True envelope (the
    # chassis-design default) has soldered-header solder tails reaching
    # header_pin_down=3.0 mm below the board. The generic 2.0 mm standoff
    # let those tails poke ~1 mm into the plate, so this tray gets its own,
    # taller standoff (tails clear by 0.5 mm) with post_h raised by the same
    # +1.5 mm so the post height *above* the board -- and hence the snap
    # lip's position/clearance relative to the board top -- is unchanged.
    drv_tray_standoff: float = 3.5
    drv_tray_post_h: float = 7.5

    drv_x: float = -54.0
    drv_y: float = 29.0  # +2.5 mm from the original 26.5 -- see deviation 9
    drv_board_x: float = 18.5
    drv_board_y: float = 16.0  # the two 16 mm edges (X ends) stay open

    buck_x: float = 13.0
    buck_y: float = -27.8  # -0.3 mm from the original -27.5 -- see deviation 9
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
    strap_slot_len: float = 12.0
    strap_slot_wid: float = 3.0
    strap_y_offset: float = 4.0  # slot Y = wid/2 + this
    strap_stations: tuple = (-19.0, -6.0)

    # ---- underside identity engraving -----------------------------------
    # Mirrored text cut into the bottom face (prints against the plate, so
    # it comes out crisp) between the rear skid socket and the strap slots;
    # readable when the robot is flipped over.
    label_lines: tuple = ("DELECTOSOFT", "© 2026  PROTO-01")
    label_font_size: float = 4.0
    label_line_spacing: float = 6.0
    label_depth: float = 0.4
    label_x: float = -34.0  # keeps 2 mm clear of the rear skid hole rim
    label_y: float = 0.0

    # ---- skid mounting holes + skid part ---------------------------------
    skid_front_x: float = 55.0
    skid_rear_x: float = -58.0  # moved in 2 mm from the brief's -60 -- at
    # -60 the Ø10 hole is exactly tangent to the plate edge, a boolean
    # degenerate case that OCCT meshes as a non-manifold STL (see report)
    skid_hole_d: float = 10.0
    skid_post_d: float = 10.0
    skid_hole_clearance: float = 0.2  # radial, straight shank only
    skid_foot_d: float = 14.0
    skid_barb_interference: float = 0.15  # radial — the demo_04-VALIDATED snap
    # lip value; the first printed skid used 0.5 and was impossible to insert
    skid_barb_h: float = 2.0
    skid_shoulder_d: float = 16.0
    skid_shoulder_h: float = 0.5  # flat land; a 45 deg cone leads up to it
    skid_slit_w: float = 2.0
    skid_slit_depth_below_barb: float = 12.0  # long slender prongs (demo_04
    # scaling); the first skid's ~3 mm gave short rigid prongs

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
    `ivol` uses for its electronics-vs-chassis checks. Used to harden
    overlap_check() against real geometry (tray posts, guide-nub arms,
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
    directions -- used to clip every added feature so nothing (a tray post,
    a guide-nub arm, ...) can ever stick out past the plate's edge, however
    tight an individual placement margin turns out to be."""
    return Pos(0, 0, -20) * extrude(plate_plan(d), amount=60)


# ---------------------------------------------------------------------------
# motor cradle
# ---------------------------------------------------------------------------


def channel_lip(wall_face_x, tip_dir, y_center, z_center, d: ChassisDims) -> Part:
    """A small diamond-section ridge (45 deg both faces) poking `overhang`
    mm out from a vertical wall face, running `lip_len` mm along Y. Prints
    without support: both the top and bottom faces slope at 45 deg."""
    oh, length = d.lip_overhang, d.lip_len
    height = 2 * oh  # symmetric diamond -> exactly 45 deg both sides
    w = Wedge(length, oh, height, 0, height / 2, length, height / 2)
    w = w.rotate(Axis.Z, 90 if tip_dir < 0 else -90)
    x = wall_face_x + tip_dir * oh / 2
    return Pos(x, y_center, z_center) * w


def motor_cradle(d: ChassisDims, side: int) -> Part:
    """One snap cradle (side=+1 -> +Y edge, side=-1 -> -Y edge)."""
    plate_top = d.plate_thickness
    axis_z = plate_top + N20.gearbox_height / 2  # motor centerline height
    gap = N20.gearbox_width + d.channel_clearance
    wall_inner_x = [d.cradle_x - gap / 2, d.cradle_x + gap / 2]
    wall_outer_x = [wall_inner_x[0] - d.wall_t, wall_inner_x[1] + d.wall_t]
    edge_y = side * (d.plate_width / 2)
    face_y = side * (d.plate_width / 2 - d.endwall_t)  # gearbox front face
    channel_run = d.endwall_t + N20.gearbox_length + N20.can_length - d.tail_exposed
    inboard_y = side * (d.plate_width / 2 - channel_run)

    def yspan():
        return (min(edge_y, inboard_y), max(edge_y, inboard_y))

    y0, y1 = yspan()

    cradle = Part()
    # two side walls
    for x0 in (wall_outer_x[0], wall_inner_x[1]):
        x1 = x0 + d.wall_t if x0 == wall_outer_x[0] else wall_outer_x[1]
        cradle += rbox(x0, x1, y0, y1, plate_top, plate_top + d.wall_h)

    # end wall / face plate at the plate edge, with a slot for the boss
    ew_y0, ew_y1 = (face_y, edge_y) if side > 0 else (edge_y, face_y)
    endwall = rbox(
        wall_outer_x[0], wall_outer_x[1], ew_y0, ew_y1, plate_top, plate_top + d.endwall_h
    )
    slot_z0 = axis_z - N20.boss_diameter / 2 - 1.0
    slot = rbox(
        d.cradle_x - d.endwall_slot_w / 2,
        d.cradle_x + d.endwall_slot_w / 2,
        ew_y0 - 0.1,
        ew_y1 + 0.1,
        slot_z0,
        plate_top + d.endwall_h + 0.1,  # open at the top
    )
    endwall -= slot
    cradle += endwall

    # low cross rib at the can / gearbox step
    rib_y_center = side * (d.plate_width / 2 - d.endwall_t - N20.gearbox_length)
    cradle += rbox(
        wall_inner_x[0],
        wall_inner_x[1],
        rib_y_center - d.rib_len / 2,
        rib_y_center + d.rib_len / 2,
        plate_top,
        plate_top + d.rib_h,
    )

    # two lip pairs over the can, inside the channel
    can_start_y = side * (d.plate_width / 2 - d.endwall_t - N20.gearbox_length)
    can_end_y = side * (
        d.plate_width / 2 - d.endwall_t - N20.gearbox_length - N20.can_length
    )
    lo, hi = sorted((max(y0, min(can_start_y, can_end_y)), min(y1, max(can_start_y, can_end_y))))
    for frac in (0.3, 0.7):
        ly = lo + frac * (hi - lo)
        lip_z = plate_top + d.wall_h - d.lip_overhang  # near the top of the wall
        cradle += channel_lip(wall_inner_x[0], -1, ly, lip_z, d)
        cradle += channel_lip(wall_inner_x[1], 1, ly, lip_z, d)

    return cradle


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
# generic clip-post PCB tray (DRV8833, MP1584EN)
# ---------------------------------------------------------------------------


def pcb_tray(cx, cy, board_x, board_y, d: ChassisDims, standoff=None, post_h=None) -> Part:
    """`standoff`/`post_h` default to the generic (MP1584) tray numbers;
    pass the DRV8833-specific values to raise its board-rest height."""
    plate_top = d.plate_thickness
    standoff = d.tray_standoff if standoff is None else standoff
    post_h = d.tray_post_h if post_h is None else post_h
    post_w = d.tray_post_w
    oh = d.tray_lip_overhang
    tray = Part()
    for sx in (-1, 1):
        for sy in (-1, 1):
            corner_x = cx + sx * board_x / 2
            corner_y = cy + sy * board_y / 2
            base = Pos(corner_x, corner_y, plate_top) * Box(
                post_w, post_w, standoff, align=ALIGN_BOTTOM
            )
            upper = Pos(corner_x, corner_y, plate_top + standoff) * Box(
                post_w, post_w, post_h - standoff, align=ALIGN_BOTTOM
            )
            board_prism = Pos(cx, cy, plate_top + standoff) * Box(
                board_x, board_y, post_h, align=ALIGN_BOTTOM
            )
            upper -= board_prism
            # snap lip: a small chamfered nub at the post top, overlapping
            # the board corner by `oh` mm in both X and Y -- the chamfer on
            # every bottom edge keeps every face <=45 deg (no support).
            lip_size = post_w - 0.5
            lip_h = 1.2
            lip_x = corner_x - sx * oh
            lip_y = corner_y - sy * oh
            lip = Pos(lip_x, lip_y, plate_top + post_h - lip_h) * Box(
                lip_size, lip_size, lip_h, align=ALIGN_BOTTOM
            )
            lip = chamfer(lip.edges().group_by(Axis.Z)[0], lip_h * 0.6)
            tray += base + upper + lip
    return tray


# ---------------------------------------------------------------------------
# battery bay: guide nubs + strap slots (slots returned separately, they
# cut the plate rather than add to it)
# ---------------------------------------------------------------------------


def battery_nubs(d: ChassisDims) -> Part:
    plate_top = d.plate_thickness
    half_x = d.battery_len / 2 + d.nub_clearance
    half_y = d.battery_wid / 2 + d.nub_clearance
    nubs = Part()
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx = d.battery_x + sx * half_x
            by = sy * half_y
            align_x = Align.MIN if sx > 0 else Align.MAX
            align_y = Align.MIN if sy > 0 else Align.MAX
            arm1 = Pos(bx, by, plate_top) * Box(
                d.nub_arm, d.nub_t, d.nub_h, align=(align_x, Align.CENTER, Align.MIN)
            )
            arm2 = Pos(bx, by, plate_top) * Box(
                d.nub_t, d.nub_arm, d.nub_h, align=(Align.CENTER, align_y, Align.MIN)
            )
            nubs += arm1 + arm2
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
    # shank to the shoulder diameter, then a short flat land. The first
    # skid used a plain cylinder whose flat underside was a 3.2 mm mid-air
    # overhang -- it printed as spaghetti.
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
    # quarter-prongs -- far more compliant than the original two half-round
    # prongs with a shallow slit, and self-centering on insertion.
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
    footprints: dict = field(default_factory=dict)


def label_engraving(d: ChassisDims) -> Part:
    """Identity text cut into the bottom face, mirrored in X so it reads
    correctly when viewed from below (robot flipped over)."""
    n = len(d.label_lines)
    text = None
    for i, line in enumerate(d.label_lines):
        y = ((n - 1) / 2 - i) * d.label_line_spacing
        t = Pos(0, y) * Text(line, font_size=d.label_font_size)
        text = t if text is None else text + t
    text = mirror(text, Plane.YZ)  # readable from underneath
    prism = extrude(text, amount=d.label_depth)  # z 0..depth, cut from the bottom
    return Pos(d.label_x, d.label_y, 0) * prism


def build(d: ChassisDims) -> Chassis:
    plate_top = d.plate_thickness
    cradle_p = motor_cradle(d, +1)
    cradle_m = motor_cradle(d, -1)
    drv_tray = pcb_tray(
        d.drv_x, d.drv_y, d.drv_board_x, d.drv_board_y, d,
        standoff=d.drv_tray_standoff, post_h=d.drv_tray_post_h,
    )
    buck_tray = pcb_tray(d.buck_x, d.buck_y, d.buck_board_x, d.buck_board_y, d)
    nubs = battery_nubs(d)
    # the DRV8833 tray's posts still clip one battery guide-nub arm even
    # after the +2.5 mm Y-nudge (see deviation 9) -- trim whatever nub
    # material actually collides with the tray's BUILT envelope, rather
    # than hand-deriving which arm/how much.
    nubs -= drv_tray

    body = plate(d)
    body += cradle_p
    body += cradle_m
    body += pi_mount(d)
    body += drv_tray
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
    # zip-tie hole near the MP1584 tray, beyond its open (22 mm) edge, on
    # the side away from the centerline / battery bay. The DRV8833 tray's
    # open edges face +-X, straight into the cradle on one side and the
    # rear plate edge on the other -- there's no room for a clean hole
    # there, so per the brief ("skip if it complicates anything") it's
    # left without one.
    # Past the board's +X short edge, NOT squeezed between its long edge and
    # the plate edge: the long-edge position left only a 0.2 mm outer wall
    # (thinner than a nozzle line), which printed as an open notch on
    # PROTO-01. Here the hole keeps >=4 mm of plate on every side.
    zip_x = d.buck_x + d.buck_board_x / 2 + 4.5
    zip_y = -(d.plate_width / 2) + 4.5 + d.zip_tie_hole_d / 2  # 4.5 mm edge wall
    body -= Pos(zip_x, zip_y, -0.5) * Cylinder(
        radius=d.zip_tie_hole_d / 2, height=d.plate_thickness + 1, align=ALIGN_BOTTOM
    )

    body -= label_engraving(d)

    skid, below = build_skid(d)

    # Hardened footprints: real BUILT Part envelopes, not nominal
    # rectangles -- see deviation 9 for why (a rectangle either badly
    # over-approximates the sparse, multi-armed guide-nub shape, or misses
    # a boolean-subtraction remnant's true material extent, or is Z-blind).
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

    footprints = {
        "cradle+Y": cradle_p,
        "cradle-Y": cradle_m,
        "pi_board": pi_env,
        "drv8833": drv_tray,
        "mp1584": buck_tray,
        "battery": battery_env,
    }

    return Chassis(d, body, skid, below, footprints)


def overlap_check(footprints: dict) -> bool:
    """`footprints[name]` is a BUILT Part (or a close proxy for pi_board --
    see build()). Two features conflict iff their exact CAD boolean
    intersection volume (ivol(), the same authoritative signal
    assembly.py's own checks use) is at or above OVERLAP_TOL -- a tiny
    positive volume from coincident/tangent faces is numerical noise, not
    a real conflict."""
    OVERLAP_TOL = 1.0  # mm^3

    names = list(footprints)
    all_ok = True
    print("\n-- footprint overlap check (BUILT-geometry boolean volume) --")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            vol = ivol(footprints[a], footprints[b])
            ok = vol < OVERLAP_TOL
            all_ok &= ok
            print(
                f"[{'PASS' if ok else 'FAIL'}] {a:10s} vs {b:10s}  "
                f"(intersection {vol:.3f} mm^3, < {OVERLAP_TOL:g})"
            )
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

    assembly = Part() + c.plate
    assembly += motor_placement(+1, d)
    assembly += motor_placement(-1, d)
    installed_skid = Pos(d.skid_front_x, 0, -c.skid_below) * c.skid
    assembly += installed_skid
    export_stl(assembly, here / "chassis_assembly.stl")

    ok = overlap_check(c.footprints)

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

    print("\nExported chassis.stl/.step, skid.stl/.step, chassis_assembly.stl")
    sys.exit(0 if ok else 1)
