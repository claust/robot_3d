"""print_lint.py: design-time printability linter for STLs already in print
orientation (this codebase's convention: as-exported = as-printed, bed at
z=0, +Z up), in the spirit of demo_04/assembly_check.py's PASS/FAIL checks.

Unlike assembly_check.py (which knows the part's own parametric geometry),
this operates on any STL from the mesh alone -- a last line of defence for
overhangs, tippy prints, weak first layers, and plate-layout fusions that
slip past a single part's own design checks.

Checks (see each check_*() docstring for the full rule):
  1. UNSUPPORTED OVERHANGS -- downward faces steeper than --threshold-deg
     with nothing within the support gap tolerance below them; clustered by
     face adjacency and scored against this codebase's ~10 mm bridge rule
     of thumb (see demo_05/README.md).
  2. KNOCKOVER RISK -- tall/skinny bed footprint (h/w ratio) with a small
     contact patch: the "34 mm tower on a 10x12 base" failure mode.
  3. FIRST-LAYER ISLANDS -- small isolated regions of material at the first
     layer (z=0.15) that won't stick to the bed.
  4. BODY SEPARATION -- connected bodies on one plate that are touching,
     overlapping, or suspiciously close -- the "two motors and a PCB fused
     into one 48 mm brick" plate-layout bug.

Uses trimesh's native ray casting (mesh.ray / mesh.contains(), rtree-backed)
and native cross-sections (mesh.section().to_2D().polygons_full, shapely +
networkx-backed) throughout -- rtree, shapely and networkx are required
project dependencies (see cad/pyproject.toml).

Usage:
  uv run print_lint.py <model.stl> [--threshold-deg 50] [--strict]
  uv run print_lint.py --selftest

Exit code 0 normally; nonzero only with --strict AND at least one HIGH
finding.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import ConvexHull, QhullError, cKDTree

# ---------------------------------------------------------------------------
# tunables
# ---------------------------------------------------------------------------

FIRST_LAYER_H = 0.3  # mm -- below this, a downward face IS the bed contact
SUPPORT_GAP_TOL = 0.6  # mm -- a hit closer than this below a facet counts as
# "already supported" (demo_06's dummy motor deliberately leaves a 0.2 mm
# breakaway gap between its shaft and its support fin; must not flag HIGH)
BRIDGE_MAX_MM = 10.0  # codebase bridge rule of thumb (demo_05/README.md)
OVERHANG_MIN_AREA = 30.0  # mm^2, second HIGH trigger for overhang clusters
NEAR_THRESHOLD_MARGIN_DEG = 5.0  # cluster's steepest face within this many
# degrees of --threshold-deg is downgraded to LOW (marginal, likely fine)

ISLAND_MED_MAX = 30.0  # mm^2
ISLAND_HIGH_MAX = 15.0  # mm^2
LAYER_Z = 0.15  # mm -- first-layer section height

FUSION_HIGH_MM = 1.0  # mm
FUSION_LOW_MM = 3.0  # mm

SEVERITY_ORDER = {"HIGH": 0, "MED": 1, "LOW": 2}


@dataclass
class Finding:
    check: str
    severity: str
    location: tuple[float, float, float]
    reason: str
    term: str
    metric: float = 0.0


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def min_caliper_width(points_xy: np.ndarray) -> float:
    """Minimum width of the point set's bounding rectangle, over all
    rectangle orientations (rotating calipers on the convex hull). This is
    the standard way to estimate an irregular region's narrowest span --
    used both for a cluster's bridge-span estimate and a bed-contact
    patch's stability width."""
    pts = np.asarray(points_xy, dtype=float)
    pts = np.unique(pts, axis=0)
    if len(pts) < 2:
        return 0.0
    if len(pts) == 2:
        return 0.0  # a line has zero width
    try:
        hull = ConvexHull(pts)
    except QhullError:
        return 0.0
    hp = pts[hull.vertices]
    n = len(hp)
    if n < 3:
        return 0.0
    edges = np.roll(hp, -1, axis=0) - hp
    lengths = np.linalg.norm(edges, axis=1)
    widths = []
    for e, length in zip(edges, lengths):
        if length < 1e-9:
            continue
        normal = np.array([-e[1], e[0]]) / length
        proj = hp @ normal
        widths.append(proj.max() - proj.min())
    return float(min(widths)) if widths else 0.0


def min_mesh_distance(a: trimesh.Trimesh, b: trimesh.Trimesh) -> float:
    """Minimum distance between two meshes' surfaces, vertex-to-vertex via
    scipy cKDTree in both directions -- the same approximation
    demo_06/assembly.py uses (a plain distance query is simpler than
    trimesh's face-accurate ProximityQuery for this purpose and plenty
    tight given the STL tessellation)."""
    tree_b = cKDTree(b.vertices)
    d_ab, _ = tree_b.query(a.vertices)
    tree_a = cKDTree(a.vertices)
    d_ba, _ = tree_a.query(b.vertices)
    return float(min(d_ab.min(), d_ba.min()))


def bodies_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh, max_samples: int = 300) -> bool:
    """Sample-based volumetric overlap test between two bodies, via
    mesh.contains() (rtree-accelerated ray parity test). Samples face
    centroids -- not corner vertices, which for axis-aligned boxes tend to
    sit exactly on the other body's boundary and never register as
    strictly inside."""
    amin, amax = a.bounds
    bmin, bmax = b.bounds
    if np.any(amax < bmin) or np.any(bmax < amin):
        return False
    rng = np.random.default_rng(0)

    def sample(mesh):
        pts = mesh.triangles_center
        if len(pts) > max_samples:
            idx = rng.choice(len(pts), max_samples, replace=False)
            pts = pts[idx]
        jitter = rng.uniform(-1e-3, 1e-3, size=pts.shape[:1] + (2,))
        pts = pts.copy()
        pts[:, :2] += jitter
        return pts

    return bool(a.contains(sample(b)).any() or b.contains(sample(a)).any())


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------


def _unsupported_facets(mesh: trimesh.Trimesh, candidates: np.ndarray,
                         centroids: np.ndarray) -> np.ndarray:
    """One batched mesh.ray.intersects_location call (rtree-accelerated)
    for every candidate facet at once: a facet is supported if a
    straight-down ray from just below its centroid hits more mesh within
    SUPPORT_GAP_TOL."""
    origins = centroids[candidates].copy()
    origins[:, 2] -= 0.02  # start just below each facet's own surface
    directions = np.tile([0.0, 0.0, -1.0], (len(candidates), 1))
    locations, index_ray, index_tri = mesh.ray.intersects_location(
        origins, directions, multiple_hits=True
    )
    supported = np.zeros(len(candidates), dtype=bool)
    if len(index_ray):
        # drop self-hits: a candidate facet's own triangle, hit again by
        # its own ray (possible right at the offset origin)
        keep = index_tri != candidates[index_ray]
        index_ray, locations = index_ray[keep], locations[keep]
        if len(index_ray):
            gap = origins[index_ray, 2] - locations[:, 2]
            supported[np.unique(index_ray[gap < SUPPORT_GAP_TOL])] = True
    return candidates[~supported]


def check_overhangs(mesh: trimesh.Trimesh, threshold_deg: float = 50.0) -> list[Finding]:
    """UNSUPPORTED OVERHANGS -- predicts sagging / spaghetti (mid-air
    extrusion). A facet is a candidate if its normal points down steeper
    than threshold_deg from vertical and it's above the first layer. A
    candidate is unsupported unless a straight-down ray from just below
    its centroid hits more mesh within SUPPORT_GAP_TOL. Unsupported
    facets are clustered by face adjacency; HIGH if the cluster's
    flat-projected span (its minimum caliper width -- the bridge estimate)
    exceeds this codebase's ~10 mm bridge rule of thumb, or its area
    exceeds 30 mm^2; MED otherwise; LOW if even the steepest facet in the
    cluster is only marginally past the threshold."""
    findings: list[Finding] = []
    nz = mesh.face_normals[:, 2]
    centroids = mesh.triangles_center
    steep = nz < -np.sin(np.radians(threshold_deg))
    above_floor = centroids[:, 2] > FIRST_LAYER_H
    candidates = np.where(steep & above_floor)[0]
    if len(candidates) == 0:
        return findings

    unsupported = _unsupported_facets(mesh, candidates, centroids)
    if len(unsupported) == 0:
        return findings

    adjacency = mesh.face_adjacency
    mask_adj = np.isin(adjacency[:, 0], unsupported) & np.isin(adjacency[:, 1], unsupported)
    edges = adjacency[mask_adj]
    remap = {f: i for i, f in enumerate(unsupported)}
    n = len(unsupported)
    if len(edges):
        ii = [remap[e[0]] for e in edges]
        jj = [remap[e[1]] for e in edges]
        graph = coo_matrix((np.ones(len(ii)), (ii, jj)), shape=(n, n))
        n_comp, labels = connected_components(graph, directed=False)
    else:
        n_comp, labels = n, np.arange(n)

    for c in range(n_comp):
        members = unsupported[labels == c]
        areas = mesh.area_faces[members]
        total_area = float(areas.sum())
        tri = mesh.triangles[members]
        pts_xy = tri[:, :, :2].reshape(-1, 2)
        span = min_caliper_width(pts_xy)
        centroid = (centroids[members] * areas[:, None]).sum(axis=0) / areas.sum()
        max_angle = float(np.degrees(np.arcsin(np.clip(-nz[members].min(), -1.0, 1.0))))

        if (max_angle - threshold_deg) <= NEAR_THRESHOLD_MARGIN_DEG:
            sev = "LOW"
        elif span > BRIDGE_MAX_MM or total_area > OVERHANG_MIN_AREA:
            sev = "HIGH"
        else:
            sev = "MED"

        term = (
            "bridging failure (unsupported span beyond the ~10 mm bridge limit)"
            if span > BRIDGE_MAX_MM
            else "unsupported overhang (drooping / mid-air extrusion)"
        )
        reason = (
            f"{total_area:.1f} mm^2 downward face with no material below "
            f"(bridge span ~{span:.1f} mm, steepest {max_angle:.0f} deg from vertical)"
        )
        findings.append(Finding(
            "OVERHANG", sev, tuple(round(float(v), 1) for v in centroid), reason, term,
            metric=max(total_area, span),
        ))
    return findings


def check_knockover(mesh: trimesh.Trimesh) -> list[Finding]:
    """KNOCKOVER RISK -- predicts mid-print detachment (tall lever, small
    anchor). Compares overall height h to the bed-contact patch's minimum
    caliper width w and its area A: HIGH if h/w > 3 and A < 200 mm^2; MED
    if h/w > 3 with more area, or h/w > 2 with A < 100 mm^2."""
    findings: list[Finding] = []
    centroids = mesh.triangles_center
    contact_mask = centroids[:, 2] < FIRST_LAYER_H
    if not contact_mask.any():
        return findings

    contact_area = float(mesh.area_faces[contact_mask].sum())
    tri = mesh.triangles[contact_mask]
    pts_xy = tri[:, :, :2].reshape(-1, 2)
    w = min_caliper_width(pts_xy)
    if w <= 1e-6:
        return findings

    h = float(mesh.bounds[1, 2] - mesh.bounds[0, 2])
    try:
        com_z = float(mesh.center_mass[2]) if mesh.is_watertight else float(mesh.centroid[2])
    except Exception:
        com_z = float(mesh.centroid[2])
    ratio = h / w

    if ratio > 3 and contact_area < 200.0:
        sev = "HIGH"
    elif (ratio > 3 and contact_area >= 200.0) or (ratio > 2 and contact_area < 100.0):
        sev = "MED"
    else:
        return findings

    contact_centroid = tri.reshape(-1, 3).mean(axis=0)
    reason = (
        f"h={h:.1f} mm over bed-contact width w={w:.1f} mm (h/w={ratio:.1f}), "
        f"contact area={contact_area:.1f} mm^2, CoM height={com_z:.1f} mm -- "
        f"recommend brim + reorient or shorten"
    )
    term = "toppling (insufficient bed-adhesion moment for the part's aspect ratio)"
    findings.append(Finding(
        "KNOCKOVER", sev,
        (round(float(contact_centroid[0]), 1), round(float(contact_centroid[1]), 1), 0.0),
        reason, term, metric=ratio,
    ))
    return findings


def _first_layer_islands(mesh: trimesh.Trimesh, layer_z: float) -> list[tuple[float, tuple[float, float]]]:
    """mesh.section().to_2D(), whose polygons_full is shapely-backed (with
    networkx path traversal under the hood) and already handles hole
    nesting correctly -- e.g. this codebase's chassis has small cradle/slot
    islands sitting inside cut-outs, which polygons_full reports as their
    own separate polygons rather than folding them into the surrounding
    plate. Polygon.area and .centroid come straight from shapely."""
    try:
        section = mesh.section(plane_origin=[0, 0, layer_z], plane_normal=[0, 0, 1])
    except Exception:
        return []
    if section is None:
        return []
    try:
        planar, to_3D = section.to_2D()
    except Exception:
        return []
    # to_2D's second return value maps planar points back UP into the
    # original 3D space directly (despite the name, it's a to-3D matrix) --
    # do not invert it
    islands = []
    for poly in planar.polygons_full:
        c = poly.centroid
        pt3 = trimesh.transformations.transform_points(np.array([[c.x, c.y, 0.0]]), to_3D)[0]
        islands.append((float(poly.area), (float(pt3[0]), float(pt3[1]))))
    return islands


def check_islands(mesh: trimesh.Trimesh, layer_z: float = LAYER_Z) -> list[Finding]:
    """FIRST-LAYER ISLANDS -- predicts adhesion failure. Sections the mesh
    at z=layer_z and flags disjoint regions of material smaller than 30
    mm^2 (HIGH if under 15 mm^2)."""
    findings: list[Finding] = []
    if mesh.bounds[1, 2] < layer_z:
        return findings

    islands = _first_layer_islands(mesh, layer_z)
    for area, (cx, cy) in islands:
        if area >= ISLAND_MED_MAX:
            continue
        sev = "HIGH" if area < ISLAND_HIGH_MAX else "MED"
        reason = f"first-layer island {area:.1f} mm^2 at z={layer_z} (min viable ~30 mm^2)"
        term = "poor bed adhesion (first-layer island too small to anchor)"
        findings.append(Finding(
            "ISLAND", sev, (round(float(cx), 1), round(float(cy), 1), layer_z), reason, term, metric=area,
        ))
    return findings


def check_fusion(mesh: trimesh.Trimesh) -> tuple[list[Finding], int]:
    """BODY SEPARATION -- predicts unintentionally fused parts. Splits the
    mesh into connected bodies and flags pairs that overlap or sit closer
    than FUSION_HIGH_MM apart as HIGH, and closer than FUSION_LOW_MM as
    LOW. Returns (findings, body_count) -- the count alone tells you at a
    glance whether a plate meant to hold N parts actually has N bodies."""
    bodies = mesh.split(only_watertight=False)
    n = len(bodies)
    findings: list[Finding] = []
    if n <= 1:
        return findings, n

    for i in range(n):
        for j in range(i + 1, n):
            a, b = bodies[i], bodies[j]
            dist = min_mesh_distance(a, b)
            overlap = dist < 1e-6 or bodies_overlap(a, b)
            if overlap:
                sev = "HIGH"
                detail = "overlapping (interpenetrating geometry)"
            elif dist < FUSION_HIGH_MM:
                sev = "HIGH"
                detail = f"{dist:.2f} mm apart"
            elif dist < FUSION_LOW_MM:
                sev = "LOW"
                detail = f"{dist:.2f} mm apart"
            else:
                continue
            mid = (a.centroid + b.centroid) / 2
            reason = f"body {i} and body {j}: {detail}"
            term = "unintended part fusion (bodies bridged or printed as one)"
            findings.append(Finding(
                "FUSION", sev, tuple(round(float(v), 1) for v in mid), reason, term,
                metric=-dist if not overlap else -1.0,
            ))
    return findings, n


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def lint(stl_path: Path, threshold_deg: float = 50.0) -> tuple[list[Finding], int]:
    mesh = trimesh.load_mesh(stl_path)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.dump())
    findings: list[Finding] = []
    findings += check_overhangs(mesh, threshold_deg)
    findings += check_knockover(mesh)
    findings += check_islands(mesh)
    fusion_findings, body_count = check_fusion(mesh)
    findings += fusion_findings
    return findings, body_count


def print_report(name: str, findings: list[Finding], body_count: int) -> None:
    print(f"\n{'=' * 72}")
    print(f"print_lint: {name}  ({body_count} {'body' if body_count == 1 else 'bodies'})")
    print("=" * 72)
    if not findings:
        print("No findings -- looks clean.")
        return
    ranked = sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], -f.metric))
    for f in ranked:
        loc = f"({f.location[0]:.1f}, {f.location[1]:.1f}, {f.location[2]:.1f})"
        print(f"[{f.severity:4}] {f.check:9} @ {loc}")
        print(f"         {f.reason}")
        print(f"         predicts: {f.term}")
    counts = {"HIGH": 0, "MED": 0, "LOW": 0}
    for f in findings:
        counts[f.severity] += 1
    print("-" * 72)
    print(f"{counts['HIGH']} HIGH, {counts['MED']} MED, {counts['LOW']} LOW")


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------


def _make_mushroom() -> trimesh.Trimesh:
    stem = trimesh.creation.cylinder(radius=4.0, height=15.0, sections=48)
    stem.apply_translation([0, 0, 7.5])
    cap = trimesh.creation.cylinder(radius=12.0, height=3.0, sections=48)
    cap.apply_translation([0, 0, 16.5])
    mesh = trimesh.util.concatenate([stem, cap])
    mesh.merge_vertices()
    return mesh


def _make_pole(w=10.0, d=12.0, h=35.0) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(w, d, h))
    mesh.apply_translation([0, 0, h / 2])
    return mesh


def _make_frustum(bottom_r: float, top_r: float, height: float, sections=48) -> trimesh.Trimesh:
    theta = np.linspace(0, 2 * np.pi, sections, endpoint=False)
    bx, by = bottom_r * np.cos(theta), bottom_r * np.sin(theta)
    tx, ty = top_r * np.cos(theta), top_r * np.sin(theta)
    bottom_ring = np.column_stack([bx, by, np.zeros(sections)])
    top_ring = np.column_stack([tx, ty, np.full(sections, height)])
    vertices = np.vstack([bottom_ring, top_ring, [[0, 0, 0]], [[0, 0, height]]])
    n = sections
    bc, tc = 2 * n, 2 * n + 1
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j])
        faces.append([i, n + j, n + i])
        faces.append([bc, j, i])
        faces.append([tc, n + i, n + j])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def _make_overlapping_boxes() -> trimesh.Trimesh:
    a = trimesh.creation.box(extents=(10, 10, 10))
    a.apply_translation([0, 0, 5])
    b = trimesh.creation.box(extents=(10, 10, 10))
    b.apply_translation([5, 0, 5])
    return trimesh.util.concatenate([a, b])


def _make_cube() -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(20, 20, 20))
    mesh.apply_translation([0, 0, 10])
    return mesh


def run_selftest() -> bool:
    cases = [
        ("mushroom -> HIGH overhang", _make_mushroom(),
         lambda fs, n: any(f.check == "OVERHANG" and f.severity == "HIGH" for f in fs)),
        ("35mm pole on 10x12 base -> HIGH knockover", _make_pole(),
         lambda fs, n: any(f.check == "KNOCKOVER" and f.severity == "HIGH" for f in fs)),
        ("cone on Ø3 tip -> HIGH island", _make_frustum(1.5, 15.0, 30.0),
         lambda fs, n: any(f.check == "ISLAND" and f.severity == "HIGH" for f in fs)),
        ("two overlapping boxes -> HIGH fusion", _make_overlapping_boxes(),
         lambda fs, n: n == 2 and any(f.check == "FUSION" and f.severity == "HIGH" for f in fs)),
        ("plain 20mm cube -> no findings", _make_cube(),
         lambda fs, n: len(fs) == 0),
    ]
    all_ok = True
    for label, mesh, assertion in cases:
        findings = []
        findings += check_overhangs(mesh)
        findings += check_knockover(mesh)
        findings += check_islands(mesh)
        fusion_findings, body_count = check_fusion(mesh)
        findings += fusion_findings
        ok = assertion(findings, body_count)
        all_ok &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            print_report(label, findings, body_count)
    print(f"\n{'ALL PASS' if all_ok else 'SOME FAILED'}")
    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stl", type=Path, nargs="?", help="STL in print orientation")
    ap.add_argument("--threshold-deg", type=float, default=50.0,
                     help="overhang angle from vertical above which a downward "
                          "face is a support candidate (default 50)")
    ap.add_argument("--strict", action="store_true",
                     help="exit nonzero if any HIGH finding is present")
    ap.add_argument("--selftest", action="store_true",
                     help="run the synthetic-mesh self-test and exit")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if run_selftest() else 1)

    if args.stl is None:
        ap.error("stl is required unless --selftest")

    findings, body_count = lint(args.stl, args.threshold_deg)
    print_report(args.stl.name, findings, body_count)

    if args.strict and any(f.severity == "HIGH" for f in findings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
