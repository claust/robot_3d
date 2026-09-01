"""Automated PASS/FAIL design checks for the demo_07 sliding-gear fidget
gearbox, extending demo_04's assembly_check with the carriage mechanism.

Checks:
- interference: every part pair in BOTH end positions (engaged/disengaged)
- carriage travel sweep: the carriage (minus its detent bumps, which
  interfere with the rails by design between the detent holes) slides the
  full travel with zero intersection against the frame; the bumps must be
  free inside the holes at both detent positions and show the intended
  deflection-interference volume at mid-travel
- disengaged tooth clearance: z12 tips fully clear z20 tips
- snap lips: radial interference band + transient press-over volume, on a
  frame post and on the carriage post
- clearance report: calibrated 0.2 mm sliding/running fits
- gear mesh sweep (engaged): one full tooth cycle, zero intersection
- strain: post slit halves and the detent spring fingers, < 1.5% (PLA)
- sliceability: min walls, min feature heights, and an overhang scan of
  every print-oriented STL. The carriage's hold-down strip undersides are
  flat ~4.4 mm bridges (wall -> pedestal) and are excluded from the naive
  scan by their z-band; print_lint.py's bridge-aware scan covers them.

Run with:  uv run assembly_check.py [steps]
Exit code 0 only if every check passes.
"""

import sys
from pathlib import Path

import numpy as np
import trimesh
from build123d import Axis, export_stl

import fidget_gearbox as fg

RESULTS = []


def check(name: str, ok: bool, detail: str):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def ivol(a, b) -> float:
    r = a & b
    return 0.0 if r is None else abs(r.volume)


def overhang_area(
    stl_path: Path, max_deg=46.0, bed_z=0.25, exclude_bands=()
) -> float:
    """Face area (mm^2) steeper than max_deg above the bed, excluding
    pure-ceiling faces (nz ~ -1) inside known bridge z-bands."""
    mesh = trimesh.load_mesh(stl_path)
    nz_face = mesh.face_normals[:, 2]
    cz = mesh.triangles_center[:, 2]
    bad = (nz_face < -np.sin(np.radians(max_deg))) & (cz > bed_z)
    for z0, z1 in exclude_bands:
        bad &= ~((nz_face < -0.99) & (cz > z0) & (cz < z1))
    return float(mesh.area_faces[bad].sum())


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 13
    print("Building fidget gearbox model...")
    gb = fg.build()
    d = gb.dims
    g1, g2, g3 = gb.gears
    z1, z2, z3 = gb.teeth
    axes = [Axis((cx, cy, 0), (0, 0, 1)) for cx, cy in gb.centers]
    car = gb.carriage
    bumps = gb.bumps

    def at(part, t):  # slide a carriage-bound part t mm toward disengaged
        return part.translate((-t, 0, 0))

    print("\n-- interference (engaged and disengaged positions) --")
    for pos, t in (("engaged", 0.0), ("disengaged", fg.TRAVEL)):
        pairs = [
            ("gear1-gear2", at(g1, t), g2),
            ("gear1-gear3", at(g1, t), g3),
            ("gear2-gear3", g2, g3),
            ("gear1-frame", at(g1, t), gb.frame),
            ("gear2-frame", g2, gb.frame),
            ("gear3-frame", g3, gb.frame),
            ("gear1-carriage", at(g1, t), at(car, t)),
            ("gear2-carriage", g2, at(car, t)),
            ("carriage-frame", at(car, t), gb.frame),
        ]
        for name, a, b in pairs:
            v = ivol(a, b)
            check(f"{pos} {name}", v < 1e-4, f"intersection {v:.6f} mm^3")

    print("\n-- disengaged tooth clearance --")
    gap = at(g1, fg.TRAVEL).distance_to(g2)
    check("disengaged z12-z20 tip gap", gap >= 1.5, f"{gap:.2f} mm (>= 1.5)")

    print(f"\n-- carriage travel sweep ({steps} positions over "
          f"{fg.TRAVEL:g} mm) --")
    worst_core = 0.0
    ok_core = True
    bump_vols = []
    for k in range(steps):
        t = fg.TRAVEL * k / (steps - 1)
        v = ivol(at(car, t), gb.frame)
        vg = ivol(at(g1, t), g2) + ivol(at(g1, t), gb.frame)
        worst_core = max(worst_core, v, vg)
        if v > 1e-4 or vg > 1e-4:
            ok_core = False
            print(f"  t={t:5.2f}: carriage-frame={v:.6f} gear1={vg:.6f} <-- HIT")
        bump_vols.append((t, ivol(at(bumps, t), gb.frame)))
    check(
        "travel sweep zero intersection (carriage core + gear1)",
        ok_core,
        f"worst {worst_core:.6f} mm^3 over {steps} positions",
    )
    v_eng, v_dis = bump_vols[0][1], bump_vols[-1][1]
    v_mid = max(v for t, v in bump_vols[1:-1])
    check(
        "detent bumps free in holes at both positions",
        v_eng < 0.02 and v_dis < 0.02,
        f"bump-frame intersection {v_eng:.4f} / {v_dis:.4f} mm^3",
    )
    check(
        "detent bumps interfere between positions (click exists)",
        0.15 <= v_mid <= 2.5,
        f"max mid-travel bump-rail intersection {v_mid:.3f} mm^3 "
        f"(expected ~0.8)",
    )

    print("\n-- snap interference (transient press-over positions) --")
    lip_int = d["lip_interference"]
    check(
        "post lip radial interference",
        0.10 <= lip_int <= 0.20,
        f"lip r {d['lip_r']:.2f} vs bore r {d['bore_r']:.2f} -> "
        f"{lip_int:.2f} mm per side (intended 0.10-0.20)",
    )
    dz = d["lip_land_z1"] - fg.GEAR_Z0 - 3
    v = ivol(g1.translate((0, 0, dz)), car)
    check("carriage post lip press-over volume", 0.3 < v < 3.0,
          f"gear1-over-lip intersection {v:.3f} mm^3 (expected ~1.2)")
    v = ivol(g2.translate((0, 0, dz)), gb.frame)
    check("frame post lip press-over volume", 0.3 < v < 3.0,
          f"gear2-over-lip intersection {v:.3f} mm^3 (expected ~1.2)")

    print("\n-- clearance report (calibrated: 0.2 mm sliding/running fits) --")
    for i, (gear, probe) in enumerate(zip(gb.gears, gb.post_probes), 1):
        dist = gear.distance_to(probe)
        check(
            f"gear{i} bore-to-post clearance",
            abs(dist - fg.RUN_CLEARANCE) < 0.02,
            f"{dist:.3f} mm radial (calibrated {fg.RUN_CLEARANCE} mm)",
        )
    dist = car.distance_to(gb.rail_probe)
    check(
        "carriage-to-rail sliding clearance",
        abs(dist - fg.SLIDE_CLR) < 0.02,
        f"{dist:.3f} mm min (calibrated {fg.SLIDE_CLR} mm)",
    )
    check("carriage nose to deck stop", abs(d["nose_gap"] - 0.1) < 0.02,
          f"{d['nose_gap']:.2f} mm (over-travel guard, intended 0.1)")
    for i, gear in enumerate(gb.gears, 1):
        dist = gear.distance_to(gb.rail_probe)
        check(f"gear{i}-to-rail distance", dist >= 0.5, f"{dist:.2f} mm (>= 0.5)")
    check(
        "gear faces to carriage strips/pedestal",
        d["strip_under_gear"] >= 0.3,
        f"{d['strip_under_gear']:.2f} mm vertical gap (>= 0.3)",
    )
    d12 = g1.distance_to(g2)
    d23 = g2.distance_to(g3)
    check(
        "gear mesh backlash gap",
        d12 > 0.02 and d23 > 0.02,
        f"static tooth gaps {d12:.3f} / {d23:.3f} mm",
    )

    print(f"\n-- gear mesh sweep, engaged ({steps} steps, one tooth cycle) --")
    cycle = 360.0 / z1
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
            print(f"  theta={theta:6.2f}: g1g2={v12:.6f} g2g3={v23:.6f} <-- HIT")
    check(
        "mesh sweep zero intersection",
        ok,
        f"{steps} positions over {cycle:.1f} deg, worst {worst:.6f} mm^3",
    )

    print("\n-- strain (cantilever: strain = 1.5*t*y/L^2, PLA limit 1.5%) --")
    t, y, L = d["lip_flex_t"], d["lip_interference"], d["lip_deflection_len"]
    strain = 1.5 * t * y / L**2 * 100
    check("strain post slit halves", strain < 1.5,
          f"t={t:.2f} y={y:.2f} L={L:.1f} -> {strain:.2f}% (< 1.5%)")
    t, y, L = d["finger_t"], fg.BUMP_ENGAGE, d["finger_len"]
    strain = 1.5 * t * y / L**2 * 100
    check("strain detent fingers (click-out)", strain < 1.5,
          f"t={t:.2f} y={y:.2f} L={L:.1f} -> {strain:.2f}% (< 1.5%)")

    print("\n-- sliceability --")
    two_layers = 2 * fg.LAYER_HEIGHT
    for name, t in [
        ("side rails", fg.RAIL_W),
        ("rail wall at detent hole", (fg.RAIL_W - fg.HOLE_D) / 2),
        ("spine", fg.ARM_W),
        ("cross arms", fg.CROSS_W),
        ("carriage wall", fg.WALL_T),
        ("detent finger", fg.FING_T),
        ("paddle lip wall", fg.LIP_WALL),
        ("post at slit", (fg.POST_D - fg.SLIT_W) / 2),
        ("gear bore rim", gb.gears_pgw[0].dedendum_radius - d["bore_r"]),
    ]:
        check(f"min wall {name}", t >= 0.8, f"{t:.2f} mm (>= 0.8)")
    for name, h in [
        ("hold-down strip", fg.STRIP_T),
        ("carriage boss", fg.BOSS2_H),
        ("post snap lip", d["post_top"] - d["lip_z0"]),
    ]:
        check(f"min height {name}", h >= two_layers, f"{h:.2f} mm (>= 0.4)")
    floor = gb.face_width - fg.DISH_DEPTH
    check("gear3 dish floor thickness", floor >= 2.0,
          f"{floor:.2f} mm under each finger dish (>= 2.0)")
    dish_a, knob_a = fg.face_feature_reach()
    root_r = gb.gears_pgw[2].dedendum_radius
    check("gear3 dishes clear of tooth roots",
          fg.FEAT_RPOS + dish_a <= root_r - 1.0,
          f"dish rim r{fg.FEAT_RPOS + dish_a:.2f} vs root r{root_r:.2f} "
          "(>= 1.0 margin)")
    check("gear3 knob clear of tooth roots",
          fg.FEAT_RPOS + knob_a <= root_r - 0.5,
          f"knob base r{fg.FEAT_RPOS + knob_a:.2f} vs root r{root_r:.2f} "
          "(>= 0.5 margin; it adds material, so it only has to stay off "
          "the teeth)")
    check("gear3 dishes clear of the bore rim",
          fg.FEAT_RPOS - dish_a >= d["bore_r"] + 1.0,
          f"dish rim r{fg.FEAT_RPOS - dish_a:.2f} vs bore r{d['bore_r']:.2f} "
          "(>= 1.0 land)")
    check("gear3 knob clear of the snap lip",
          fg.FEAT_RPOS - knob_a >= d["lip_r"] + 0.3,
          f"knob base r{fg.FEAT_RPOS - knob_a:.2f} vs lip r{d['lip_r']:.2f} "
          "(>= 0.3 gap)")
    # the dome's base is its steepest point and it only flattens going up,
    # so no facet ever faces downward: printable with the gear flat
    knob_wall = np.degrees(
        np.arctan2(fg.KNOB_SPH_R - fg.KNOB_H, fg.knob_base_r())
    )
    check("gear3 knob dome self-supporting", knob_wall <= 50.0,
          f"{knob_wall:.1f} deg off vertical at the base (<= 50)")
    check("finger kerf printable gap", fg.KERF >= 0.8,
          f"{fg.KERF:.2f} mm (>= 0.8, narrower gaps fuse)")

    here = Path(__file__).parent
    export_stl(gb.frame, here / "frame.stl")
    car_print = gb.carriage_full.translate(
        (-d["x_engaged"], 0, -d["plate_z0"])
    )
    export_stl(car_print, here / "carriage.stl")
    for z, (cx, cy), part in zip(gb.teeth, gb.centers, gb.gears):
        export_stl(
            part.translate((-cx, -cy, -fg.GEAR_Z0)), here / f"gear_z{z}.stl"
        )
    strip_band = (
        fg.STRIP_Z0 - d["plate_z0"] - 0.05,
        fg.STRIP_Z0 - d["plate_z0"] + 0.05,
    )
    scans = [("frame.stl", ()), ("carriage.stl", (strip_band,))] + [
        (f"gear_z{z}.stl", ()) for z in gb.teeth
    ]
    for stl, bands in scans:
        area = overhang_area(here / stl, exclude_bands=bands)
        note = " (strip-bridge band excluded)" if bands else ""
        check(
            f"overhangs {stl}",
            area < 0.5,
            f"{area:.2f} mm^2 steeper than 45 deg above the bed{note}",
        )

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{'=' * 60}")
    print(f"{len(RESULTS) - len(fails)}/{len(RESULTS)} checks passed", end="")
    print(f", {len(fails)} FAILED" if fails else " -- ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
