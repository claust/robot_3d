"""robot_car: the power block -- one printed block holding the power switch,
the harness's male XT60 and the fuse, so the pack's power goes XT60 ->
fuse -> switch inside a few centimetres.

THE SWITCH

switch_well.py's well, unchanged: the KCD1 snaps into its panel from
above, rolled in, its three terminals bent over and pointing forward (+X)
just above the plate.

THE FUSE

A low-profile mini blade fuse stands upright in front of the switch,
blades down, right over terminal 1 -- the terminal the pack's + comes to,
so everything after it, the switch included, is behind the fuse. Its
inner blade's tip rests on the terminal's bent-over leg, so a dot of
solder joins them; the outer blade stands 8 mm further out on a printed
pedestal of the same height, where the wire from the XT60 is soldered.
The fuse's wide faces point across the car, so its other blade is nowhere
near the next terminal. Rails grip its narrow edges, which
also cover the blades' bare outer edges; both wide faces are open between
the rails, a window on each side to see the element through.

THE XT60

xt60_holder.py's holder -- the channel and its fits, the mark grooves,
the edge ledges -- stood on its side along the switch well's rear: the
male stands upright, its V-shaped (+) end down in the matching groove, its
mating face at the block's -Y end, where the pack's female plugs in from
the battery side, its wires out the +Y end. The holder's flat latch arm
would print as a 13 mm overhang standing up, so the latch is a finger
instead: it rises from the plate outside the channel's open side and its
barb reaches in through that side's window behind the male's rear face.
The male slides in from the wire end and its leading edge pushes the barb
out; once past, the finger springs back and the barb holds the male
against the push of plugging the pack in. Push the finger's top outward
to slide the male back out.

Frame: the switch's centre at X = Y = 0, terminals toward +X, Z up from
the plate's underside (the coupon's slab is the plate).

Run with:  uv run robot_car/power_block.py [--no-render]
Runs the PASS/FAIL checks, exports power_block.stl (print orientation:
as is) and renders power_block.png.
"""

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import Axis, Part, Polyline, Pos, export_stl, extrude, make_face  # noqa: E402

from chassis import ChassisDims, cantilever, ivol  # noqa: E402
from kcd1_rocker import make_kcd1  # noqa: E402
from switch_well import make_well, neighbour_sections, rbox, roll_in_check  # noqa: E402
from xt60 import make_shrink  # noqa: E402
from xt60_holder import (  # noqa: E402
    XT, HolderDims, barb_lift_needed, female_mated, make_frame, male_seated, shrink_seated,
    xz_prism,
)


def yz_prism(pts, x0, x1) -> Part:
    face = make_face(Polyline(*[(0, y, z) for y, z in pts], close=True))
    return Pos(x0, 0, 0) * extrude(face, amount=x1 - x0, dir=(1, 0, 0))


@dataclass
class FuseDims:
    """Low-profile mini blade fuse, calipered unless marked est."""
    width: float = 10.9
    thick: float = 3.8
    length: float = 9.5  # top of the body to the blade tips
    body: float = 7.5  # top of the body to its lowest point, between the blades
    cap: float = 3.0  # the top band that covers the full width
    blade_w: float = 2.85  # est
    blade_t: float = 0.65  # est

    @property
    def pitch(self) -> float:  # blade centres
        return self.width - self.blade_w


@dataclass
class BlockDims:
    car: ChassisDims = field(default_factory=ChassisDims)
    fuse: FuseDims = field(default_factory=FuseDims)
    # terminal 1, the pack's side, is the one at car Y = fuse_y: the switch's
    # outer terminals sit at Y = +-7 (its pitch), the middle one at 0
    fuse_y: float = 7.0
    fuse_x: float = 10.4  # inner blade's centre, on the leg past the panel's edge
    fuse_fit: float = 0.1  # per side, in the rails
    rail_t: float = 1.2
    rail_lip: float = 1.3  # how far each rail's flanges reach over the fuse's face
    # XT60 on its side
    holder: HolderDims = field(default_factory=lambda: replace(HolderDims(), gap=0.0, width=19.2))
    # latch finger, outside the channel's open side
    finger_gap: float = 0.5
    finger_t: float = 1.2
    finger_w: float = 4.5  # along the plug
    barb_h: float = 3.0  # barb's extent across the plug's width
    margin: float = 3.0  # coupon slab past the parts

    @property
    def T(self) -> float:
        return self.car.plate_thickness

    @property
    def w(self):
        return self.car.well

    @property
    def panel_z(self) -> float:
        return self.T + self.w.height

    @property
    def leg_top(self) -> float:  # the terminals' horizontal legs, top face
        sw = self.w.sw
        return self.panel_z - sw.body_depth - sw.terminal_bottom + sw.terminal_t

    @property
    def fuse_x0(self) -> float:  # fuse's inner edge
        return self.fuse_x - self.fuse.blade_w / 2


def place_switch(b: BlockDims, part: Part) -> Part:
    """switch_well.py's frame -> the block's (chassis._switch_to_car at 0, 0)."""
    return Pos(0, 0, b.panel_z) * part.rotate(Axis.Z, -90)


def make_fuse(b: BlockDims) -> Part:
    f, x0, y, z0 = b.fuse, b.fuse_x0, b.fuse_y, b.leg_top
    xc, top = x0 + f.width / 2, z0 + f.length
    fuse = rbox(x0, x0 + f.width, y - f.thick / 2, y + f.thick / 2, top - f.cap, top)
    core = f.width - 2 * f.blade_w
    fuse += rbox(xc - core / 2, xc + core / 2, y - f.thick / 2, y + f.thick / 2, top - f.body, top - f.cap)
    for s in (-1, 1):
        bx = xc + s * f.pitch / 2
        fuse += rbox(bx - f.blade_w / 2, bx + f.blade_w / 2, y - f.blade_t / 2, y + f.blade_t / 2,
                     z0, top - 1.0)
    return fuse


def fuse_holder(b: BlockDims) -> Part:
    """Rails round the fuse's narrow edges and a pedestal under the outer
    blade. The outer rail is a C, its back the fuse's stop; the inner one is
    only the two flanges, because terminal 1 sweeps through its back's
    place as the switch rolls in; they reach up into the well's panel."""
    f, c, t, y = b.fuse, b.fuse_fit, b.rail_t, b.fuse_y
    x0, x1 = b.fuse_x0, b.fuse_x0 + f.width
    top = b.leg_top + f.length
    half = f.thick / 2 + c
    out = rbox(x1 + c, x1 + c + t, y - half - t, y + half + t, b.T - 0.01, top)
    panel_bottom = b.panel_z - b.w.panel_t
    for s, xe in ((-1, x0), (1, x1)):
        # the inner flanges run on up into the switch well's panel, so
        # they don't stand alone
        z1 = top if s > 0 else panel_bottom + 0.01
        for sy in (-1, 1):
            out += rbox(*sorted((xe + s * (c + t), xe - s * b.rail_lip)),
                        *sorted((y + sy * half, y + sy * (half + t))), b.T - 0.01, z1)
    xc = x0 + f.width / 2
    bx = xc + f.pitch / 2
    out += rbox(bx - f.blade_w / 2 - 0.2, x1 + c + 0.01, y - half, y + half, b.T - 0.01, b.leg_top)
    return out


# ---- the XT60, upright -------------------------------------------------------


def to_block(b: BlockDims, part: Part) -> Part:
    """Holder frame (xt60_holder.py, gap 0) -> the block: the plug's width
    stood upright with its V end down, its mating end toward -Y at the
    well's -Y end, the channel's floor against the well's rear (-X) face."""
    h, w = b.holder, b.w
    up = part.rotate(Axis.X, 90).rotate(Axis.Z, -90)  # holder x -> -Y, y -> Z, z -> -X
    return Pos(-w.half_y, -w.half_x, b.T + h.width / 2) * up


def finger(b: BlockDims) -> Part:
    """The latch finger in the holder frame: a plate outside the channel's
    open side (holder +z), rooted at the plate, and its barb through the
    window behind the male's rear face, with a 45 deg underside."""
    h = b.holder
    zf = h.z_top + b.finger_gap
    yb1 = XT.width / 2 + h.side_fit - h.lip_w - 0.5  # under the square side's lip
    yb0 = yb1 - b.barb_h
    xc = h.x_barb - h.barb_len / 2
    plate = rbox(xc - b.finger_w / 2, xc + b.finger_w / 2, -h.width / 2 - 0.01, yb1 + 0.5, zf, zf + b.finger_t)
    z_tip = h.z_plug_top - h.barb_depth
    x0 = h.x_barb
    pts = [(x0, zf + 0.01), (x0, z_tip), (x0 - h.barb_len, z_tip),
           (x0 - h.barb_len - h.ramp_len, h.z_plug_top), (x0 - h.barb_len - h.ramp_len, zf + 0.01)]
    barb = xz_prism(pts, yb0 - (zf - z_tip) - 1, yb1)
    under = [(yb1, z_tip - 0.01), (yb0, z_tip - 0.01), (yb0 - (zf - z_tip) - 0.02, zf + 0.02), (yb1, zf + 0.02)]
    barb &= yz_prism(under, x0 - h.barb_len - h.ramp_len - 1, x0 + 1)
    return plate + barb, (zf, yb0, yb1)


def finger_len(b: BlockDims) -> float:
    """Root (plate) to the barb's middle, along the finger."""
    zf, yb0, yb1 = finger(b)[1]
    return (yb0 + yb1) / 2 + b.holder.width / 2


# ---- the block -----------------------------------------------------------------


def make_block(b: BlockDims):
    """(block, finger) in the block frame; the block includes the slab."""
    well = place_switch(b, make_well(b.w))
    chan = to_block(b, make_frame(b.holder, Part()))
    fing = to_block(b, finger(b)[0])
    parts = well + chan + fuse_holder(b) + fing
    bb = parts.bounding_box()
    m = b.margin
    slab = rbox(bb.min.X - m, bb.max.X + m, bb.min.Y - m, bb.max.Y + m, 0, b.T)
    return slab + parts, fing


def plugs(b: BlockDims) -> dict:
    h = b.holder
    return {"male": to_block(b, male_seated(h) + shrink_seated(h)), "female": to_block(b, female_mated(h))}


def checks(b: BlockDims, block: Part, fing: Part) -> bool:
    ok = True

    def report(name, passed, detail=""):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  {detail}")

    sw = place_switch(b, make_kcd1(b.w.sw, clips=False))
    fuse = make_fuse(b)
    pl = plugs(b)
    h = b.holder
    report("one solid", len(block.solids()) == 1, f"{len(block.solids())}")
    v = ivol(block, sw)
    report("switch seats in its well", v < 0.5, f"{v:.3f} mm^3 (clips flex)")
    obstacles = neighbour_sections(b.w, (0.0, 0.0, b.panel_z), [block])
    rolled, path = roll_in_check(b.w, obstacles)
    report("switch rolls in past the fuse rails and the XT60 channel", rolled,
           f"{len(path)} poses" if rolled else "no collision-free path")
    v = ivol(block, fuse)
    report("fuse stands in its rails", v < 1e-6, f"{v:.3f} mm^3")
    d1 = fuse.distance_to(sw)
    report("fuse's inner blade rests on terminal 1", d1 < 0.05, f"{d1:.2f} mm")
    mid = sw & rbox(0, 20, -1, 1, b.T, b.panel_z)
    d2 = fuse.distance_to(mid)
    report("fuse clears the middle terminal by >= 2.5 mm", d2 >= 2.5, f"{d2:.2f} mm")
    for name, part in pl.items():
        v = ivol(part, block)
        report(f"XT60 {name} clear of the block", v < 1e-6, f"{v:.3f} mm^3")
        v = ivol(part, sw + fuse)
        report(f"XT60 {name} clear of the switch and fuse", v < 1e-6, f"{v:.3f} mm^3")
    male = male_seated(h) + shrink_seated(h)
    frame = make_frame(h, Part())
    fh = finger(b)[0]
    worst, need = 0.0, 0.0
    for dx in [-30 + i for i in range(31)]:
        worst = max(worst, ivol(Pos(dx, 0, 0) * male, frame))
        need = max(need, barb_lift_needed(h, dx))
    report("male slides in from the wire end clear of the channel", worst < 1e-6, f"{worst:.3f} mm^3")
    held = ivol(Pos(-0.5, 0, 0) * male_seated(h), fh)
    report("barb stands behind the seated male", held > 0.5 and ivol(male, fh) < 1e-6,
           f"{held:.2f} mm^3 in the way 0.5 mm back")
    s = make_shrink(XT, -XT.male_len, -1)
    gap = fh.distance_to(s[0] + s[1])
    report("barb clears the male's heat-shrink by >= 0.5 mm", gap >= 0.5, f"{gap:.2f} mm")
    L = finger_len(b)
    bend = cantilever(L, b.finger_t, b.finger_w, need)
    report("finger strain on the way in <= 1 %", bend["strain"] <= 0.01,
           f"lift {need:.2f} mm over {L:.1f} mm: {100 * bend['strain']:.2f} %, {bend['force']:.1f} N")
    v = ivol(fh, frame)
    report("finger free of the channel", v < 1e-6, f"{v:.3f} mm^3")
    return ok


def render(b: BlockDims, block: Part) -> None:
    import numpy as np

    import xt60_twin as tw
    from xt60 import make_female, make_male
    tw.LOOKS.setdefault("fuse", ("#d9cfa8", 0.5, 0.0))
    h = b.holder
    seat = Pos(h.x_rim, 0, h.z_plug)
    sm, sf = make_shrink(XT, -XT.male_len, -1), make_shrink(XT, XT.female_body_len, +1)
    m = tw.mesh_of
    statics = [("block", m(block, 0.02), "holder"),
               ("switch", m(place_switch(b, make_kcd1(b.w.sw, clips=True)), 0.02), "switch"),
               ("fuse", m(make_fuse(b), 0.02), "fuse"),
               ("male", m(to_block(b, seat * make_male(XT)), 0.02), "xt60"),
               ("female", m(to_block(b, seat * make_female(XT)), 0.02), "amber"),
               ("shrink", m(to_block(b, seat * (sm[0] + sm[1] + sf[0] + sf[1])), 0.02), "shrink")]
    bb = block.bounding_box()
    t = np.array([(bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2 - 4, 10.0])

    def ortho(name, direction, width):
        v = np.array(direction, float)
        v /= np.linalg.norm(v)
        return (name, t + 600 * v, t, 50.0, width)

    cams = [ortho("front", (1.0, -0.8, 0.8), 70.0), ortho("rear", (-1.0, -0.6, 0.7), 70.0),
            ortho("top", (0.0, -0.001, 1.0), 85.0)]
    fz = b.leg_top + b.fuse.length
    labels = {"front": [("Fuse on terminal 1", (0.80, 0.10), [(b.fuse_x0 + 5.5, b.fuse_y, fz)]),
                        ("Switch", (0.45, 0.07), [(0, 0, b.panel_z + 4)]),
                        ("Pack's female", (0.15, 0.85), [(-8.5 - h.z_top / 2, -b.w.half_x - 4, b.T + 18)])],
              "rear": [("Latch finger", (0.25, 0.12), [(-b.w.half_y - h.z_top - 1.1, -b.w.half_x + 20, b.T + 14)]),
                       ("Male, upright, V end down", (0.70, 0.08), [(-8.5 - h.z_top, -b.w.half_x + 9, b.T + 11)])],
              "top": [("Fuse", (0.85, 0.20), [(b.fuse_x0 + 5.5, b.fuse_y, fz)]),
                      ("XT60 channel", (0.12, 0.30), [(-8.5 - h.z_top / 2, 0, b.T + 19)])]}
    tw.render_stills("power_block", tw.stage(statics, [], cams), cams, w=1000, labels=labels)


def main() -> None:
    b = BlockDims()
    block, fing = make_block(b)
    bb = block.bounding_box()
    print(f"power block: {bb.size.X:.1f} x {bb.size.Y:.1f} mm on the slab, {bb.max.Z - b.T:.1f} mm "
          f"tall above the plate; fuse over terminal 1 at Y {b.fuse_y:+g}")
    print("PASS/FAIL checks:")
    ok = checks(b, block, fing)
    export_stl(block, HERE / "power_block.stl")
    print(f"power_block.stl: {block.volume / 1000:.2f} cm^3")
    if "--no-render" not in sys.argv:
        render(b, block)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
