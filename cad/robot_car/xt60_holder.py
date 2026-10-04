"""robot_car: the XT60 holder -- the right motor's lid, with a channel on top
that the harness's male XT60 slides into and clicks into, facing the rear.

WHAT IT DOES

The pack's female XT60 plugs into a male plug that the car holds still. The
pack's lead leaves its rear end, so the male faces the rear: it lies flat
in a channel along the car's X axis on top of the right (-Y) motor lid, its
mating face at the lid's rear edge, its wires out the front toward the fuse
and the switch. The female comes in from behind and plugs in moving
forward. The channel is open at both ends and along most of its top. Past
the male's rim there is nothing above the channel floor, so the female seats
fully: its body is the same 16 x 8.1 outline as the male's, and it meets the
male's rim face to face (cad/parts/xt60.py).

The right lid, not the left, because the mated female stands out behind
the lid, and behind the left lid are the DRV8833 and the leads on its
header pins. The right-rear corner is empty.

HOW IT HOLDS THE PLUG

- Keyed outline. The channel follows the plug's outline, including the two
  45 deg chamfers on its (+) end, which sit in a matching V-groove. The V's
  upper flank holds that side down, a lip holds the square side down, so
  the plug can only go in one way up and can't lift out. The fit on every
  face is side_fit (snug: the friction is what holds the plug against the
  pull of unplugging -- see below).
- Mark reliefs. The moulded + and - stand 0.2 mm proud of the plug's two
  short ends near its wire end. A shallow groove runs the full length of
  each side wall at their height, so the snug fit is on the 15.7 mm body,
  not on the marks, wherever along the plug they sit.
- Held at its edges only. The plug's front half is the shroud the female
  goes into, a hollow with 0.7 mm walls: pressed in the middle, top or
  bottom, it bends inward. So the plug stands on two ledges along the
  channel floor's edges (ledge_w on the square side, past the foot of the
  V on the other), where the floor -- a bridge when printed -- is anchored
  and doesn't sag; between them the floor drops floor_relief, room for the
  bridge's sag. On top, the lips and the V's upper flank hold the edges,
  and the crossbar the arm grows from stands crossbar_clear above the
  plug.
- Latch. A flat arm on top, rooted at the mating end and lying over the
  plug, carries a barb at its free end. The plug goes in rim first from the
  wire end (from the front of the car): its leading edge rides up the
  barb's ramp and lifts the arm; once its back face is past, the arm drops
  and the barb sits behind it, between the two solder cups and above their
  heat-shrink. Pushing the pack's female in loads the arm in tension, not
  bending. Lift the arm's tail with a fingernail to slide the plug back
  out. The arm prints flat on the bed and bends within its layers.
- Unplugging pulls the male toward the female, and the male has no face
  that way except its rim, which the female covers. So nothing can stop it
  there but friction: hold the lid when pulling the pack's plug.

HOW IT SITS ON THE LID

The lid's 2 mm ceiling is the spring that clamps the motor: its pad sits
0.30 mm into the motor top and the ceiling bows to seat (lid_coupons.py).
Walls bonded along the ceiling would stiffen it many times over. So the
holder is a rigid frame that touches the lid only on two plinths, one over
each skirt, where the ceiling meets the skirts, and clears the rest of the
ceiling by `gap` -- room for the bow plus the sag of the ceiling's first
layer, which prints as a bridge between the plinths. The ceiling still bows
over its full span; what the frame takes away is the skirts' outward splay.
At lid E's 0.30 mm preload the holder lid still slides on by hand and holds
the motor, better than at 0.20 (xt60_lid_trials.py, lid K).

PRINTING

The lid prints upside down as before, so the holder's top is on the bed:
the lips, the crossbar and the arm are first layers, the walls rise, the
channel floor bridges the channel (y), the plinths stand on the frame and
the ceiling bridges between them (x). No supports.

Frames: the holder frame has x toward the mating end (car -X) from the
lid's rear edge at x = 0, y across the car (car -Y, outboard) from the
lid's centre, and z up from the lid's top face. For the right lid that is
the car frame turned 180 deg about Z and moved to holder_origin()
(to_car, car_pts); to_lid puts it on lid_coupons.py's lid frame. Run with:  uv run robot_car/xt60_holder.py
Exports xt60_lid.stl (print orientation) and runs the PASS/FAIL checks.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

import numpy as np  # noqa: E402
from build123d import (  # noqa: E402
    Axis,
    Box,
    Cylinder,
    Part,
    Polyline,
    Pos,
    export_stl,
    extrude,
    make_face,
)

from chassis import ChassisDims, _to_side, cantilever, ivol, lid_dims  # noqa: E402
from lid_coupons import LidDims, lid_for_print, make_cradle, make_lid, tips  # noqa: E402
from xt60 import Xt60Dims, make_female, make_male, make_shrink  # noqa: E402

XT = Xt60Dims()


@dataclass
class HolderDims:
    # ---- plug in its channel --------------------------------------------
    side_fit: float = 0.15  # every face of the outline, per side: coupon Z
    top_fit: float = 0.30  # plug top to the lip undersides: coupon Z
    setback: float = 0.0  # male rim this far inside the lid's rear edge
    rim_proud: float = 0.5  # rim stands this far ahead of the walls
    # ---- frame on the lid --------------------------------------------------
    gap: float = 1.2  # frame underside above the ceiling: bow + bridge sag
    floor_t: float = 1.2
    floor_relief: float = 0.5  # middle of the floor, below the plug's ledges
    ledge_w: float = 2.0  # floor under the plug along its square end
    floor_drop: float = 0.3  # floor ahead of the walls, below the female
    lip_t: float = 1.5  # the top skin: lips and crossbar
    lip_w: float = 1.2  # square-side lip reach over the plug
    width: float = 23.0  # across the car = the lid's length
    mark_clear: float = 0.15  # the + / - marks to the floor of their grooves
    mark_band: float = 2.4  # groove height, centred on the plug's axis
    # ---- latch arm ---------------------------------------------------------
    arm_t: float = 1.0
    arm_w: float = 6.0
    arm_root_r: float = 1.0  # plan-view radius where the arm leaves the crossbar
    crossbar: float = 4.0  # front top bar the arm grows from, along x
    crossbar_clear: float = 0.5  # crossbar underside above the plug
    barb_depth: float = 1.0  # below the plug's top
    barb_w: float = 3.0  # between the solder cups' heat-shrink
    barb_len: float = 2.5
    barb_fit: float = 0.15  # plug rear face to barb, seated
    ramp_len: float = 2.0
    tab_len: float = 1.5  # arm past the ramp, to lift it by
    tail: float = 1.0  # frame past the arm's tab

    # ---- derived (holder frame) -------------------------------------------
    @property
    def z_plug(self) -> float:  # plug bottom = floor top
        return self.gap + self.floor_t

    @property
    def z_plug_top(self) -> float:
        return self.z_plug + XT.height

    @property
    def z_top(self) -> float:
        return self.z_plug_top + self.top_fit + self.lip_t

    @property
    def x_rim(self) -> float:
        return -self.setback

    @property
    def x_wall_front(self) -> float:
        return self.x_rim - self.rim_proud

    @property
    def x_rear_face(self) -> float:  # plug's rear face, seated
        return self.x_rim - XT.male_len

    @property
    def x_root(self) -> float:  # arm root = crossbar's rear edge
        return self.x_wall_front - self.crossbar

    @property
    def x_barb(self) -> float:  # barb's front (holding) face
        return self.x_rear_face - self.barb_fit

    @property
    def x_tab(self) -> float:  # arm's free end
        return self.x_barb - self.barb_len - self.ramp_len - self.tab_len

    @property
    def x_end(self) -> float:  # frame's rear end
        return self.x_tab - self.tail

    @property
    def arm_len(self) -> float:  # root to the barb's middle
        return self.x_root - (self.x_barb - self.barb_len / 2)


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def yz_prism(pts, x0, x1) -> Part:
    face = make_face(Polyline(*[(0, y, z) for y, z in pts], close=True))
    return Pos(min(x0, x1), 0, 0) * extrude(face, amount=abs(x1 - x0), dir=(1, 0, 0))


def xz_prism(pts, y0, y1) -> Part:
    face = make_face(Polyline(*[(x, 0, z) for x, z in pts], close=True))
    return Pos(0, y0, 0) * extrude(face, amount=y1 - y0, dir=(0, 1, 0))


def cavity_profile(h: HolderDims, grow: float = 0.0) -> list:
    """The channel's YZ section around the plug: its outline grown by
    side_fit (top_fit above), chamfered end at -y, floor flat at z_plug.
    `grow` widens it further, for the entry lead-in."""
    w, ht, c = XT.width / 2, XT.height, XT.chamfer
    f = h.side_fit + grow
    zc, zt = h.z_plug - grow, h.z_plug_top + h.top_fit + grow
    k = f * (2 ** 0.5 - 1)  # where an f-offset 45 deg flank meets an f-offset flat
    s = f * 2 ** 0.5  # an f-offset 45 deg flank, shifted along y
    y_top = (zt - h.z_plug - ht + c) - w - s  # upper flank at the channel top
    y_bot = -w + c - s - (h.z_plug - zc)  # lower flank at the floor
    return [(w + f, zc), (w + f, zt), (y_top, zt), (-w - f, h.z_plug + ht - c + k),
            (-w - f, h.z_plug + c - k), (y_bot, zc)]


def slot_edges(h: HolderDims) -> tuple[float, float]:
    """The top opening between the chamfer side's wall and the square
    side's lip."""
    y_lo = cavity_profile(h)[2][0]
    y_hi = XT.width / 2 + h.side_fit - h.lip_w
    return y_lo, y_hi


def make_arm(h: HolderDims) -> Part:
    """The latch arm, relaxed, from its root on the crossbar to its tab."""
    zt = h.z_top
    arm = rbox(h.x_tab, h.x_root + 0.01, -h.arm_w / 2, h.arm_w / 2, zt - h.arm_t, zt)
    z_tip = h.z_plug_top - h.barb_depth
    x0 = h.x_barb
    pts = [(x0, zt - h.arm_t + 0.01), (x0, z_tip), (x0 - h.barb_len, z_tip),
           (x0 - h.barb_len - h.ramp_len, zt - h.arm_t + 0.01)]
    return arm + xz_prism(pts, -h.barb_w / 2, h.barb_w / 2)


def arm_pivot(h: HolderDims) -> tuple[float, float]:
    """(x, z) the arm swings about when it lifts: its root, mid-thickness."""
    return h.x_root, h.z_top - h.arm_t / 2


def make_frame(h: HolderDims, plinth_xs: tuple) -> Part:
    """The holder without its arm: walls, lips, crossbar, floor and the two
    plinths (x ranges) that bond it to the lid."""
    yw = h.width / 2
    frame = rbox(h.x_end, h.x_wall_front, -yw, yw, h.gap, h.z_top)
    frame -= yz_prism(cavity_profile(h), h.x_end - 1, h.x_wall_front + 1)
    # a groove along each side wall for the + / - marks
    depth = XT.mark_h + h.mark_clear - h.side_fit
    zc = h.z_plug + XT.axis_z
    for s in (-1, 1):
        y0 = s * (XT.width / 2 + h.side_fit)
        frame -= rbox(h.x_end - 1, h.x_wall_front + 1, *sorted((y0 - s * 0.5, y0 + s * depth)),
                      zc - h.mark_band / 2, zc + h.mark_band / 2)
    # entry lead-in: a 45 deg funnel on the wire-end opening
    lead = 0.6
    for i in range(6):
        g = lead * (1 - i / 6)
        frame -= yz_prism(cavity_profile(h, g), h.x_end - 1, h.x_end + lead * (i + 1) / 6)
    # the top opening, behind the crossbar, and the crossbar's underside
    # lifted clear of the shroud
    y_lo, y_hi = slot_edges(h)
    frame -= rbox(h.x_end - 1, h.x_root, y_lo, y_hi, h.z_plug_top, h.z_top + 1)
    frame -= rbox(h.x_root - 0.01, h.x_wall_front + 1, y_lo, y_hi,
                  h.z_plug_top, h.z_plug_top + h.crossbar_clear)
    # the floor's middle dropped below the two ledges the plug stands on
    w, f = XT.width / 2, h.side_fit
    y_a = -w + XT.chamfer - f * 2 ** 0.5 + 1.0  # 1 mm past the foot of the V
    y_b = w + f - h.ledge_w
    frame -= rbox(h.x_end - 1, h.x_wall_front + 1, y_a, y_b, h.z_plug - h.floor_relief, h.z_plug + 0.01)
    # radii where the arm leaves the crossbar
    r = h.arm_root_r
    for s in (-1, 1):
        yc = s * (h.arm_w / 2 + r)
        corner = rbox(h.x_root - r, h.x_root, *sorted((s * h.arm_w / 2, yc)), h.z_top - h.arm_t, h.z_top)
        corner -= Pos(h.x_root - r, yc, h.z_top - h.arm_t / 2) * Cylinder(radius=r, height=h.arm_t + 1)
        frame += corner
    # floor ahead of the walls, out to the lid's rear edge, a little low so
    # the mated female rides over it
    frame += rbox(h.x_wall_front - 0.01, 0, -yw, yw, h.gap, h.z_plug - h.floor_drop)
    for x0, x1 in plinth_xs:
        frame += rbox(x0, x1, -yw, yw, -0.01, h.gap + 0.01)
    return frame


def plinths(h: HolderDims, cd: ChassisDims) -> tuple:
    """The two plinths in holder x: over the lid's two skirts."""
    ld = lid_dims(cd)
    span, skirt = 2 * ld.lid_half_w, ld.skirt_t
    return ((-skirt, 0.0), (-span, -span + skirt))


def holder_origin(cd: ChassisDims) -> tuple[float, float, float]:
    """Car coordinates of the holder frame's origin on the right (-Y) lid:
    the lid's rear edge, its centre across the car, its top face."""
    ld = lid_dims(cd)
    x = cd.cradle_x - ld.lid_half_w
    y = -(cd.plate_width / 2 - ld.edge_y + ld.lid_len / 2)
    z = ld.T + ld.rail_clearance + ld.ceiling_t
    return x, y, z


def to_car(part: Part, cd: ChassisDims) -> Part:
    return Pos(*holder_origin(cd)) * part.rotate(Axis.Z, 180)


def car_pts(p, cd: ChassisDims) -> np.ndarray:
    """to_car for points: holder-frame (..., 3) array -> car coordinates."""
    return np.asarray(p, float) * [-1, -1, 1] + holder_origin(cd)


def to_lid(part: Part, cd: ChassisDims) -> Part:
    """Holder frame -> lid_coupons.py's lid frame (before chassis._to_side
    turns the lid round for the -Y side, which takes lid +x to car -X)."""
    ld = lid_dims(cd)
    z = ld.T + ld.rail_clearance + ld.ceiling_t
    return Pos(ld.lid_half_w, ld.lid_len / 2, z) * part


def make_holder(h: HolderDims, cd: ChassisDims) -> tuple[Part, Part]:
    """(frame, arm) in the holder frame."""
    return make_frame(h, plinths(h, cd)), make_arm(h)


def make_holder_lid(h: HolderDims, cd: ChassisDims, ld: LidDims | None = None) -> Part:
    """The right lid with the holder on it, in the lid frame. `ld` swaps in
    another lid (a different pad preload, a label); default the car's."""
    frame, arm = make_holder(h, cd)
    return make_lid(ld or lid_dims(cd)) + to_lid(frame + arm, cd)


def male_seated(h: HolderDims) -> Part:
    return Pos(h.x_rim, 0, h.z_plug) * make_male(XT)


def shrink_seated(h: HolderDims) -> Part:
    s = make_shrink(XT, -XT.male_len, -1)
    return Pos(h.x_rim, 0, h.z_plug) * (s[0] + s[1])


def female_mated(h: HolderDims) -> Part:
    s = make_shrink(XT, XT.female_body_len, +1)
    return Pos(h.x_rim, 0, h.z_plug) * (make_female(XT) + s[0] + s[1])


def barb_lift_needed(h: HolderDims, plug_dx: float) -> float:
    """How far the barb's underside must rise for the plug, slid plug_dx
    from seated (negative = not yet in), to pass under it."""
    top = h.z_plug_top
    x_front, x_back = h.x_rim + plug_dx, h.x_rear_face + plug_dx
    z_tip = h.z_plug_top - h.barb_depth
    z_arm = h.z_top - h.arm_t
    xb0, xb1, xb2 = h.x_barb, h.x_barb - h.barb_len, h.x_barb - h.barb_len - h.ramp_len

    def barb_z(x):  # barb underside at x, relaxed
        if xb1 <= x <= xb0:
            return z_tip
        if xb2 <= x < xb1:
            return z_tip + (z_arm - z_tip) * (xb1 - x) / (xb1 - xb2)
        return z_arm

    lo, hi = max(x_back, xb2), min(x_front, xb0)
    if lo > hi:
        return 0.0
    xs = [lo + (hi - lo) * i / 40 for i in range(41)]
    return max(0.0, max(top - barb_z(x) for x in xs))


def checks(h: HolderDims, cd: ChassisDims, car: list | None = None) -> bool:
    ok = True

    def report(name, passed, detail=""):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  {detail}")

    ld = lid_dims(cd)
    frame, arm = make_holder(h, cd)
    holder = frame + arm
    male, shrink, female = male_seated(h), shrink_seated(h), female_mated(h)

    report("male seated clear of the holder", ivol(male + shrink, holder) < 1e-6,
           f"{ivol(male + shrink, holder):.3f} mm^3")
    gap_shrink = arm.distance_to(shrink)
    report("barb clears the heat-shrink by >= 0.5 mm", gap_shrink >= 0.5,
           f"{gap_shrink:.2f} mm to the {XT.shrink_d:g} mm sleeves")
    report("pack's female, mated, clear of the holder", ivol(female, holder) < 1e-6,
           f"{ivol(female, holder):.3f} mm^3")

    # sliding in from the wire end: the plug and its heat-shrink clear the frame
    # all the way; only the arm is in the way, and it lifts
    worst, need = 0.0, 0.0
    for dx in [-30 + i for i in range(31)]:
        moved = Pos(dx, 0, 0) * (male + shrink)
        worst = max(worst, ivol(moved, frame))
        need = max(need, barb_lift_needed(h, dx))
    report("plug slides in from the wire end clear of the frame", worst < 1e-6,
           f"{worst:.3f} mm^3 at worst over 30 mm of travel")
    held = ivol(Pos(-0.5, 0, 0) * male, arm)
    report("barb stands behind the seated plug (holds it against the push)",
           held > 0.5 and ivol(male + shrink, arm) < 1e-6, f"{held:.2f} mm^3 in the way 0.5 mm back")
    bend = cantilever(h.arm_len, h.arm_t, h.arm_w, need)
    report("latch arm strain on the way in <= 1 %", bend["strain"] <= 0.01,
           f"lift {need:.2f} mm over {h.arm_len:.1f} mm: {100 * bend['strain']:.2f} % peak, "
           f"{bend['force']:.1f} N at the barb")

    # the lid still clamps the motor through its ceiling
    bow = ld.pad_preload - ld.rail_clearance * (2 ** 0.5 - 1)
    sag = 0.5  # first bridge layer over the plinths' span, allowance
    report("ceiling bows clear of the frame", bow + sag < h.gap,
           f"bow {bow:.2f} + bridge sag {sag:.1f} < gap {h.gap:.1f} mm")
    span = 2 * ld.lid_half_w - 2 * ld.skirt_t
    w, f = XT.width / 2, h.side_fit
    middle = (w + f - h.ledge_w) - (-w + XT.chamfer - f * 2 ** 0.5 + 1.0)
    print(f"         ceiling bridge between the plinths: {span:.1f} mm; channel floor: plug on "
          f"its edge ledges, the {middle:.1f} mm between them {h.floor_relief:g} mm lower; "
          f"crossbar {h.crossbar_clear:g} mm over the shroud")

    # the lid still slides on: lid + holder vs the cradle, seated and on the way
    lid = make_holder_lid(h, cd)
    cradle = make_cradle(ld)
    body = lid - tips(ld)
    for dy in (0.0, -3.0, -12.0, -22.0):
        v = ivol(Pos(0, dy, 0) * (body if dy else lid), cradle)
        report(f"holder lid clear of the cradle at y{dy:+.0f}", v < 1e-6, f"{v:.3f} mm^3")

    if car is not None:
        placed = _to_side(lid, cd, -1)
        plain = _to_side(make_lid(ld), cd, -1)
        m, s, f = (to_car(p, cd) for p in (male, shrink, female))
        for name, part in car:
            if name == "motor lid":
                continue
            v_lid = ivol(placed, part)
            if name == "N20 gearmotor" and v_lid > 0:
                v_plain = ivol(plain, part)
                report("holder lid presses the motor only as lid E does",
                       abs(v_lid - v_plain) < 0.05, f"{v_lid:.2f} vs {v_plain:.2f} mm^3 (pad preload)")
            else:
                report(f"holder lid clear of {name}", v_lid < 1e-6, f"{v_lid:.3f} mm^3")
            v = ivol(m + s + f, part)
            report(f"plugs clear of {name}", v < 1e-6, f"{v:.3f} mm^3")
    return ok


def car_parts():
    """Every part on the car, from render_assembly, minus both lids (the
    checks place their own)."""
    from render_assembly import assembly_parts
    _, parts = assembly_parts()
    return parts


def main() -> None:
    cd, h = ChassisDims(), HolderDims()
    print(f"holder: {h.x_end:.1f}..0 x +-{h.width / 2:.1f} x 0..{h.z_top:.2f} mm on the lid; "
          f"plug rim at x {h.x_rim:.1f}, top {h.z_top:.1f} above the lid "
          f"(car Z {holder_origin(cd)[2] + h.z_top:.1f})")
    print("PASS/FAIL checks:")
    ok = checks(h, cd, car_parts())
    lid = make_holder_lid(h, cd)
    printable = lid_for_print(lid, lid_dims(cd))
    export_stl(printable, HERE / "xt60_lid.stl")
    bb = printable.bounding_box()
    print(f"xt60_lid.stl: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"{printable.volume / 1000:.2f} cm^3, solids: {len(printable.solids())}")
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
