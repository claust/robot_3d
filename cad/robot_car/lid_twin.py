"""robot_car: viewable twin + movie of the slide-on motor lid coupon.

Two outputs, both from the very same Parts lid_coupons.py checks and prints:

- lid_coupon_twin.usdz -- base cradle, N20 motor and the car's lid (E),
  colour-coded, with the lid ANIMATED sliding on from the inboard side,
  pausing seated, and sliding back off. macOS Quick Look plays USDZ animation directly:
      qlmanage -p robot_car/lid_coupon_twin.usdz
      open robot_car/lid_coupon_twin.usdz        # Preview.app
- lid_coupon_slide.mp4 -- the same motion rendered as a short movie: the
  USDZ's two cameras rendered frame by frame with macOS's usdrecord
  (Hydra/Storm, a real z-buffered renderer -- matplotlib's painter's
  algorithm showed walls through the lid) and stitched by ffmpeg.

Run with:  uv run robot_car/lid_twin.py [--no-movie]
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from build123d import Pos, export_stl  # noqa: E402

from lid_coupons import CHOSEN, make_base, make_lid, motor_placement  # noqa: E402

COLOURS = {"base": "#5a6472", "motor": "#9aa5b1", "lid": "#e07b39"}
FPS = 24
OFF_Y = -26.0  # lid fully withdrawn (inboard of the channel)
# keyframes: (frame, lid y) -- ease-in/out between them
KEYS = [(0, OFF_Y), (12, OFF_Y), (48, 0.0), (72, 0.0), (108, OFF_Y), (120, OFF_Y)]


def srgb_to_linear(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


def mesh_of(part, tol=0.02):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "p.stl"
        export_stl(part, p, tolerance=tol, angular_tolerance=0.2)
        return trimesh.load_mesh(p)


def lid_y(frame: int) -> float:
    for (f0, y0), (f1, y1) in zip(KEYS, KEYS[1:]):
        if f0 <= frame <= f1:
            t = (frame - f0) / max(f1 - f0, 1)
            s = t * t * (3 - 2 * t)  # smoothstep
            return y0 + (y1 - y0) * s
    return KEYS[-1][1]


def fmt(a):
    return ", ".join(f"({x:.4g}, {y:.4g}, {z:.4g})" for x, y, z in a)


def usda(meshes: dict) -> str:
    n_frames = KEYS[-1][0]
    L = ["#usda 1.0", "(", '    defaultPrim = "LidCoupon"', "    metersPerUnit = 0.001",
         '    upAxis = "Z"', f"    startTimeCode = 0", f"    endTimeCode = {n_frames}",
         f"    timeCodesPerSecond = {FPS}", ")", "", 'def Xform "LidCoupon"', "{",
         '    def Scope "Looks"', "    {"]
    for name, hexc in COLOURS.items():
        r, g, b = srgb_to_linear(hexc)
        L += [f'        def Material "{name}"', "        {",
              f"            token outputs:surface.connect = </LidCoupon/Looks/{name}/Surface.outputs:surface>",
              '            def Shader "Surface"', "            {",
              '                uniform token info:id = "UsdPreviewSurface"',
              f"                color3f inputs:diffuseColor = ({r:.4f}, {g:.4f}, {b:.4f})",
              "                float inputs:roughness = 0.6", "                float inputs:metallic = 0",
              "                token outputs:surface", "            }", "        }"]
    L += ["    }", ""]
    for name, m in meshes.items():
        lo, hi = m.bounds
        normals = np.repeat(m.face_normals, 3, axis=0)
        L += [f'    def Xform "{name}_xf"', "    {"]
        if name == "lid":
            samples = ", ".join(f"{f}: (0, {lid_y(f):.4g}, 0)" for f in range(n_frames + 1))
            L += [f"        double3 xformOp:translate.timeSamples = {{ {samples} }}",
                  '        uniform token[] xformOpOrder = ["xformOp:translate"]']
        L += [f'        def Mesh "{name}" (', '            prepend apiSchemas = ["MaterialBindingAPI"]',
              "        )", "        {", '            uniform token subdivisionScheme = "none"',
              f"            float3[] extent = [({lo[0]:.4g}, {lo[1]:.4g}, {lo[2]:.4g}), ({hi[0]:.4g}, {hi[1]:.4g}, {hi[2]:.4g})]",
              f"            int[] faceVertexCounts = [{', '.join(['3'] * len(m.faces))}]",
              f"            int[] faceVertexIndices = [{', '.join(map(str, m.faces.ravel()))}]",
              f"            point3f[] points = [{fmt(m.vertices)}]",
              f"            normal3f[] normals = [{fmt(normals)}] (", '                interpolation = "faceVarying"', "            )",
              f"            rel material:binding = </LidCoupon/Looks/{name}>", "        }", "    }"]
    for name, eye, target in CAMERAS:
        L += camera_prim(name, np.array(eye, float), np.array(target, float))
    L += ["}", ""]
    return "\n".join(L)


# (name, eye, look-at) in mm. The coupon spans x +-17, y -11..25, z 0..17.
CAMERAS = [
    ("iso", (-95, -110, 85), (0, 4, 8)),  # from inboard, above, off to -X
    ("end", (0, -150, 30), (0, 4, 8)),  # looking down the channel from inboard
]


def camera_prim(name, eye, target):
    """A UsdGeomCamera looking from eye at target, Z up. Camera space looks
    down -Z, so the camera's local +Z axis points from target back to eye."""
    z = eye - target; z /= np.linalg.norm(z)
    x = np.cross([0, 0, 1], z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    rows = [(*x, 0), (*y, 0), (*z, 0), (*eye, 1)]
    m = ", ".join("(" + ", ".join(f"{v:.6g}" for v in r) + ")" for r in rows)
    return [f'    def Camera "{name}"', "    {",
            "        float focalLength = 50", "        float horizontalAperture = 20.955",
            "        float verticalAperture = 12.573",  # 5:3 frame
            "        float2 clippingRange = (10, 2000)",
            f"        matrix4d xformOp:transform = ( {m} )",
            '        uniform token[] xformOpOrder = ["xformOp:transform"]', "    }"]


def write_usdz(meshes: dict, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "lid_coupon_twin.usda"
        a.write_text(usda(meshes))
        c = Path(tmp) / "lid_coupon_twin.usdc"
        subprocess.run(["usdcat", "-o", str(c), str(a)], check=True)
        if out.exists():
            out.unlink()
        subprocess.run(["usdzip", str(out), str(c)], check=True, stdout=subprocess.DEVNULL)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")
    chk = subprocess.run(["usdchecker", str(out)], capture_output=True, text=True)
    print(f"usdchecker: {(chk.stdout + chk.stderr).strip().splitlines()[-1]}")


def write_movie(usdz: Path, out: Path) -> None:
    n_frames = KEYS[-1][0]
    with tempfile.TemporaryDirectory() as tmp:
        # placeholder form matters: "####" prints frame 10+ as "1e+01" and
        # the files overwrite each other; "####.###" gives plain 8-digit ints
        procs = [subprocess.Popen(["usdrecord", "--frames", f"0:{n_frames}", "--imageWidth", "800",
                                   "--cam", name, str(usdz), str(Path(tmp) / f"{name}.########.png")],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                 for name, _, _ in CAMERAS]
        for pr in procs:
            if pr.wait() != 0:
                raise RuntimeError("usdrecord failed")
        inputs = []
        for name, _, _ in CAMERAS:
            inputs += ["-framerate", str(FPS), "-i", str(Path(tmp) / f"{name}.%08d.png")]
        n = len(CAMERAS)
        # usdrecord leaves the background transparent (black once encoded):
        # stack the views, then lay them over a light ground
        w, h = 800, 480
        chain = "".join(f"[{i}]" for i in range(n)) + f"hstack=inputs={n}[v];"
        chain += f"color=c=0xeeeeee:s={w * n}x{h}[bg];[bg][v]overlay=shortest=1,format=yuv420p"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                        "-filter_complex", chain, str(out)], check=True)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.2f} MB, {n_frames / FPS:.0f} s, "
          f"{n} views: {', '.join(c[0] for c in CAMERAS)})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-movie", action="store_true")
    args = ap.parse_args()
    d = CHOSEN
    meshes = {"base": mesh_of(make_base(d)), "motor": mesh_of(motor_placement(d)),
              "lid": mesh_of(make_lid(d))}
    print({k: len(m.faces) for k, m in meshes.items()}, "triangles")
    usdz = HERE / "lid_coupon_twin.usdz"
    write_usdz(meshes, usdz)
    if not args.no_movie:
        write_movie(usdz, HERE / "lid_coupon_slide.mp4")


if __name__ == "__main__":
    main()
