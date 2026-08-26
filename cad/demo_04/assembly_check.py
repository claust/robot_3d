"""Automated PASS/FAIL design checks for the demo_04 gearbox, in the spirit
of print_pipeline.py verify — run BEFORE slicing anything.

Checks:
- interference: boolean-intersect every part pair in assembled position
  (must be zero); snap features are additionally checked in their transient
  press-over position, where the intersection must equal the intended
  interference (nonzero, bounded)
- clearance report: minimum distances asserted against calibrated values
- gear mesh sweep: rotates the train through one full tooth cycle asserting
  zero intersection at every step
- snap-arm strain: cantilever formula strain = 1.5*t*y/L^2 under 1.5% (PLA)
- sliceability: min walls, snap lip heights, and a mesh overhang scan of
  every print-oriented STL (all faces <= 45 degrees or on the bed)

Run with:  uv run assembly_check.py [steps]
Exit code 0 only if every check passes.
"""

import sys
from pathlib import Path

import numpy as np
import trimesh
from build123d import Axis, export_stl

import gearbox

RESULTS = []


def check(name: str, ok: bool, detail: str):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def ivol(a, b) -> float:
    """Boolean intersection volume of two parts (0.0 if disjoint)."""
    r = a & b
    return 0.0 if r is None else abs(r.volume)


def overhang_area(stl_path: Path, max_deg=46.0, bed_z=0.25) -> float:
    """Total face area (mm^2) steeper than max_deg overhang, above the bed."""
    mesh = trimesh.load_mesh(stl_path)
    nz = mesh.triangles_center[:, 2]
    bad = (mesh.face_normals[:, 2] < -np.sin(np.radians(max_deg))) & (nz > bed_z)
    return float(mesh.area_faces[bad].sum())


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 13
    print("Building gearbox model...")
    gb = gearbox.build()
    d = gb.dims
    g1, g2, g3 = gb.gears
    z1, z2, z3 = gb.teeth
    axes = [Axis((cx, cy, 0), (0, 0, 1)) for cx, cy in gb.centers]

    print("\n-- interference (assembled position) --")
    pairs = [
        ("gear1-gear2", g1, g2),
        ("gear2-gear3", g2, g3),
        ("gear1-gear3", g1, g3),
        ("gear1-base", g1, gb.base),
        ("gear2-base", g2, gb.base),
        ("gear3-base", g3, gb.base),
        ("gear1-lid", g1, gb.lid),
        ("gear2-lid", g2, gb.lid),
        ("gear3-lid", g3, gb.lid),
        ("base-lid", gb.base, gb.lid),
    ]
    for name, a, b in pairs:
        v = ivol(a, b)
        check(f"interference {name}", v < 1e-4, f"intersection {v:.6f} mm^3")

    print("\n-- snap interference (transient press-over positions) --")
    lip_int = d["lip_interference"]
    check(
        "post lip radial interference",
        0.10 <= lip_int <= 0.20,
        f"lip r {d['lip_r']:.2f} vs bore r {d['bore_r']:.2f} -> "
        f"{lip_int:.2f} mm per side (intended 0.10-0.20)",
    )
    # slide gear1 up so its bore band sits over the lip land: intersection
    # must be exactly the lip material inside the bore path, not more
    transient = g1.translate((0, 0, d["lip_land_z1"] - gearbox.GEAR_Z0 - 3))
    v = ivol(transient, gb.base)
    check(
        "post lip press-over volume",
        0.3 < v < 3.0,
        f"gear-over-lip intersection {v:.3f} mm^3 (expected ~1.2)",
    )
    arm_defl = d["arm_deflection"]
    check(
        "snap bump engagement",
        0.3 <= arm_defl <= 0.6,
        f"bump protrudes {arm_defl:.2f} mm past arm inner face",
    )
    lifted = gb.lid.translate((0, 0, 1.0))
    v = ivol(lifted, gb.base)
    check(
        "snap arm press-over volume",
        0.2 < v < 20.0,
        f"lid lifted 1 mm: bump/arm intersection {v:.3f} mm^3 over 4 arms",
    )

    print("\n-- clearance report (calibrated: 0.2 running, 0.10-0.15 static) --")
    for i, (gear, probe) in enumerate(zip(gb.gears, gb.post_probes), 1):
        dist = gear.distance_to(probe)
        check(
            f"gear{i} bore-to-post clearance",
            abs(dist - gearbox.RUN_CLEARANCE) < 0.02,
            f"{dist:.3f} mm radial (calibrated {gearbox.RUN_CLEARANCE} mm)",
        )
    for i, gear in enumerate(gb.gears, 1):
        dist = gear.distance_to(gb.wall_probe)
        check(f"gear{i} tip-to-wall", dist >= 1.0, f"{dist:.2f} mm (>= 1.0)")
    for i, gear in enumerate(gb.gears, 1):
        dist = gear.distance_to(gb.lid)
        check(f"gear{i}-to-lid distance", dist >= 1.0, f"{dist:.2f} mm (>= 1.0)")
    headroom = d["ceil_z"] - d["gear_top"]
    check("gear top to lid ceiling", headroom >= 1.5, f"{headroom:.2f} mm (>= 1.5)")
    post_clear = d["ceil_z"] - d["post_top"]
    check("post tip to lid ceiling", post_clear >= 0.5, f"{post_clear:.2f} mm (>= 0.5)")
    static = gearbox.SNAP_CLEARANCE
    check(
        "static fit clearances (lid lip, arm gap)",
        0.10 <= static <= 0.15,
        f"{static:.2f} mm radial per side (calibrated 0.10-0.15)",
    )
    d12 = g1.distance_to(g2)
    d23 = g2.distance_to(g3)
    check(
        "gear mesh backlash gap",
        d12 > 0.02 and d23 > 0.02,
        f"static tooth gaps {d12:.3f} / {d23:.3f} mm",
    )

    print(f"\n-- gear mesh sweep ({steps} steps over one tooth cycle) --")
    cycle = 360.0 / z1  # one full tooth cycle of gear1
    worst = 0.0
    ok = True
    for k in range(steps):
        theta = cycle * k / (steps - 1)
        r1 = g1.rotate(axes[0], theta)
        r2 = g2.rotate(axes[1], -theta * z1 / z2)
        r3 = g3.rotate(axes[2], theta * z1 / z3)
        v12 = ivol(r1, r2)
        v23 = ivol(r2, r3)
        worst = max(worst, v12, v23)
        if v12 > 1e-4 or v23 > 1e-4:
            ok = False
            print(f"  theta={theta:6.2f}: g1g2={v12:.6f} g2g3={v23:.6f} mm^3  <-- HIT")
    check(
        "mesh sweep zero intersection",
        ok,
        f"{steps} positions over {cycle:.1f} deg, worst intersection {worst:.6f} mm^3",
    )

    print("\n-- snap strain (cantilever: strain = 1.5*t*y/L^2, PLA limit 1.5%) --")
    for name, t, y, L in [
        ("post slit halves", d["lip_flex_t"], d["lip_interference"],
         d["lip_deflection_len"]),
        ("lid snap arms", d["arm_flex_t"], d["arm_deflection"], d["arm_flex_len"]),
    ]:
        strain = 1.5 * t * y / L**2 * 100
        check(
            f"strain {name}",
            strain < 1.5,
            f"t={t:.2f} y={y:.2f} L={L:.1f} -> {strain:.2f}% (< 1.5%)",
        )

    print("\n-- sliceability --")
    two_layers = 2 * gearbox.LAYER_HEIGHT
    for name, t in [
        ("perimeter wall", gearbox.WALL_T),
        ("snap arm", gearbox.ARM_T),
        ("lid plate", gearbox.LID_T),
        ("lid locating lip", gearbox.LID_LIP_T),
        ("base plate", gearbox.BASE_T),
        ("gear bore rim", gb.gears_pgw[0].dedendum_radius - d["bore_r"]),
    ]:
        check(f"min wall {name}", t >= 0.8, f"{t:.2f} mm (>= 0.8)")
    lip_h = d["post_top"] - d["lip_z0"]
    bump_h = gearbox.BUMP_TOP_Z - d["bump_cham_z"]
    check("post snap lip height", lip_h >= two_layers, f"{lip_h:.2f} mm (>= 0.4)")
    check("wall snap bump height", bump_h >= two_layers, f"{bump_h:.2f} mm (>= 0.4)")

    here = Path(__file__).parent
    lid_print = gearbox.lid_print_orientation(gb)
    export_stl(lid_print, here / "lid.stl")
    export_stl(gb.base, here / "base.stl")
    for z, (cx, cy), part in zip(gb.teeth, gb.centers, gb.gears):
        export_stl(
            part.translate((-cx, -cy, -gearbox.GEAR_Z0)), here / f"gear_z{z}.stl"
        )
    for stl in ["base.stl", "lid.stl"] + [f"gear_z{z}.stl" for z in gb.teeth]:
        area = overhang_area(here / stl)
        check(
            f"overhangs {stl}",
            area < 0.5,
            f"{area:.2f} mm^2 of faces steeper than 45 deg above the bed",
        )

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{'=' * 60}")
    print(f"{len(RESULTS) - len(fails)}/{len(RESULTS)} checks passed", end="")
    print(f", {len(fails)} FAILED" if fails else " -- ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
