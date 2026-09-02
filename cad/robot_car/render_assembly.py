"""robot_car: colour-coded render of the full prototype assembly.

Builds every part in its installed position (the same placement helpers
assembly.py's checks use -- nothing is re-derived here), gives each one a
distinct colour and renders an isometric view plus a labelled top plan and
two elevations, so the layout can be read at a glance: what sits where,
how tall it stands, and which module is which.

Mirrored pairs (the two motors, the two wheels) are kept as SEPARATE parts
even though they share a colour -- merged into one part their convex hull
in plan view bridges the gap between them and covers the whole plate.

Run with:  uv run robot_car/render_assembly.py
Writes robot_car/car_assembly_colour.png (gitignored).
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from build123d import Pos, export_stl
from matplotlib.patches import Patch, Polygon
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.spatial import ConvexHull

from assembly import (
    battery_placement, pi_placement, tray_placement, wheel_placement,
)
from chassis import ChassisDims, build, motor_placement
from d2_drv8833 import Drv8833Dims, make_drv8833
from p1_mp1584 import Mp1584Dims, make_mp1584
from wheel import WheelDims

# module -> colour. Deliberately NOT the filament colours: the point is to
# tell the modules apart, not to preview the print.
COLOURS = {
    "chassis plate": "#5a6472",
    "N20 gearmotor": "#e07b39",
    "drive wheel": "#7d5ba6",
    "front skid": "#c9b458",
    "Pi Zero 2 W": "#2e9e5b",
    "DRV8833 driver": "#d64550",
    "MP1584EN buck": "#39a8c4",
    "LiPo pack": "#3b6fd4",
}

# module -> text anchor for the top-plan leader lines. Small modules get a
# callout out in clear space rather than a label dropped on a 16 mm board.
PLAN_CALLOUTS = {
    "DRV8833 driver": (-72, 52),
    "MP1584EN buck": (10, -54),
    "N20 gearmotor": (-92, 26),
    "drive wheel": (-24, 54),
    "front skid": (86, -26),
}
PLAN_INLINE = ("LiPo pack", "Pi Zero 2 W")  # big enough to label in place

# draw order, back to front
ORDER = ["chassis plate", "drive wheel", "N20 gearmotor", "front skid",
         "LiPo pack", "Pi Zero 2 W", "DRV8833 driver", "MP1584EN buck"]


def assembly_parts():
    """[(module, Part)] for every instance in installed position."""
    d = ChassisDims()
    wd = WheelDims()
    c = build(d)
    drv_dims, mp_dims = Drv8833Dims(), Mp1584Dims()

    parts = [
        ("chassis plate", c.plate),
        ("front skid", Pos(d.skid_front_x, 0, -c.skid_below) * c.skid),
        ("Pi Zero 2 W", pi_placement(d)[0]),
        ("DRV8833 driver", tray_placement(
            d.drv_x, d.drv_y, drv_dims.board_thickness, make_drv8833(drv_dims), d,
            standoff=d.drv_tray_standoff)),
        ("MP1584EN buck", tray_placement(
            d.buck_x, d.buck_y, mp_dims.board_thickness, make_mp1584(mp_dims), d)),
        ("LiPo pack", battery_placement(d)[0]),
    ]
    for side in (+1, -1):
        parts.append(("N20 gearmotor", motor_placement(side, d)))
        parts.append(("drive wheel", wheel_placement(side, d, wd)[0]))
    return d, parts


def tessellate(parts):
    """Mesh every part once. Returns the concatenated triangle soup with a
    per-face colour (a single collection, so matplotlib depth-sorts the
    whole scene consistently) and the per-instance vertex clouds."""
    tris, face_colours, clouds = [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (module, part) in enumerate(parts):
            stl = Path(tmp) / f"part_{i}.stl"
            export_stl(part, stl)
            mesh = trimesh.load_mesh(stl)
            t = mesh.vertices[mesh.faces]
            tris.append(t)
            face_colours += [COLOURS[module]] * len(t)
            clouds.append((module, mesh.vertices))
    return np.concatenate(tris), face_colours, clouds


def scene_3d(ax, tris, face_colours, elev, azim, title):
    ax.add_collection3d(Poly3DCollection(
        tris, facecolors=face_colours, edgecolors="#00000018", linewidths=0.04
    ))
    lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
    for i, axis in enumerate("xyz"):  # tight limits, true proportions
        getattr(ax, f"set_{axis}lim")(lo[i], hi[i])
    ax.set_box_aspect(tuple(hi - lo), zoom=1.35)
    ax.set_proj_type("ortho")
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, fontsize=12, pad=-6)


def silhouettes(ax, clouds, i, j, flip_x=False):
    """Fill each instance's convex hull projected onto axes (i, j)."""
    hulls = {}
    for module, verts in clouds:
        p = verts[:, [i, j]].copy()
        if flip_x:
            p[:, 0] *= -1
        hull = p[ConvexHull(p).vertices]
        ax.add_patch(Polygon(
            hull, closed=True, facecolor=COLOURS[module], edgecolor="#2b2b2b",
            linewidth=0.8, zorder=ORDER.index(module),
            alpha=0.75 if module == "chassis plate" else 0.95,
        ))
        hulls.setdefault(module, []).append(hull)
    return hulls


def finish_2d(ax, title, xlabel, ylabel, xlim, ylim):
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_title(title, fontsize=12)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, linewidth=0.3, alpha=0.4)
    ax.set_axisbelow(True)


def plan_2d(ax, clouds, d: ChassisDims):
    hulls = silhouettes(ax, clouds, 0, 1)

    for module in PLAN_INLINE:
        cx, cy = hulls[module][0].mean(axis=0)
        ax.text(cx, cy, module, fontsize=10, fontweight="bold", color="white",
                ha="center", va="center", zorder=50)

    for module, (tx, ty) in PLAN_CALLOUTS.items():
        pts = np.concatenate(hulls[module])  # nearest instance, not the
        target = pts[np.argmin(np.hypot(pts[:, 0] - tx, pts[:, 1] - ty))]
        ax.annotate(
            module, xy=target, xytext=(tx, ty), fontsize=9.5, ha="center",
            va="center", zorder=50,
            bbox=dict(boxstyle="round,pad=0.3", fc="white",
                      ec=COLOURS[module], lw=1.6),
            arrowprops=dict(arrowstyle="-", color=COLOURS[module], lw=1.4),
        )

    nose = d.plate_length / 2
    ax.annotate("", xy=(nose + 34, 0), xytext=(nose + 12, 0),
                arrowprops=dict(arrowstyle="-|>", color="#333333", lw=2))
    ax.text(nose + 23, 5, "FRONT", fontsize=10, fontweight="bold",
            ha="center", color="#333333")
    finish_2d(ax, f"top plan -- plate {d.plate_length:g} x {d.plate_width:g} mm",
              "X (mm)", "Y (mm)", (-105, 105), (-62, 62))


def side_2d(ax, clouds, d: ChassisDims):
    """Looking in from the +Y side: X to the right (front at the right)."""
    hulls = silhouettes(ax, clouds, 0, 2)
    top = max(h[:, 1].max() for hs in hulls.values() for h in hs)
    bottom = min(h[:, 1].max() * 0 + h[:, 1].min() for hs in hulls.values() for h in hs)

    ax.axhline(bottom, color="#8a6d3b", lw=1.4, ls="--", zorder=40)
    ax.text(-95, bottom - 4.5, "ground", fontsize=9, color="#8a6d3b")
    ax.annotate(
        "", xy=(88, bottom), xytext=(88, top),
        arrowprops=dict(arrowstyle="<->", color="#333333", lw=1.2), zorder=50)
    ax.text(84, (top + bottom) / 2, f"{top - bottom:.1f} mm\noverall",
            fontsize=9, ha="right", va="center")
    ax.annotate(
        "", xy=(-88, bottom), xytext=(-88, 0),
        arrowprops=dict(arrowstyle="<->", color="#333333", lw=1.2), zorder=50)
    ax.text(-84, bottom / 2, f"{-bottom:.1f} mm\nclearance", fontsize=9,
            ha="left", va="center")
    finish_2d(ax, "side elevation -- from the +Y wheel, front to the right",
              "X (mm)", "Z (mm)", (-105, 105), (bottom - 8, top + 8))


def front_2d(ax, clouds, d: ChassisDims):
    """Looking at the front (+X) edge: +Y is to the LEFT, as seen head-on."""
    hulls = silhouettes(ax, clouds, 1, 2, flip_x=True)
    top = max(h[:, 1].max() for hs in hulls.values() for h in hs)
    bottom = min(h[:, 1].min() for hs in hulls.values() for h in hs)
    track = max(abs(h[:, 0]).max() for h in hulls["drive wheel"])
    ax.annotate("", xy=(-track, top + 5), xytext=(track, top + 5),
                arrowprops=dict(arrowstyle="<->", color="#333333", lw=1.2))
    ax.text(0, top + 7, f"track {2 * track:.1f} mm", fontsize=9, ha="center")
    finish_2d(ax, "front elevation -- head-on at the +X edge",
              "Y (mm)  (+Y to the left)", "Z (mm)", (-72, 72), (bottom - 8, top + 14))


def render(out: Path) -> None:
    d, parts = assembly_parts()
    tris, face_colours, clouds = tessellate(parts)

    fig = plt.figure(figsize=(18, 11.5))
    fig.suptitle("robot car -- full assembly, colour-coded by module",
                 fontsize=17, fontweight="bold")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.1, 1],
                          left=0.045, right=0.985, top=0.94, bottom=0.085,
                          wspace=0.13, hspace=0.20)

    scene_3d(fig.add_subplot(gs[0, 0], projection="3d"), tris, face_colours,
             24, -58, "isometric -- front-right")
    plan_2d(fig.add_subplot(gs[0, 1]), clouds, d)
    side_2d(fig.add_subplot(gs[1, 0]), clouds, d)
    front_2d(fig.add_subplot(gs[1, 1]), clouds, d)

    fig.legend(
        handles=[Patch(facecolor=COLOURS[m], edgecolor="#333333", label=m)
                 for m in ORDER],
        loc="lower center", ncol=8, frameon=False, fontsize=11.5,
    )
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    render(HERE / "car_assembly_colour.png")
