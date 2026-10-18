"""The Canon motor (parts library M1) on top of the spindle tower: a cap and
a hub, no screws anywhere.

- Cap: slides over the tower's top and rests on its top outer edge on a
  45 deg cone inside the skirt (a flat lip there would print hanging in
  the air). The Canon stands in a cup on top, shaft down,
  face on the cup's floor and its front boss in a counterbore there, so
  the shaft lines up with the axle. Gravity holds the motor in and the cap
  on; the snug fits stop rattling and carry the motor's torque. Two windows
  in the skirt let you line the hub's slots up with the pin.
- Hub: pressed onto the Canon's shaft. Its lower end is a sleeve that
  slides loosely over the axle's top and has two slots that drop over the
  ends of the filament pin. The pin drives the rotor; the loose sleeve
  lets the motor and the axle sit slightly out of line without bending
  anything.

Fits, from cap_coupons.py (2026-10-18), radial:
  cap over the tower  0.05 (ring A)
  can in the cup      0.05 (cup F)
  hub on the shaft    0.15 (hub L; small holes print undersized)

Use a filament pin about 20 mm long so its ends reach into the slots.

Frame: the spindle's (spindle_coupons.py), Z=0 at the tower flange's
underside. Built around round 1's rotor and tower.

Run with:  uv run robot_car/canon_mount.py
Exports canon_mount.stl (cap and hub as they print, gitignored), runs the
PASS/FAIL checks and renders canon_mount.png, the stack cut in half.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import Align, Box, Cone, Cylinder, Part, Pos, Rot, export_stl  # noqa: E402

from ck35_motor import MEASURED_DIMS, Ck35Dims, make_motor  # noqa: E402
from spindle_coupons import (  # noqa: E402
    ALIGN_BOTTOM, SpindleDims, bearings, ivol, make_rotor, make_tower, make_washer, mouth,
    tube,
)


@dataclass
class MountDims:
    """All dimensions in mm, spindle frame."""

    spindle: SpindleDims = field(default_factory=lambda: SpindleDims(axle_clearance=0.05, press_clearance=0.05))
    cap_fit: float = 0.05  # ring A
    cup_fit: float = 0.05  # cup F
    shaft_fit: float = 0.15  # hub L
    wall: float = 2.5
    skirt_len: float = 12.0  # down the tower from its rim
    lip_d: float = 28.0  # the cone's inner edge, clear of the pin's ends
    floor_t: float = 2.5
    cup_h: float = 8.0
    boss_recess_d: float = 8.5  # the front boss is Ø7.9 at its base
    boss_recess_h: float = 1.8  # the boss stands 1.6
    shaft_hole_d: float = 3.5
    window_w: float = 12.0
    hub_r: float = 8.0
    sleeve_play: float = 0.25  # radial, over the axle's top
    slot_w: float = 2.4  # for 1.75 filament
    hub_gap: float = 0.6  # hub to the washer below
    sleeve_gap: float = 1.0  # axle top to the sleeve's bridged ceiling, which may sag
    # The cap's ceiling is a 45 deg cone all the way in to the shaft hole,
    # so nothing there prints as a bridge (a flat Ø10 ceiling dropped a
    # strand across the hole). The hub's top is a cone too, 0.5 mm inside it.
    hub_top_r: float = 2.25  # the hub's tip; 1.1 mm of wall round the shaft
    hub_top_gap: float = 1.0  # hub's tip below the cone's
    pin_len: float = 20.0

    @property
    def can_d(self) -> float:
        return MEASURED_DIMS["can_diameter"]

    @property
    def shaft_below_face(self) -> float:
        """Shaft length past the face, boss included."""
        return MEASURED_DIMS["shaft_length"]

    @property
    def skirt_r(self) -> float:
        return self.spindle.tower_od / 2 + self.cap_fit

    @property
    def floor_z(self) -> float:
        """Underside of the cup floor: the shaft (past the floor) must reach
        down into the hub's top, and the sleeve must clear the axle's top."""
        return self.hub_top + self.hub_top_gap

    @property
    def hub_top(self) -> float:
        return self.spindle.axle_top + self.sleeve_gap + 1.0 + self.grip

    @property
    def grip(self) -> float:
        """Shaft inside the hub."""
        return self.shaft_below_face - self.floor_t - self.hub_top_gap - 0.4

    @property
    def face_z(self) -> float:
        return self.floor_z + self.floor_t


def make_cap(m: MountDims) -> Part:
    s = m.spindle
    r_in, r_out = m.skirt_r, m.skirt_r + m.wall
    z0 = s.span - m.skirt_len
    cap = tube(r_out, r_in, m.floor_z - z0, z0)
    # 45 deg cone resting on the tower's top outer edge
    lip_h = r_in - m.lip_d / 2
    cap += Pos(0, 0, s.span) * (Cylinder(r_in, lip_h, align=ALIGN_BOTTOM)
                                - Cone(r_in, m.lip_d / 2, lip_h, align=ALIGN_BOTTOM))
    # floor, with a 45 deg cone under it right in to the shaft hole
    tip_r = m.shaft_hole_d / 2
    cone_h = r_in - tip_r
    cap += Pos(0, 0, m.floor_z - cone_h) * (
        Cylinder(r_in, cone_h, align=ALIGN_BOTTOM)
        - Cone(r_in, tip_r, cone_h, align=ALIGN_BOTTOM))
    cup_r = m.can_d / 2 + m.cup_fit
    cup_out = cup_r + m.wall
    # the cup is wider than the skirt: a 45 deg step out under the floor
    step = cup_out - r_out
    cap += Pos(0, 0, m.floor_z - step) * (Cone(r_out, cup_out, step, align=ALIGN_BOTTOM)
                                          - Cylinder(r_in, step, align=ALIGN_BOTTOM))
    cap += Pos(0, 0, m.floor_z) * Cylinder(cup_out, m.floor_t, align=ALIGN_BOTTOM)
    cap += tube(cup_out, cup_r, m.cup_h, m.face_z)
    cap -= mouth(cup_r, 0.5, m.face_z + m.cup_h, up=False)
    cap -= mouth(r_in, 0.5, z0, up=True)
    cap -= Pos(0, 0, m.face_z - m.boss_recess_h) * Cylinder(
        m.boss_recess_d / 2, m.boss_recess_h + 0.01, align=ALIGN_BOTTOM)
    cap -= Pos(0, 0, m.floor_z - 1) * Cylinder(m.shaft_hole_d / 2, m.floor_t + 2, align=ALIGN_BOTTOM)
    # windows to line the hub's slots up with the pin; pointed tops print
    # without a bridge
    wz0 = s.span + lip_h + 0.3
    gable = m.window_w / 2
    wz1 = m.floor_z - cone_h - 0.5 - gable
    for a in (0, 180):
        x = r_in - 0.5 + 2 * m.wall
        win = Pos(x, 0, wz0) * Box(4 * m.wall, m.window_w, wz1 - wz0, align=ALIGN_BOTTOM)
        win += Pos(x, 0, wz1) * Rot(45, 0, 0) * Box(4 * m.wall, gable * 2 ** 0.5, gable * 2 ** 0.5)
        cap -= Rot(0, 0, a) * win
    return cap


def make_hub(m: MountDims) -> Part:
    s = m.spindle
    z_bot = s.span + s.washer_t + m.hub_gap
    z_top = m.hub_top
    bevel = m.hub_r - m.hub_top_r
    hub = Pos(0, 0, z_bot) * Cylinder(m.hub_r, z_top - bevel - z_bot, align=ALIGN_BOTTOM)
    hub += Pos(0, 0, z_top - bevel) * Cone(m.hub_r, m.hub_top_r, bevel, align=ALIGN_BOTTOM)
    sleeve_top = s.axle_top + m.sleeve_gap
    hub -= Pos(0, 0, z_bot - 0.01) * Cylinder(s.axle_d / 2 + m.sleeve_play, sleeve_top - z_bot + 0.01,
                                             align=ALIGN_BOTTOM)
    hub -= mouth(s.axle_d / 2 + m.sleeve_play, 0.5, z_bot, up=True)
    slot_top = s.pin_z + s.pin_hole_d / 2 + 0.8
    hub -= Pos(0, 0, z_bot - 0.01) * Box(2 * m.hub_r + 2, m.slot_w, slot_top - z_bot, align=ALIGN_BOTTOM)
    shaft_r = MEASURED_DIMS["shaft_diameter"] / 2 + m.shaft_fit
    hub -= Pos(0, 0, z_top - m.grip - 0.4) * Cylinder(shaft_r, m.grip + 0.41, align=ALIGN_BOTTOM)
    hub -= mouth(shaft_r, 0.3, z_top, up=False)
    return hub


def make_long_pin(m: MountDims) -> Part:
    s = m.spindle
    z = s.pin_z - (s.pin_hole_d - s.pin_d) / 2
    return Pos(0, 0, z) * Rot(0, 90, 0) * Cylinder(s.pin_d / 2, m.pin_len)


def canon(m: MountDims) -> Part:
    """The motor face-down in its cup: its own frame has the face at Z=0,
    shaft -Z, so it goes in as built."""
    return Pos(0, 0, m.face_z) * make_motor(Ck35Dims(**MEASURED_DIMS))


def check(ok: bool, text: str) -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    return ok


def checks(m: MountDims) -> bool:
    s = m.spindle
    cap, hub, pin = make_cap(m), make_hub(m), make_long_pin(m)
    tower, rotor, washer = make_tower(s), make_rotor(s), make_washer(s)
    (lo_o, lo_i), (hi_o, hi_i) = bearings(s)
    motor = canon(m)
    ok = True
    v = ivol(cap, tower) + ivol(cap, hi_o)
    ok &= check(v < 1e-3, f"cap slides over the tower and lands on its rim, {v:.3f} mm^3")
    turning = rotor + washer + pin + hub + hi_i + lo_i
    v = ivol(cap, turning)
    ok &= check(v < 1e-3, f"everything that turns clears the cap, {v:.3f} mm^3")
    v = ivol(hub, rotor + washer)
    ok &= check(v < 1e-3, f"hub sleeve slides over the axle top, clear of the washer, {v:.3f} mm^3")
    v = ivol(hub, pin)
    ok &= check(v < 1e-3, f"the pin sits in the hub's slots, {v:.3f} mm^3")
    reach = m.pin_len / 2 - m.hub_r
    ok &= check(reach >= 1.0, f"a {m.pin_len:g} mm pin reaches {reach:.1f} mm past the hub")
    v = ivol(motor, cap)
    ok &= check(v < 1e-3, f"the Canon sits in its cup and the boss in its recess, {v:.3f} mm^3")
    v = ivol(motor, hub)
    ok &= check(v < 1e-3, f"the shaft goes {m.grip:.1f} mm into the hub, tip clear, {v:.3f} mm^3")
    v = ivol(cap, hub)
    radial = m.shaft_hole_d / 2 + m.hub_top_gap - m.hub_top_r
    ok &= check(v < 1e-3 and radial >= 0.4,
                f"hub's cone runs {radial:.2f} mm inside the cap's, {v:.3f} mm^3")
    print(f"  stack: cap floor at Z {m.floor_z:.1f}, Canon face at {m.face_z:.1f}, "
          f"cap {m.floor_z + m.floor_t + m.cup_h - (s.span - m.skirt_len):.1f} mm tall")
    return ok


def render(m: MountDims) -> None:
    import numpy as np

    from xt60_twin import mesh_of, render_stills, stage

    s = m.spindle
    keep = Box(400, 400, 400, align=(Align.MIN, Align.CENTER, Align.CENTER))
    pieces = [(make_tower(s), "holder"), (make_rotor(s), "battery"), (make_washer(s), "xt60"),
              (make_long_pin(m), "red"), (make_cap(m), "amber"), (make_hub(m), "pi"),
              (canon(m), "wheel")]
    for o, i in bearings(s):
        pieces += [(o, "motor"), (i, "motor")]
    statics = [(f"p{k}", mesh_of(p & keep, 0.02), look) for k, (p, look) in enumerate(pieces)]
    whole = [(f"w{k}", mesh_of(Pos(0, 300, 0) * p, 0.03), look)
             for k, (p, look) in enumerate(pieces[:7])]
    cams = [("section", np.array([-400.0, 0.0, 55.0]), np.array([0.0, 0.0, 55.0]), 50.0, 180.0),
            ("whole", np.array([300.0, 300 - 360.0, 260.0]), np.array([0.0, 300.0, 45.0]), 50.0, 200.0)]
    render_stills("canon_mount", stage(statics + whole, [], cams), [c[0] for c in cams], w=900)


def main() -> None:
    m = MountDims()
    print("PASS/FAIL checks:")
    ok = checks(m)
    cap, hub = make_cap(m), make_hub(m)
    s = m.spindle
    plate = Pos(0, 0, -(s.span - m.skirt_len)) * cap
    hb = hub.bounding_box()
    plate += Pos(45, 0, -hb.min.Z) * hub
    ok &= check(len(plate.solids()) == 2, f"print plate: cap and hub, {len(plate.solids())} parts")
    export_stl(plate, HERE / "canon_mount.stl")
    print("Exported canon_mount.stl")
    render(m)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
