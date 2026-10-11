"""Reference model of the robot car's swivel caster: a small bought
furniture caster with a Ø24.7 rubber wheel, swivelling under a square
steel top plate that has a hole in each corner.

This is a *reference* part: it models the bought hardware so a mount can be
designed around it. It is not meant to be printed.

Measured by the user unless marked "est" (read off photos). The plate is
40.2 mm across the middle of each side, a little less toward the corners,
and 1.5 mm thick. Its top face
is flat: the swivel rivet sits flush. On the underside a pressed bearing
ring stands out, its edge about 5 mm in from the middle of each side, so
a 5 mm strip along every edge is flat on both faces. That strip is what a
slide-in mount grips. The fork hangs from the ring and turns on it.

Frame: origin at the centre of the plate's top face, plate edges along X
and Y, wheel below (-Z). At heading 0 the wheel trails toward +X.

Run with:  uv run parts/swivel_caster.py   (exports swivel_caster.stl, gitignored)
"""

import math
from dataclasses import dataclass

from build123d import Axis, Box, Cylinder, Part, Plane, Pos, Rot, export_stl, extrude, fillet
from build123d import Polyline, make_face


@dataclass
class CasterDims:
    plate: float = 40.2  # square, across the middle of each side
    plate_t: float = 1.5
    corner_r: float = 3.0  # est
    hole_d: float = 5.3
    hole_pitch: float = 29.2  # centre to centre (23.9 between near edges), both ways
    ring_d: float = 30.0  # bearing ring under the plate
    ring_h: float = 3.0  # est, below the plate's underside
    height: float = 34.0  # floor to the plate's top face
    wheel_d: float = 24.7
    wheel_w: float = 12.0  # est
    trail: float = 12.0  # est, swivel axis to axle, horizontal
    fork_t: float = 1.5  # est, sheet thickness
    fork_gap: float = 1.0  # est, wheel face to fork leg

    @property
    def axle_z(self) -> float:
        return -(self.height - self.wheel_d / 2)

    @property
    def wheel_top_below_plate(self) -> float:
        """Gap from the plate's underside down to the top of the wheel."""
        return self.height - self.plate_t - self.wheel_d


def make_plate(d: CasterDims) -> Part:
    p = Pos(0, 0, -d.plate_t / 2) * Box(d.plate, d.plate, d.plate_t)
    p = fillet(p.edges().filter_by(Axis.Z), d.corner_r)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p -= Pos(sx * d.hole_pitch / 2, sy * d.hole_pitch / 2, -d.plate_t / 2) * Cylinder(
                d.hole_d / 2, d.plate_t * 2)
    return p


def make_ring(d: CasterDims) -> Part:
    return Pos(0, 0, -d.plate_t - d.ring_h / 2) * Cylinder(d.ring_d / 2, d.ring_h)


def make_fork(d: CasterDims) -> Part:
    """est throughout: two side plates from under the ring down to the axle."""
    top = -d.plate_t - d.ring_h
    boss_r = 4.5
    pts = [(-d.ring_d / 2 + 4, top), (d.ring_d / 2 - 2, top),
           (d.trail + boss_r, d.axle_z), (d.trail - boss_r, d.axle_z - boss_r * 0.6)]
    leg = extrude(Plane.XZ * make_face(Polyline(*pts, close=True)), amount=d.fork_t)
    y = d.wheel_w / 2 + d.fork_gap
    fork = Pos(0, y + d.fork_t, 0) * leg + Pos(0, -y, 0) * leg
    fork += Pos(0, 0, top - d.fork_t / 2) * Box(d.ring_d - 6, 2 * (y + d.fork_t), d.fork_t)
    return fork


def make_wheel(d: CasterDims) -> Part:
    return Pos(d.trail, 0, d.axle_z) * Rot(90, 0, 0) * Cylinder(d.wheel_d / 2, d.wheel_w)


def make_caster(d: CasterDims | None = None, heading: float = 0.0) -> dict:
    """name -> Part, the fork and wheel turned `heading` degrees about the
    swivel axis."""
    d = d or CasterDims()
    turn = Rot(0, 0, heading)
    return {
        "plate": make_plate(d),
        "ring": make_ring(d),
        "fork": turn * make_fork(d),
        "wheel": turn * make_wheel(d),
    }


if __name__ == "__main__":
    d = CasterDims()
    parts = make_caster(d)
    whole = sum(parts.values(), Part())
    bb = whole.bounding_box()
    print(f"Caster: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm "
          f"(floor to plate top {-bb.min.Z:.2f}, spec {d.height:g})")
    print(f"Wheel top {d.wheel_top_below_plate:.1f} mm below the plate's underside; "
          f"swing radius at the floor {d.trail + d.wheel_d / 2:.1f} (est trail)")
    assert math.isclose(-bb.min.Z, d.height, abs_tol=0.01)
    export_stl(whole, "swivel_caster.stl")
    print("Exported swivel_caster.stl")
