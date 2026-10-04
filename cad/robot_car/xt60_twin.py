"""robot_car: animated twin, movie and stills of the XT60 holder on the car.

Everything comes from the Parts xt60_holder.py checks: the car from
render_assembly, the right motor lid with the holder, the latch arm, the
male plug on the harness and the female on the pack's lead.

- xt60_holder_twin.usdz -- the whole car; the male comes down in front of
  the holder and slides in toward the rear, lifting the latch arm until it
  drops behind the plug, then the pack's female lifts off the pack, comes
  round behind the holder and plugs in, its lead following from the pack's
  rear end. macOS Quick Look plays it:
      qlmanage -p robot_car/xt60_holder_twin.usdz
- xt60_holder.mp4 (+ .png, its last frame) -- that animation from two
  cameras, over a labelled cut through the plug's centre line, rendered
  with usdrecord (Hydra Storm) and stitched by ffmpeg.
- xt60_holder_section.png, xt60_holder_print.png -- stills: the two
  sections through the holder, and the lid as it lies on the print bed.

The wire colours follow the common convention (red on the chamfered side);
the housings' own +/- marks win.

Run with:  uv run robot_car/xt60_twin.py [--no-movie] [--no-stills]
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from build123d import Axis, Box, Part, Pos, Torus, export_stl, fillet  # noqa: E402

from chassis import ChassisDims, _to_side, lid_dims  # noqa: E402
from lid_coupons import lid_for_print, make_lid  # noqa: E402
from xt60 import make_female, make_male, make_shrink  # noqa: E402
from xt60_holder import (  # noqa: E402
    XT, HolderDims, arm_pivot, barb_lift_needed, car_pts, holder_origin, make_holder,
    make_holder_lid, to_car,
)

FPS = 24
# (sRGB hex, roughness, metallic)
LOOKS = {
    "plate": ("#59626e", 0.8, 0.0),
    "lid": ("#8a94a3", 0.8, 0.0),
    "holder": ("#e8772e", 0.6, 0.0),
    "motor": ("#b9c0c8", 0.35, 0.8),
    "wheel": ("#4a4f57", 0.8, 0.0),
    "tyre": ("#202124", 0.9, 0.0),
    "pi": ("#2e9e5b", 0.55, 0.0),
    "drv": ("#d64550", 0.55, 0.0),
    "buck": ("#39a8c4", 0.55, 0.0),
    "switch": ("#2a2a2a", 0.6, 0.0),
    "battery": ("#3b6fd4", 0.45, 0.0),
    "caster": ("#c9b458", 0.5, 0.4),
    "xt60": ("#f3c316", 0.45, 0.0),
    "amber": ("#d9901a", 0.45, 0.0),
    "shrink": ("#1c1c1f", 0.7, 0.0),
    "red": ("#d7261e", 0.5, 0.0),
    "black": ("#2b2c30", 0.5, 0.0),
    "floor": ("#e4e4e0", 1.0, 0.0),
}
MODULE_LOOK = {
    "chassis plate": "plate", "caster": "caster", "Pi Zero 2 W": "pi",
    "DRV8833 driver": "drv", "MP1584EN buck": "buck", "power switch": "switch",
    "N20 gearmotor": "motor", "drive wheel": "wheel",
}

# ---- timeline (frames) -----------------------------------------------------
# Offsets in car coordinates, from each plug's seated position.
N_FRAMES = 228
MALE_ABOVE = np.array([23.6, 0.0, 13.0])  # over the channel's front entrance
MALE_ENTRY = np.array([23.6, 0.0, 0.0])  # in line, rim at the entrance
MALE_KEYS = [(0, MALE_ABOVE), (14, MALE_ABOVE), (36, MALE_ENTRY), (92, np.zeros(3))]
FEMALE_START, FEMALE_ALIGNED, FEMALE_MATED = 112, 160, 186
# the pack's female: lying on the pack, then up, back past the holder and
# down into line 14 mm behind the male, then in
F_PATH = np.array([[6.0, 21.0, 2.2], [6.0, 21.0, 12.0], [-14.0, 12.0, 12.0], [-14.0, 0.0, 0.0]])
F_CUT_START = 24.0  # the cutaway's female waits this far out, in line
HARNESS_END = np.array([12.0, 0.0, 25.0])  # over the pack, on its way to the fuse (cut)


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def male_offset(f: int) -> np.ndarray:
    for (f0, a), (f1, b) in zip(MALE_KEYS, MALE_KEYS[1:]):
        if f0 <= f <= f1:
            return a + (b - a) * smooth((f - f0) / max(f1 - f0, 1))
    return MALE_KEYS[-1][1].copy()


def female_offset(f: int) -> np.ndarray:
    if f <= FEMALE_START:
        return F_PATH[0].copy()
    if f <= FEMALE_ALIGNED:
        path = spline(F_PATH, 200)
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        at = smooth((f - FEMALE_START) / (FEMALE_ALIGNED - FEMALE_START)) * s[-1]
        return np.array([np.interp(at, s, path[:, k]) for k in range(3)])
    t = smooth((f - FEMALE_ALIGNED) / (FEMALE_MATED - FEMALE_ALIGNED))
    return (1 - t) * F_PATH[-1]


def female_cut_offset(f: int) -> np.ndarray:
    """The cutaway's female: waits in line, then comes straight in."""
    t = smooth((f - FEMALE_START) / (FEMALE_MATED - FEMALE_START))
    return np.array([-F_CUT_START * (1 - t), 0.0, 0.0])


def arm_angle(h: HolderDims, f: int) -> float:
    """Latch arm rotation about car Y (deg) for the male at frame f. The
    holder frame is the car's turned 180 deg, so lifting is negative here."""
    lift = barb_lift_needed(h, -male_offset(f)[0])
    return -float(np.degrees(np.arctan2(lift, h.arm_len)))


# ---- geometry ----------------------------------------------------------------


def mesh_of(part, tol=0.03):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "p.stl"
        export_stl(part, p, tolerance=tol, angular_tolerance=0.15)
        return trimesh.load_mesh(p)


def battery_body(cd: ChassisDims) -> Part:
    pack = fillet(Box(cd.battery_len, cd.battery_wid, cd.battery_h).edges(), 2.0)
    return Pos(cd.battery_x, 0, cd.plate_thickness + cd.battery_h / 2) * pack


def tyres(cd: ChassisDims) -> list[Part]:
    from assembly import wheel_geometry
    from wheel import WheelDims
    wd = WheelDims()
    out = []
    for side in (1, -1):
        g = wheel_geometry(side, cd, wd)
        major = wd.groove_root_diameter / 2 + wd.oring_cord / 2
        t = Torus(major, wd.oring_cord / 2).rotate(Axis.X, 90)
        out.append(Pos(cd.cradle_x, g["y_origin"] - side * wd.rim_width / 2, g["axis_z"]) * t)
    return out


def tube(path: np.ndarray, r: float, sides: int = 14):
    """Vertices and triangles of a capped tube along a polyline, framed by
    parallel transport so it doesn't twist."""
    t = np.gradient(path, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    n = np.cross(t[0], [0, 0, 1.0])
    if np.linalg.norm(n) < 1e-6:
        n = np.cross(t[0], [0, 1.0, 0])
    n /= np.linalg.norm(n)
    frames = []
    for i in range(len(path)):
        if i:
            n = n - np.dot(n, t[i]) * t[i]
            n /= np.linalg.norm(n)
        frames.append((n, np.cross(t[i], n)))
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    verts = np.array([p + r * (np.cos(a) * nn + np.sin(a) * bb)
                      for p, (nn, bb) in zip(path, frames) for a in ang])
    faces = []
    for i in range(len(path) - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            c, d = a + sides, b + sides
            faces += [(a, b, d), (a, d, c)]
    c0, c1 = len(verts), len(verts) + 1
    verts = np.vstack([verts, path[0], path[-1]])
    last = (len(path) - 1) * sides
    for j in range(sides):
        faces.append((c0, (j + 1) % sides, j))
        faces.append((c1, last + j, last + (j + 1) % sides))
    return verts, np.array(faces)


def spline(points: np.ndarray, n: int = 90) -> np.ndarray:
    """Centripetal Catmull-Rom through `points`, n samples."""
    p = np.vstack([2 * points[0] - points[1], points, 2 * points[-1] - points[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        t0 = 0.0
        t1 = t0 + np.linalg.norm(p1 - p0) ** 0.5
        t2 = t1 + np.linalg.norm(p2 - p1) ** 0.5
        t3 = t2 + np.linalg.norm(p3 - p2) ** 0.5
        m = max(2, n // (len(p) - 3))
        for t in np.linspace(t1, t2, m, endpoint=(i == len(p) - 3)):
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    return np.array(out)


def line(a, b, n):
    return np.linspace(a, b, n)


def bezier(p0, p1, p2, p3, n):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def wire_pair(center: np.ndarray, d0: float, r: float):
    """Two wires side by side along a sampled centre path, offset across it
    in the horizontal plane: d0 from the centre at the plug (half the pin
    pitch), closing to touching within 12 mm. Red goes on car +Y at the
    plug -- the chamfered side, which the holder keeps inboard."""
    t = np.gradient(center, axis=0)
    n = np.stack([-t[:, 1], t[:, 0], np.zeros(len(t))], axis=1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(center, axis=0), axis=1))])
    d = r + 0.2 + (d0 - r - 0.2) * (1 - np.array([smooth(v / 12.0) for v in s]))
    red = 1.0 if n[0, 1] > 0 else -1.0
    out = []
    for look, sg in (("red", red), ("black", -red)):
        v, f = tube(center + (sg * d)[:, None] * n, r)
        out.append((look, v, f))
    return out


def pack_lead(cd: ChassisDims, h: HolderDims, offset: np.ndarray):
    """The pack's lead, [(look, verts, faces)]: out of the female's
    heat-shrink rearward, a U-turn behind the car, and into the pack's rear
    end face."""
    tail = car_pts([h.x_rim + XT.female_body_len + XT.shrink_len, 0, h.z_plug + XT.axis_z], cd)
    tail = tail + offset
    exit_ = np.array([cd.battery_x - cd.battery_len / 2, -8.0, 17.0])
    p1, e1 = tail + [-5, 0, 0], exit_ + [-5, 0, 0]
    reach = 0.75 * np.linalg.norm(p1 - e1) + 5
    center = np.vstack([line(tail, p1, 6)[:-1],
                        bezier(p1, p1 + [-reach, 0, 0], e1 + [-reach, 0, 0], e1, 90),
                        line(e1, exit_ + [1.5, 0, 0], 8)[1:]])
    return wire_pair(center, XT.pitch / 2, 1.9)


def harness_lead(cd: ChassisDims, h: HolderDims, offset: np.ndarray):
    """The harness's two wires: forward out of the male's heat-shrink, then
    up and inboard across the pack, toward the fuse and the switch."""
    start = car_pts([h.x_rim - XT.male_len - XT.shrink_len, 0, h.z_plug + XT.axis_z], cd)
    start = start + offset
    p1 = start + [2.5, 4.0, 5.0]
    a = HARNESS_END
    pts = np.array([start, p1, p1 + (a - p1) * 0.4 + [0, 0, 5], p1 + (a - p1) * 0.75 + [0, 0, 3], a])
    return wire_pair(spline(pts, 90), XT.pitch / 2, 1.7)


# ---- USD ---------------------------------------------------------------------


def srgb_to_linear(hx):
    c = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


def fmt(a):
    return ", ".join(f"({x:.4g}, {y:.4g}, {z:.4g})" for x, y, z in a)


def mesh_prim(name, verts, faces, look, indent, smooth_normals=False, anim_points=None):
    pad = " " * indent
    # the bound has to hold every time sample, or a renderer culls the mesh
    allv = np.vstack([v for _, v in anim_points]) if anim_points else verts
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    L = [f'{pad}def Mesh "{name}" (', f'{pad}    prepend apiSchemas = ["MaterialBindingAPI"]',
         f"{pad})", f"{pad}{{", f'{pad}    uniform token subdivisionScheme = "none"',
         f"{pad}    float3[] extent = [({lo[0]:.4g}, {lo[1]:.4g}, {lo[2]:.4g}), ({hi[0]:.4g}, {hi[1]:.4g}, {hi[2]:.4g})]",
         f"{pad}    int[] faceVertexCounts = [{', '.join(['3'] * len(faces))}]",
         f"{pad}    int[] faceVertexIndices = [{', '.join(map(str, np.asarray(faces).ravel()))}]"]
    if anim_points:
        samples = ", ".join(f"{fr}: [{fmt(v)}]" for fr, v in anim_points)
        L.append(f"{pad}    point3f[] points.timeSamples = {{ {samples} }}")
    else:
        L.append(f"{pad}    point3f[] points = [{fmt(verts)}]")
    if not smooth_normals:
        m = trimesh.Trimesh(verts, faces, process=False)
        normals = np.repeat(m.face_normals, 3, axis=0)
        L += [f"{pad}    normal3f[] normals = [{fmt(normals)}] (",
              f'{pad}        interpolation = "faceVarying"', f"{pad}    )"]
    L += [f"{pad}    rel material:binding = </Scene/Looks/{look}>", f"{pad}}}"]
    return L


def camera_prim(name, eye, target, focal=50.0, ortho_w=None, aspect=5 / 3):
    """A camera at eye looking at target, Z up. With ortho_w it is
    orthographic and ortho_w mm wide (USD apertures are in tenths of a
    scene unit, so 10 x the width)."""
    eye, target = np.array(eye, float), np.array(target, float)
    z = eye - target
    z /= np.linalg.norm(z)
    x = np.cross([0, 0, 1], z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    rows = [(*x, 0), (*y, 0), (*z, 0), (*eye, 1)]
    m = ", ".join("(" + ", ".join(f"{v:.6g}" for v in r) + ")" for r in rows)
    if ortho_w:
        lens = ['        token projection = "orthographic"',
                f"        float horizontalAperture = {10 * ortho_w:.6g}",
                f"        float verticalAperture = {10 * ortho_w / aspect:.6g}"]
    else:
        lens = [f"        float focalLength = {focal}", "        float horizontalAperture = 20.955",
                "        float verticalAperture = 12.573"]
    return [f'    def Camera "{name}"', "    {", *lens, "        float2 clippingRange = (1, 5000)",
            f"        matrix4d xformOp:transform = ( {m} )",
            '        uniform token[] xformOpOrder = ["xformOp:transform"]', "    }"]


def framed(name, target, direction, radius, focal=50.0):
    """A perspective camera looking at target from `direction`, backed off
    until a sphere of `radius` fills the 5:3 frame's height."""
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    half_v = np.arctan(12.573 / 2 / focal)
    target = np.array(target, float)
    return (name, target + d * radius / np.sin(half_v), target, focal)


def stage(statics, movers, cameras, n_frames=0, floor_z=None):
    """statics: [(name, mesh, look)]; movers: [(name, kind, data)] where
    kind 'translate' -> (mesh_list, {frame: (x,y,z)}), 'rotate' -> (mesh_list,
    pivot, {frame: deg}), 'points' -> (look, faces, [(frame, verts)])."""
    L = ["#usda 1.0", "(", '    defaultPrim = "Scene"', "    metersPerUnit = 0.001",
         '    upAxis = "Z"', "    startTimeCode = 0", f"    endTimeCode = {n_frames}",
         f"    timeCodesPerSecond = {FPS}", ")", "", 'def Xform "Scene"', "{",
         '    def Scope "Looks"', "    {"]
    for name, (hx, rough, metal) in LOOKS.items():
        r, g, b = srgb_to_linear(hx)
        L += [f'        def Material "{name}"', "        {",
              f"            token outputs:surface.connect = </Scene/Looks/{name}/Surface.outputs:surface>",
              '            def Shader "Surface"', "            {",
              '                uniform token info:id = "UsdPreviewSurface"',
              f"                color3f inputs:diffuseColor = ({r:.4f}, {g:.4f}, {b:.4f})",
              f"                float inputs:roughness = {rough}", f"                float inputs:metallic = {metal}",
              "                token outputs:surface", "            }", "        }"]
    L += ["    }", ""]
    L += ['    def DomeLight "Sky"', "    {", "        float inputs:intensity = 0.7",
          "        color3f inputs:color = (0.92, 0.95, 1.0)", "    }",
          '    def DistantLight "Sun"', "    {", "        float inputs:intensity = 2.2",
          "        float inputs:angle = 2", "        color3f inputs:color = (1.0, 0.97, 0.92)",
          '        float3 xformOp:rotateXYZ = (40, 0, -35)',
          '        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]', "    }",
          '    def DistantLight "Fill"', "    {", "        float inputs:intensity = 0.6",
          '        float3 xformOp:rotateXYZ = (-60, 0, 150)',
          '        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]', "    }"]
    if floor_z is not None:
        s = 400
        v = np.array([[-s, -s, floor_z], [s, -s, floor_z], [s, s, floor_z], [-s, s, floor_z]])
        L += mesh_prim("Floor", v, [(0, 1, 2), (0, 2, 3)], "floor", 4)
    for i, (name, m, look) in enumerate(statics):
        L += mesh_prim(f"{name}_{i}", m.vertices, m.faces, look, 4)
    for name, kind, data in movers:
        if kind == "points":
            look, faces, samples = data
            L += mesh_prim(name, samples[0][1], faces, look, 4, smooth_normals=True, anim_points=samples)
            continue
        L += [f'    def Xform "{name}"', "    {"]
        if kind == "translate":
            meshes, keys = data
            s = ", ".join(f"{f}: ({x:.4g}, {y:.4g}, {z:.4g})" for f, (x, y, z) in keys.items())
            L += [f"        double3 xformOp:translate.timeSamples = {{ {s} }}",
                  '        uniform token[] xformOpOrder = ["xformOp:translate"]']
        else:
            meshes, (px, py, pz), keys = data
            s = ", ".join(f"{f}: {a:.4g}" for f, a in keys.items())
            L += [f"        double3 xformOp:translate = ({px:.4g}, {py:.4g}, {pz:.4g})",
                  f"        float xformOp:rotateY.timeSamples = {{ {s} }}",
                  f"        double3 xformOp:translate:pivot = ({-px:.4g}, {-py:.4g}, {-pz:.4g})",
                  '        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateY", "xformOp:translate:pivot"]']
        for j, (mname, verts, faces, look) in enumerate(meshes):
            L += mesh_prim(f"{mname}_{j}", verts, faces, look, 8, smooth_normals=look in ("red", "black"))
        L += ["    }"]
    for cam in cameras:
        L += camera_prim(*cam)
    L += ["}", ""]
    return "\n".join(L)


def write_usdz(text: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / f"{out.stem}.usda"
        a.write_text(text)
        c = Path(tmp) / f"{out.stem}.usdc"
        subprocess.run(["usdcat", "-o", str(c), str(a)], check=True)
        if out.exists():
            out.unlink()
        subprocess.run(["usdzip", str(out), str(c)], check=True, stdout=subprocess.DEVNULL)
    print(f"Wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB)")


def record(usdz: Path, cam: str, out_pattern: str, frames: str, width: int) -> subprocess.Popen:
    return subprocess.Popen(["usdrecord", "--frames", frames, "--imageWidth", str(width),
                             "--cam", cam, str(usdz), out_pattern],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


# ---- scenes ------------------------------------------------------------------


def car_statics(cd: ChassisDims, h: HolderDims):
    from render_assembly import assembly_parts
    _, parts = assembly_parts()
    statics = []
    for name, part in parts:
        if name == "motor lid":  # the left one, plain
            statics.append(("lid_left", mesh_of(part), "lid"))
            continue
        if name == "XT60 holder lid":  # built below, its arm animated apart
            continue
        if name == "LiPo pack":
            continue
        statics.append((name.replace(" ", "_"), mesh_of(part, 0.05), MODULE_LOOK[name]))
    statics.append(("battery", mesh_of(battery_body(cd), 0.05), "battery"))
    for i, t in enumerate(tyres(cd)):
        statics.append((f"tyre{i}", mesh_of(t, 0.05), "tyre"))
    frame, _ = make_holder(h, cd)
    holder_lid = _to_side(make_lid(lid_dims(cd)), cd, -1) + to_car(frame, cd)
    statics.append(("holder_lid", mesh_of(holder_lid, 0.02), "holder"))
    return statics


def plug_meshes(h: HolderDims, cd: ChassisDims, male: bool):
    """The seated male or the mated female with its heat-shrink, in car
    coordinates, as [(name, verts, faces, look)]."""
    seat = Pos(h.x_rim, 0, h.z_plug)
    if male:
        parts = [("male", make_male(XT), "xt60")] + [
            ("shrink", s, "shrink") for s in make_shrink(XT, -XT.male_len, -1)]
    else:
        parts = [("female", make_female(XT), "xt60")] + [
            ("fshrink", s, "shrink") for s in make_shrink(XT, XT.female_body_len, +1)]
    out = []
    for name, part, look in parts:
        m = mesh_of(to_car(seat * part, cd), 0.02)
        out.append((name, m.vertices, m.faces, look))
    return out


SECTION_LIFT = 300.0  # the animated cutaway hangs this far above the car, out of the 3D views
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"


def cut_pieces(cd: ChassisDims, h: HolderDims, keep: Part):
    """The cutaway: every piece near the holder, cut by `keep`, as
    [(name, Part, look, role)]; role says what moves it in the movie. The
    lid and the holder get their own colours here (they print as one part)
    so the gap and the plinths between them read."""
    from render_assembly import assembly_parts
    _, oy, _ = holder_origin(cd)
    _, parts = assembly_parts()
    plate = next(p for n, p in parts if n == "chassis plate")
    motor = [p for n, p in parts if n == "N20 gearmotor"][1]
    frame, arm = make_holder(h, cd)
    seat = Pos(h.x_rim, 0, h.z_plug)
    sm, sf = make_shrink(XT, -XT.male_len, -1), make_shrink(XT, XT.female_body_len, +1)
    near = Pos(car_pts([-12, 0, 0], cd)[0], oy, 0) * Box(70, 40, 70)
    items = [("plate", plate & near, "plate", "static"),
             ("motor", motor, "motor", "static"),
             ("lid", _to_side(make_lid(lid_dims(cd)), cd, -1), "lid", "static"),
             ("frame", to_car(frame, cd), "holder", "static"),
             ("arm", to_car(arm, cd), "holder", "arm"),
             ("male", to_car(seat * make_male(XT), cd), "xt60", "male"),
             ("mshrink", to_car(seat * (sm[0] + sm[1]), cd), "shrink", "male"),
             ("female", to_car(seat * make_female(XT), cd), "amber", "female"),
             ("fshrink", to_car(seat * (sf[0] + sf[1]), cd), "shrink", "female")]
    out = []
    for name, part, look, role in items:
        c = part & keep
        if c is not None and c.volume > 1e-3:
            out.append((name, c, look, role))
    return out


def keep_half(cd: ChassisDims) -> Part:
    """Everything on the holder frame's -y side of the plug's centre plane
    (the car's inboard half), to be seen from +y."""
    return to_car(Pos(-40, -30, 3) * Box(240, 60, 120), cd)


def ortho_px(cam, p, w, aspect):
    """Pixel of world point p in an orthographic camera's w-wide image."""
    eye, target, ortho_w = cam[1], cam[2], cam[4]
    eye, target, p = (np.array(v, float) for v in (eye, target, p))
    z = eye - target
    z /= np.linalg.norm(z)
    x = np.cross([0, 0, 1], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    s = w / ortho_w
    return w / 2 + np.dot(p - target, x) * s, w / aspect / 2 - np.dot(p - target, y) * s


def label_layer(out: Path, w: int, hgt: int, labels, cam=None, aspect=None, size=22, title=None):
    """A transparent PNG of leader-line labels. labels: [(text, (tx, ty),
    [world points])] with the text's anchor in pixels; with cam, the points
    are projected through that orthographic camera."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, size)
    ink = (34, 38, 46, 255)
    for text, (tx, ty), points in labels:
        box = d.textbbox((tx, ty), text, font=font, anchor="mm")
        for p in points:
            px, py = ortho_px(cam, p, w, aspect) if cam else p
            ax = min(max(px, box[0]), box[2])
            ay = box[1] - 3 if py < box[1] else (box[3] + 3 if py > box[3] else ty)
            d.line([(ax, ay), (px, py)], fill=ink, width=2)
            d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=ink)
        pad = 6
        d.rounded_rectangle([box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad], 6,
                            fill=(255, 255, 255, 225), outline=ink, width=1)
        d.text((tx, ty), text, font=font, fill=ink, anchor="mm")
    if title:
        d.text((24, 22), title, font=ImageFont.truetype(FONT, size + 6), fill=ink)
    img.save(out)


def along_labels(cd: ChassisDims, h: HolderDims, lift: float = 0.0):
    """Labels for the cut along the plug's axis, anchors as fractions of
    the frame (x, y), points in holder coordinates."""
    P = lambda x, z: tuple(car_pts([x, 0, z], cd) + [0, 0, lift])  # noqa: E731
    return [
        ("pack's female", (0.20, 0.10), [P(h.x_rim + 4, h.z_plug + 5)]),
        ("male XT60 on the harness", (0.42, 0.10), [P(h.x_rim - 12, h.z_plug + 5)]),
        ("latch arm + barb", (0.66, 0.10), [P(h.x_root - 6, h.z_top - 0.5), P(h.x_barb - 1.2, h.z_plug_top - 0.5)]),
        ("gap: the lid's ceiling still flexes", (0.83, 0.40), [P(-8.0, h.gap / 2)]),
        ("plinths, over the lid's skirts", (0.50, 0.92), [P(-1.0, 0.6), P(-22.4, 0.6)]),
        ("lid pad clamps the motor", (0.85, 0.62), [P(-8.5, -2.3)]),
    ]


def across_labels(cd: ChassisDims, h: HolderDims, cut: float, lift: float):
    P = lambda y, z: tuple(car_pts([cut, y, z], cd) + [0, 0, lift])  # noqa: E731
    return [
        ("V-groove holds the chamfered (+) side", (0.24, 0.07), [P(-XT.width / 2 + 1.3, h.z_plug + 6.7)]),
        ("groove for the + / - marks (both sides)", (0.84, 0.24),
         [P(XT.width / 2 + h.side_fit + 0.15, h.z_plug + XT.axis_z)]),
        ("lip", (0.78, 0.07), [P(7.4, h.z_top - 0.6)]),
        ("latch arm", (0.52, 0.07), [P(0.0, h.z_top - 0.5)]),
        ("channel floor", (0.86, 0.36), [P(9.0, h.gap + 0.5)]),
        ("gap", (0.10, 0.40), [P(-6.0, h.gap / 2)]),
        ("motor (cut lengthwise)", (0.50, 0.88), [P(2.0, -8.0)]),
    ]


def movie_scene(cd: ChassisDims, h: HolderDims, render: bool = True):
    """The animated car. With render, also the floor and the lifted cutaway
    the movie's third camera films; without, just the car, for Quick Look."""
    statics = car_statics(cd, h)
    _, arm = make_holder(h, cd)
    am = mesh_of(to_car(arm, cd), 0.02)
    px, pz = arm_pivot(h)
    pivot = tuple(car_pts([px, 0, pz], cd))
    every = range(N_FRAMES + 1)
    male_keys = {f: tuple(male_offset(f)) for f in every}
    arm_keys = {f: arm_angle(h, f) for f in every}
    movers = [
        ("Male", "translate", (plug_meshes(h, cd, True), male_keys)),
        ("Arm", "rotate", ([("arm", am.vertices, am.faces, "holder")], pivot, arm_keys)),
        ("Female", "translate", (plug_meshes(h, cd, False),
                                 {f: tuple(female_offset(f)) for f in every})),
    ]
    for name, fn, moving, offset in (
            ("Lead", pack_lead, range(FEMALE_START, FEMALE_MATED + 1), female_offset),
            ("Harness", harness_lead, range(0, MALE_KEYS[-1][0] + 1), male_offset)):
        frames = sorted({0, N_FRAMES, *moving})
        per_frame = {f: fn(cd, h, offset(f)) for f in frames}
        for k, look in enumerate(("red", "black")):
            samples = [(f, per_frame[f][k][1]) for f in frames]
            movers.append((f"{name}_{look}", "points", (look, per_frame[0][k][2], samples)))
    target = car_pts([-12, 0, 4], cd)
    cameras = [
        framed("hero", target + [12, 14, -6], (-0.85, -1.0, 1.3), 60.0),
        framed("close", target + [-2, -1, 0], (-1.0, -0.65, 0.95), 29.0, focal=60.0),
    ]
    if not render:
        return stage(statics, movers, cameras, N_FRAMES)
    # the cutaway, lifted clear of the car: same motion, the female straight in
    lift = Pos(0, 0, SECTION_LIFT)
    groups = {"male": [], "arm": [], "female": []}
    for name, part, look, role in cut_pieces(cd, h, keep_half(cd)):
        m = mesh_of(lift * part, 0.02)
        if role == "static":
            statics.append((f"cut_{name}", m, look))
        else:
            groups[role].append((f"cut_{name}", m.vertices, m.faces, look))
    movers += [
        ("CutMale", "translate", (groups["male"], male_keys)),
        ("CutArm", "rotate", (groups["arm"], (pivot[0], pivot[1], pivot[2] + SECTION_LIFT), arm_keys)),
        ("CutFemale", "translate", (groups["female"], {f: tuple(female_cut_offset(f)) for f in every})),
    ]
    cameras.append(section_camera(cd, h))
    return stage(statics, movers, cameras, N_FRAMES, floor_z=-14.0)


SECTION_W, SECTION_ASPECT = 1920, 1920 / 560


def section_camera(cd: ChassisDims, h: HolderDims):
    lift = np.array([0, 0, SECTION_LIFT])
    t = car_pts([-20, 0, -1.5], cd) + lift
    return ("section", car_pts([-20, 300, -1.5], cd) + lift, t, 0, 112.0, SECTION_ASPECT)


def write_movie(cd: ChassisDims, h: HolderDims, usdz: Path, out: Path, w=960, hh=576) -> None:
    cams = ("hero", "close", "section")
    widths = {"hero": w, "close": w, "section": SECTION_W}
    sh = round(SECTION_W / SECTION_ASPECT)
    with tempfile.TemporaryDirectory() as tmp:
        T = Path(tmp)
        procs = [record(usdz, c, str(T / f"{c}.####.###.png"), f"0:{N_FRAMES}", widths[c]) for c in cams]
        # labels for the cutaway, and a caption per step
        cam = section_camera(cd, h)
        moving = ("pack's female", "male XT60 on the harness")
        labels = [(t, (fx * SECTION_W, fy * sh), pts) for t, (fx, fy), pts in
                  along_labels(cd, h, SECTION_LIFT) if t not in moving]
        label_layer(T / "labels.png", SECTION_W, sh, labels, cam, SECTION_ASPECT,
                    title="Cut through the plug's centre line")
        steps = [(0, MALE_KEYS[-1][0] + 8, "1  Slide the harness plug in from the front - the latch arm lifts, then drops behind it"),
                 (MALE_KEYS[-1][0] + 8, FEMALE_START, "2  The plug is held: barb behind it, V-groove and lip on top"),
                 (FEMALE_START, N_FRAMES + 1, "3  Plug the pack in from behind - nothing stands over the male's rim")]
        for i, (_, _, text) in enumerate(steps):
            label_layer(T / f"step{i}.png", 2 * w, 64, [], size=26, title=text)
        for p in procs:
            if p.wait() != 0:
                raise RuntimeError(f"usdrecord failed: {p.stderr.read().decode()[-800:]}")
        inputs = []
        for c in cams:
            inputs += ["-framerate", str(FPS), "-i", str(T / f"{c}.%08d.png")]
        inputs += ["-i", str(T / "labels.png")]
        for i in range(len(steps)):
            inputs += ["-i", str(T / f"step{i}.png")]
        W, H = 2 * w, hh + 64 + sh
        chain = (f"color=c=0xf4f4f2:s={W}x{H}:r={FPS}[bg];"
                 f"[bg][0]overlay=0:64:shortest=1[a];[a][1]overlay={w}:64[b];"
                 f"[b][2]overlay=0:{hh + 64}[c];[c][3]overlay=0:{hh + 64}[d];")
        last = "d"
        for i, (f0, f1, _) in enumerate(steps):
            chain += (f"[{last}][{4 + i}]overlay=0:0:enable='between(n,{f0},{f1 - 1})'[s{i}];")
            last = f"s{i}"
        chain += f"[{last}]format=yuv420p"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", chain,
                        "-frames:v", str(N_FRAMES + 1), "-c:v", "libx264", "-crf", "18",
                        "-movflags", "+faststart", str(out)], check=True)
        # poster: the last frame
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.1", "-i", str(out),
                        "-frames:v", "1", "-update", "1", str(out.with_suffix(".png"))], check=True)
    print(f"Wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB, {N_FRAMES / FPS:.1f} s) "
          f"and {out.with_suffix('.png').name}")


def section_scene(cd: ChassisDims, h: HolderDims):
    """Two cuts through the seated plug, holder, lid, motor and cradle:
    along the plug's axis (the latch, the gap, the plinths) and across it
    (the keyed outline). The first keeps the inboard half; the second is a
    thin slice, so the gap under the holder shows, lifted out of the first
    camera's view."""
    statics = [(f"{n}_a", mesh_of(p, 0.02), look)
               for n, p, look, _ in cut_pieces(cd, h, keep_half(cd))]
    cut = h.x_rim - 9.0  # holder x, through the solid housing behind the shroud
    keep_b = to_car(Pos(cut - 1.5, 0, 3) * Box(3, 60, 80), cd)
    lift = np.array([0, 0, SECTION_LIFT])
    statics += [(f"{n}_b", mesh_of(Pos(*lift) * p, 0.02), look)
                for n, p, look, _ in cut_pieces(cd, h, keep_b) if n not in ("female", "fshrink")]
    ta = car_pts([-12, 0, -3], cd)
    tb = car_pts([cut, 0, -3], cd) + lift
    cameras = [("along", car_pts([-12, 300, -3], cd), ta, 0, 74.0),
               ("across", car_pts([cut + 300, 0, -3], cd) + lift, tb, 0, 52.0)]
    return stage(statics, [], cameras), cameras, cut


def print_scene(cd: ChassisDims, h: HolderDims):
    lid = lid_for_print(make_holder_lid(h, cd), lid_dims(cd))
    bb = lid.bounding_box()
    lid = Pos(-bb.center().X, -bb.center().Y, 0) * lid
    bed = Pos(0, 0, -0.5) * Box(90, 70, 1)
    statics = [("lid", mesh_of(lid, 0.02), "holder"), ("bed", mesh_of(bed), "floor")]
    t = np.array([0, 0, bb.size.Z / 2])
    cameras = [framed("bed", t, (1.0, -1.2, 1.0), 26.0), framed("bed_back", t, (-1.1, 1.0, 0.9), 26.0)]
    return stage(statics, [], cameras)


def render_stills(name: str, text: str, cams, w=1100, labels=None) -> None:
    """Render one frame per camera and put them side by side, each with its
    labels (fractions-of-frame anchors) when given."""
    with tempfile.TemporaryDirectory() as tmp:
        T = Path(tmp)
        usdz = T / f"{name}.usdz"
        write_usdz(text, usdz)
        names = [c[0] if isinstance(c, tuple) else c for c in cams]
        procs = [record(usdz, c, str(T / f"{c}.####.###.png"), "0:0", w) for c in names]
        for p in procs:
            if p.wait() != 0:
                raise RuntimeError(f"usdrecord failed: {p.stderr.read().decode()[-800:]}")
        hgt = round(w * 0.6)
        inputs, chain = [], f"color=c=0xf4f4f2:s={w * len(names)}x{hgt}[bg];"
        last = "bg"
        for i, c in enumerate(names):
            inputs += ["-i", str(T / f"{c}.00000000.png")]
            chain += f"[{last}][{len(inputs) // 2 - 1}]overlay={i * w}:0[o{i}];"
            last = f"o{i}"
        for i, c in enumerate(names):
            if labels and labels.get(c):
                cam = next(k for k in cams if isinstance(k, tuple) and k[0] == c)
                lab = [(t, (fx * w, fy * hgt), pts) for t, (fx, fy), pts in labels[c]]
                label_layer(T / f"{c}_labels.png", w, hgt, lab, cam, w / hgt, size=19)
                inputs += ["-i", str(T / f"{c}_labels.png")]
                chain += f"[{last}][{len(inputs) // 2 - 1}]overlay={i * w}:0[l{i}];"
                last = f"l{i}"
        chain = chain + f"[{last}]null"
        out = HERE / f"{name}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", chain,
                        "-frames:v", "1", "-update", "1", str(out)], check=True)
    print(f"Wrote {out.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-movie", action="store_true")
    ap.add_argument("--no-stills", action="store_true")
    args = ap.parse_args()
    cd, h = ChassisDims(), HolderDims()
    if not args.no_stills:
        text, cams, cut = section_scene(cd, h)
        render_stills("xt60_holder_section", text, cams, labels={
            "along": along_labels(cd, h), "across": across_labels(cd, h, cut, SECTION_LIFT)})
        render_stills("xt60_holder_print", print_scene(cd, h), ("bed", "bed_back"))
    write_usdz(movie_scene(cd, h, render=False), HERE / "xt60_holder_twin.usdz")
    if not args.no_movie:
        with tempfile.TemporaryDirectory() as tmp:
            usdz = Path(tmp) / "xt60_holder_movie.usdz"
            write_usdz(movie_scene(cd, h), usdz)
            write_movie(cd, h, usdz, HERE / "xt60_holder.mp4")


if __name__ == "__main__":
    main()
