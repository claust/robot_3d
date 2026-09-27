"""robot_car: swivel caster on a nose arm, in place of the front skid.

A Ø40 caster wheel on a 10 mm trail, carried on an arm that clamps under
the plate's nose and reaches forward past it. The wheel is taller than the
20.5 mm under the plate, so it swivels out in front: the pivot sits far
enough ahead that the wheel's whole swing circle clears the arm's leg.

Car frame as chassis.py: +X front, plate bottom Z=0, the floor at
Z = -skid_below_plate (the drive wheels' contact). Every number is in
CasterDims.

PARTS (all printed, six pieces, five designs)

- Arm (caster_arm): foot, leg and beam in one side-view profile, printed
  lying on its side so the loads run along the layers. The foot sits under
  the plate's front, the anchor rivet pulls it up against the plate through
  the front skid hole, and a bumper takes the nose face. The leg stands
  clear of the Pi's front connectors, and the beam carries the pivot
  housing out ahead of the nose.
- Anchor rivet (caster_anchor): the skid's snap stem with a head. It pushes
  up through the foot and the plate hole and its barb clicks over the plate
  top, clamping the foot on. Hollow, so the short prongs bend at the same
  strain the skid's long ones do.
- Fork (caster_fork): crown and two legs, printed crown down. Its crown top
  bears on the housing's underside. That face carries the car's weight,
  and it turns there.
- Pin (caster_pin, print two): a Ø5 snap pin with a head and a slit barb,
  demo_04's validated snap post. One is the pivot: up through the crown
  (snug) and the housing (running fit), barb over the housing top, head
  under the crown. The other is the wheel's axle: through a leg, the wheel
  (running fit) and the other leg. Both grips are 14 mm.
- Wheel (caster_wheel): Ø40 x 8, printed flat on its web.

ASSEMBLY

Take out the skid. Push the anchor rivet up through the arm's foot and the
plate's front hole until it clicks. Push a pin up through the fork's crown
from underneath and on through the housing until it clicks. Set the wheel
between the fork legs and push the other pin through leg, wheel and leg.

Run with:  uv run robot_car/caster.py
Exports (gitignored) into robot_car/: caster_arm, caster_anchor,
caster_fork, caster_pin, caster_wheel (.stl/.step, print orientation),
caster_plate.stl (all six on one plate) and caster_assembly.stl (installed
on the chassis, for looking at). Writes caster_render.png. Exits nonzero
if any check fails.
"""

import math
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import (  # noqa: E402
    Axis,
    Box,
    Cone,
    Cylinder,
    GeomType,
    Part,
    Plane,
    Polygon,
    Pos,
    chamfer,
    export_step,
    export_stl,
    extrude,
)

from assembly import pi_placement  # noqa: E402
from chassis import ALIGN_BOTTOM, ChassisDims, build, ivol, rbox, skid_below_plate  # noqa: E402


@dataclass
class CasterDims:
    # ---- wheel ----------------------------------------------------------
    wheel_d: float = 40.0
    wheel_w: float = 8.0
    trail: float = 10.0  # pivot axis to axle, horizontal
    rim_t: float = 4.0  # radial
    web_t: float = 2.4
    hub_d: float = 11.0
    tread_chamfer: float = 0.8  # eases scrub while it swivels

    # ---- fits (project-wide values: README, Settled fits) ---------------
    running_fit: float = 0.2  # radial, anything that turns
    snug_fit: float = 0.1  # radial, firm push-on (the drive-wheel bore's)

    # ---- fork -----------------------------------------------------------
    crown_t: float = 4.0
    crown_gap: float = 2.0  # wheel top to crown underside
    leg_t: float = 2.5
    leg_gap: float = 0.5  # wheel face to leg, each side
    leg_len_x: float = 10.0  # along X, centred on the axle
    axle_boss_r: float = 5.0

    # ---- pin (pivot and axle): demo_04's snap post ----------------------
    pin_d: float = 5.0
    pin_head_d: float = 9.0
    pin_head_t: float = 1.5
    pin_lip: float = 0.15  # radial, over the running-fit bore
    pin_land: float = 0.4
    pin_slit_w: float = 1.5
    pin_slit_depth: float = 6.5  # below the lip
    pin_play: float = 0.3  # axial, so the stack turns without binding

    # ---- arm ------------------------------------------------------------
    arm_w: float = 14.0  # Y; the print height
    foot_t: float = 4.0
    foot_x0: float = 45.0  # rear end, 5 mm behind the skid hole's rim
    nose_gap: float = 0.1  # bumper to the plate's nose face
    # The Pi's front connectors reach 0.5 mm past the nose (to X=65.5 on the
    # centreline), so the leg's back face stands off 1.5 mm from the nose
    # above the bumper.
    leg_back_gap: float = 1.5
    arm_leg_t: float = 4.0  # X
    housing_h: float = 10.0  # pivot bearing length
    housing_half: float = 7.0  # X, either side of the pivot
    beam_lift: float = 1.0  # beam underside above the housing's
    gusset: float = 10.0
    swing_clearance: float = 3.0  # wheel's swing circle to the leg

    # ---- anchor rivet (the skid's stem, chassis.py numbers) -------------
    anchor_head_d: float = 16.0
    anchor_head_t: float = 2.0
    anchor_bore_d: float = 5.0
    anchor_slit_w: float = 2.0

    @property
    def wheel_r(self) -> float:
        return self.wheel_d / 2

    @property
    def pin_grip(self) -> float:
        """Head underside to lip, less the play: the stack a pin clamps."""
        return self.crown_t + self.housing_h

    @property
    def swing_radius(self) -> float:
        """The wheel's reach from the pivot axis at axle height: the far
        corner of its tread."""
        return math.hypot(self.trail + self.wheel_r, self.wheel_w / 2)


# ---------------------------------------------------------------------------
# frame: where things sit on the car
# ---------------------------------------------------------------------------


@dataclass
class Frame:
    floor_z: float
    nose_x: float
    leg_back: float
    leg_front: float
    pivot_x: float
    housing_bot: float  # = crown top
    housing_top: float


def frame(d: ChassisDims, c: CasterDims) -> Frame:
    floor_z = -skid_below_plate(d)
    nose_x = d.plate_length / 2
    leg_back = nose_x + c.leg_back_gap
    leg_front = leg_back + c.arm_leg_t
    pivot_x = leg_front + c.swing_clearance + c.swing_radius
    housing_bot = floor_z + c.wheel_d + c.crown_gap + c.crown_t
    return Frame(floor_z, nose_x, leg_back, leg_front, pivot_x,
                 housing_bot, housing_bot + c.housing_h)


# ---------------------------------------------------------------------------
# parts, each in its own frame
# ---------------------------------------------------------------------------


def teardrop_z(r: float, z0: float, z1: float) -> Part:
    """A Z-axis hole cutter with a 45 deg roof toward +Y, for a hole that
    prints horizontal with +Y up."""
    h = z1 - z0
    roof = Box(2 * r, 2 * r, h, align=ALIGN_BOTTOM).rotate(Axis.Z, 45)
    roof &= rbox(-2 * r, 2 * r, 0, 2 * r, 0, h)
    return Pos(0, 0, z0) * (Cylinder(r, h, align=ALIGN_BOTTOM) + roof)


def make_pin(c: CasterDims) -> Part:
    """Snap pin, axis +Z, head underside at z=head_t, lip starting at
    head_t + grip + play. Print orientation (head on the bed)."""
    r = c.pin_d / 2
    lip_r = r + c.running_fit + c.pin_lip
    z_lip = c.pin_head_t + c.pin_grip + c.pin_play
    ramp = lip_r - r  # 45 deg chamfers above and below the land
    tip_r = r - 0.3
    pin = Cylinder(c.pin_head_d / 2, c.pin_head_t, align=ALIGN_BOTTOM)
    pin += Pos(0, 0, c.pin_head_t) * Cylinder(r, z_lip - c.pin_head_t, align=ALIGN_BOTTOM)
    pin += Pos(0, 0, z_lip) * Cone(r, lip_r, ramp, align=ALIGN_BOTTOM)
    pin += Pos(0, 0, z_lip + ramp) * Cylinder(lip_r, c.pin_land, align=ALIGN_BOTTOM)
    z = z_lip + ramp + c.pin_land
    pin += Pos(0, 0, z) * Cone(lip_r, tip_r, lip_r - tip_r, align=ALIGN_BOTTOM)
    top = z + lip_r - tip_r
    slit_z0 = z_lip - c.pin_slit_depth
    pin -= Pos(0, 0, slit_z0) * Box(c.pin_d + 2, c.pin_slit_w, top - slit_z0 + 1,
                                    align=ALIGN_BOTTOM)
    return pin


def make_anchor(d: ChassisDims, c: CasterDims) -> Part:
    """The skid's snap stem (chassis.build_skid numbers) under a head that
    clamps the arm's foot. Head underside at z=0, the foot on top of it,
    the plate on the foot, the barb's retention ramp starting at the plate
    top. Print orientation."""
    shank_r = d.skid_hole_d / 2 - d.skid_hole_clearance
    barb_r = d.skid_hole_d / 2 + d.skid_barb_interference
    ramp, land = d.skid_barb_h * 0.4, d.skid_barb_h * 0.2
    lead_in = barb_r - shank_r
    z_barb = c.anchor_head_t + c.foot_t + d.plate_thickness
    a = Cylinder(c.anchor_head_d / 2, c.anchor_head_t, align=ALIGN_BOTTOM)
    a += Pos(0, 0, c.anchor_head_t) * Cylinder(shank_r, z_barb - c.anchor_head_t,
                                               align=ALIGN_BOTTOM)
    a += Pos(0, 0, z_barb) * Cone(shank_r, barb_r, ramp, align=ALIGN_BOTTOM)
    a += Pos(0, 0, z_barb + ramp) * Cylinder(barb_r, land, align=ALIGN_BOTTOM)
    a += Pos(0, 0, z_barb + ramp + land) * Cone(barb_r, shank_r, lead_in, align=ALIGN_BOTTOM)
    top = z_barb + ramp + land + lead_in
    a -= Cylinder(c.anchor_bore_d / 2, top + 1, align=ALIGN_BOTTOM)
    slit = Pos(0, 0, c.anchor_head_t) * Box(
        2 * barb_r + 2, c.anchor_slit_w, top, align=ALIGN_BOTTOM)
    a -= slit
    a -= slit.rotate(Axis.Z, 90)
    return a


def make_wheel(c: CasterDims) -> Part:
    """Axis +Z, web on the bed. Print orientation."""
    r, w = c.wheel_r, c.wheel_w
    rim = Cylinder(r, w, align=ALIGN_BOTTOM) - Cylinder(r - c.rim_t, w, align=ALIGN_BOTTOM)
    tread = rim.edges().filter_by(GeomType.CIRCLE).filter_by(lambda e: abs(e.radius - r) < 1e-3)
    rim = chamfer(tread, c.tread_chamfer)
    wheel = rim + Cylinder(r - c.rim_t + 0.5, c.web_t, align=ALIGN_BOTTOM)
    wheel += Cylinder(c.hub_d / 2, w, align=ALIGN_BOTTOM)
    wheel -= Cylinder(c.pin_d / 2 + c.running_fit, w, align=ALIGN_BOTTOM)
    return wheel


def axle_z(c: CasterDims) -> float:
    """Axle height in the fork's frame (crown top Z=0)."""
    return -(c.crown_t + c.crown_gap + c.wheel_r)


def make_fork(c: CasterDims) -> Part:
    """Fork frame: pivot axis on Z, crown top at Z=0, the wheel trailing
    toward -X. Upside down (crown on the bed) is its print orientation."""
    half_w = c.wheel_w / 2 + c.leg_gap + c.leg_t
    x_rear = -c.trail - c.leg_len_x / 2
    x_leg_front = -c.trail + c.leg_len_x / 2
    za = axle_z(c)
    crown = rbox(x_rear, 0, -half_w, half_w, -c.crown_t, 0)
    crown += Pos(0, 0, -c.crown_t) * Cylinder(half_w, c.crown_t, align=ALIGN_BOTTOM)
    crown -= Pos(0, 0, -c.crown_t - 1) * Cylinder(
        c.pin_d / 2 + c.snug_fit, c.crown_t + 2, align=ALIGN_BOTTOM)
    fork = crown
    for sy in (1, -1):
        y0, y1 = sorted((sy * (c.wheel_w / 2 + c.leg_gap), sy * half_w))
        fork += rbox(x_rear, x_leg_front, y0, y1, za, -c.crown_t)
        fork += Pos(-c.trail, (y0 + y1) / 2, za) * Cylinder(
            c.axle_boss_r, c.leg_t, rotation=(90, 0, 0))
    # axle hole: prints horizontal with the fork upside down, so its roof
    # points down the car's -Z
    hole = teardrop_z(c.pin_d / 2 + c.running_fit, -half_w - 1, half_w + 1)
    fork -= Pos(-c.trail, 0, za) * hole.rotate(Axis.X, -90)
    return fork


def make_arm(d: ChassisDims, c: CasterDims) -> Part:
    """Car frame. One side-view profile extruded across Y: prints lying on
    its -Y face."""
    f = frame(d, c)
    yw = c.arm_w / 2
    arm = rbox(c.foot_x0, f.leg_front, -yw, yw, -c.foot_t, 0)  # foot
    arm += rbox(f.nose_x + c.nose_gap, f.leg_back, -yw, yw, 0, d.plate_thickness)  # bumper
    arm += rbox(f.leg_back, f.leg_front, -yw, yw, -c.foot_t, f.housing_top)  # leg
    arm += rbox(f.leg_back, f.pivot_x, -yw, yw, f.housing_bot + c.beam_lift, f.housing_top)
    arm += rbox(f.pivot_x - c.housing_half, f.pivot_x + c.housing_half, -yw, yw,
                f.housing_bot, f.housing_top)
    zb = f.housing_bot + c.beam_lift
    tri = Polygon((f.leg_front - 0.5, zb - c.gusset), (f.leg_front - 0.5, zb + 0.5),
                  (f.leg_front + c.gusset, zb + 0.5), align=None)
    arm += extrude(Plane.XZ * tri, amount=yw, both=True)
    arm -= Pos(d.skid_front_x, 0, 0) * teardrop_z(d.skid_hole_d / 2, -c.foot_t - 1, 1)
    arm -= Pos(f.pivot_x, 0, 0) * teardrop_z(
        c.pin_d / 2 + c.running_fit, f.housing_bot - 1, f.housing_top + 1)
    return arm


# ---------------------------------------------------------------------------
# placement on the car
# ---------------------------------------------------------------------------


def swivel(d: ChassisDims, c: CasterDims, theta: float) -> dict:
    """The fork, wheel and both pins placed on the car, turned `theta`
    degrees about the pivot (0 = wheel trailing, driving forward)."""
    f = frame(d, c)
    za = axle_z(c)
    half_w = c.wheel_w / 2 + c.leg_gap + c.leg_t
    wheel = Pos(-c.trail, c.wheel_w / 2, za) * make_wheel(c).rotate(Axis.X, 90)
    pin = make_pin(c)
    pivot_pin = Pos(0, 0, -c.crown_t - c.pin_head_t) * pin
    axle_pin = Pos(-c.trail, half_w + c.pin_head_t, za) * pin.rotate(Axis.X, 90)
    place = Pos(f.pivot_x, 0, f.housing_bot)
    return {name: place * p.rotate(Axis.Z, theta) for name, p in (
        ("fork", make_fork(c)), ("wheel", wheel),
        ("pivot_pin", pivot_pin), ("axle_pin", axle_pin))}


def arm_installed(d: ChassisDims, c: CasterDims) -> dict:
    anchor = Pos(d.skid_front_x, 0, -c.foot_t - c.anchor_head_t) * make_anchor(d, c)
    return {"arm": make_arm(d, c), "anchor": anchor}


# ---------------------------------------------------------------------------
# print orientation
# ---------------------------------------------------------------------------


def on_bed(p: Part) -> Part:
    bb = p.bounding_box()
    return Pos(-bb.min.X, -bb.min.Y, -bb.min.Z) * p


def print_parts(d: ChassisDims, c: CasterDims) -> dict:
    """name -> (part on the bed at the origin, copies)."""
    return {
        "caster_arm": (on_bed(make_arm(d, c).rotate(Axis.X, 90)), 1),  # +Y up
        "caster_fork": (on_bed(make_fork(c).rotate(Axis.X, 180)), 1),  # crown down
        "caster_wheel": (on_bed(make_wheel(c)), 1),
        "caster_pin": (on_bed(make_pin(c)), 2),
        "caster_anchor": (on_bed(make_anchor(d, c)), 1),
    }


def plate_layout(parts: dict, gap: float = 6.0) -> Part:
    """Every copy in one row, `gap` apart, centred on the origin."""
    plate, x = Part(), 0.0
    for part, n in parts.values():
        for _ in range(n):
            bb = part.bounding_box()
            plate += Pos(x, -bb.size.Y / 2, 0) * part
            x += bb.size.X + gap
    bb = plate.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, 0) * plate


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

OVERLAP_TOL = 0.5  # mm^3; coincident bearing faces mesh to a sliver


def report(ok: bool, text: str) -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {text}")
    return ok


def run_checks(d: ChassisDims, c: CasterDims) -> bool:
    f = frame(d, c)
    chassis = build(d).plate
    pi = pi_placement(d)[0]
    fixed = arm_installed(d, c)
    ok = True

    print("\n-- caster checks --")
    grips = (c.crown_t + c.housing_h, 2 * (c.leg_t + c.leg_gap) + c.wheel_w)
    ok &= report(abs(grips[0] - grips[1]) < 1e-6 and abs(grips[0] - c.pin_grip) < 1e-6,
                 f"one pin fits both stacks: pivot {grips[0]:g}, axle {grips[1]:g} mm")

    for name, (part, _) in print_parts(d, c).items():
        n = len(part.solids())
        ok &= report(n == 1, f"{name} is one solid ({n})")

    s0 = swivel(d, c, 0)
    low = s0["wheel"].bounding_box().min.Z
    ok &= report(abs(low - f.floor_z) < 0.05,
                 f"caster wheel meets the floor with the drive wheels "
                 f"(Z {low:.2f} vs {f.floor_z:.2f}): the plate stays level")

    # the moving parts clear each other: running fits and gaps, no contact
    pairs = (("wheel", "fork"), ("wheel", "axle_pin"), ("wheel", "pivot_pin"),
             ("fork", "axle_pin"), ("fork", "pivot_pin"))
    for a, b in pairs:
        v = ivol(s0[a], s0[b])
        ok &= report(v < OVERLAP_TOL, f"{a} vs {b}: {v:.3f} mm^3")
    gap = s0["pivot_pin"].distance_to(s0["wheel"])
    ok &= report(gap >= 1.0, f"pivot pin head clears the wheel by {gap:.2f} mm (>= 1)")

    for name, part in fixed.items():
        v = ivol(part, chassis)
        ok &= report(v < OVERLAP_TOL, f"{name} vs chassis: {v:.3f} mm^3")
        g = part.distance_to(pi)
        ok &= report(g >= 0.5, f"{name} clears the Pi (connectors included) by {g:.2f} mm")
    v = ivol(fixed["arm"], fixed["anchor"])
    ok &= report(v < OVERLAP_TOL, f"anchor vs arm: {v:.3f} mm^3")

    # swing: every heading, the moving parts against everything fixed
    worst_ivol, worst_gap = 0.0, math.inf
    for theta in range(0, 360, 15):
        s = swivel(d, c, theta)
        moving = s["fork"] + s["wheel"] + s["axle_pin"]
        for part in (fixed["arm"], fixed["anchor"], chassis):
            worst_ivol = max(worst_ivol, ivol(moving, part))
        worst_ivol = max(worst_ivol, ivol(s["pivot_pin"], fixed["arm"]))
        worst_gap = min(worst_gap, s["wheel"].distance_to(fixed["arm"]))
    ok &= report(worst_ivol < OVERLAP_TOL,
                 f"swings a full turn without touching arm, anchor or chassis "
                 f"(worst {worst_ivol:.3f} mm^3, 15 deg steps)")
    ok &= report(worst_gap >= c.swing_clearance - 0.05,
                 f"wheel stays {worst_gap:.2f} mm off the arm at every heading "
                 f"(>= {c.swing_clearance:g})")

    under = min(p.bounding_box().min.Z for p in fixed.values())
    ok &= report(under - f.floor_z >= 12.0,
                 f"arm and anchor ride {under - f.floor_z:.1f} mm above the floor (>= 12)")
    return ok


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

COLOURS = {
    "chassis": "#5a6472", "Pi": "#2e9e5b", "arm": "#1d9e75", "anchor": "#0f6e56",
    "fork": "#d85a30", "wheel": "#993c1d", "pins": "#f0997b",
}


def render(d: ChassisDims, c: CasterDims, out: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np
    import trimesh
    from matplotlib.patches import Circle, Patch
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    f = frame(d, c)
    front = rbox(20, 200, -80, 80, -40, 80)  # the nose end of the car
    s = swivel(d, c, 0)
    fixed = arm_installed(d, c)
    groups = [
        ("chassis", build(d).plate & front), ("Pi", pi_placement(d)[0] & front),
        ("arm", fixed["arm"]), ("anchor", fixed["anchor"]),
        ("fork", s["fork"]), ("wheel", s["wheel"]),
        ("pins", s["pivot_pin"] + s["axle_pin"]),
    ]
    meshes = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, part) in enumerate(groups):
            p = Path(tmp) / f"{i}.stl"
            export_stl(part, p)
            meshes.append((name, trimesh.load_mesh(p)))

    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"robot car -- nose caster, Ø{c.wheel_d:g} wheel, {c.trail:g} mm trail",
                 fontsize=15, fontweight="bold")
    views = [(fig.add_subplot(2, 2, 1, projection="3d"), 22, -60, "isometric, front left"),
             (fig.add_subplot(2, 2, 2, projection="3d"), 12, 35, "isometric, front right")]
    for ax, elev, azim, title in views:
        tris = np.concatenate([m.vertices[m.faces] for _, m in meshes])
        cols = sum(([COLOURS[n]] * len(m.faces) for n, m in meshes), [])
        ax.add_collection3d(Poly3DCollection(tris, facecolors=cols,
                                             edgecolors="#00000014", linewidths=0.05))
        lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
        for i, a in enumerate("xyz"):
            getattr(ax, f"set_{a}lim")(lo[i], hi[i])
        ax.set_box_aspect(tuple(hi - lo), zoom=1.2)
        ax.set_proj_type("ortho")
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(title)

    def flat(ax, i, j, title, ylabel):
        for name, m in meshes:
            tri = m.vertices[m.faces][:, :, [i, j]]
            from matplotlib.collections import PolyCollection
            ax.add_collection(PolyCollection(tri, facecolors=COLOURS[name],
                                             edgecolors="none", alpha=0.9))
        ax.set_aspect("equal")
        ax.set_title(title)
        ax.set_xlabel("X (mm)")
        ax.set_ylabel(ylabel)
        ax.grid(True, lw=0.3, alpha=0.4)

    side = fig.add_subplot(2, 2, 3)
    flat(side, 0, 2, "side elevation, from +Y (front to the right)", "Z (mm)")
    side.axhline(f.floor_z, color="#8a6d3b", ls="--", lw=1.2)
    side.axvline(f.pivot_x, color="#555555", ls="-.", lw=0.7)
    side.set_xlim(25, f.pivot_x + c.swing_radius + 8)
    side.set_ylim(f.floor_z - 4, f.housing_top + 8)

    plan = fig.add_subplot(2, 2, 4)
    flat(plan, 0, 1, "top plan, swing circle dashed", "Y (mm)")
    plan.add_patch(Circle((f.pivot_x, 0), c.swing_radius, fill=False, ls="--",
                          ec="#d85a30", lw=1.2))
    plan.set_xlim(25, f.pivot_x + c.swing_radius + 8)
    plan.set_ylim(-c.swing_radius - 6, c.swing_radius + 6)

    fig.legend(handles=[Patch(facecolor=v, label=k) for k, v in COLOURS.items()],
               loc="lower center", ncol=len(COLOURS), frameon=False, fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"Wrote {out.name}")


if __name__ == "__main__":
    d, c = ChassisDims(), CasterDims()
    f = frame(d, c)

    parts = print_parts(d, c)
    for name, (part, n) in parts.items():
        export_stl(part, HERE / f"{name}.stl")
        export_step(part, HERE / f"{name}.step")
    plate = plate_layout(parts)
    export_stl(plate, HERE / "caster_plate.stl")

    s = swivel(d, c, 0)
    installed = build(d).plate + sum(arm_installed(d, c).values(), Part())
    installed += s["fork"] + s["wheel"] + s["pivot_pin"] + s["axle_pin"]
    export_stl(installed, HERE / "caster_assembly.stl")

    ok = run_checks(d, c)
    render(d, c, HERE / "caster_render.png")

    bb = plate.bounding_box()
    print(f"\nPivot X={f.pivot_x:.1f}: {f.pivot_x - f.nose_x:.1f} mm ahead of the nose, "
          f"swing radius {c.swing_radius:.1f} mm")
    print(f"Wheelbase {f.pivot_x - c.trail - d.cradle_x:.1f} mm driving forward, "
          f"{f.pivot_x + c.trail - d.cradle_x:.1f} reversing (skid: "
          f"{d.skid_front_x - d.cradle_x:g})")
    print(f"Nose top {f.housing_top - f.floor_z + c.pin_play + 1.5:.1f} mm above the floor")
    print(f"Plate: {len(plate.solids())} pieces, {bb.size.X:.1f} x {bb.size.Y:.1f} "
          f"x {bb.size.Z:.1f} mm")
    print("Exported caster_arm/_fork/_wheel/_pin (print two)/_anchor .stl/.step, "
          "caster_plate.stl, caster_assembly.stl")
    sys.exit(0 if ok else 1)
