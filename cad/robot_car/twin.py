"""robot_car: colour-coded USD "digital twin" of the assembled robot car.

Writes a single self-contained .usdz that macOS Quick Look and Preview open
directly (spacebar in Finder, or double-click) with real materials and
orbit/zoom -- a 3D model to walk around, not a drawing.

Every part is placed by the same helpers assembly.py's PASS/FAIL checks
use, so the twin always shows the current design. Each module gets its own
Mesh prim and its own UsdPreviewSurface material, so parts stay
individually selectable and distinguishable by colour.

Units are millimetres (metersPerUnit = 0.001) with Z up, matching the CAD.

Run with:  uv run robot_car/twin.py [--tolerance 0.02]
Writes robot_car/robot_car_twin.usdz (gitignored). Open with:
    qlmanage -p robot_car/robot_car_twin.usdz     # Quick Look
    open robot_car/robot_car_twin.usdz            # Preview.app
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

import numpy as np
import trimesh
from build123d import export_stl

from render_assembly import COLOURS, assembly_parts

# Roughness/metallic per module, so the twin reads as materials rather than
# eight flat colours: printed PLA is matt, the motor cans and the O-ring
# wheels are not.
FINISH = {
    "chassis plate": (0.75, 0.0),
    "front skid": (0.75, 0.0),
    "N20 gearmotor": (0.35, 0.9),
    "drive wheel": (0.85, 0.0),
    "Pi Zero 2 W": (0.55, 0.0),
    "DRV8833 driver": (0.55, 0.0),
    "MP1584EN buck": (0.55, 0.0),
    "LiPo pack": (0.45, 0.0),
}


def srgb_to_linear(hex_colour: str) -> tuple[float, float, float]:
    """UsdPreviewSurface diffuseColor is linear, the palette is sRGB."""
    out = []
    for i in (1, 3, 5):
        c = int(hex_colour[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def ident(name: str) -> str:
    """USD prim names must be valid identifiers."""
    return "".join(ch if ch.isalnum() else "_" for ch in name)


def meshes(parts, tolerance: float, angular_tolerance: float):
    """Tessellate every part once, at a resolution chosen for viewing
    rather than for printing -- the twin does not need 1 micron chords."""
    out, counter = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for i, (module, part) in enumerate(parts):
            stl = Path(tmp) / f"part_{i}.stl"
            export_stl(part, stl, tolerance=tolerance,
                       angular_tolerance=angular_tolerance)
            mesh = trimesh.load_mesh(stl)
            counter[module] = counter.get(module, 0) + 1
            # instance suffix: the two motors and two wheels share a module
            out.append((module, f"{ident(module)}_{counter[module]}", mesh))
    return out


def fmt_points(a: np.ndarray) -> str:
    return ", ".join(f"({x:.4g}, {y:.4g}, {z:.4g})" for x, y, z in a)


def usda(mesh_list) -> str:
    lines = [
        "#usda 1.0",
        "(",
        '    defaultPrim = "RobotCar"',
        "    metersPerUnit = 0.001",
        '    upAxis = "Z"',
        '    doc = "robot car -- colour-coded assembly twin"',
        ")",
        "",
        'def Xform "RobotCar"',
        "{",
        '    def Scope "Looks"',
        "    {",
    ]
    for module in dict.fromkeys(m for m, _, _ in mesh_list):
        r, g, b = srgb_to_linear(COLOURS[module])
        rough, metal = FINISH[module]
        mat = ident(module)
        lines += [
            f'        def Material "{mat}"',
            "        {",
            f"            token outputs:surface.connect = "
            f"</RobotCar/Looks/{mat}/Surface.outputs:surface>",
            '            def Shader "Surface"',
            "            {",
            '                uniform token info:id = "UsdPreviewSurface"',
            f"                color3f inputs:diffuseColor = ({r:.4f}, {g:.4f}, {b:.4f})",
            f"                float inputs:roughness = {rough}",
            f"                float inputs:metallic = {metal}",
            "                token outputs:surface",
            "            }",
            "        }",
        ]
    lines += ["    }", ""]

    for module, name, mesh in mesh_list:
        v, f = mesh.vertices, mesh.faces
        lo, hi = mesh.bounds
        # flat shading: one face normal repeated per corner
        normals = np.repeat(mesh.face_normals, 3, axis=0)
        lines += [
            f'    def Mesh "{name}" (',
            '        prepend apiSchemas = ["MaterialBindingAPI"]',
            "    )",
            "    {",
            f"        uniform token subdivisionScheme = \"none\"",
            f"        float3[] extent = [({lo[0]:.4g}, {lo[1]:.4g}, {lo[2]:.4g}), "
            f"({hi[0]:.4g}, {hi[1]:.4g}, {hi[2]:.4g})]",
            f"        int[] faceVertexCounts = [{', '.join(['3'] * len(f))}]",
            f"        int[] faceVertexIndices = [{', '.join(map(str, f.ravel()))}]",
            f"        point3f[] points = [{fmt_points(v)}]",
            f"        normal3f[] normals = [{fmt_points(normals)}] (",
            '            interpolation = "faceVarying"',
            "        )",
            f"        rel material:binding = </RobotCar/Looks/{ident(module)}>",
            "    }",
        ]
    lines += ["}", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tolerance", type=float, default=0.02,
                    help="linear tessellation tolerance in mm (default 0.02)")
    ap.add_argument("--angular-tolerance", type=float, default=0.2,
                    help="angular tessellation tolerance in rad (default 0.2)")
    ap.add_argument("--keep-usda", action="store_true",
                    help="also leave the intermediate ASCII .usda next to the .usdz")
    args = ap.parse_args()

    _, parts = assembly_parts()
    mesh_list = meshes(parts, args.tolerance, args.angular_tolerance)
    tris = sum(len(m.faces) for _, _, m in mesh_list)
    print(f"{len(mesh_list)} parts, {tris} triangles "
          f"(tolerance {args.tolerance} mm / {args.angular_tolerance} rad)")

    out = HERE / "robot_car_twin.usdz"
    with tempfile.TemporaryDirectory() as tmp:
        ascii_path = Path(tmp) / "robot_car_twin.usda"
        ascii_path.write_text(usda(mesh_list))
        # crunch the ASCII down to binary usdc before packaging: same
        # scene, a fraction of the bytes for Quick Look to parse
        binary = Path(tmp) / "robot_car_twin.usdc"
        subprocess.run(["usdcat", "-o", str(binary), str(ascii_path)], check=True)
        if out.exists():
            out.unlink()  # usdzip appends to an existing archive
        subprocess.run(["usdzip", str(out), str(binary)], check=True,
                       stdout=subprocess.DEVNULL)
        if args.keep_usda:
            shutil.copy(ascii_path, HERE / ascii_path.name)
            print(f"Wrote {HERE / ascii_path.name}")

    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    check = subprocess.run(["usdchecker", str(out)], capture_output=True, text=True)
    print(f"usdchecker: {(check.stdout + check.stderr).strip() or 'OK'}")
    return check.returncode


if __name__ == "__main__":
    sys.exit(main())
