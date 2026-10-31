"""robot_car: the power block -- one printed block holding the power switch,
the harness's male XT60 and the fuse, so the pack's power goes XT60 ->
fuse -> switch inside a few centimetres.

ONE BLOCK

In plan the block is one rectangle and its top is one height all round:
the XT60's channel along the back, the switch's panel in the middle, and
in front a bay for the fuse, walled at the front and on the -Y side and
open on top, on the +Y side and across most of its front. The
height is set by the channel; the switch's panel comes up to meet it, so
the switch stands floor_gap higher than in the plate's own well, its
terminals that much further off the plate.

THE XT60

The male stands upright in a closed channel along the back, its V-shaped
(+) end down in the matching floor, its mating face flush with the
block's -Y end, where the pack's female plugs in from the battery side.
The channel is the male's outline grown by xt_fit on every face, with a
groove in the floor and the roof for the moulded + and - marks. Its roof
is a 45 deg peak, not flat: a flat roof is a bridge, and on the first
coupon it drooped onto the plug. The peak meets the male's top corners,
so it holds the male down.

There is no latch. The male goes in wires first from the mating end, its
heat-shrunk wires threaded out through a slot in the back wall, until its
rear face meets that wall. Plugging the pack in pushes the male against
the wall; pulling the pack's plug out is resisted by the snug fit, so hold
the block while unplugging.

THE FUSE

A low-profile mini blade fuse stands upright in the front bay, blades
down, right over terminal 1 -- the terminal the pack's + comes to, so
everything after it, the switch included, is behind the fuse. Its inner
blade rests on the terminal's bent-over leg, so a dot of solder joins
them; the outer blade stands 8 mm further out on a printed pedestal of
the same height, where the wire from the XT60 is soldered. Rails grip its
narrow edges and cover the blades' bare outer edges: the outer one is the
front wall, the inner ones run up into the switch's panel (the leg sweeps
through where a back would be, as the switch rolls in). The bay is open on
top and on the +Y side, beside the fuse's face, to solder the inner blade
to the terminal and to see the element. The front wall is only the fuse's
rail and a short return at the -Y corner; between them the front is open
from the plate up, to solder the switch's other two terminals and lead
their wires out.

Frame: the switch's centre at X = Y = 0, terminals toward +X, Z up from
the plate's underside (the coupon's slab is the plate).

Run with:  uv run robot_car/power_block.py [--no-render | fit-coupon]
(fit-coupon exports xt60_fit_coupon.stl: four short channel slices.)
Runs the PASS/FAIL checks, exports power_block.stl (print orientation:
as is), power_block.usdz (to turn round in Quick Look) and renders
power_block.png.
"""

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import Axis, Part, Pos, export_stl  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

from chassis import ChassisDims, ivol  # noqa: E402
from kcd1_rocker import make_kcd1  # noqa: E402
from switch_well import make_well, neighbour_sections, rbox, roll_in_check  # noqa: E402
from xt60 import Xt60Dims, make_female, make_male, make_shrink, outline, yz_prism  # noqa: E402

XT = Xt60Dims()


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
    # terminal 1, the pack's side, is the one at Y = fuse_y (the outer
    # terminals sit at Y = +-7, the switch's pitch)
    fuse_y: float = 7.0
    fuse_x: float = 10.4  # inner blade's centre, on the leg past the panel's edge
    fuse_fit: float = 0.1  # per side, in the rails
    rail_t: float = 1.6
    rail_lip: float = 1.3  # how far each rail's flanges reach over the fuse's face
    # XT60 upright, every face of the male's outline; negative is a press
    # fit: the fit coupons' H (8.00 x 15.60 for the 8.1 x 15.7 male) holds
    # it best, everything looser slid freely
    xt_fit: float = -0.05
    xt_wall: float = 1.6
    xt_floor: float = 1.2
    xt_skin: float = 1.2  # over the roof's peak
    mark_clear: float = 0.3
    mark_band: float = 2.4
    lead_in: float = 0.6
    sleeve_slot: float = 0.25  # round the heat-shrink, in the back wall
    wall_t: float = 1.6  # the fuse bay's side and front walls
    corner: float = 3.0  # the front wall's return at the -Y corner
    margin: float = 3.0  # coupon slab past the block

    @property
    def T(self) -> float:
        return self.car.plate_thickness

    @property
    def chan_in(self) -> float:  # channel's inner width, across the male
        return XT.height + 2 * self.xt_fit

    @property
    def H(self) -> float:  # block top above the plate top
        return self.xt_floor + XT.width + 2 * self.xt_fit + self.chan_in / 2 + self.xt_skin

    @property
    def w(self):
        """switch_well.py's well with its panel raised to the block's top."""
        w0 = self.car.well
        return replace(w0, floor_gap=self.H - w0.sw.lowest)

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

    @property
    def x_front(self) -> float:
        return self.fuse_x0 + self.fuse.width + self.fuse_fit + self.rail_t

    @property
    def x_back(self) -> float:
        return -self.w.half_y - self.chan_in - 2 * self.xt_wall

    @property
    def half_len(self) -> float:  # along Y
        return self.w.wall_in + self.w.wall_t

    @property
    def xt_x(self) -> float:  # channel's centre line
        return -self.w.half_y - self.xt_wall - self.chan_in / 2

    @property
    def xt_z(self) -> float:  # the male's width centre
        return self.T + self.xt_floor + self.xt_fit + XT.width / 2


def place_switch(b: BlockDims, part: Part) -> Part:
    """switch_well.py's frame -> the block's (chassis._switch_to_car at 0, 0)."""
    return Pos(0, 0, b.panel_z) * part.rotate(Axis.Z, -90)


def place_xt(b: BlockDims, part: Part) -> Part:
    """xt60.py's frame (rim at x = 0, male toward -X, width along Y with the
    chamfered end at -Y, height along Z) -> the block: upright, chamfered
    end down, mating face at the block's -Y end, male toward +Y."""
    up = part.rotate(Axis.X, 90).rotate(Axis.Z, -90)
    return Pos(b.xt_x + XT.height / 2, -b.half_len, b.xt_z) * up


def channel_cut(b: BlockDims) -> Part:
    """In xt60.py's frame: the male's outline grown by xt_fit, the roof
    peak over its square end, the mark grooves, the lead-in at the mouth
    and the back wall's slot for the heat-shrink."""
    f = b.xt_fit
    w, h = XT.width / 2, XT.height
    grown = outline(XT).buffer(f, join_style="mitre")
    peak = Polygon([(w + f, -f), (w + f + h / 2 + f, h / 2), (w + f, h + f)])
    sect = grown.union(peak)
    zc = XT.axis_z
    for s in (-1, 1):  # the + and - marks on both short ends
        y0 = s * (w + f)
        sect = sect.union(Polygon([(y0, zc - b.mark_band / 2), (y0 + s * (XT.mark_h + b.mark_clear), zc - b.mark_band / 2),
                                   (y0 + s * (XT.mark_h + b.mark_clear), zc + b.mark_band / 2), (y0, zc + b.mark_band / 2)]))
    rear = -XT.male_len
    cut = yz_prism(sect, rear, 1.0)
    for i in range(6):  # 45 deg lead-in at the mouth
        g = b.lead_in * (1 - i / 6)
        cut += yz_prism(sect.buffer(g, join_style="mitre"), -b.lead_in * (i + 1) / 6, 1.0)
    pitch, r = XT.pitch / 2, XT.shrink_d / 2 + b.sleeve_slot
    top = pitch + r  # the slot's top (upright), peaked like the roof
    slot = Polygon([(-top, zc - r), (top, zc - r), (top + r, zc), (top, zc + r), (-top, zc + r)])
    cut += yz_prism(slot, rear - 40, rear + 0.01)
    return cut


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


def fuse_bay(b: BlockDims) -> Part:
    """The bay's side and front walls, the rails and the outer blade's
    pedestal."""
    f, c, t, y = b.fuse, b.fuse_fit, b.rail_t, b.fuse_y
    x0, x1 = b.fuse_x0, b.fuse_x0 + f.width
    top, L = b.T + b.H, b.half_len
    half = f.thick / 2 + c
    xs = b.w.half_y - 0.01
    bay = rbox(x1 + c, b.x_front, -L, L, b.T - 0.01, top)  # front wall = outer rail's back
    # one side wall, on the -Y side: with the front wall it makes a corner,
    # and the +Y side, beside the fuse's face, stays open to solder through
    bay += rbox(xs, b.x_front, -L, -L + b.wall_t, b.T - 0.01, top)
    panel_bottom = b.panel_z - b.w.panel_t
    for s, xe in ((-1, x0), (1, x1)):
        z1 = top if s > 0 else panel_bottom + 0.01
        for sy in (-1, 1):
            bay += rbox(*sorted((xe + s * (c + t), xe - s * b.rail_lip)),
                        *sorted((y + sy * half, y + sy * (half + t))), b.T - 0.01, z1)
    bx = x0 + f.width / 2 + f.pitch / 2
    bay += rbox(bx - f.blade_w / 2 - 0.2, x1 + c + 0.01, y - half, y + half, b.T - 0.01, b.leg_top)
    # the front wall stays only as the fuse's rail and a short return at the
    # -Y corner: between them it's open from the plate up, to reach the
    # switch's other two terminals with an iron and to lead their wires out
    bay -= rbox(x1, b.x_front + 1, -L + b.wall_t + b.corner, y - half - t, b.T, top + 1)
    return bay


def block_body(b: BlockDims) -> Part:
    """The block on the plate's top face, without a plate: what the car's
    plate grows."""
    L, top = b.half_len, b.T + b.H
    chan = rbox(b.x_back, -b.w.half_y + 0.01, -L, L, b.T - 0.01, top)
    chan -= place_xt(b, channel_cut(b))
    return chan + place_switch(b, make_well(b.w)) + fuse_bay(b)


def make_block(b: BlockDims) -> Part:
    """The coupon: the block on a slab of plate."""
    L = b.half_len
    block = block_body(b)
    m = b.margin
    slab = rbox(b.x_back - m, b.x_front + m, -L - m, L + m, 0, b.T)
    return slab + block


def plugs(b: BlockDims) -> dict:
    sm = make_shrink(XT, -XT.male_len, -1)
    sf = make_shrink(XT, XT.female_body_len, +1)
    return {"male": place_xt(b, make_male(XT) + sm[0] + sm[1]),
            "female": place_xt(b, make_female(XT) + sf[0] + sf[1])}


def checks(b: BlockDims, block: Part) -> bool:
    ok = True

    def report(name, passed, detail=""):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  {detail}")

    sw = place_switch(b, make_kcd1(b.w.sw, clips=False))
    fuse = make_fuse(b)
    pl = plugs(b)
    bb = block.bounding_box()
    report("one solid", len(block.solids()) == 1, f"{len(block.solids())}")
    report("one height all round", abs(bb.max.Z - (b.T + b.H)) < 0.02,
           f"top {bb.max.Z - b.T:.2f} above the plate (switch panel {b.w.height:.2f})")
    v = ivol(block, sw)
    report("switch seats in its well", v < 0.5, f"{v:.3f} mm^3 (clips flex)")
    rolled, path = roll_in_check(b.w, neighbour_sections(b.w, (0.0, 0.0, b.panel_z), [block]))
    report("switch rolls in past the fuse rails", rolled, f"{len(path)} poses" if rolled else "no path")
    v = ivol(block, fuse)
    report("fuse stands in its rails", v < 1e-6, f"{v:.3f} mm^3")
    report("fuse's inner blade rests on terminal 1", fuse.distance_to(sw) < 0.05, f"{fuse.distance_to(sw):.2f} mm")
    mid = sw & rbox(0, 20, -1, 1, b.T, b.panel_z)
    report("fuse clears the middle terminal by >= 2.5 mm", fuse.distance_to(mid) >= 2.5,
           f"{fuse.distance_to(mid):.2f} mm")
    # a press fit overlaps the male by design: the male's checks run against
    # the channel at zero clearance, so all they see is the press
    b0 = replace(b, xt_fit=max(b.xt_fit, 0.0))
    nominal, male0 = make_block(b0), plugs(b0)["male"]
    if b.xt_fit < 0:
        print(f"         male pressed in {-b.xt_fit:g} mm per side")
    for name, part in pl.items():
        v = ivol(male0, nominal) if name == "male" else ivol(part, block)
        report(f"XT60 {name} clear of the block", v < 1e-6, f"{v:.3f} mm^3")
    # the male goes in wires first from the mating end
    worst = max(ivol(Pos(0, -dy, 0) * male0, nominal) for dy in range(0, 31))
    report("male slides in from the mating end", worst < 1e-6, f"{worst:.3f} mm^3 at worst over 30 mm")
    stop = ivol(Pos(0, 0.5, 0) * pl["male"], block)
    report("back wall stops the male 0 mm past seated", stop > 1.0, f"{stop:.1f} mm^3 in the way 0.5 mm further in")
    lift = 2 * max(b.xt_fit, 0.0) + 0.3  # past the play of the fit, top and bottom
    up = ivol(Pos(0, 0, lift) * place_xt(b, make_male(XT)), block)
    report("roof holds the male down", up > 0.5, f"{up:.1f} mm^3 in the way {lift:g} mm up")
    rim_y = place_xt(b, rbox(-0.01, 0.01, -1, 1, 1, 2)).bounding_box().center().Y
    report("male's rim flush with the block's end", abs(rim_y + b.half_len) < 0.02, f"{rim_y + b.half_len:+.2f} mm")
    return ok


def render(b: BlockDims, block: Part) -> None:
    import numpy as np

    import xt60_twin as tw
    tw.LOOKS.setdefault("fuse", ("#d9cfa8", 0.5, 0.0))
    tw.LOOKS["holder"] = ("#3fae4c", 0.6, 0.0)  # green PLA
    m = tw.mesh_of
    sm, sf = make_shrink(XT, -XT.male_len, -1), make_shrink(XT, XT.female_body_len, +1)
    statics = [("block", m(block, 0.02), "holder"),
               ("switch", m(place_switch(b, make_kcd1(b.w.sw, clips=True)), 0.02), "switch"),
               ("fuse", m(make_fuse(b), 0.02), "fuse"),
               ("male", m(place_xt(b, make_male(XT)), 0.02), "xt60"),
               ("female", m(place_xt(b, make_female(XT)), 0.02), "amber"),
               ("shrink", m(place_xt(b, sm[0] + sm[1] + sf[0] + sf[1]), 0.02), "shrink")]
    tw.write_usdz(tw.stage(statics, [], []), HERE / "power_block.usdz")
    bb = block.bounding_box()
    t = np.array([(bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2 - 4, 12.0])

    def ortho(name, direction, width):
        v = np.array(direction, float)
        v /= np.linalg.norm(v)
        return (name, t + 600 * v, t, 50.0, width)

    cams = [ortho("front", (1.0, -0.3, 0.6), 72.0), ortho("rear", (-1.0, -0.7, 0.75), 72.0),
            ortho("open_side", (0.7, 1.0, 0.75), 72.0), ortho("top", (0.0, -0.001, 1.0), 80.0)]
    fz = b.leg_top + b.fuse.length
    labels = {"front": [("Fuse on terminal 1", (0.82, 0.10), [(b.fuse_x0 + 5.5, b.fuse_y, fz)]),
                        ("Open front: terminals 2 and 3", (0.30, 0.92), [(b.fuse_x0 + 2, -4.0, b.leg_top)]),
                        ("Switch", (0.45, 0.06), [(0, 0, b.panel_z + 4)]),
                        ("Pack's female", (0.12, 0.85), [(b.xt_x, -b.half_len - 4, b.xt_z)])],
              "rear": [("Male, upright, V end down", (0.70, 0.08), [(b.xt_x, -b.half_len, b.xt_z + 6)]),
                       ("Wires out the back", (0.25, 0.10), [(b.xt_x, b.half_len + 2, b.xt_z)])],
              "open_side": [("Open side: solder the blade to terminal 1", (0.45, 0.07),
                             [(b.fuse_x, b.fuse_y + b.fuse.thick / 2, b.leg_top + 1)]),
                            ("Corner wall", (0.85, 0.85), [(b.x_front, -b.half_len + 4, b.T + b.H - 4)])],
              "top": [("Fuse bay", (0.85, 0.2), [(b.fuse_x0 + 5.5, b.fuse_y, fz)]),
                      ("XT60 channel", (0.12, 0.3), [(b.xt_x, 0, b.T + b.H)])]}
    tw.render_stills("power_block", tw.stage(statics, [], cams), cams, w=1000, labels=labels)


# ---- XT60 fit coupon --------------------------------------------------------
# Upright, 0.15 per side (8.40 across the male, coupon 1, flat roof) was too
# tight, 0.25 (8.60) slid freely and 0.20 (8.50) is still loose. Four short
# slices of the channel, mouth and all, open at both ends, lettered. Round 1
# (green, 2026-10-31) at 0.10-0.175 (A-D): all slide freely, A the
# tightest; the male calipered at 15.7 x 8.1 again. Round 2 (green,
# 2026-10-31), zero clearance and a press fit: H (-0.05) feels best, and
# it is BlockDims.xt_fit.
FIT_COUPON = (("E", 0.05), ("F", 0.025), ("G", 0.0), ("H", -0.05))
SLICE = 6.0  # along the male


def fit_coupon() -> Part:
    from spindle_coupons import raised
    plate, pitch = Part(), 20.0
    for i, (letter, fit) in enumerate(FIT_COUPON):
        b = replace(BlockDims(), xt_fit=fit)
        L = b.half_len
        piece = rbox(b.x_back, -b.w.half_y, -L, -L + SLICE, b.T - 0.01, b.T + b.H)
        piece -= place_xt(b, channel_cut(b))
        x0 = (b.x_back - b.w.half_y) / 2
        piece = Pos(i * pitch - x0, L, 0) * piece
        plate += piece + raised(letter, 6.0, i * pitch, SLICE + 5.0, b.T)
    bb = plate.bounding_box()
    slab = rbox(bb.min.X - 3, bb.max.X + 3, -3, bb.max.Y + 3, 0, BlockDims().T)
    return slab + plate


def main() -> None:
    if "fit-coupon" in sys.argv:
        part = fit_coupon()
        bb = part.bounding_box()
        print("XT60 fit coupon: " + ", ".join(
            f"{k} {XT.height + 2 * f:.2f} x {XT.width + 2 * f:.2f}" for k, f in FIT_COUPON)
            + f" mm; {bb.size.X:.0f} x {bb.size.Y:.0f} mm, {len(part.solids())} solid")
        export_stl(part, HERE / "xt60_fit_coupon.stl")
        print("Exported xt60_fit_coupon.stl")
        return
    b = BlockDims()
    block = make_block(b)
    bb = block.bounding_box()
    print(f"power block: {b.x_front - b.x_back:.1f} x {2 * b.half_len:.1f} x {b.H:.1f} mm above the plate; "
          f"XT60 fit {b.xt_fit:g} per side; switch panel {b.w.height:.1f} up (floor gap {b.w.floor_gap:.1f})")
    print("PASS/FAIL checks:")
    ok = checks(b, block)
    export_stl(block, HERE / "power_block.stl")
    print(f"power_block.stl: {block.volume / 1000:.2f} cm^3, slab {bb.size.X:.1f} x {bb.size.Y:.1f}")
    if "--no-render" not in sys.argv:
        render(b, block)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
