"""Extract the mesh from a downloaded .3mf project into an STL for slicing.

Run with:  uv run extract_3mf.py <model.3mf> [out.stl]

Models downloaded from MakerWorld/Printables come as .3mf project files, which
the slice pipeline doesn't take. This flattens one to a single binary STL,
dropped next to the .3mf if no output path is given.

Objects are baked in scene coordinates, so a project holding several parts
keeps their relative layout, and the result is moved to sit at the origin with
its base on z=0. Print settings saved in the project are ignored — slicing
uses our own profiles.
"""

import sys
from pathlib import Path

import trimesh


def extract(threemf: Path, out: Path | None = None) -> Path:
    out = out or threemf.with_suffix(".stl")
    scene = trimesh.load(threemf, file_type="3mf")
    # A .3mf is always a scene: to_mesh() bakes each instance's placement
    # transform, which a plain concatenate of the geometries would discard.
    mesh = scene.to_mesh() if isinstance(scene, trimesh.Scene) else scene
    mesh.apply_translation(-mesh.bounds[0])
    mesh.export(out, file_type="stl")

    print(f"Wrote {out}: {len(mesh.faces)} facets, "
          f"{mesh.extents[0]:.2f} x {mesh.extents[1]:.2f} x {mesh.extents[2]:.2f} mm")
    if not mesh.is_watertight:
        print("WARNING: mesh is not watertight — check it renders and slices sanely")
    return out


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(__doc__)
    extract(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
