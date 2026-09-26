"""robot_car: snap-in well for the power switch (cad/parts/kcd1_rocker.py).

chassis.py builds the well into the plate (switch_well, at switch_x /
switch_y). This file owns its geometry, proves the switch can be put into
it on the car, and exports the fit coupon.

THE WELL

A raised panel with the switch's cutout in it, standing on two end walls.
The switch goes in from above; the clips on its short ends spring out under
the panel and their upper slope pulls the flange down onto it. So:

- The cutout is 19.0 x 13.0, the standard size for this switch family:
  the 18.6 mm long axis at the body's bottom has to pass through, and the
  detents just under the flange (12.8 across) centre the body in the 13.0.
- The panel is thinner than the clips' bulge depth (Kcd1Dims.clip_peak),
  so the slope, not the bulge, meets its lower edge.
- The end walls stand outboard of the clips' relaxed span. 45 deg gussets
  under the long bars cut the bars' printed bridge to 10 mm; they sit
  beside the body, clear of the clips in the middle of each short end.
- Both long sides are open underneath. The terminals are factory-bent over
  toward one long side and reach 6.2 mm past the body, so the switch goes
  in shifted away from them, drops until the bent legs are under the
  panel, slides back and presses down. roll_in_check() searches for that
  motion on the car. The open sides are also where the wires come in.
- The terminals' lowest point is floor_gap above the plate: the switch
  sits as low as it can while the tips stay off the plate.

On the car the long axis runs across it, so the rocker toggles left/right,
and the terminals point forward, toward the motor buck.

Run with:  uv run robot_car/switch_well.py
Exports (gitignored): switch_well_coupon.stl/.step, switch_well.png (roll-in
sections), switch_well_3d.png (usdrecord stills).
"""

import sys
import tempfile
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

import numpy as np  # noqa: E402
from build123d import Box, Part, Plane, Pos, Text, export_step, export_stl, extrude  # noqa: E402

from kcd1_rocker import Kcd1Dims, clip_x, make_kcd1, section_profile, xz_prism  # noqa: E402


@dataclass
class WellDims:
    sw: Kcd1Dims = field(default_factory=Kcd1Dims)
    panel_t: float = 3.0  # coupon C, the best fit of the three
    cutout_fit_long: float = 0.2  # per end, past the 18.6 mm body bottom
    cutout_fit_short: float = 0.1  # per side, past the 12.8 mm detents
    rim: float = 1.0  # panel beyond the flange, all round
    wall_t: float = 1.6  # end walls
    clip_clearance: float = 0.25  # end wall inner face beyond the relaxed clip bulge
    floor_gap: float = 1.0  # terminals' lowest point above the plate top
    bridge_max: float = 10.0  # print_lint's bridge limit; the gussets keep under it

    @property
    def cut_x(self) -> float:
        return max(self.sw.body_x, self.sw.neck_x) + 2 * self.cutout_fit_long

    @property
    def cut_y(self) -> float:
        return max(self.sw.body_y, self.sw.neck_y) + 2 * self.cutout_fit_short

    @property
    def wall_in(self) -> float:  # end wall inner face, from the centre
        return self.sw.clip_span / 2 + self.clip_clearance

    @property
    def half_x(self) -> float:  # panel half-length (long axis)
        return max(self.sw.flange_x / 2 + self.rim, self.wall_in + self.wall_t)

    @property
    def half_y(self) -> float:  # panel half-width (short axis)
        return self.sw.flange_y / 2 + self.rim

    @property
    def gusset(self) -> float:
        """45 deg gusset under each long bar at each end wall, sized so the
        bar's unsupported span stays under bridge_max."""
        return max(0.0, self.wall_in - self.bridge_max / 2 + 0.2)

    @property
    def height(self) -> float:  # panel top above the plate top
        return self.floor_gap + self.sw.lowest


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def make_well(w: WellDims) -> Part:
    """In the switch's own frame: origin at the panel top centre, long axis
    X, terminals toward +Y, the plate top at z = -height."""
    H, t = w.height, w.panel_t
    well = rbox(-w.half_x, w.half_x, -w.half_y, w.half_y, -t, 0)
    well -= rbox(-w.cut_x / 2, w.cut_x / 2, -w.cut_y / 2, w.cut_y / 2, -t - 1, 1)
    for s in (-1, 1):
        x0, x1 = sorted((s * w.wall_in, s * (w.wall_in + w.wall_t)))
        well += rbox(x0, x1, -w.half_y, w.half_y, -H, -t + 0.01)
        # gussets under both long bars, clear of the clips in the middle
        g, xi = w.gusset, s * w.wall_in
        tri = [(xi + s * 0.01, -t + 0.01), (xi - s * g, -t + 0.01), (xi + s * 0.01, -t - g)]
        for y0, y1 in ((w.cut_y / 2, w.half_y), (-w.half_y, -w.cut_y / 2)):
            well += xz_prism(tri, y0, y1)
    return well


# The clips' real profile is an arc, drawn here as two straight flanks, so
# how far a clip reaches past the cutout edge under a given panel is only
# known once printed. The coupon tries three panels. RESULT (black PLA
# Basic, X2D, 2026-09-26, printed with floor_gap 4.0 -- 3 mm taller than
# the car's well now): C fits best, and 3.0 is the car's panel.
COUPON_PANELS = (("A", 2.0), ("B", 2.5), ("C", 3.0))


def coupon(base_t: float = 2.0, gap: float = 4.0) -> Part:
    """One well per COUPON_PANELS entry, at car height, side by side along
    their short axis on one base, each lettered on the base beside it."""
    ws = [(letter, replace(WellDims(), panel_t=t)) for letter, t in COUPON_PANELS]
    w0 = ws[0][1]
    pitch = 2 * w0.half_y + gap + 6
    n = len(ws)
    plate = rbox(-w0.half_x - 9, w0.half_x + 2, -(n * pitch) / 2, (n * pitch) / 2, 0, base_t)
    for i, (letter, w) in enumerate(ws):
        y = (i - (n - 1) / 2) * pitch
        plate += Pos(0, y, base_t + w.height) * make_well(w)
        text = Text(letter, font_size=6, font="Arial Black")
        plate += extrude(Plane.XY.offset(base_t) * Pos(-w0.half_x - 4.5, y) * text, amount=0.8)
    return plate


# ---------------------------------------------------------------------------
# checks on the car
# ---------------------------------------------------------------------------

RESULTS = []


def check(name: str, ok: bool, detail: str) -> None:
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def ivol(a: Part, b: Part) -> float:
    r = a & b
    return 0.0 if r is None else abs(r.volume)


def to_mesh(part: Part):
    import trimesh

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.stl"
        export_stl(part, p)
        return trimesh.load_mesh(p)


def neighbour_sections(w: WellDims, pos, parts) -> list:
    """The obstacles in the switch's Y-Z plane (switch frame), one union
    per terminal: every part cut at that terminal's chassis Y."""
    import shapely
    from shapely.ops import unary_union

    meshes = [to_mesh(p) for p in parts]
    out = []
    for i in (-1, 0, 1):
        y_car = pos[1] - i * w.sw.terminal_pitch
        polys = []
        for m in meshes:
            s = m.section(plane_origin=(0, y_car, 0), plane_normal=(0, 1, 0))
            if s is None:
                continue
            for loop in s.discrete:  # chassis (X, Z) -> switch frame (y, z)
                ring = [(p[0] - pos[0], p[2] - pos[2]) for p in loop]
                if len(ring) >= 3:
                    polys.append(shapely.Polygon(ring).buffer(0))
        out.append(unary_union(polys))
    return out


def roll_in_check(w: WellDims, obstacles: list, step=0.5, dtheta=2.5):
    """Motion search in the switch's Y-Z plane. A pose is (dy, dz, theta):
    the switch rotated by theta about its origin, then moved by dy, dz from
    its seat. Every pose on a grid is tested against the obstacles in all
    three terminal sections; the switch can be put in iff its seat is
    connected, through free poses, to a pose entirely above the panel.

    The switch profile is shrunk 0.08 mm so resting contact isn't a
    collision, and sampled on its outline every 0.1 mm and inside on a
    0.4 mm grid, so an obstacle lying wholly inside the profile is caught
    too (the smallest obstacle, a 0.6 mm tray ledge, always holds a grid
    point). Grid steps (0.5 mm, 2.5 deg: <= 0.9 mm at the tips) are below
    the thinnest obstacle plus the 0.64 mm terminal strip, so nothing
    tunnels between neighbouring poses. Returns (ok, poses from the free
    pose down to the seat)."""
    import shapely

    prof = section_profile(w.sw).buffer(-0.08)
    pts = []
    for ring in [prof.exterior, *prof.interiors]:
        n = max(int(ring.length / 0.1), 8)
        pts += [ring.interpolate(k / n, normalized=True).coords[0] for k in range(n)]
    x0, z0, x1, z1 = prof.bounds
    gx, gz = np.meshgrid(np.arange(x0, x1, 0.4), np.arange(z0, z1, 0.4))
    inner = shapely.contains_xy(prof, gx, gz)
    pts = np.vstack([np.array(pts), np.column_stack([gx[inner], gz[inner]])])

    res = 0.05
    y_lo, y_hi, z_lo, z_hi = -40.0, 40.0, -w.height - 2, 20.0
    gy = np.arange(y_lo, y_hi, res) + res / 2
    gz = np.arange(z_lo, z_hi, res) + res / 2
    YY, ZZ = np.meshgrid(gy, gz, indexing="ij")
    occ = np.logical_or.reduce([shapely.contains_xy(o, YY, ZZ) for o in obstacles])

    dys = np.arange(-14, 14 + 1e-9, step)
    dzs = np.arange(0, 28 + 1e-9, step)
    ths = np.arange(-90, 90 + 1e-9, dtheta)
    free = np.zeros((len(dys), len(dzs), len(ths)), bool)
    above = np.zeros_like(free)
    for k, th in enumerate(ths):
        a = np.radians(th)
        rot = pts @ np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
        py = rot[None, None, :, 0] + dys[:, None, None]  # (ndy, ndz, npts)
        pz = rot[None, None, :, 1] + dzs[None, :, None]
        py, pz = np.broadcast_arrays(py, pz)
        iy = np.floor((py - y_lo) / res).astype(int)
        iz = np.floor((pz - z_lo) / res).astype(int)
        inside = (iy >= 0) & (iy < len(gy)) & (iz >= 0) & (iz < len(gz))
        hit = np.zeros(py.shape, bool)
        hit[inside] = occ[iy[inside], iz[inside]]
        free[:, :, k] = ~hit.any(axis=2)
        above[:, :, k] = pz.min(axis=2) > 0.2

    start = (int(np.argmin(abs(dys))), 0, int(np.argmin(abs(ths))))
    if not free[start]:
        return False, []
    prev = {start: None}
    q = deque([start])
    goal = None
    while q:
        n = q.popleft()
        if above[n]:
            goal = n
            break
        for ax in range(3):
            for s in (-1, 1):
                m = list(n)
                m[ax] += s
                m = tuple(m)
                if 0 <= m[ax] < free.shape[ax] and free[m] and m not in prev:
                    prev[m] = n
                    q.append(m)
    path = []
    while goal is not None:
        path.append((dys[goal[0]], dzs[goal[1]], ths[goal[2]]))
        goal = prev[goal]
    return bool(path), path


def pose(profile, p):
    from shapely.affinity import rotate, translate

    dy, dz, th = p
    return translate(rotate(profile, th, origin=(0, 0)), dy, dz)


def render(w, pos, obstacles, path, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MPoly

    prof = section_profile(w.sw)

    def draw(ax, geom, **kw):
        for g in getattr(geom, "geoms", [geom]):
            if not g.is_empty:
                ax.add_patch(MPoly(np.array(g.exterior.coords), closed=True, **kw))

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))
    names = ["inboard terminal", "middle terminal", "outboard terminal"]
    for ax, obs, name, i in zip(axes, obstacles, names, (1, 0, -1)):
        y_car = pos[1] - i * w.sw.terminal_pitch
        draw(ax, obs, facecolor="#5a6472", edgecolor="k", lw=0.3)
        for p in path[:: max(len(path) // 8, 1)]:
            draw(ax, pose(prof, p), facecolor="none", edgecolor="#e07b39", lw=0.8)
        draw(ax, prof, facecolor="#222222", alpha=0.85)
        ax.set_xlim(-22, 26); ax.set_ylim(-w.height - 1, 24); ax.set_aspect("equal")
        ax.grid(alpha=0.3)
        ax.set_title(f"{name}, chassis Y={y_car:.1f}")
        ax.set_xlabel(f"mm along chassis X from X={pos[0]:g}  (<- cradle | buck ->)")
        ax.set_ylabel("mm from the panel top")
    fig.suptitle("Switch seated (black) and the insertion path found (orange outlines). "
                 "Grey: chassis with the well, lid, buck board with its headers", fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(f"Wrote {out.name}")


def render_3d(out: Path) -> None:
    """Stills of the switch on the car through macOS usdrecord, the same USD
    scene twin.py writes (matplotlib's 3D sorts whole triangles and shows
    hidden geometry through the parts)."""
    import subprocess

    import twin
    from lid_twin import camera_prim
    from render_assembly import assembly_parts

    d, parts = assembly_parts()
    target = np.array([d.switch_x + 8, d.switch_y - 4, 12.0])
    cams = [("above_left", target + (40, 150, 230)), ("front_left", target + (200, 150, 120)),
            ("front", target + (230, -20, 60))]
    text = twin.usda(twin.meshes(parts, 0.02, 0.2)).rstrip().rstrip("}")
    for name, eye in cams:
        text += "\n".join(camera_prim(name, eye, target)) + "\n"
    text += "}\n"
    with tempfile.TemporaryDirectory() as tmp:
        scene = Path(tmp) / "switch.usda"
        scene.write_text(text)
        stills = []
        for name, _ in cams:
            png = Path(tmp) / f"{name}.png"
            subprocess.run(["usdrecord", "--imageWidth", "900", "--cam", name, str(scene), str(png)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stills.append(png)
        inputs = sum((["-i", str(p)] for p in stills), [])
        n = len(stills)
        chain = "".join(f"[{i}]" for i in range(n)) + f"hstack=inputs={n}[v];"
        chain += f"color=c=0xeeeeee:s={900 * n}x540[bg];[bg][v]overlay"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", chain,
                        "-frames:v", "1", str(out)], check=True)
    print(f"Wrote {out.name}")


def main() -> None:
    from build123d import Axis

    from chassis import ChassisDims, buck_board_pose, build, switch_placement
    from p1_mp1584 import Mp1584Dims, make_mp1584

    d = ChassisDims()
    w = d.well
    c = build(d)
    pos = (d.switch_x, d.switch_y, d.plate_thickness + w.height)
    sw = switch_placement(d)

    print(f"Well: panel {2 * w.half_x:.1f} x {2 * w.half_y:.1f} x {w.panel_t:g} mm, "
          f"cutout {w.cut_x:.2f} x {w.cut_y:.2f}, panel top Z={pos[2]:.1f} "
          f"({w.height:.1f} above the plate), rocker top Z="
          f"{pos[2] + w.sw.flange_t + w.sw.rocker_h:.1f}")
    print(f"On the car: switch centre X={pos[0]:g} Y={pos[1]:g}; "
          f"terminal tips reach X={pos[0] + w.sw.tip_y:.2f}\n")

    v = ivol(make_well(w), make_kcd1(w.sw, clips=False))
    check("switch seats in the well without interference (clips flex)", v < 0.5,
          f"{v:.3f} mm^3")
    check("panel thinner than the clip bulge depth", w.panel_t < w.sw.clip_peak,
          f"panel {w.panel_t:g}, bulge {w.sw.clip_peak:g} down")
    check("end walls clear the relaxed clips", w.wall_in > w.sw.clip_span / 2,
          f"{w.wall_in - w.sw.clip_span / 2:.2f} mm")
    print("       clip reach past the cutout edge at the panel's underside "
          "(two-flank model, the real arc reaches further):")
    for letter, t in COUPON_PANELS:
        mark = "  <- car" if t == w.panel_t else ""
        print(f"         {letter}: panel {t:g} -> {clip_x(w.sw, t) - w.cut_x / 2:+.2f} mm{mark}")
    # chassis.py's overlap check covers the well and switch against every
    # footprint; what matters here is the room left around the terminals
    tips = c.footprints["buck_motor"].distance_to(sw)
    check("room to solder at the terminal tips", tips >= 3.0,
          f"{tips:.2f} mm from the tips to the motor buck's tray (>= 3.0)")
    body = c.footprints["cradle+Y"].distance_to(sw)
    print(f"       switch body to the cradle: {body:.2f} mm")

    mp = Mp1584Dims()
    x, y, rot = buck_board_pose(d, +1)
    board = Pos(x, y, d.plate_thickness + d.tray_standoff + mp.board_thickness / 2) * \
        make_mp1584(mp, with_headers=True, with_dupont=True, mounted=True).rotate(Axis.Z, rot)
    obstacles = neighbour_sections(w, pos, [c.plate, c.lids[0], board])
    ok, path = roll_in_check(w, obstacles)
    detail = (f"{len(path)} poses, up to {max(abs(p[2]) for p in path):g} deg of tilt"
              if ok else "no collision-free path found")
    check("switch can be put into its seat", ok, detail)

    cp = coupon()
    export_stl(cp, HERE / "switch_well_coupon.stl")
    export_step(cp, HERE / "switch_well_coupon.step")
    render(w, pos, obstacles, path, HERE / "switch_well.png")
    render_3d(HERE / "switch_well_3d.png")
    ok = all(RESULTS)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
