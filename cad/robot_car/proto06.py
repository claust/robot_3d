"""robot_car PROTO-06: four-wheel drive with the mower spindle in the middle.

The layout to discuss before chassis.py takes it over. It builds the plate
from chassis.py's own parts (motor cradles and lids, the tilt-and-slide
board trays, the switch well, the XT60 lid) and checks every pair on the
built geometry, the way chassis.py does.

+X is FRONT, +Y LEFT. The plate is centred on the origin, bottom face Z=0.

- Four N20s, one per corner, in chassis.py's cradles and slide-on lids at
  X = +-cradle_x, each driving an Ø80 lawn wheel (light_wheel.py). No
  caster. The rear-right lid is xt60_holder.py's, as on PROTO-05.
- The spindle tower is part of the plate: spindle_coupons.py's tower with
  the plate as its flange, so nothing has to hold it down and it prints
  the way the tested tower did, upright with the lower bearing seat
  opening at the bed. The lower bearing presses in from underneath, flush
  with the plate's underside, and the rotor goes in from below. Its disc
  turns 6 mm under the plate. The Canon stands on canon_mount.py's cap.
- Battery on the right of the tower, its lead out at the rear toward the
  XT60 lid. Its strap never goes under the plate, where it would run
  just above the spinning disc: it threads through two printed loops on
  the plate, one each side of the pack, and round the pack.
- Pi Zero 2 W on the left, long axis along X, connectors facing out.
- Front of the tower: the two MP1584 bucks. Behind it: the DRV8833, which
  drives all four motors (the two on a side in parallel on one channel),
  and the TB6612 for the Canon. The TB6612 carries its pin rows along its
  21 mm edges, so its tray grips the 18.3 mm edges instead, and a 10 uF
  capacitor sits right at one of those: the two tongues stand either side
  of it, so the board only goes in one way round. Power switch at the
  rear edge, terminals forward.

Run with `tb-coupon` to export the TB6612's tray alone, on a small base,
as tb_tray_coupon.stl.

Run with:  uv run robot_car/proto06.py [tb-coupon]
Runs the PASS/FAIL checks, exports proto06_chassis.stl (gitignored) and
renders proto06.png: from above, and from the front left.
"""

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import (  # noqa: E402
    Align, Axis, Box, Cylinder, Part, Pos, Rectangle, export_stl, extrude, fillet,
)

import chassis as ch  # noqa: E402
from chassis import ChassisDims, header_tray, ivol, rbox  # noqa: E402
from canon_mount import MountDims, canon, make_cap, make_hub, make_long_pin  # noqa: E402
from spindle_coupons import bearings, make_rotor, make_washer, tower_bore  # noqa: E402

ALIGN_BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass
class P6Dims:
    """All dimensions in mm. The fits, standoffs and part sizes come from
    ChassisDims (`car`); these are the PROTO-06 positions."""

    car: ChassisDims = field(default_factory=lambda: ChassisDims(plate_width=136.0))
    mount: MountDims = field(default_factory=MountDims)  # round 1's rotor and the Canon's cap
    plate_half_x: float = 77.0
    cradle_x: float = 62.0  # front cradles at +, rear at -
    wheel_gap: float = 1.0  # wheel's inner face to the plate edge

    # battery, right of the tower; strap loops each side
    battery_y_in: float = 28.2  # pack's inner long side, |Y|
    loop_opening: float = 23.0  # along X, for the 21 mm strap
    loop_gap: float = 4.0  # strap passage height above the plate
    loop_roof: float = 2.0
    loop_depth: float = 3.0  # along Y
    loop_post: float = 3.0

    pi_y: float = 41.5  # board centre; 26.5..56.5

    buck_x: float = 41.0
    buck_y: float = 11.85
    drv_x: float = -39.0
    drv_y: float = 11.65
    tb_x: float = -39.5
    tb_y: float = -13.4
    tb_board_x: float = 21.0  # pin rows along these edges (calipered)
    tb_board_y: float = 18.3  # calipered; the tray grips these
    # Tongues either side of the 10 uF tantalum cap at the board's edge
    # (from a photo: Y -0.85..+2.55 in the tray frame, 0.4 mm in from the
    # edge); the header rows start 6.65 out. Coupon (2026-10-18): the
    # tongues miss the cap, the board sits flat, the latch lets it out.
    tb_tongue_ys: tuple = (4.6, -3.75)
    # Corner walls as long as the bucks', so the ledges 3.2-4.7 mm in from
    # the pin-row edges stand against them, not alone as thin pillars.
    tb_corner_arm: float = 5.0
    switch_x: float = -66.0

    label_lines: tuple = ("DELECTOSOFT", "© 2026  PROTO-06")
    label_x: float = -50.0

    @property
    def spindle(self):
        return self.mount.spindle

    @property
    def half_y(self) -> float:
        return self.car.plate_width / 2

    @property
    def battery_yc(self) -> float:
        return -(self.battery_y_in + self.car.battery_wid / 2)


def at_cradle(p: P6Dims, x: float) -> ChassisDims:
    """chassis.py's dims with the cradle at x, for its placement helpers."""
    return replace(p.car, cradle_x=x)


def corners(p: P6Dims):
    """(name, x, side) for the four motors; side +1 is the left (+Y) edge."""
    return [("FL", p.cradle_x, +1), ("FR", p.cradle_x, -1),
            ("RL", -p.cradle_x, +1), ("RR", -p.cradle_x, -1)]


def plate(p: P6Dims) -> Part:
    c = p.car
    plan = fillet(Rectangle(2 * p.plate_half_x, c.plate_width).vertices(), c.corner_radius)
    return Part() + extrude(plan, amount=c.plate_thickness)


def footprint_prism(p: P6Dims) -> Part:
    c = p.car
    plan = fillet(Rectangle(2 * p.plate_half_x, c.plate_width).vertices(), c.corner_radius)
    return Pos(0, 0, -20) * extrude(plan, amount=200)


def tower_tube(p: P6Dims) -> Part:
    """The tower's tube on the plate; tower_bore cuts both seats through
    it and the plate. The spindle frame's Z=0, the seat's mouth, is the
    plate's underside, where the tested tower had its flange's."""
    s = p.spindle
    return Cylinder(s.tower_od / 2, s.span, align=ALIGN_BOTTOM)


def battery_nubs(p: P6Dims) -> Part:
    return Pos(0, p.battery_yc, 0) * ch.battery_nubs(replace(p.car, battery_x=0.0))


def strap_loops(p: P6Dims) -> Part:
    """A staple each side of the pack: two posts and a roof the strap runs
    under, on the plate's top face."""
    c = p.car
    z0 = c.plate_thickness
    w = c.battery_wid / 2 + c.nub_clearance
    loops = Part()
    for y_face, sgn in ((p.battery_yc + w, +1), (p.battery_yc - w, -1)):
        y0, y1 = sorted((y_face, y_face + sgn * p.loop_depth))
        half = p.loop_opening / 2
        for sx in (-1, 1):
            x0, x1 = sorted((sx * half, sx * (half + p.loop_post)))
            loops += rbox(x0, x1, y0, y1, z0, z0 + p.loop_gap + p.loop_roof)
        loops += rbox(-half - p.loop_post, half + p.loop_post, y0, y1,
                      z0 + p.loop_gap, z0 + p.loop_gap + p.loop_roof)
    return loops


def pi_bosses(p: P6Dims) -> Part:
    c = p.car
    z0 = c.plate_thickness
    out = Part()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * c.pi_hole_y / 2, p.pi_y + sy * c.pi_hole_x / 2
            boss = Pos(x, y, z0) * Cylinder(c.pi_boss_d / 2, c.pi_boss_h, align=ALIGN_BOTTOM)
            boss -= Pos(x, y, z0 + 1) * Cylinder(c.pi_pilot_d / 2, c.pi_boss_h, align=ALIGN_BOTTOM)
            out += boss
    return out


def pi_env(p: P6Dims) -> Part:
    c = p.car
    z = c.plate_thickness + c.pi_boss_h
    return rbox(-c.pi_board_y / 2, c.pi_board_y / 2, p.pi_y - c.pi_board_x / 2,
                p.pi_y + c.pi_board_x / 2, z, z + c.tray_board_t)


def place_tray(tray: Part, x: float, y: float, latch_side: int) -> Part:
    """header_tray's canonical frame (tongues +X, latch -X) -> the car, the
    board's ends along car X and the latch outboard on `latch_side`."""
    return Pos(x, y, 0) * tray.rotate(Axis.Z, -90 if latch_side > 0 else 90)


def buck_tray(p: P6Dims, side: int) -> Part:
    c = p.car
    tray = header_tray(c, c.buck_board_y, c.buck_board_x, c.buck_tongue_xs,
                       arm=c.buck_corner_arm, ledge_inset=c.buck_ledge_inset,
                       ledge_len=c.buck_ledge_len, end_fit=c.buck_end_fit)
    return place_tray(tray, p.buck_x, side * p.buck_y, side)


def drv_tray(p: P6Dims) -> Part:
    c = p.car
    tray = header_tray(c, c.drv_board_y, c.drv_board_x, (c.drv_hook_span, -c.drv_hook_span))
    return place_tray(tray, p.drv_x, p.drv_y, +1)


def tb_tray(p: P6Dims) -> Part:
    """Grips the 18.3 mm edges: its pin rows run along the 21 mm ones. The
    ledges sit 3.2 mm in from the pin-row edges, past the rows' solder."""
    c = p.car
    tray = header_tray(c, p.tb_board_x, p.tb_board_y, p.tb_tongue_ys,
                       arm=p.tb_corner_arm, ledge_inset=3.2, ledge_len=1.5)
    return place_tray(tray, p.tb_x, p.tb_y, -1)


def switch_dims(p: P6Dims) -> ChassisDims:
    return replace(p.car, switch_x=p.switch_x, switch_y=0.0)


def lids(p: P6Dims) -> dict:
    from xt60_holder import right_lid
    out = {}
    for name, x, side in corners(p):
        cd = at_cradle(p, x)
        out[name] = right_lid(cd) if name == "RR" else ch.motor_lid(cd, side)
    return out


def build(p: P6Dims):
    c = p.car
    cradles = {n: ch.motor_cradle(at_cradle(p, x), s) for n, x, s in corners(p)}
    trays = {"buck_L": buck_tray(p, +1), "buck_R": buck_tray(p, -1),
             "drv8833": drv_tray(p), "tb6612": tb_tray(p)}
    well = ch.switch_well(switch_dims(p))
    nubs = battery_nubs(p)
    loops = strap_loops(p)
    tube = tower_tube(p)

    body = plate(p)
    for part in (*cradles.values(), *trays.values(), well, nubs, loops, tube, pi_bosses(p)):
        body += part
    body &= footprint_prism(p)
    body -= tower_bore(p.spindle)
    body -= ch.label_engraving(replace(c, label_lines=p.label_lines, label_x=p.label_x))

    pack = rbox(-c.battery_len / 2, c.battery_len / 2, p.battery_yc - c.battery_wid / 2,
                p.battery_yc + c.battery_wid / 2, c.plate_thickness,
                c.plate_thickness + c.battery_h)
    the_lids = lids(p)
    fp = {f"cradle_{n}": cradles[n] for n, _, _ in corners(p)}
    fp.update({f"motor_{n}": ch.motor_placement(s, at_cradle(p, x)) for n, x, s in corners(p)})
    fp.update({f"lid_{n}": the_lids[n] for n, _, _ in corners(p)})
    fp.update(trays)
    fp.update({"pi_board": pi_env(p), "switch_well": well,
               "switch": ch.switch_placement(switch_dims(p)),
               "battery": pack + nubs, "strap_loops": loops, "tower": tube})
    return body, the_lids, fp


def spindle_parts(p: P6Dims) -> dict:
    """Bearings, round 1's rotor, washer and pin, and the hub: everything
    in the tower. The spindle frame is the car's."""
    s, m = p.spindle, p.mount
    out = {"rotor": make_rotor(s), "washer": make_washer(s), "pin": make_long_pin(m),
           "hub": make_hub(m)}
    for i, (outer, inner) in enumerate(bearings(s)):
        out[f"bearing{i}"] = outer + inner
    return out


def canon_on_top(p: P6Dims) -> dict:
    """canon_mount.py's cap and the Canon standing in it."""
    return {"cap": make_cap(p.mount), "canon": canon(p.mount)}


def wheels(p: P6Dims) -> dict:
    from light_wheel import VARIANTS, make_light_wheel
    w = make_light_wheel(VARIANTS["B"])
    axis_z = p.car.plate_thickness + ch.N20.gearbox_height / 2
    y0 = p.half_y + p.wheel_gap
    out = {}
    for name, x, side in corners(p):
        part = w.rotate(Axis.X, -90 if side > 0 else 90)
        out[name] = Pos(x, side * y0, axis_z) * part
    return out


def check(ok: bool, text: str) -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    return ok


def overlap_check(fp: dict) -> bool:
    expected = {(f"motor_{n}", f"lid_{n}"): (10.0, 60.0) for n in ("FL", "FR", "RL", "RR")}
    names, ok = list(fp), True
    bad = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = ivol(fp[a], fp[b])
            band = expected.get((a, b)) or expected.get((b, a))
            good = band[0] <= v <= band[1] if band else v < 1.0
            if not good:
                bad.append(f"{a} vs {b}: {v:.2f} mm^3")
            ok &= good
    n = len(names) * (len(names) - 1) // 2
    check(ok, f"{n} pairs of parts clear each other; each lid presses its motor 10-60 mm^3"
          + ("" if ok else " -- " + "; ".join(bad)))
    return ok


def checks(p: P6Dims, body: Part, fp: dict) -> bool:
    print("PASS/FAIL checks:")
    ok = overlap_check(fp)
    ok &= check(len(body.solids()) == 1, f"plate is one solid ({len(body.solids())})")
    sp = spindle_parts(p)
    v = sum(ivol(part, body) for part in sp.values())
    ok &= check(v < 1e-3, f"bearings, rotor, washer, pin and hub sit in the plate's tower, {v:.3f} mm^3")
    stand = canon_on_top(p)
    others = [fp[k] for k in fp] + [body]
    v = sum(ivol(stand["cap"] + stand["canon"], o) for o in others)
    ok &= check(v < 1e-3, f"cap and Canon clear everything on the plate, {v:.3f} mm^3")
    disc_r = p.spindle.disc_d / 2
    tip_r = 50.5  # blade tips, blade_disc.py
    ok &= check(tip_r < p.half_y - 2, f"blade tips (r {tip_r}) stay under the plate (half width {p.half_y:g})")
    wh = wheels(p)
    gaps = [wh[n].distance_to(body) for n in wh]
    ok &= check(min(gaps) >= 0.9, f"wheels clear the plate by {min(gaps):.2f} mm")
    front, rear = wh["FL"].bounding_box(), wh["RL"].bounding_box()
    ok &= check(front.min.X - rear.max.X > 20,
                f"front and rear wheels {front.min.X - rear.max.X:.1f} mm apart along a side")
    ok &= check(p.car.plate_thickness == p.spindle.flange_t,
                "the plate is as thick as the tested tower's flange, so the seats are the same")
    print(f"  disc Ø{2 * disc_r:g} turns {p.spindle.boss_h:g} mm under the plate")
    return ok


def render(p: P6Dims, body: Part, the_lids: dict) -> None:
    import numpy as np

    import xt60_twin as tw
    from b2_lipo import LipoDims, make_lipo
    from d2_drv8833 import Drv8833Dims, make_drv8833
    from p1_mp1584 import Mp1584Dims, make_mp1584
    from pi_zero_2w import PiZero2WDims, make_pi_zero_2w

    tw.LOOKS.setdefault("tb", ("#c94f7c", 0.55, 0.0))
    tw.LOOKS.setdefault("disc", ("#2f6fb3", 0.6, 0.0))
    c = p.car
    m = tw.mesh_of
    board_z = c.plate_thickness + c.tray_standoff
    pi = make_pi_zero_2w(PiZero2WDims()).rotate(Axis.Z, 180)
    pi = Pos(0, p.pi_y, c.plate_thickness + c.pi_boss_h + PiZero2WDims().board_thickness / 2) * pi
    lipo = make_lipo(LipoDims()).rotate(Axis.Z, 180)
    lipo = Pos(0, p.battery_yc, c.plate_thickness + LipoDims().height / 2) * lipo
    drv = Pos(p.drv_x, p.drv_y, board_z + 0.8) * make_drv8833(Drv8833Dims())
    bucks = [Pos(p.buck_x, s * p.buck_y, board_z + 0.8) * make_mp1584(
        Mp1584Dims(), with_headers=True, with_dupont=True, mounted=True).rotate(Axis.Z, 0 if s > 0 else 180)
        for s in (+1, -1)]
    tb = Pos(p.tb_x, p.tb_y, board_z) * (
        Box(p.tb_board_y, p.tb_board_x, c.tray_board_t, align=ALIGN_BOTTOM)
        + sum((Pos(0, sy * (p.tb_board_x / 2 - 1.27), c.tray_board_t) * Box(
            20.3, 2.5, 8.5, align=ALIGN_BOTTOM) for sy in (-1, 1)), Part()))

    statics = [("plate", m(body, 0.05), "plate"), ("pi", m(pi), "pi"), ("lipo", m(lipo), "battery"),
               ("drv", m(drv), "drv"), ("tb", m(tb), "tb"),
               ("switch", m(ch.switch_placement(switch_dims(p), clips=True)), "switch")]
    statics += [(f"buck{i}", m(b), "buck") for i, b in enumerate(bucks)]
    for name, x, side in corners(p):
        statics.append((f"motor{name}", m(ch.motor_placement(side, at_cradle(p, x))), "motor"))
        statics.append((f"lid{name}", m(the_lids[name]), "lid" if name != "RR" else "holder"))
    for name, w in wheels(p).items():
        statics.append((f"wheel{name}", m(w, 0.08), "wheel"))
    sp = spindle_parts(p)
    statics += [("rotor", m(sp["rotor"]), "disc"), ("hub", m(sp["hub"]), "pi")]
    disc_bottom = -p.spindle.boss_h - p.spindle.disc_t
    tips = Pos(0, 0, disc_bottom - 0.8) * (Cylinder(50.5, 0.6, align=ALIGN_BOTTOM)
                                          - Cylinder(49.5, 0.6, align=ALIGN_BOTTOM))
    statics.append(("tips", m(tips), "red"))
    stand = canon_on_top(p)
    statics += [("cap", m(stand["cap"]), "holder"), ("canon", m(stand["canon"]), "motor")]

    def ortho(name, target, direction, width):
        v = np.array(direction, float)
        v /= np.linalg.norm(v)
        t = np.array(target, float)
        return (name, t + 800 * v, t, 50.0, width)

    cams = [ortho("top", (0, 0, 0), (0.0, -0.001, 1.0), 345.0),
            ortho("front_left", (0, 0, 25), (1.0, 0.85, 0.75), 300.0),
            ortho("below", (0, 0, 0), (0.45, 0.6, -0.9), 300.0)]
    labels = {"top": [
        ("Battery", (0.50, 0.92), [(0, p.battery_yc, 21)]),
        ("Pi Zero 2 W", (0.50, 0.08), [(10, p.pi_y, 10)]),
        ("Bucks", (0.83, 0.30), [(p.buck_x + 6, p.buck_y, 12)]),
        ("DRV8833", (0.14, 0.30), [(p.drv_x, p.drv_y + 4, 12)]),
        ("TB6612", (0.14, 0.70), [(p.tb_x - 4, p.tb_y, 12)]),
        ("Switch", (0.14, 0.50), [(p.switch_x, 0, 20)]),
        ("XT60", (0.30, 0.94), [(-p.cradle_x - 8, -p.half_y + 12, 30)]),
        ("Canon on the tower", (0.83, 0.70), [(12, -12, 100)]),
    ]}
    tw.render_stills("proto06", tw.stage(statics, [], cams), cams, w=1100, labels=labels)


def tb_coupon(p: P6Dims) -> Part:
    """The TB6612's tray on a slab of plate, its letters on the slab."""
    from spindle_coupons import raised
    c = p.car
    tray = header_tray(c, p.tb_board_x, p.tb_board_y, p.tb_tongue_ys,
                       arm=p.tb_corner_arm, ledge_inset=3.2, ledge_len=1.5)
    bb = tray.bounding_box()
    slab = rbox(bb.min.X - 3, bb.max.X + 3, bb.min.Y - 3, bb.max.Y + 12, 0, c.plate_thickness)
    return slab + tray + raised("TB", 7.0, (bb.min.X + bb.max.X) / 2, bb.max.Y + 6, c.plate_thickness)


def main() -> None:
    p = P6Dims()
    if "tb-coupon" in sys.argv:
        part = tb_coupon(p)
        print(f"TB6612 tray coupon: {len(part.solids())} solid, tongues at "
              f"{p.tb_tongue_ys} along the gripped edge")
        export_stl(part, HERE / "tb_tray_coupon.stl")
        print("Exported tb_tray_coupon.stl")
        return
    body, the_lids, fp = build(p)
    ok = checks(p, body, fp)
    export_stl(body, HERE / "proto06_chassis.stl")
    bb = body.bounding_box()
    wb = 2 * p.cradle_x
    wheel_w = 30.0
    print(f"Plate {bb.size.X:.0f} x {bb.size.Y:.0f} mm, wheelbase {wb:g} mm, track "
          f"{2 * (p.half_y + p.wheel_gap) + wheel_w:.0f} mm between wheel centres; "
          f"{2 * (p.cradle_x + 40):.0f} x {2 * (p.half_y + p.wheel_gap + wheel_w):.0f} mm "
          "over the wheels")
    print("Exported proto06_chassis.stl")
    render(p, body, the_lids)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
