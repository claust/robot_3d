"""Render screenshots of an exported STL so the design can be checked visually.

Run with:  uv run render.py [model.stl]
Produces <model>_iso.png, <model>_top.png and <model>_front.png.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

VIEWS = {
    "iso": (30, -60),
    "top": (90, -90),
    "front": (0, -90),
}


def render(stl_path: Path) -> None:
    mesh = trimesh.load_mesh(stl_path)

    for name, (elev, azim) in VIEWS.items():
        fig = plt.figure(figsize=(6, 6))
        ax = fig.add_subplot(projection="3d")

        faces = Poly3DCollection(
            mesh.vertices[mesh.faces],
            facecolor="#4a90d9",
            edgecolor="#1c3f5f",
            linewidths=0.1,
        )
        ax.add_collection3d(faces)

        # Equal aspect ratio so circles stay circular
        span = mesh.bounds[1] - mesh.bounds[0]
        center = mesh.bounds.mean(axis=0)
        radius = span.max() / 2
        ax.set_xlim(center[0] - radius, center[0] + radius)
        ax.set_ylim(center[1] - radius, center[1] + radius)
        ax.set_zlim(center[2] - radius, center[2] + radius)
        ax.set_box_aspect((1, 1, 1))

        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm)")
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(f"{stl_path.stem} – {name}")

        out = stl_path.with_name(f"{stl_path.stem}_{name}.png")
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Wrote {out}")


if __name__ == "__main__":
    render(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("washer.stl"))
