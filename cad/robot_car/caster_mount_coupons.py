"""Slide-in mount for the bought swivel caster (parts/swivel_caster.py):
the pocket, and fit coupons for it.

The caster's 40.2 x 40.2 x 1.5 steel plate slides into a pocket built into
the chassis plate's underside, from the front, until it lands on a stop
at the rear. No bolts. The pocket is three layers of the chassis plate:

- Ledges: the bottom ledge_t of the plate, printed on the bed. They run
  under the caster plate's flat edge strip on both sides and across the
  back, and hold the caster up when the car is lifted. Between them a
  U-shaped opening, open to the front, lets the bearing ring and the fork
  through. The ring is Ø30, so the ledges can reach 5 mm in from the
  plate edge before they touch it. They reach ledge_w.
- Slot: the caster plate's thickness plus slot_h - plate_t of play, and
  side_fit per side. Open at the front, with lead-ins.
- Lips: above the slot, along both sides, a flat land lip_land wide
  reaches in over the plate's edge, and a 45 deg face rises from it. The
  floor pushes the wheel up and the plate up against the lands, so they
  carry the car's weight. Over the middle of the plate the pocket is an
  open window, and at the back a plain wall is the stop.

Everything above the slot is built so that no line is printed across
open air between two far anchors. A roof over the slot would be a 40 mm
bridge, and it sags into a 1.5 mm slot. A land along a side wall is
printed as lines along the wall, each fused to the wall or its
neighbour for its whole length, and the 45 deg face above it prints like
any wall. A lip across the back would hang its lines between the two
rear corners, and they sag the same way, so the back has none.

Driving forward, the floor drags the caster back against the rear stop.
In reverse only friction holds it in.

COUPONS (uv run robot_car/caster_mount_coupons.py) are the pocket cut
out of the chassis, in a 2 x 2 grid, land 2.0:

    I  slot 1.8  side fit 0.10      J  slot 1.8  side fit 0.20
    K  slot 2.0  side fit 0.10      L  slot 2.0  side fit 0.20

- SLOT HEIGHT is ledge top to land underside, for the 1.5 plate. Both
  faces land on the 0.2 mm layer grid, so the steps are 0.2 apart.
- SIDE FIT (per side) is the gap between the 40.2 plate and each side
  wall, as drawn. The printer holds the slot width to about 0.1: a slot
  drawn 40.2 printed 40.1, and at that zero fit the plate went in only
  by spreading the side walls apart.
- LAND 2.0: the lip's flat underside, reaching in over the plate's edge
  from the side wall. 2.0 printed cleaner and fit better than 1.0.

A coupon's side walls are wall_t thick, so they don't spread more than
the chassis plate around a pocket would. A coupon that gives sideways
judges a fit looser than the car will have it.

RESULT (dark blue PLA Basic, X2D): J fits best -- the caster slides in
by hand and stays put. J's numbers are MountDims' defaults.

Fitting: turn the fork so the wheel trails forward, slide the plate in
from the open end until it stops. Judge per coupon: does it go in by
hand, does it rattle when shaken, does it stay in when held mouth-down
and tapped, does the caster still swivel freely.

Frame: the caster plate's centre at X = Y = 0, the chassis underside
(the bed) at Z = 0, the mouth at +X (the car's front).

Exports (gitignored) into robot_car/: caster_mount_coupons.stl/.step and
caster_mount_render.png. Exits nonzero if any check fails.
"""

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import (  # noqa: E402
    Align,
    Box,
    Cylinder,
    FontStyle,
    Part,
    Plane,
    Polyline,
    Pos,
    Text,
    export_step,
    export_stl,
    extrude,
    make_face,
)

from swivel_caster import CasterDims, make_caster  # noqa: E402

LAYER = 0.2
SLOT_HS = (1.8, 2.0)
SIDE_FITS = (0.10, 0.20)


@dataclass
class MountDims:
    slot_h: float = 1.8  # ledge top to land underside (coupon J)
    side_fit: float = 0.20  # per side, plate edge to wall, as drawn (coupon J)
    end_fit: float = 0.10  # plate's rear edge to the stop, plate centred
    ledge_t: float = 1.2  # on the bed: six layers
    ledge_w: float = 2.5  # under the plate's flat edge strip
    lip_land: float = 2.0  # flat ceiling reaching in from the side walls (coupon J)
    roof_t: float = 2.4  # lip height above the slot
    wall_t: float = 8.0  # beside the slot (coupon): stiff, like the chassis around it
    stop_t: float = 3.0  # behind the stop face (coupon)
    lead_in: float = 0.5  # 45 deg, at the mouth: walls, ledge tops, lands

    def ledge_top(self) -> float:
        return self.ledge_t

    def ceiling(self) -> float:
        return self.ledge_t + self.slot_h

    def top(self) -> float:
        return self.ceiling() + self.roof_t


def rbox(x0, x1, y0, y1, z0, z1) -> Part:
    return Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN)).translate(
        (x0, y0, z0))


def ivol(a: Part, b: Part) -> float:
    r = a & b
    return 0.0 if r is None else abs(r.volume)


def _prism(points, plane: Plane, amount: float) -> Part:
    return extrude(plane * make_face(Polyline(*points, close=True)), amount=amount)


def pocket_cut(m: MountDims, c: CasterDims) -> Part:
    """What a plate loses to the pocket: the slot, the U opening through the
    ledges, and the lead-ins at the mouth. The slot's top is the ceiling,
    so on a plate exactly that thick the slot opens upward into the
    window between the lips."""
    a = c.plate / 2 + m.side_fit  # slot half-width
    tip = a - m.ledge_w  # ledge tips, and the opening's radius at the rear
    x_stop = -c.plate / 2 - m.end_fit
    x_mouth = c.plate / 2
    z_l, z_c = m.ledge_top(), m.ceiling()

    cut = rbox(x_stop, x_mouth + 1, -a, a, z_l, z_c)
    # U opening through the ledges: round at the back, open at the front
    cut += Pos(0, 0, -0.5) * Cylinder(tip, z_l + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cut += rbox(0, x_mouth + 1, -tip, tip, -0.5, z_l + 0.5)

    # lead-ins at the mouth, 45 deg
    li, x0 = m.lead_in, x_mouth - m.lead_in
    for s in (-1, 1):  # side walls flare out
        tri = [(x0, s * a), (x_mouth + 0.01, s * a), (x_mouth + 0.01, s * (a + li))]
        cut += Pos(0, 0, z_l) * _prism(tri, Plane.XY, m.slot_h)
    span = a + li + 0.5
    for z, dz in ((z_l, -li), (z_c, li)):  # ledge tops drop, lands lift
        tri = [(x0, z), (x_mouth + 0.01, z), (x_mouth + 0.01, z + dz)]
        cut += Pos(0, span, 0) * _prism(tri, Plane.XZ, 2 * span)
    return cut


def lip_rails(m: MountDims, c: CasterDims, x0: float, rail_w: float) -> Part:
    """The two lips, standing on the plate beside the slot from x0 to the
    mouth: rail_w wide outside the slot wall, the land reaching lip_land in
    over the slot, a 45 deg face rising from the land's edge to the top."""
    a = c.plate / 2 + m.side_fit
    z_c, z_t = m.ceiling(), m.top()
    rails = Part()
    for s in (-1, 1):
        prof = [(s * (a - m.lip_land), z_c), (s * (a + rail_w), z_c),
                (s * (a + rail_w), z_t), (s * (a - m.lip_land - m.roof_t), z_t)]
        if s < 0:
            prof.reverse()
        rails += Pos(x0, 0, 0) * _prism(prof, Plane.YZ, c.plate / 2 - x0)
    return rails


def make_pocket(m: MountDims, c: CasterDims) -> Part:
    """The coupon: a square of plate ceiling-thick, a rear wall up to the
    lips' top, the lips along both sides, less the pocket."""
    a = c.plate / 2 + m.side_fit
    x_stop = -c.plate / 2 - m.end_fit
    x_back = x_stop - m.stop_t
    w = a + m.wall_t
    body = rbox(x_back, c.plate / 2, -w, w, 0, m.ceiling())
    body += rbox(x_back, x_stop, -w, w, m.ceiling(), m.top())
    body += lip_rails(m, c, x_back, m.wall_t)
    return body - pocket_cut(m, c)


# ---------------------------------------------------------------------------
# coupons
# ---------------------------------------------------------------------------

TEXT_HEIGHT = 0.6
FONT, FONT_SIZE = "Arial", 8.0  # bold: ~1 mm strokes, over the 0.8 legibility floor
GAP = 4.0


def grid() -> list[tuple[str, MountDims]]:
    letters = iter("IJKL")
    return [(next(letters), MountDims(slot_h=h, side_fit=f)) for h in SLOT_HS for f in SIDE_FITS]


def settled() -> tuple[str, MountDims]:
    """The coupon whose numbers are MountDims' defaults: the pocket the
    chassis builds."""
    return next((letter, m) for letter, m in grid() if m == MountDims())


def coupon(m: MountDims, c: CasterDims, letter: str) -> Part:
    part = make_pocket(m, c)
    text = Text(letter, font_size=FONT_SIZE, font=FONT, font_style=FontStyle.BOLD)
    # on the -Y side lip, centred across its top face, toward the back
    y0 = -(c.plate / 2 + m.side_fit + m.wall_t)
    y1 = -(c.plate / 2 + m.side_fit - m.lip_land - m.roof_t)
    part += extrude(Plane.XY.offset(m.top()) * Pos(-c.plate / 4, (y0 + y1) / 2) * text,
                    amount=TEXT_HEIGHT)
    return part


def plate_layout(c: CasterDims) -> Part:
    plate = Part()
    entries = grid()
    sizes = [make_pocket(m, c).bounding_box().size for _, m in entries]
    px = max(s.X for s in sizes) + GAP
    py = max(s.Y for s in sizes) + GAP
    for i, (letter, m) in enumerate(entries):
        row, col = divmod(i, 2)
        plate += Pos((col - 0.5) * px, (0.5 - row) * py, 0) * coupon(m, c, letter)
    return plate


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

OVERLAP_TOL = 0.01  # mm^3


def report(ok: bool, text: str) -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {text}")
    return ok


def seated(m: MountDims, c: CasterDims, heading: float = 0.0, dx: float = 0.0,
           loaded: bool = False) -> dict:
    """The caster in the pocket, `dx` out toward the mouth. Lifted, the
    plate rests on the ledges; loaded, the floor pushes it up to the lands."""
    z = (m.ceiling() if loaded else m.ledge_top() + c.plate_t)
    return {k: Pos(dx, 0, z) * p for k, p in make_caster(c, heading).items()}


def on_grid(z: float) -> bool:
    return abs(z / LAYER - round(z / LAYER)) < 1e-6


def run_checks(c: CasterDims) -> bool:
    ok = True
    for letter, m in grid():
        print(f"\n-- coupon {letter}: slot {m.slot_h:g}, land {m.lip_land:g}, "
              f"side fit {m.side_fit:g} --")
        pocket = make_pocket(m, c)
        ok &= report(len(pocket.solids()) == 1, f"one solid ({len(pocket.solids())})")
        zs = {"ledge top": m.ledge_top(), "land underside": m.ceiling(), "top": m.top()}
        ok &= report(all(on_grid(z) for z in zs.values()),
                     "on the 0.2 layer grid: " + ", ".join(f"{k} {v:g}" for k, v in zs.items()))

        for loaded in (False, True):
            s = seated(m, c, loaded=loaded)
            v = ivol(s["plate"], pocket)
            where = "pressed up to the lands" if loaded else "resting on the ledges"
            ok &= report(v < OVERLAP_TOL, f"plate {where}: no overlap ({v:.4f} mm^3)")
        # the plate floating mid-slot: each face of the slot at its own gap
        play = m.slot_h - c.plate_t
        floating = Pos(0, 0, m.ledge_top() + play / 2 + c.plate_t) * make_caster(c)["plate"]
        a, z_l, z_c = c.plate / 2 + m.side_fit, m.ledge_top(), m.ceiling()
        faces = {
            "side walls": (rbox(-40, 40, c.plate / 2, 40, z_l, z_c)
                           + rbox(-40, 40, -40, -c.plate / 2, z_l, z_c), m.side_fit),
            "rear stop": (rbox(-40, -c.plate / 2, -a, a, z_l, z_c), m.end_fit),
            "ledges": (rbox(-40, 40, -a, a, z_l - 0.5, z_l), play / 2),
            "lands": (rbox(-40, 40, -a, a, z_c, z_c + 0.5), play / 2),
        }
        for name, (region, want) in faces.items():
            got = floating.distance_to(pocket & region)
            ok &= report(abs(got - want) < 0.005,
                         f"plate centred in the slot: {got:.3f} mm to the {name} (want {want:.3f})")
        grip = m.lip_land - m.side_fit
        ok &= report(grip >= 0.8, f"lands reach {grip:.2f} mm over the plate edge, centred (>= 0.8)")
        # the first layer over the slot, inside the lands (the 45 deg faces
        # step in one layer width above it)
        x_stop, w0 = -c.plate / 2 - m.end_fit, a - m.lip_land - LAYER
        v = ivol(pocket, rbox(x_stop + 0.01, c.plate / 2,
                              -w0 + 0.01, w0 - 0.01, z_c, z_c + LAYER))
        ok &= report(v < OVERLAP_TOL,
                     f"no bridge: nothing over the plate inside the side lands, "
                     f"back to the stop ({v:.4f} mm^3)")
        s = seated(m, c)
        ring_gap = s["ring"].distance_to(pocket & rbox(-40, 40, -40, 40, 0, z_l))
        ok &= report(ring_gap >= 2.0,
                     f"bearing ring clears the ledges by {ring_gap:.2f} mm (>= 2)")

        # slide out: plate, ring and fork travel +X clear of everything
        worst = 0.0
        for dx in range(0, int(c.plate) + 2, 2):
            s = seated(m, c, dx=dx)
            moving = s["plate"] + s["ring"] + s["fork"]
            worst = max(worst, ivol(moving, pocket))
        ok &= report(worst < OVERLAP_TOL,
                     f"slides out the mouth without touching ({worst:.4f} mm^3, 2 mm steps)")

        # swivel: nothing of the pocket hangs below the chassis underside, and
        # the ring is the only moving part that reaches up into the ledges
        worst = 0.0
        for heading in range(0, 360, 30):
            s = seated(m, c, heading=heading)
            worst = max(worst, ivol(s["fork"] + s["wheel"], pocket))
        ok &= report(worst < OVERLAP_TOL,
                     f"swivels a full turn clear of the pocket ({worst:.4f} mm^3, 30 deg steps)")
    return ok


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

COLOURS = {"pocket": "#5a6472", "plate": "#c9ced6", "ring": "#9aa3ad",
           "fork": "#d85a30", "wheel": "#993c1d"}

# (scene offset, camera eye, look-at), mm. Each scene is drawn twice in one
# USD stage, side by side, so one file renders both stills.
STILLS = {
    "printed": ((0, 0, 0), (175, -75, 60), (0, 0, 2)),  # top up, looking into the mouth
    "below": ((150, 0, 0), (150 + 135, -120, -95), (150, 0, -6)),  # caster slid in
}


def usd_stills(c: CasterDims, m: MountDims, letter: str, out_dir: Path) -> dict:
    """Render STILLS with macOS usdrecord (Hydra/Storm: z-buffered, so no
    painter's-algorithm see-through). Returns name -> png path."""
    import subprocess

    import numpy as np
    from lid_twin import camera_prim, fmt, mesh_of, srgb_to_linear

    s = seated(m, c, loaded=True)
    groups = [("printed", "pocket", coupon(m, c, letter))]
    groups += [("below", "pocket", make_pocket(m, c))]
    groups += [("below", k, s[k]) for k in ("plate", "ring", "fork", "wheel")]

    L = ["#usda 1.0", "(", '    defaultPrim = "Mount"', "    metersPerUnit = 0.001",
         '    upAxis = "Z"', ")", "", 'def Xform "Mount"', "{", '    def Scope "Looks"', "    {"]
    for name, hexc in COLOURS.items():
        r, g, b = srgb_to_linear(hexc)
        L += [f'        def Material "{name}"', "        {",
              f"            token outputs:surface.connect = </Mount/Looks/{name}/Surface.outputs:surface>",
              '            def Shader "Surface"', "            {",
              '                uniform token info:id = "UsdPreviewSurface"',
              f"                color3f inputs:diffuseColor = ({r:.4f}, {g:.4f}, {b:.4f})",
              "                float inputs:roughness = 0.6", "                float inputs:metallic = 0",
              "                token outputs:surface", "            }", "        }"]
    L += ["    }", ""]
    for i, (scene, look, part) in enumerate(groups):
        mesh = mesh_of(Pos(*STILLS[scene][0]) * part)
        lo, hi = mesh.bounds
        normals = np.repeat(mesh.face_normals, 3, axis=0)
        L += [f'    def Mesh "{scene}_{look}_{i}" (', '        prepend apiSchemas = ["MaterialBindingAPI"]',
              "    )", "    {", '        uniform token subdivisionScheme = "none"',
              f"        float3[] extent = [({lo[0]:.4g}, {lo[1]:.4g}, {lo[2]:.4g}), ({hi[0]:.4g}, {hi[1]:.4g}, {hi[2]:.4g})]",
              f"        int[] faceVertexCounts = [{', '.join(['3'] * len(mesh.faces))}]",
              f"        int[] faceVertexIndices = [{', '.join(map(str, mesh.faces.ravel()))}]",
              f"        point3f[] points = [{fmt(mesh.vertices)}]",
              f"        normal3f[] normals = [{fmt(normals)}] (", '            interpolation = "faceVarying"', "        )",
              f"        rel material:binding = </Mount/Looks/{look}>", "    }"]
    for name, (_, eye, target) in STILLS.items():
        L += camera_prim(name, np.array(eye, float), np.array(target, float))
    L += ["}", ""]
    stage = out_dir / "mount.usda"
    stage.write_text("\n".join(L))

    pngs, procs = {}, []
    for name in STILLS:
        pngs[name] = out_dir / f"{name}.png"
        procs.append(subprocess.Popen(["usdrecord", "--cam", name, "--imageWidth", "1000",
                                       str(stage), str(pngs[name])],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
    for p in procs:
        if p.wait() != 0:
            raise RuntimeError(f"usdrecord failed: {p.stderr.read().decode()[-400:]}")
    return pngs


def render(c: CasterDims, out: Path) -> None:
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt
    import trimesh
    from matplotlib.collections import PolyCollection
    from matplotlib.patches import Patch

    letter, m = settled()
    s = seated(m, c, loaded=True)
    groups = [("pocket", make_pocket(m, c)), ("plate", s["plate"]), ("ring", s["ring"]),
              ("fork", s["fork"]), ("wheel", s["wheel"])]
    meshes = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, part) in enumerate(groups):
            p = Path(tmp) / f"{i}.stl"
            export_stl(part, p)
            meshes.append((name, trimesh.load_mesh(p)))
        stills = {k: mpimg.imread(v) for k, v in usd_stills(c, m, letter, Path(tmp)).items()}

    fig = plt.figure(figsize=(16, 11))
    fig.suptitle(f"robot car -- slide-in caster mount, coupon {letter} (slot {m.slot_h:g}, "
                 f"land {m.lip_land:g}, side fit {m.side_fit:g})",
                 fontsize=15, fontweight="bold")
    for i, (name, title) in enumerate((
            ("printed", "coupon as printed: lips up, mouth toward the viewer"),
            ("below", "from below: caster slid in, wheel trailing (fork and wheel est)"))):
        ax = fig.add_subplot(2, 2, i + 1)
        ax.imshow(stills[name])
        ax.set_axis_off()
        ax.set_title(title)

    def section(ax, normal, origin, axes, title, xlabel):
        for name, mm in meshes:
            sec = mm.section(plane_origin=origin, plane_normal=normal)
            if sec is None:
                continue
            for poly in sec.discrete:
                pts = poly[:, axes]
                ax.add_collection(PolyCollection([pts], facecolors=COLOURS[name],
                                                 edgecolors="#222222", linewidths=0.4))
        ax.axhline(0, color="#8a6d3b", ls="--", lw=0.8)
        ax.set_aspect("equal")
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Z (mm)")
        ax.grid(True, lw=0.3, alpha=0.4)

    a = c.plate / 2 + m.side_fit + m.wall_t
    ax = fig.add_subplot(2, 2, 3)
    section(ax, [1, 0, 0], [0, 0, 0], [1, 2],
            "section across the slot (X = 0), dashed = chassis underside", "Y (mm)")
    ax.set_xlim(-a - 1, a + 1)
    ax.set_ylim(-12, m.top() + 2)
    ax = fig.add_subplot(2, 2, 4)
    section(ax, [0, 1, 0], [0, 0, 0], [0, 2],
            "section along the slot (Y = 0), mouth at right", "X (mm)")
    ax.set_xlim(-c.plate / 2 - m.stop_t - 1, c.plate / 2 + 3)
    ax.set_ylim(-12, m.top() + 2)

    fig.legend(handles=[Patch(facecolor=v, label=k) for k, v in COLOURS.items()],
               loc="lower center", ncol=len(COLOURS), frameon=False, fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"Wrote {out.name}")


if __name__ == "__main__":
    c = CasterDims()
    ok = run_checks(c)
    plate = plate_layout(c)
    n = len(plate.solids())
    print()
    ok &= report(n == 4, f"coupon plate: {n} solids (expect 4)")
    bb = plate.bounding_box()
    print(f"Bounding box (mm): {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f}")
    print(f"Volume: {plate.volume / 1000:.2f} cm^3")
    export_stl(plate, HERE / "caster_mount_coupons.stl")
    export_step(plate, HERE / "caster_mount_coupons.step")
    print("Exported caster_mount_coupons.stl/.step")
    render(c, HERE / "caster_mount_render.png")
    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    sys.exit(0 if ok else 1)
