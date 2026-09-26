"""Reference model of the mini snap-in rocker switch (KCD1 style, marked
6A 250VAC / 10A 125VAC, three terminals), the robot car's power switch
(cad/robot_car/WIRING.md: pack -> fuse -> switch -> both bucks).

This is a *reference* part: it models the bought hardware so a mount can be
designed around it. It is not meant to be printed.

Calipered by the user unless marked "est" (read off photos). The body is
18.6 x 12 at the bottom and 17.2 x 12.8 just under the flange, where small
detents on the long faces centre it in the cutout.

The switch snaps into a panel cutout from above. A springy clip on each
SHORT end is squeezed in by the cutout edge and springs back out under the
panel. Each clip is a slow arc: it leaves the body right under the flange,
bulges out furthest 4 mm down and is back flush 8.3 mm down, so its upper
slope bears on the panel's lower edge and pulls the flange down onto it for
any panel thinner than the bulge depth. The rocker toggles along the long
axis.

The terminals come from the factory bent over, and don't straighten: each
drops 6.2 mm below the body, turns in a slow arc toward one long side and
reaches 6.2 mm past that side's body face -- well past the flange. The
switch cannot drop straight through a cutout; it has to be rolled in.

Frame: origin at the centre of the flange underside (the panel's top face
once seated), long axis X, short axis Y, rocker up +Z, terminals bent
toward +Y.

Run with:  uv run parts/kcd1_rocker.py   (exports kcd1_rocker.stl, gitignored)
"""

import math
from dataclasses import dataclass

from build123d import Box, Part, Plane, Polyline, Pos, export_stl, extrude, make_face
from shapely.geometry import LineString, Polygon, box


@dataclass
class Kcd1Dims:
    flange_x: float = 20.5
    flange_y: float = 15.0
    flange_t: float = 1.8
    body_x: float = 18.6  # at the bottom
    body_y: float = 12.0  # at the bottom
    # just under the flange: small detents on the long faces widen the body
    # to 12.8, and the long axis narrows to 17.2
    neck_x: float = 17.2
    neck_y: float = 12.8
    neck_h: float = 1.5  # est, how far down the detents run
    body_depth: float = 11.0  # flange underside to body bottom
    rocker_x: float = 15.5  # est
    rocker_y: float = 10.5  # est
    rocker_h: float = 3.8  # above the flange, at the high end

    # snap clips, one per short (X) end: rooted on the 17.2 mm neck at the
    # flange, bulging out to clip_span, back on the 18.6 mm body lower down.
    # Drawn as two straight flanks; the real ones are an arc.
    clip_w: float = 5.0  # est, along Y
    clip_span: float = 20.8  # across both clips at the bulge, relaxed
    clip_peak: float = 4.0  # bulge depth below the flange underside
    clip_len: float = 8.3  # flush with the body again this far down

    # terminals: three in a row along X, bent toward +Y
    terminal_pitch: float = 7.0  # 7.8 outside to outside, less one 0.8 width
    terminal_w: float = 0.8  # along X
    terminal_t: float = 0.8  # est, strip thickness
    terminal_root_y: float = 1.0  # est, where the leg leaves the body
    terminal_bend_r: float = 1.5  # est, centreline radius of the arc
    terminal_bottom: float = 6.3  # lowest point below the body bottom
    terminal_reach: float = 6.2  # tips past the +Y body face

    @property
    def lowest(self) -> float:
        """Lowest point of the switch below the flange underside."""
        return self.body_depth + self.terminal_bottom

    @property
    def tip_y(self) -> float:
        return self.body_y / 2 + self.terminal_reach


def terminal_profile(d: Kcd1Dims) -> Polygon:
    """One terminal's Y-Z section: a strip terminal_t thick along a
    centreline that drops from the body, arcs through 90 deg and runs out
    to the tip."""
    r, t = d.terminal_bend_r, d.terminal_t
    y0 = d.terminal_root_y
    zc = -d.body_depth - d.terminal_bottom + t / 2  # horizontal leg centreline
    pts = [(y0, -d.body_depth + 0.3), (y0, zc + r)]
    arc = [math.pi / 2 * i / 12 for i in range(1, 13)]
    pts += [(y0 + r - r * math.cos(a), zc + r - r * math.sin(a)) for a in arc]
    pts += [(d.tip_y, zc)]
    return LineString(pts).buffer(t / 2, cap_style="flat", join_style="round")


def section_profile(d: Kcd1Dims, with_terminal=True) -> Polygon:
    """The switch's Y-Z section through a terminal (clips excluded: they are
    on the short ends, and they flex)."""
    s = box(-d.flange_y / 2, 0, d.flange_y / 2, d.flange_t)
    s = s.union(box(-d.rocker_y / 2, d.flange_t, d.rocker_y / 2, d.flange_t + d.rocker_h))
    s = s.union(box(-d.body_y / 2, -d.body_depth, d.body_y / 2, 0))
    s = s.union(box(-d.neck_y / 2, -d.neck_h, d.neck_y / 2, 0))
    return s.union(terminal_profile(d)) if with_terminal else s


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def xz_prism(points, y0, y1) -> Part:
    face = make_face(Polyline(*[(x, z) for x, z in points], close=True))
    return Pos(0, y1, 0) * extrude(Plane.XZ * face, amount=y1 - y0)


def yz_prism(points, x0, x1) -> Part:
    face = make_face(Polyline(*[(y, z) for y, z in points], close=True))
    return Pos(x0, 0, 0) * extrude(Plane.YZ * face, amount=x1 - x0)


def clip_x(d: Kcd1Dims, depth: float) -> float:
    """How far out from the centre a clip reaches at `depth` below the
    flange, relaxed (on the two-flank model)."""
    root, tip, foot = d.neck_x / 2, d.clip_span / 2, d.body_x / 2
    if depth <= d.clip_peak:
        return root + (tip - root) * depth / d.clip_peak
    return tip + (foot - tip) * min(depth - d.clip_peak, d.clip_len - d.clip_peak) / (
        d.clip_len - d.clip_peak)


def make_kcd1(d: Kcd1Dims | None = None, clips: bool = True) -> Part:
    """clips=False leaves the snap clips off: they flex out of the way of a
    cutout edge, so a fit check against rigid geometry must skip them."""
    d = d or Kcd1Dims()
    sw = rbox(-d.flange_x / 2, d.flange_x / 2, -d.flange_y / 2, d.flange_y / 2, 0, d.flange_t)
    sw += rbox(-d.rocker_x / 2, d.rocker_x / 2, -d.rocker_y / 2, d.rocker_y / 2,
               d.flange_t, d.flange_t + d.rocker_h)
    sw += rbox(-d.body_x / 2, d.body_x / 2, -d.body_y / 2, d.body_y / 2, -d.body_depth, 0)
    sw += rbox(-d.neck_x / 2, d.neck_x / 2, -d.neck_y / 2, d.neck_y / 2, -d.neck_h, 0)
    for s in (-1, 1) if clips else ():
        prof = [(s * d.neck_x / 2, -0.01), (s * d.clip_span / 2, -d.clip_peak),
                (s * d.body_x / 2, -d.clip_len), (0, -d.clip_len), (0, -0.01)]
        sw += xz_prism(prof, -d.clip_w / 2, d.clip_w / 2)
    term = list(terminal_profile(d).exterior.coords)[:-1]
    for i in (-1, 0, 1):
        x = i * d.terminal_pitch
        sw += yz_prism(term, x - d.terminal_w / 2, x + d.terminal_w / 2)
    return sw


if __name__ == "__main__":
    from pathlib import Path

    export_stl(make_kcd1(), Path(__file__).parent / "kcd1_rocker.stl")
    print("Exported kcd1_rocker.stl")
