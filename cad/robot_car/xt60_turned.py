"""robot_car PROTO-06: the XT60 holder lid with the plug turned 90 deg --
lying along the rear-right lid, its mating face out toward the wheel and
its wires in toward the power switch.

WHY TURNED

The pack's rear end stands 3.6 mm in front of the rear-right lid. A male
facing the rear with its wires forward would have its heat-shrink against
the pack and its wires nowhere to go. Turned, the male's wires run inboard,
straight to the switch in the middle of the rear edge, and the pack's lead,
which leaves the pack's rear end at its outboard corner, comes round to the
male's mating face from the wheel side.

THE HOLDER

xt60_holder.py's holder, unchanged: the channel and its fits, the mark
grooves, the edge ledges, the latch arm and barb, the two plinths over the
lid's skirts that leave its ceiling (the motor-clamp spring) free. Here it
lies along the lid instead of across it:

- The male's rim stands FEMALE_ROOM in from the wheel's inner face: room
  for the pack's female to line up before it goes in, its 7.8 mm nose,
  8 mm body and 4.6 mm solder cups in a row, with its lead bent up off the
  cups and over to the pack. So the holder's wire
  end reaches past the lid's inner end, over the plate behind the pack, and
  the female sits in the open above the lid, between the plinth walls and
  their posts at the lid's outer end (xt60_holder.plinths), where it can
  be pinched by its sides to unplug it.
- The lid slides on from inboard, 23 mm, under the holder's inboard part,
  which passes over the switch on the way. So the holder stands on its
  plinths high enough to clear the switch's rocker by SLIDE_CLEAR: the
  plinths are walls along the skirts, the ceiling still bridges between
  them, and the frame sits on top.
- The male goes in from the switch side and clicks in, with the lid on the
  car.
- Plugging the pack in pushes the male inboard, the way the lid slides off,
  against only the lid's detent: hold the holder's inboard end while
  plugging in. Pulling the pack's plug out pushes the lid against its end
  wall.

Run with:  uv run robot_car/xt60_turned.py [--no-render]
Runs the holder's PASS/FAIL checks and PROTO-06's (plugs clear of
everything, the female's room to the wheel, the lid's slide past the
switch), exports xt60_turned_lid.stl (print orientation) and renders
xt60_turned.png: the corner from above and behind, from above, and the lid
as it prints.
"""

import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

import numpy as np  # noqa: E402
from build123d import Axis, Box, Part, Pos, export_stl, fillet  # noqa: E402

import chassis as ch  # noqa: E402
from chassis import ChassisDims, ivol, lid_dims  # noqa: E402
from lid_coupons import lid_for_print  # noqa: E402
from proto06 import P6Dims, at_cradle, build, switch_dims, wheels  # noqa: E402
from xt60_holder import (  # noqa: E402
    XT, HolderDims, female_mated, make_holder_lid, male_seated, shrink_seated, to_lid,
)
from xt60_holder import checks as holder_checks  # noqa: E402

FEMALE_ROOM = 24.0  # male's rim to the wheel's inner face
SLIDE_CLEAR = 1.0  # holder's underside over the switch's rocker


def rr(p: P6Dims) -> ChassisDims:
    """chassis.py's dims at the rear-right cradle."""
    return at_cradle(p, -p.cradle_x)


def lid_top(cd: ChassisDims) -> float:
    ld = lid_dims(cd)
    return ld.T + ld.rail_clearance + ld.ceiling_t


def holder_dims(p: P6Dims) -> HolderDims:
    """The holder along the rear-right lid: rim FEMALE_ROOM in from the
    wheel, underside SLIDE_CLEAR over the switch."""
    cd = rr(p)
    ld = lid_dims(cd)
    lid_end = cd.plate_width / 2 - ld.edge_y + ld.lid_len  # |Y| of the lid's outer end
    wheel = p.half_y + p.wheel_gap
    switch_top = ch.switch_placement(switch_dims(p)).bounding_box().max.Z
    return replace(HolderDims(), turned=True, width=2 * ld.lid_half_w,
                   setback=FEMALE_ROOM - (wheel - lid_end),
                   gap=switch_top + SLIDE_CLEAR - lid_top(cd))


def to_car(part: Part, p: P6Dims) -> Part:
    """Holder frame -> car."""
    return ch._to_side(to_lid(part, rr(p), turned=True), rr(p), -1)


def car_pts(pts, p: P6Dims) -> np.ndarray:
    """to_car for points: holder x is car -Y, holder y car +X, from the
    lid's outer end on its top face."""
    cd, ld = rr(p), lid_dims(rr(p))
    q = np.asarray(pts, float)
    origin = [cd.cradle_x, -(cd.plate_width / 2 - ld.edge_y + ld.lid_len), lid_top(cd)]
    return np.stack([q[..., 1], -q[..., 0], q[..., 2]], axis=-1) + origin


def turned_lid(p: P6Dims) -> Part:
    """The rear-right lid with the turned holder, seated on its cradle."""
    return ch._to_side(make_holder_lid(holder_dims(p), rr(p)), rr(p), -1)


def plugs(p: P6Dims, h: HolderDims) -> dict:
    """The seated male with its heat-shrink, and the pack's mated female
    with hers, in the car."""
    return {"male": to_car(male_seated(h) + shrink_seated(h), p), "female": to_car(female_mated(h), p)}


def report(ok: bool, text: str) -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    return ok


def car_checks(p: P6Dims, h: HolderDims, body: Part, fp: dict) -> bool:
    ok = True
    wh = wheels(p)
    others = {**fp, **{f"wheel_{n}": w for n, w in wh.items()}, "plate": body}
    for name, part in plugs(p, h).items():
        hits = {n: ivol(part, o) for n, o in others.items()}
        bad = [f"{n} {v:.2f} mm^3" for n, v in hits.items() if v > 1e-6]
        ok &= report(not bad, f"{name} plug clear of the car's {len(others)} parts"
                     + (" -- " + "; ".join(bad) if bad else ""))
    rigid = XT.nose_len + XT.female_body_len + XT.cup_len
    ok &= report(FEMALE_ROOM - rigid >= 3.0,
                 f"pack's female lines up for the push {FEMALE_ROOM - rigid:.1f} mm from the wheel "
                 f"(nose, body and cups {rigid:.1f} mm, lead bent up off the cups)")
    cups = FEMALE_ROOM - XT.female_body_len - XT.cup_len
    shrink = FEMALE_ROOM - XT.female_body_len - XT.shrink_len
    ok &= report(shrink >= 2.0, f"mated, its cups end {cups:.1f} mm and its heat-shrink "
                 f"{shrink:.1f} mm from the wheel")
    gap = plugs(p, h)["female"].distance_to(wh["RR"])
    ok &= report(abs(gap - shrink) < 0.3, f"female to the turning wheel, measured: {gap:.1f} mm")

    # sliding the lid on from inboard: its holder passes over the switch
    lid = fp["lid_RR"]
    skip = {"lid_RR", "cradle_RR", "motor_RR"}
    worst = []
    for dy in np.arange(1.0, 24.0, 2.0):
        moved = Pos(0, dy, 0) * lid
        worst += [(dy, n, ivol(moved, o)) for n, o in fp.items() if n not in skip]
    bad = [f"{n} at {dy:g} mm" for dy, n, v in worst if v > 1e-6]
    ok &= report(not bad, "lid slides 23 mm inboard clear of everything but its own cradle"
                 + (" -- " + ", ".join(sorted(set(bad))[:6]) if bad else ""))
    sw = ch.switch_placement(switch_dims(p)).bounding_box()
    print(f"         holder underside {lid_top(rr(p)) + h.gap:.1f} above the plate's underside, "
          f"switch top {sw.max.Z:.1f}; wire end {abs(car_pts([h.x_end, 0, 0], p)[1]):.1f} mm "
          f"from the centre line, switch side {abs(sw.min.Y):.1f}")
    return ok


# ---- render ----------------------------------------------------------------


def leads(p: P6Dims, h: HolderDims):
    """Static meshes for the two leads: the male's wires inboard and down
    to the switch, the pack's up off the female and over to the pack's
    rear end at its outboard corner."""
    import trimesh

    import xt60_twin as tw
    c = p.car
    z = h.z_plug + XT.axis_z
    start = car_pts([h.x_rim - XT.male_len - XT.shrink_len, 0, z], p)
    sw = ch.switch_placement(switch_dims(p)).bounding_box()
    end = np.array([sw.max.X + 3, sw.min.Y + 6, sw.max.Z - 12])
    harness = tw.spline(np.array([start, start + [0, 6, 0], start + [1, 12, -4], end + [2, -2, 6], end]), 90)
    tail = car_pts([h.x_rim + XT.female_body_len + XT.shrink_len, 0, z], p)
    corner = np.array([-c.battery_len / 2, p.battery_yc - c.battery_wid / 2 + 6, c.plate_thickness + 6])
    pack = tw.spline(np.array([tail, tail + [0, -0.8, 5], tail + [5, 2, 11], corner + [-8, -1, 16],
                               corner + [-7, 0, 3], corner + [1, 0, 0]]), 110)
    out = []
    for i, (look, v, f) in enumerate(tw.wire_pair(harness, XT.pitch / 2, 1.7) + tw.wire_pair(pack, XT.pitch / 2, 1.9)):
        out.append((f"lead{i}", trimesh.Trimesh(v, f, process=False), look))
    return out


def render(p: P6Dims, h: HolderDims, body: Part, the_lids: dict) -> None:
    import xt60_twin as tw
    from xt60 import make_female, make_male, make_shrink

    c, m = p.car, tw.mesh_of
    pack = fillet(Box(c.battery_len, c.battery_wid, c.battery_h).edges(), 2.0)
    pack = Pos(0, p.battery_yc, c.plate_thickness + c.battery_h / 2) * pack
    seat = Pos(h.x_rim, 0, h.z_plug)
    sm, sf = make_shrink(XT, -XT.male_len, -1), make_shrink(XT, XT.female_body_len, +1)
    wh = wheels(p)
    statics = [("plate", m(body, 0.05), "plate"), ("pack", m(pack), "battery"),
               ("switch", m(ch.switch_placement(switch_dims(p), clips=True)), "switch"),
               ("wheelRR", m(wh["RR"], 0.08), "wheel"), ("wheelRL", m(wh["RL"], 0.08), "wheel"),
               ("male", m(to_car(seat * make_male(XT), p), 0.02), "xt60"),
               ("female", m(to_car(seat * make_female(XT), p), 0.02), "amber"),
               ("shrink", m(to_car(seat * (sm[0] + sm[1] + sf[0] + sf[1]), p), 0.02), "shrink")]
    for name in ("RL", "RR", "FR"):
        x = -p.cradle_x if name[0] == "R" else p.cradle_x
        side = 1 if name[1] == "L" else -1
        statics.append((f"motor{name}", m(ch.motor_placement(side, at_cradle(p, x))), "motor"))
        statics.append((f"lid{name}", m(the_lids[name], 0.02), "holder" if name == "RR" else "lid"))
    statics += leads(p, h)
    printed = lid_for_print(make_holder_lid(h, rr(p)), lid_dims(rr(p)))
    bb = printed.bounding_box()
    off = np.array([0.0, 260.0, 0.0])  # the print bed, well away from the car
    statics += [("printed", m(Pos(*(off - [bb.center().X, bb.center().Y, 0])) * printed, 0.02), "holder"),
                ("bed", m(Pos(*(off - [0, 0, 0.5])) * Box(80, 70, 1)), "floor")]

    def ortho(name, target, direction, width):
        v = np.array(direction, float)
        v /= np.linalg.norm(v)
        t = np.array(target, float)
        return (name, t + 800 * v, t, 50.0, width)

    target = car_pts([-22, 0, 6], p)
    cams = [ortho("behind", target + [0, 8, 0], (-1.0, 0.18, 0.42), 100.0),
            ortho("top", (-52, -32, 0), (0.0, -0.001, 1.0), 110.0),
            ortho("print", off + [0, 0, bb.size.Z / 2], (1.0, -1.6, 0.7), 85.0)]
    zf = h.z_plug + XT.height
    half = lid_dims(rr(p)).lid_half_w
    labels = {
        "behind": [("Pack's female", (0.83, 0.12), [car_pts([h.x_rim + 4, -half, zf - 2], p)]),
                   ("Male, clicked in", (0.50, 0.08), [car_pts([h.x_rim - 9, 4.5, h.z_top], p)]),
                   ("Wires to the switch", (0.18, 0.10), [car_pts([h.x_end - 6, 0, h.z_plug + 3], p)]),
                   ("Switch", (0.10, 0.62), [(-73.5, 0, 22)]),
                   ("Plinth wall: lifts the holder over the switch", (0.30, 0.90),
                    [car_pts([-12, -half + 1, h.gap / 2], p)]),
                   ("Wheel", (0.90, 0.85), [(-102, -84, 10)])],
        "top": [("Wheel", (0.15, 0.92), [(-62, -80, 40)]),
                ("Pack", (0.85, 0.75), [(-20, p.battery_yc, 22)]),
                ("Switch", (0.10, 0.20), [(-64, 0, 27)]),
                ("Female from the wheel side", (0.62, 0.95), [car_pts([h.x_rim + 5, 0, zf], p)])],
        "print": [("Holder top on the bed", (0.20, 0.88), [tuple(off + [-6, 0, 0.5])]),
                  ("Plinth walls", (0.15, 0.25), [tuple(off + [0, 0, bb.size.Z * 0.55])]),
                  ("Ceiling bridges between them", (0.70, 0.10), [tuple(off + [8, 0, bb.size.Z - 6])])],
    }
    tw.render_stills("xt60_turned", tw.stage(statics, [], cams), cams, w=1100, labels=labels)


def main() -> None:
    p = P6Dims()
    h = holder_dims(p)
    cd = rr(p)
    print(f"turned holder: rim {h.setback:.1f} mm in from the lid's outer end "
          f"({FEMALE_ROOM:g} from the wheel), wire end {h.x_end:.1f}; "
          f"underside {h.gap:.1f} over the lid, top {h.z_top:.1f}")
    print("Holder, xt60_holder.py's checks:")
    ok = holder_checks(h, cd)
    print("On PROTO-06:")
    body, the_lids, fp = build(p)
    ok &= car_checks(p, h, body, fp)
    printable = lid_for_print(make_holder_lid(h, cd), lid_dims(cd))
    export_stl(printable, HERE / "xt60_turned_lid.stl")
    bb = printable.bounding_box()
    print(f"xt60_turned_lid.stl: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"{printable.volume / 1000:.2f} cm^3, solids: {len(printable.solids())}")
    ok &= report(len(printable.solids()) == 1, "the lid prints as one solid")
    if "--no-render" not in sys.argv:
        render(p, h, body, the_lids)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
