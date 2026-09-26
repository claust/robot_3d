"""robot_car: coupon for the PROTO-03 motor mount -- a slide-on locking lid.

PROTO-02's cradle holds the N20 with two retention lips on flexing fingers;
in use the motors pop out too easily. This coupon tries the alternative the
user sketched: the cradle keeps its rigid U-channel but carries a heavy
DOVETAIL RAIL along the outside of each wall, and a separate LID slides on
from the inboard side toward the wheel, its two skirts hooking under the
rails. The lid's ceiling has a centre pad that lands on the motor's top
(gearbox top and can crown are both 12 mm above the plate) with a small
PRELOAD, so the motor is clamped down rather than merely fenced in. The
lid stops against the end wall at the plate edge, is removable by sliding
it back inboard, and ends 1 mm before the can's rear face so the two solder
tabs and their wires stay completely free.

Fit is the whole question, so the coupon is one base plus lids that vary
the fit, printed in rounds (the variant lists near the bottom, ROUND1 and
VARIANTS, carry the exact values and each round's result):

    round 1  base + lids A-D   rail clearance 0.1-0.3, preload 0.1-0.3
             -> A (0.10 rail) fit best, motor still a bit wobbly
    round 2  lids E-G only     rail clearance 0.10, preload 0.3 / 0.4 / 0.5
             -> E fits nicely; F and G too tight to slide on

Design values carried forward: rail_clearance 0.10, pad_preload 0.30.

Rail clearance is the gap on every mating face of the dovetail; preload is
how far the pad's underside sits below the motor's top, i.e. how much the
2 mm ceiling has to bow to seat. Each lid is engraved with its letter on the
pad face (its printed top). Everything prints support-free: the rails' undersides
and the hooks' upper faces are the same 45 deg dovetail flank, and the lids
print upside down (ceiling on the bed).

A detent holds the seated lid against creeping back inboard: a small tip
on the inside of each skirt, right at the lid's inboard end, rides along
the rail's outer face during the slide (the skirt springs out by the
0.15 mm interference) and snaps into a matching recess in the rail as the
lid meets the end wall. Both ends of the tip ramp at 45 deg, so it clicks
in and a firm pull clicks it back out. The skirt is short and stiff, so a
beam estimate says ~3 % strain -- pessimistic, since only the free corner
of a 23 mm plate is loaded, but this IS the thing the coupon has to prove.

Run with:  uv run robot_car/lid_coupons.py
Exports lid_coupons.stl/.step (the print plate: the current round's lids,
plus the base when PRINT_BASE is set), writes
lid_coupons.png (section + isometric), and runs the PASS/FAIL checks.
"""

import sys
from dataclasses import dataclass, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "parts"))

import numpy as np  # noqa: E402
from build123d import (  # noqa: E402
    Align,
    Axis,
    Box,
    Part,
    Plane,
    Polyline,
    Pos,
    Text,
    chamfer,
    export_step,
    export_stl,
    extrude,
    make_face,
    mirror,
)

from n20_motor import N20Dims, make_motor  # noqa: E402

N20 = N20Dims()
FONT = "Arial Black"
MIN_STROKE = 0.8  # two nozzle widths -- thinner engraves illegibly


@dataclass
class LidDims:
    # ---- coupon base -----------------------------------------------------
    plate_t: float = 3.0
    base_x: float = 34.0
    base_inboard: float = 11.0  # base extends this far inboard of the channel
    # ---- cradle (same channel as chassis.py's motor_cradle) ------------
    channel_clearance: float = 0.2  # radial, around the 10 mm can flats
    wall_t: float = 3.0
    wall_top_gap: float = 0.2  # wall top sits this much above the motor top
    tail_exposed: float = 1.0  # can left bare inboard: tabs + wires live there
    endwall_t: float = 2.0
    endwall_slot_w: float = 4.5  # clears the Ø4 boss, open at the top
    # ---- dovetail rail on the OUTSIDE of each wall ----------------------
    rail_out: float = 1.5  # how far it stands proud of the wall
    rail_land: float = 0.6  # vertical land at its outer edge; below that, 45 deg
    rail_lead_in: float = 1.0  # chamfer at the inboard end
    # ---- lid -------------------------------------------------------------
    rail_clearance: float = 0.2  # on every dovetail face (varies per lid)
    ceiling_t: float = 2.0
    skirt_t: float = 2.0
    hook_t: float = 1.5  # the hook's flat-bottomed root under the 45 deg flank
    pad_half_w: float = 4.5  # pad sits between the walls, 0.6 mm from each
    pad_preload: float = 0.1  # pad underside BELOW the motor top (varies per lid)
    lid_lead_in: float = 0.8  # chamfer on the hooks' inboard end
    # ---- detent: a small tip on the inside of each skirt, right at the
    # lid's inboard end, that rides along the rail's outer face and snaps
    # into a matching recess as the lid meets the end wall. The skirt is
    # the spring; the tip carries 45 deg ramps both ways so it clicks in
    # and a firm pull clicks it out.
    tip_len: float = 1.5  # along Y, flat part
    tip_y: float = 1.0  # tip's inboard edge from the lid's inboard end
    tip_interference: float = 0.15  # tip height beyond the rail clearance
    recess_clearance: float = 0.1
    label: str = "B"
    label_size: float = 5.0
    label_depth: float = 0.5

    # ---- derived ---------------------------------------------------------
    @property
    def gap(self) -> float:
        return N20.gearbox_width + self.channel_clearance

    @property
    def W(self) -> float:  # wall outer half-width
        return self.gap / 2 + self.wall_t

    @property
    def motor_top(self) -> float:
        return self.plate_t + N20.gearbox_height

    @property
    def axis_z(self) -> float:
        return self.plate_t + N20.gearbox_height / 2

    @property
    def T(self) -> float:  # wall top
        return self.motor_top + self.wall_top_gap

    @property
    def channel_run(self) -> float:
        return self.endwall_t + N20.gearbox_length + N20.can_length - self.tail_exposed

    @property
    def edge_y(self) -> float:  # plate edge, wheel side
        return self.channel_run

    @property
    def face_y(self) -> float:  # gearbox front face / end wall inner face
        return self.edge_y - self.endwall_t

    @property
    def lid_len(self) -> float:
        return self.face_y  # lid runs y = 0 .. face_y

    @property
    def rail_h(self) -> float:
        return self.rail_land + self.rail_out

    @property
    def skirt_x0(self) -> float:  # skirt inner face
        return self.W + self.rail_out + self.rail_clearance

    @property
    def lid_half_w(self) -> float:
        return self.skirt_x0 + self.skirt_t

    @property
    def hook_top_z(self) -> float:
        """Hook top at the tip (x = W + c): rail underside there is T - rail_h,
        pushed down by c*sqrt2 so a 45 deg flank keeps c clearance."""
        return self.T - self.rail_h - self.rail_clearance * 2 ** 0.5 + self.rail_clearance

    @property
    def hook_bottom_z(self) -> float:
        return self.hook_top_z - self.hook_t

    @property
    def horizontal_engagement(self) -> float:
        return self.rail_out - self.rail_clearance

    @property
    def pad_lead_in(self) -> float:
        """45 deg chamfer on the pad's leading (wheel-end) bottom edge. The
        lid slides on from inboard, so the pad's front meets the rear rim of
        the can first; without a ramp, preload above ~0.1 hits it head-on.
        It spans the pad's whole height bar 0.05, so its top ends above the
        motor top by the wall-top gap plus the rail clearance."""
        return (self.T + self.rail_clearance) - (self.motor_top - self.pad_preload) - 0.05

    @property
    def tip_h(self) -> float:  # tip stands this far off the skirt's inner face
        return self.rail_clearance + self.tip_interference

    @property
    def skirt_free_h(self) -> float:  # ceiling underside down to the hook bottom
        return self.T + self.rail_clearance - self.hook_bottom_z

    @property
    def skirt_strain_bound(self) -> float:
        """Beam upper bound (%) on the skirt's strain as the tip rides the
        rail. Pessimistic: only the skirt's free corner is loaded, and a
        23 mm plate corner is far softer than a beam of its height."""
        return 100 * 3 * self.skirt_t * self.tip_interference / (2 * self.skirt_free_h ** 2)


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def ivol(a: Part, b: Part) -> float:
    i = a & b
    return i.volume if i is not None and i.volume else 0.0


def xz_prism(points, y0, y1) -> Part:
    """Extrude a closed XZ polygon along Y from y0 to y1."""
    face = make_face(Polyline(*[(x, 0, z) for x, z in points], close=True))
    face = Plane.XZ * face if False else face  # points already carry z
    prism = extrude(face, amount=y1 - y0, dir=(0, 1, 0))
    return Pos(0, y0, 0) * prism


def yz_prism(points, x0, x1) -> Part:
    """Extrude a closed YZ polygon along X from x0 to x1."""
    face = make_face(Polyline(*[(0, y, z) for y, z in points], close=True))
    prism = extrude(face, amount=abs(x1 - x0), dir=(1, 0, 0))
    return Pos(min(x0, x1), 0, 0) * prism


def xy_prism(points, z0, z1) -> Part:
    """Extrude a closed XY polygon along Z from z0 to z1."""
    face = make_face(Polyline(*[(x, y, 0) for x, y in points], close=True))
    return Pos(0, 0, z0) * extrude(face, amount=z1 - z0)


def tip_prism(d: LidDims, sgn: int) -> Part:
    """The snap tip on the +X (sgn=+1) or -X skirt: a ridge on the skirt's
    inner face reaching `tip_h` toward the rail, 45 deg ramps at both Y
    ends, spanning the skirt face from the hook flank up to the ceiling."""
    h, y0 = d.tip_h, d.tip_y
    x_face = sgn * d.skirt_x0
    x_in = x_face - sgn * h
    pts = [(x_face, y0 - h), (x_in, y0), (x_in, y0 + d.tip_len), (x_face, y0 + d.tip_len + h)]
    z0 = d.hook_top_z + d.rail_out - 0.01  # where the flank meets the skirt face
    z1 = d.T + d.rail_clearance + 0.01
    return xy_prism(pts, z0, z1)


def recess(d: LidDims, sgn: int) -> Part:
    """Recess for the tip, cut into the outer face of the +X / -X rail."""
    depth = d.tip_h + d.recess_clearance
    y0 = d.tip_y - d.recess_clearance
    y1 = d.tip_y + d.tip_len + d.recess_clearance
    x_face = sgn * (d.W + d.rail_out)
    x_in = x_face - sgn * depth
    x_out = x_face + sgn * 0.5
    pts = [(x_out, y0 - depth - 0.5), (x_in, y0), (x_in, y1), (x_out, y1 + depth + 0.5)]
    return xy_prism(pts, d.T - d.rail_h - 0.5, d.T + 0.5)


def rail_profile(d: LidDims):
    """Right-hand rail section (XZ), left is mirrored."""
    W, T = d.W, d.T
    return [
        (W, T),
        (W + d.rail_out, T),
        (W + d.rail_out, T - d.rail_land),
        (W, T - d.rail_h),
    ]


def hook_profile(d: LidDims):
    """Right-hand skirt + hook section (XZ), ceiling excluded."""
    c = d.rail_clearance
    x_tip = d.W + c
    x_s = d.skirt_x0
    z_tip = d.hook_top_z
    z_root = z_tip + (x_s - x_tip)  # the 45 deg flank, continued to the skirt
    z_bot = d.hook_bottom_z
    return [
        (x_tip, z_tip),
        (x_s, z_root),
        (x_s, d.T + c),  # ceiling underside
        (d.lid_half_w, d.T + c),
        (d.lid_half_w, z_bot),
        (x_tip, z_bot),
    ]


def make_base(d: LidDims) -> Part:
    plate_top = d.plate_t
    y0, y1 = -d.base_inboard, d.edge_y
    base = rbox(-d.base_x / 2, d.base_x / 2, y0, y1, 0, plate_top)

    # channel walls
    for sgn in (-1, 1):
        base += rbox(*sorted((sgn * d.gap / 2, sgn * d.W)), 0, d.edge_y,
                     plate_top, d.T)
        # dovetail rail along the outside, lead-in chamfer at the inboard end
        rail = xz_prism(rail_profile(d), 0, d.edge_y)
        inboard_edges = rail.faces().sort_by(Axis.Y)[0].edges()
        rail = chamfer(inboard_edges.filter_by(Axis.X), d.rail_lead_in)
        if sgn < 0:
            rail = mirror(rail, Plane.YZ)
        base += rail

    # detent recess in each rail's outer face, where the tip lands seated
    for sgn in (-1, 1):
        base -= recess(d, sgn)

    # end wall: as wide as the lid, tall enough to stop its ceiling
    ew = rbox(-d.lid_half_w, d.lid_half_w, d.face_y, d.edge_y,
              plate_top, d.T + d.ceiling_t)
    slot_z0 = d.axis_z - N20.boss_diameter / 2 - 1.0
    ew -= rbox(-d.endwall_slot_w / 2, d.endwall_slot_w / 2,
               d.face_y - 0.1, d.edge_y + 0.1, slot_z0, d.T + d.ceiling_t + 1)
    base += ew

    # identity, raised on the plate beside the channel
    txt = label_face("O2 LID", 5.0)
    bb = txt.bounding_box()
    txt = Pos(-bb.center().X, -bb.center().Y) * txt
    txt = txt.rotate(Axis.Z, 90)
    base += Pos(-d.lid_half_w - 3.2, 8, plate_top) * extrude(txt, amount=0.6)
    return base


def label_face(text: str, size: float):
    face = Text(text, font_size=size, font=FONT)
    area = sum(f.area for f in face.faces())
    perimeter = sum(e.length for e in face.edges())
    stroke = 2 * area / perimeter
    if stroke < MIN_STROKE:
        raise ValueError(f"label {text!r}: ~{stroke:.2f} mm strokes < {MIN_STROKE}")
    return face


def make_lid(d: LidDims) -> Part:
    """Lid in its INSTALLED position over the base's channel."""
    c = d.rail_clearance
    y0, y1 = 0.0, d.lid_len
    lid = rbox(-d.lid_half_w, d.lid_half_w, y0, y1, d.T + c, d.T + c + d.ceiling_t)
    # preload pad between the walls, lead-in ramp on its leading bottom edge
    pad = rbox(-d.pad_half_w, d.pad_half_w, y0, y1,
               d.motor_top - d.pad_preload, d.T + c + 0.01)
    lead = pad.edges().group_by(Axis.Z)[0].sort_by(Axis.Y)[-1]
    lid += chamfer(lead, d.pad_lead_in)
    for sgn in (-1, 1):
        hook = xz_prism(hook_profile(d), y0, y1)
        inboard = hook.faces().sort_by(Axis.Y)[0].edges()
        # lead-in on the hook's flank and tip at the inboard end
        hook = chamfer(inboard.filter_by(Axis.X), min(d.lid_lead_in, d.hook_t * 0.5))
        if sgn < 0:
            hook = mirror(hook, Plane.YZ)
        lid += hook
    for sgn in (-1, 1):
        lid += tip_prism(d, sgn)
    # letter engraved into the pad face (the lid's printed top)
    txt = label_face(d.label, d.label_size)
    bb = txt.bounding_box()
    txt = Pos(-bb.center().X, -bb.center().Y) * txt
    txt = mirror(txt, Plane.YZ)  # reads correctly looking up at the pad
    cut = extrude(txt, amount=d.label_depth)
    lid -= Pos(0, d.lid_len / 2, d.motor_top - d.pad_preload) * cut
    return lid


def tips(d: LidDims) -> Part:
    return tip_prism(d, -1) + tip_prism(d, +1)


def lid_for_print(lid: Part, d: LidDims) -> Part:
    """Flip the lid ceiling-down onto z=0."""
    flipped = lid.rotate(Axis.Y, 180)
    z0 = flipped.bounding_box().min.Z
    return Pos(0, 0, -z0) * flipped


def motor_placement(d: LidDims) -> Part:
    m = make_motor(N20).rotate(Axis.X, 90)  # body along -Y, tall axis up
    return Pos(0, d.face_y, d.axis_z) * m


# Round 1 (printed 2026-09-05 in black with the base): A fitted best, but
# the motor was still a bit wobbly under its 0.1 mm preload.
ROUND1 = [
    LidDims(label="A", rail_clearance=0.10, pad_preload=0.10),
    LidDims(label="B", rail_clearance=0.20, pad_preload=0.10),
    LidDims(label="C", rail_clearance=0.30, pad_preload=0.10),
    LidDims(label="D", rail_clearance=0.20, pad_preload=0.30),
]

# Round 2 (printed 2026-09-26 in black, lids only -- the round-1 base is
# reused): A's rail fit, harder clamp. New letters so they can't be mixed
# up with round 1 on the bench. RESULT: E fits nicely and holds the motor;
# F and G are too tight to slide on at all. So the design values are
# rail_clearance 0.10 and pad_preload 0.30 -- lid E.
VARIANTS = [
    LidDims(label="E", rail_clearance=0.10, pad_preload=0.30),
    LidDims(label="F", rail_clearance=0.10, pad_preload=0.40),
    LidDims(label="G", rail_clearance=0.10, pad_preload=0.50),
]
PRINT_BASE = False


def checks(base: Part, motor: Part, lids: list[tuple[LidDims, Part]]) -> bool:
    ok = True

    def report(name, passed, detail=""):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  {detail}")

    d0 = VARIANTS[0]
    report("motor clear of cradle", ivol(motor, base) < 1e-6,
           f"{ivol(motor, base):.3f} mm^3")
    # terminals: rear face + reach must be inboard of the lid
    rear_y = d0.face_y - N20.gearbox_length - N20.can_length
    report("solder tabs inboard of the lid",
           rear_y < 0 and rear_y - N20.terminal_reach < 0,
           f"rear face y={rear_y:+.1f}, tab tips y={rear_y - N20.terminal_reach:+.1f}, lid ends y=0")
    for d, lid in lids:
        pad = rbox(-d.pad_half_w, d.pad_half_w, 0, d.lid_len,
                   d.motor_top - d.pad_preload, d.motor_top + 0.5)
        v_base = ivol(lid, base)
        report(f"lid {d.label} clear of cradle (seated)", v_base < 1e-6, f"{v_base:.3f} mm^3")
        body = lid - tips(d)
        for dy in (-3.0, -12.0, -22.0):
            v = ivol(Pos(0, dy, 0) * body, base)
            report(f"lid {d.label} clear of cradle at y{dy:+.0f} (sliding on, tips aside)",
                   v < 1e-6, f"{v:.3f} mm^3")
        # the tips only meet the rails in the last 2.5 mm of travel: there they must
        # bite the rail by the interference and touch nothing else
        ride = Pos(0, -1.5, 0) * tips(d)  # tip over the rail, short of the recess
        rails = Part()
        for sgn in (-1, 1):
            rails += rbox(*sorted((sgn * (d.W + d.rail_out - 1), sgn * (d.W + d.rail_out))),
                          0, d.face_y, d.T - d.rail_h - 0.5, d.T + 0.5)
        v_tip = ivol(ride, base)
        v_elsewhere = ivol(ride - rails, base)
        report(f"lid {d.label} tips ride only on the rails",
               v_tip > 0 and v_elsewhere < 1e-6,
               f"{v_tip:.2f} mm^3 into the rail ({d.tip_interference:g} mm), {v_elsewhere:.3f} elsewhere")
        print(f"         skirt strain, beam upper bound: {d.skirt_strain_bound:.1f} % "
              f"({d.skirt_t:g} mm skirt, {d.skirt_free_h:.1f} mm free, corner-loaded so real is lower)")
        ramp_top = d.motor_top - d.pad_preload + d.pad_lead_in
        report(f"lid {d.label} pad lead-in tops out above the motor",
               ramp_top > d.motor_top + 0.1,
               f"{d.pad_lead_in:.2f} mm ramp, top {ramp_top - d.motor_top:+.2f} mm vs motor top")
        # sliding on over the motor: the can rim must meet the ramp, never
        # the pad's square front or anything else on the lid
        rear_y = d.face_y - N20.gearbox_length - N20.can_length
        worst = 0.0
        for into in (0.3, 0.6, 0.9):
            dy = rear_y + into - d.lid_len
            hit = (Pos(0, dy, 0) * lid) & motor
            if hit is not None and hit.volume > 1e-6:
                worst = max(worst, hit.bounding_box().max.Z)
        report(f"lid {d.label} meets the can rim on the ramp",
               worst <= ramp_top + 1e-3,
               f"contact up to z={worst:.2f}, ramp top z={ramp_top:.2f}")
        # ceiling bow: pessimistic fixed-fixed beam, point load, span between
        # the hook contacts. Real strain is lower -- the pad spreads the load
        # and the 45 deg flanks let the skirts splay -- but it ranks the lids.
        span = 2 * (d.W + d.rail_out / 2)
        bow = max(d.pad_preload - d.rail_clearance * (2 ** 0.5 - 1), 0)
        print(f"         ceiling bow ~{bow:.2f} mm over {span:.1f} mm span: "
              f"<= {100 * 12 * bow * d.ceiling_t / span ** 2:.1f} % strain (upper bound)")
        report(f"lid {d.label} hook engagement >= 1.0 mm",
               d.horizontal_engagement >= 1.0,
               f"{d.horizontal_engagement:.2f} mm under the rail, {d.hook_t:.1f} mm hook root")
    return ok


def render(base: Part, motor: Part, lids, plate: Part, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(15, 5.2))
    d = VARIANTS[-1]

    # -- section (XZ) through the can, lid B seated
    ax = fig.add_subplot(1, 3, 1)
    ax.set_title(f"section through the can, lid {d.label} seated")
    W, T = d.W, d.T
    ax.add_patch(Polygon([(-17, 0), (17, 0), (17, d.plate_t), (-17, d.plate_t)], color="#5a6472"))
    for s in (-1, 1):
        ax.add_patch(Polygon([(s * d.gap / 2, d.plate_t), (s * W, d.plate_t), (s * W, T), (s * d.gap / 2, T)], color="#5a6472"))
        ax.add_patch(Polygon([(s * x, z) for x, z in rail_profile(d)], color="#3b4a5a"))
        ax.add_patch(Polygon([(s * x, z) for x, z in hook_profile(d)], color="#e07b39"))
    c = d.rail_clearance
    ax.add_patch(Polygon([(-d.lid_half_w, T + c), (d.lid_half_w, T + c), (d.lid_half_w, T + c + d.ceiling_t), (-d.lid_half_w, T + c + d.ceiling_t)], color="#e07b39"))
    ax.add_patch(Polygon([(-d.pad_half_w, d.motor_top - d.pad_preload), (d.pad_half_w, d.motor_top - d.pad_preload), (d.pad_half_w, T + c), (-d.pad_half_w, T + c)], color="#c9652a"))
    # the can: Ø12 with 10 mm flats
    th = np.linspace(0, 2 * np.pi, 200)
    cx, cz = 6 * np.cos(th), d.axis_z + 6 * np.sin(th)
    cx = np.clip(cx, -5, 5)
    ax.add_patch(Polygon(list(zip(cx, cz)), color="#9aa5b1", alpha=0.9))
    ax.set_xlim(-17, 17); ax.set_ylim(-1, 19); ax.set_aspect("equal")
    ax.set_xlabel("X mm"); ax.set_ylabel("Z mm")
    ax.annotate(f"rail {d.rail_out:g} out, 45° under", (W + 1.6, T - 0.3), fontsize=8)
    ax.annotate(f"pad preload {d.pad_preload:g}", (-4.3, d.motor_top + 0.35), fontsize=8)

    def add_mesh(ax3, part, color, alpha=1.0):
        import tempfile, trimesh
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=True) as f:
            export_stl(part, f.name)
            m = trimesh.load(f.name)
        tri = m.vertices[m.faces]
        coll = Poly3DCollection(tri, alpha=alpha, facecolor=color, edgecolor="none")
        ax3.add_collection3d(coll)
        return m.bounds

    def frame(ax3, bounds_list):
        lo = np.min([b[0] for b in bounds_list], axis=0); hi = np.max([b[1] for b in bounds_list], axis=0)
        ctr = (lo + hi) / 2; r = (hi - lo).max() / 2
        ax3.set_xlim(ctr[0] - r, ctr[0] + r); ax3.set_ylim(ctr[1] - r, ctr[1] + r); ax3.set_zlim(ctr[2] - r, ctr[2] + r)
        ax3.set_box_aspect((1, 1, 1))

    ax3 = fig.add_subplot(1, 3, 2, projection="3d")
    ax3.set_title(f"coupon assembled: base, N20, lid {VARIANTS[-1].label} (half on)")
    b = [add_mesh(ax3, base, "#5a6472"), add_mesh(ax3, motor, "#9aa5b1"),
         add_mesh(ax3, Pos(0, -9, 0) * lids[-1][1], "#e07b39", 0.85)]
    frame(ax3, b); ax3.view_init(elev=28, azim=-50)

    ax4 = fig.add_subplot(1, 3, 3, projection="3d")
    ax4.set_title("print plate: lids " + ", ".join(v.label for v in VARIANTS) + " upside down")
    frame(ax4, [add_mesh(ax4, plate, "#5a6472")]); ax4.view_init(elev=45, azim=-60)

    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(f"Wrote {out.name}")


def main() -> None:
    d0 = VARIANTS[0]
    base = make_base(d0)
    motor = motor_placement(d0)
    lids = [(d, make_lid(d)) for d in VARIANTS]

    print("PASS/FAIL checks:")
    ok = checks(base, motor, lids)

    # print plate: base at the origin, lids in a row alongside (+X)
    pitch = 2 * d0.lid_half_w + 6
    plate = base if PRINT_BASE else Part()
    x0 = d0.base_x / 2 + 6 + d0.lid_half_w if PRINT_BASE else 0.0
    for i, (d, lid) in enumerate(lids):
        plate += Pos(x0 + i * pitch, 0, 0) * lid_for_print(lid, d)

    export_stl(plate, HERE / "lid_coupons.stl")
    export_step(plate, HERE / "lid_coupons.step")
    bb = plate.bounding_box()
    print(f"Plate {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"{plate.volume / 1000:.1f} cm^3")
    for d in VARIANTS:
        print(f"  lid {d.label}: rail clearance {d.rail_clearance:.2f}, "
              f"preload {d.pad_preload:.2f}, hook {d.horizontal_engagement:.2f} mm under rail")
    render(base, motor, lids, plate, HERE / "lid_coupons.png")
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
