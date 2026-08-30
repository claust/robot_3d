"""Slice, upload and print on the Bambu X2D over the LAN.

Usage:
  uv run print_pipeline.py slice <model.stl> [--name job]
  uv run print_pipeline.py upload <file.gcode.3mf>
  uv run print_pipeline.py print <file.gcode.3mf> [--ams-slot N]
  uv run print_pipeline.py status

`slice` produces <name>.gcode.3mf next to the STL, `upload` puts it on the
printer's SD card over FTPS, `print` starts a previously uploaded file (asks
for confirmation), `status` shows what the printer is doing.

Printer credentials come from .env (BAMBU_PRINTER_IP/SERIAL/ACCESS_CODE).
"""

import argparse

import json
import re
import os
import ssl
import subprocess
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

IP = os.environ["BAMBU_PRINTER_IP"]
SERIAL = os.environ["BAMBU_PRINTER_SERIAL"]
ACCESS_CODE = os.environ["BAMBU_ACCESS_CODE"]

STUDIO = "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
PROFILES = "/Applications/BambuStudio.app/Contents/Resources/profiles/BBL"
MACHINE = f"{PROFILES}/machine/Bambu Lab X2D 0.4 nozzle.json"
PROCESS = f"{PROFILES}/process/0.20mm Standard @BBL X2D.json"
FILAMENT = f"{PROFILES}/filament/Bambu PLA Basic @BBL X2D 0.4 nozzle.json"
# Must match the plate physically on the bed — the X2D detects it optically
# and pauses the print on mismatch.
BED_TYPE = "Textured PEI Plate"

# Dual-nozzle support printing: filament 1 (body, AMS-fed left extruder) and
# filament 2 (support, aux Bowden extruder fed from the external spool).
# Colours are cosmetic in the gcode but make Studio/preview sanity checks easy.
BODY_COLOUR = "#0A2989"     # AMS slot 2, PLA Basic dark blue (tray_color)
SUPPORT_COLOUR = "#FFFFFF"  # external spool on the aux nozzle, white PLA
# The aux (Bowden) extruder's external spool reports as virtual tray 255 in
# the printer's vir_slot status (254 is the other, empty, virtual slot).
EXT_SPOOL_TRAY = 255


# ---------- slicing ----------

def _lint_before_slice(stl: Path) -> None:
    """Run print_lint's design-time printability checks on the input STL
    and surface any HIGH findings loudly before slicing. Informational
    only -- never blocks the slice (see print_lint.py for the checks)."""
    try:
        import print_lint
        findings, _body_count = print_lint.lint(stl)
    except Exception as e:
        print(f"print_lint: skipped ({e})")
        return
    highs = [f for f in findings if f.severity == "HIGH"]
    if highs:
        print(f"\n*** print_lint: {len(highs)} HIGH-severity finding(s) in {stl.name} ***")
        for f in highs:
            print(f"    [HIGH] {f.check} @ {f.location}: {f.reason}")
        print(f"*** slicing anyway -- run `uv run print_lint.py {stl}` for the full report ***\n")

def resolve_profile(path: Path) -> dict:
    """Flatten a Bambu profile's `inherits`/`include` chain into one dict.

    The CLI does not resolve these itself, which silently drops e.g. the
    machine start gcode (containing the AMS filament load) — producing prints
    that move but never extrude.
    """
    d = json.loads(path.read_text())
    merged: dict = {}
    parent = d.get("inherits")
    if parent:
        merged.update(resolve_profile(path.parent / f"{parent}.json"))
    for inc in d.get("include", []):
        merged.update(resolve_profile(path.parent / f"{inc}.json"))
    merged.update({k: v for k, v in d.items() if k not in ("inherits", "include")})
    return merged


def flatten_profiles(
    build_dir: Path,
    supports: bool = False,
    support_type: str = "normal(auto)",
    overrides: dict[str, str] | None = None,
) -> tuple[Path, Path, list[Path]]:
    build_dir.mkdir(exist_ok=True)

    machine = resolve_profile(Path(MACHINE))
    process = resolve_profile(Path(PROCESS))
    process["curr_bed_type"] = BED_TYPE

    filaments = []
    body = resolve_profile(Path(FILAMENT))
    if supports:
        # Filament indices are 1-based in process settings; "0" means default.
        # Print all support (base + interface) with filament 2. The
        # filament->extruder map must go on the CLI, not in this profile:
        # as a profile key it segfaults the CLI (BambuStudio issue #9119).
        process.update({
            "enable_support": "1",
            "support_type": support_type,
            "support_filament": "2",
            "support_interface_filament": "2",
        })
        support = resolve_profile(Path(FILAMENT))
        support["name"] = support["name"] + " aux support"
        sup_path = build_dir / (Path(FILAMENT).stem + " aux support.json")
        sup_path.write_text(json.dumps(support, indent=1))
        filaments.append(sup_path)

    process.update(overrides or {})

    paths = []
    for src, resolved in ((MACHINE, machine), (PROCESS, process), (FILAMENT, body)):
        dst = build_dir / Path(src).name
        dst.write_text(json.dumps(resolved, indent=1))
        paths.append(dst)
    machine_p, process_p, body_p = paths
    return machine_p, process_p, [body_p, *filaments]


def slice_stl(
    stl: Path,
    name: str | None = None,
    supports: bool = False,
    support_type: str = "normal(auto)",
    overrides: dict[str, str] | None = None,
    aux: bool = False,
) -> Path:
    if aux and supports:
        raise ValueError("--aux is a single-filament mode; it can't combine with --supports")
    _lint_before_slice(stl)
    name = name or stl.stem
    out = stl.parent / f"{name}.gcode.3mf"
    machine, process, filaments = flatten_profiles(
        stl.parent / "profiles_resolved", supports, support_type, overrides
    )
    cmd = [
        STUDIO, "--debug", "1",
        "--load-settings", f"{machine};{process}",
        "--load-filaments", ";".join(str(f) for f in filaments),
        "--slice", "0", "--arrange", "1",
        "--export-3mf", str(out.resolve()),
        str(stl.resolve()),
    ]
    if supports:
        cmd[3:3] = [
            "--allow-multicolor-oneplate",
            # filament 1 (body) -> extruder 1 (AMS, direct drive),
            # filament 2 (support) -> extruder 2 (aux Bowden, external spool)
            "--filament-map", "1,2",
            "--filament-map-mode", "Manual",
            "--nozzle-volume-type", "Standard,Standard",
            "--filament-colour", f"{BODY_COLOUR};{SUPPORT_COLOUR}",
            # The default prime tower position lies outside the aux extruder's
            # reachable area (X >= 20.5), which fails the multi-extruder
            # printable-area check; park it where both extruders reach.
            "--wipe-tower-x", "180",
            "--wipe-tower-y", "180",
        ]
    if aux:
        # Whole single-filament job from the aux (Bowden) extruder's external
        # spool: map the only filament to extruder 2. No prime tower needed
        # (no tool changes), but every move must stay in the aux reachable
        # area (X >= 20.5) — verify checks this.
        cmd[3:3] = [
            "--filament-map", "2",
            "--filament-map-mode", "Manual",
            "--nozzle-volume-type", "Standard",
        ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if not out.exists():
        print(res.stdout[-2000:], res.stderr[-2000:])
        raise RuntimeError("Slicing failed")
    print(f"Sliced {stl.name} -> {out.name}"
          + (" (supports on aux-nozzle filament)" if supports else "")
          + (" (whole job on aux nozzle)" if aux else ""))
    return out


# ---------- verification ----------

def verify(threemf: Path, plot: bool = True) -> bool:
    """Pre-flight checks on a sliced .gcode.3mf before it may be printed.

    Catches the failure modes a visual preview would: missing AMS filament
    load (air print), zero extrusion, out-of-bed moves, silly temperatures.
    """
    import zipfile

    with zipfile.ZipFile(threemf) as z:
        gcode = z.read("Metadata/plate_1.gcode").decode(errors="replace")

    header = dict(
        re.findall(r"^; ([\w \[\]]+?) ?[:=] (.+)$", gcode.split("EXECUTABLE_BLOCK_START")[0], re.M)
    )

    # Simulate moves (Bambu gcode uses relative E via M83), per tool.
    # T0 = left/AMS extruder; T1 = aux Bowden extruder (reaches only X>=20.5).
    # Bambu templates also emit pseudo tools (T255, T1000, T65535...) — ignore.
    x = y = z = 0.0
    tool = 0
    extruded_by_tool: dict[int, float] = {}
    minx_by_tool: dict[int, float] = {}
    minx, maxx, miny, maxy, maxz = 1e9, -1e9, 1e9, -1e9, 0.0
    body = gcode.split("EXECUTABLE_BLOCK_START")[-1]
    for line in body.splitlines():
        t = re.match(r"^T(\d)\b", line)
        if t:
            tool = int(t.group(1))
            continue
        if not line.startswith(("G0 ", "G1 ", "G2 ", "G3 ")):
            continue
        coords = dict(re.findall(r"([XYZE])([-\d.]+)", line))
        e = float(coords.get("E", 0))
        nx, ny = float(coords.get("X", x)), float(coords.get("Y", y))
        z = float(coords.get("Z", z))
        if e > 0 and ("X" in coords or "Y" in coords):
            extruded_by_tool[tool] = extruded_by_tool.get(tool, 0.0) + e
            minx_by_tool[tool] = min(minx_by_tool.get(tool, 1e9), x, nx)
            minx, maxx = min(minx, x, nx), max(maxx, x, nx)
            miny, maxy = min(miny, y, ny), max(maxy, y, ny)
            maxz = max(maxz, z)
        x, y = nx, ny
    extruded = sum(extruded_by_tool.values())
    nozzle_temps = [float(t) for t in re.findall(r"M10[49] S(\d+)", body)]
    bed_temps = [float(t) for t in re.findall(r"M1[49]0 S(\d+)", body)]

    header_len = sum(
        float(v) for v in header.get("total filament length [mm]", "0").split(",")
    )
    checks = [
        ("AMS filament load present (M620)", gcode.count("M620") >= 1),
        ("tool selection present (T cmd)", re.search(r"^T\d+", gcode, re.M) is not None),
        ("extrusion moves exist", extruded > 0),
        ("extrusion matches header estimate",
         header_len > 0 and 0.5 < (extruded / header_len) < 2.0),
        ("print stays on bed (0..256 mm)",
         0 <= minx and maxx <= 256 and 0 <= miny and maxy <= 256),
        ("nozzle reaches print temp, none above 320",
         nozzle_temps and 180 <= max(nozzle_temps) <= 320),
        ("bed temps sane (<=110)", all(t <= 110 for t in bed_temps)),
    ]
    if 1 in extruded_by_tool:
        checks.append(
            ("aux nozzle (T1) stays in its reachable area (X>=20.5)",
             minx_by_tool[1] >= 20.5)
        )

    print(f"Verifying {threemf.name}:")
    per_tool = ", ".join(
        f"T{t}: {e:.0f} mm" for t, e in sorted(extruded_by_tool.items())
    )
    print(f"  extruded {extruded:.0f} mm filament ({per_tool}; header says "
          f"{header_len:.0f} mm), "
          f"footprint X {minx:.0f}-{maxx:.0f} Y {miny:.0f}-{maxy:.0f}, max Z {maxz:.1f}")
    ok = True
    for label, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")
        ok = ok and bool(passed)

    if plot:
        png = plot_toolpath(gcode, threemf.with_suffix("").with_suffix(".toolpath.png"))
        print(f"  toolpath plot: {png}")
    print("VERDICT:", "OK to print" if ok else "DO NOT PRINT")
    return ok


def plot_toolpath(gcode: str, out: Path) -> Path:
    """Top-down plot of extrusion moves, colored by layer."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    import math

    fig, ax = plt.subplots(figsize=(6, 6))
    x = y = 0.0
    layer = 0
    tool = 0
    cmap = plt.get_cmap("viridis")
    segments_by_layer: dict[int, list] = {}
    aux_segments: list = []  # T1 (support) moves, drawn flat-colored on top
    for line in gcode.split("EXECUTABLE_BLOCK_START")[-1].splitlines():
        if line.startswith("; CHANGE_LAYER"):
            layer += 1
        t = re.match(r"^T(\d)\b", line)
        if t:
            tool = int(t.group(1))
        if not line.startswith(("G0 ", "G1 ", "G2 ", "G3 ")):
            continue
        coords = dict(re.findall(r"([XYZEIJ])([-\d.]+)", line))
        nx, ny = float(coords.get("X", x)), float(coords.get("Y", y))
        extruding = float(coords.get("E", 0)) > 0 and ("X" in coords or "Y" in coords)
        if extruding and line.startswith(("G2", "G3")) and ("I" in coords or "J" in coords):
            # interpolate the arc so circles don't render as chords
            cx, cy = x + float(coords.get("I", 0)), y + float(coords.get("J", 0))
            r = math.hypot(x - cx, y - cy)
            a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
            if line.startswith("G2"):  # clockwise
                while a1 >= a0:
                    a1 -= 2 * math.pi
            else:
                while a1 <= a0:
                    a1 += 2 * math.pi
            steps = max(4, int(abs(a1 - a0) * r))
            pts = [(cx + r * math.cos(a0 + (a1 - a0) * i / steps),
                    cy + r * math.sin(a0 + (a1 - a0) * i / steps))
                   for i in range(steps + 1)]
            for (px, py), (qx, qy) in zip(pts, pts[1:]):
                seg = ((px, qx), (py, qy))
                (aux_segments if tool == 1
                 else segments_by_layer.setdefault(layer, [])).append(seg)
        elif extruding:
            seg = ((x, nx), (y, ny))
            (aux_segments if tool == 1
             else segments_by_layer.setdefault(layer, [])).append(seg)
        x, y = nx, ny
    total_layers = max(segments_by_layer, default=1)
    for lyr, segs in segments_by_layer.items():
        color = cmap(lyr / max(total_layers, 1))
        for (xs, ys) in segs:
            ax.plot(xs, ys, color=color, linewidth=0.5)
    for (xs, ys) in aux_segments:
        ax.plot(xs, ys, color="crimson", linewidth=0.5, alpha=0.6)
    ax.set_aspect("equal")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    title = f"Toolpath (extrusion only), {total_layers} layers"
    if aux_segments:
        title += " — aux nozzle (support) in red"
    ax.set_title(title)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------- upload (implicit FTPS on port 990) ----------
# curl instead of ftplib: the printer's FTP server demands TLS session reuse
# on the data channel, which ftplib cannot provide.

def _ftps(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["curl", "-sS", "--insecure", "--ssl-reqd",
         "--user", f"bblp:{ACCESS_CODE}", *args],
        capture_output=True, text=True,
    )


def upload(path: Path) -> str:
    res = _ftps("-T", str(path), f"ftps://{IP}:990/{path.name}")
    if res.returncode != 0:
        raise RuntimeError(f"Upload failed: {res.stderr.strip()}")
    listing = _ftps(f"ftps://{IP}:990/")
    if path.name not in listing.stdout:
        raise RuntimeError(f"{path.name} not visible on printer storage after upload")
    print(f"Uploaded {path.name} to printer storage")
    return path.name


# ---------- MQTT ----------

def mqtt_client() -> mqtt.Client:
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.username_pw_set("bblp", ACCESS_CODE)
    c.tls_set(cert_reqs=ssl.CERT_NONE)
    c.tls_insecure_set(True)
    c.connect(IP, 8883, keepalive=30)
    return c


def get_status(timeout: float = 8.0) -> dict:
    state: dict = {}

    def on_connect(c, u, f, rc, p):
        c.subscribe(f"device/{SERIAL}/report")
        c.publish(
            f"device/{SERIAL}/request",
            json.dumps({"pushing": {"sequence_id": "1", "command": "pushall"}}),
        )

    def on_message(c, u, msg):
        d = json.loads(msg.payload)
        if "print" in d:
            state.update(d["print"])

    c = mqtt_client()
    c.on_connect = on_connect
    c.on_message = on_message
    c.loop_start()
    deadline = time.time() + timeout
    while time.time() < deadline and "gcode_state" not in state:
        time.sleep(0.3)
    c.loop_stop()
    c.disconnect()
    return state


def build_tray_mappings(trays: list[str]) -> tuple[list[int], list[dict]]:
    """Map sliced filament slots (in order) to printer trays.

    Each entry is an AMS slot number ("0".."3") or "ext" for the external
    spool feeding the aux nozzle. Returns (ams_mapping, ams_mapping2) in the
    wire format Bambu Studio's network plugin uses: external-spool filaments
    are -1 in the flat v0 array and carried by ams_id in the v2 array.
    """
    m1: list[int] = []
    m2: list[dict] = []
    for item in trays:
        if item == "ext":
            m1.append(-1)
            m2.append({"ams_id": EXT_SPOOL_TRAY, "slot_id": 0})
        else:
            slot = int(item)
            m1.append(slot)  # global tray id: ams_id * 4 + slot (one AMS unit)
            m2.append({"ams_id": 0, "slot_id": slot})
    return m1, m2


def start_print(filename: str, trays: list[str], wait: float = 90.0) -> None:
    ams_mapping, ams_mapping2 = build_tray_mappings(trays)
    cmd = {
        "print": {
            "sequence_id": "0",
            "command": "project_file",
            "param": "Metadata/plate_1.gcode",
            "url": f"ftp://{filename}",
            "subtask_name": Path(filename).name.removesuffix(".gcode.3mf"),
            "bed_type": "auto",
            "timelapse": False,
            "bed_leveling": True,
            "flow_cali": False,
            "vibration_cali": False,
            "layer_inspect": False,
            "use_ams": True,
            "ams_mapping": ams_mapping,
            "ams_mapping2": ams_mapping2,
            "subtask_id": "0",
            "task_id": "0",
            "project_id": "0",
            "profile_id": "0",
        }
    }

    states: list[str] = []

    def on_connect(c, u, f, rc, p):
        c.subscribe(f"device/{SERIAL}/report")
        c.publish(f"device/{SERIAL}/request", json.dumps(cmd))
        print(f"Print command sent for {filename} (trays: {', '.join(trays)})")

    def on_message(c, u, msg):
        d = json.loads(msg.payload).get("print", {})
        s = d.get("gcode_state")
        if s and (not states or states[-1] != s):
            states.append(s)
            print(f"  printer state: {s}")

    c = mqtt_client()
    c.on_connect = on_connect
    c.on_message = on_message
    c.loop_start()
    deadline = time.time() + wait
    while time.time() < deadline:
        if states and states[-1] in ("RUNNING", "PREPARE"):
            time.sleep(5)  # a few extra updates, then leave it to it
            break
        if states and states[-1] == "FAILED":
            break
        time.sleep(0.5)
    c.loop_stop()
    c.disconnect()
    if not states:
        print("No state updates received — check the printer screen")


# ---------- CLI ----------

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_slice = sub.add_parser("slice")
    p_slice.add_argument("stl", type=Path)
    p_slice.add_argument("--name")
    p_slice.add_argument("--aux", action="store_true",
                         help="print the whole single-filament job from the aux "
                              "nozzle's external spool (start it with --trays ext)")
    p_slice.add_argument("--supports", action="store_true",
                         help="enable supports, printed white from the aux nozzle")
    p_slice.add_argument("--support-type", default="normal(auto)",
                         help="normal(auto), tree(auto), normal(manual), tree(manual)")
    p_slice.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                         help="override a process-profile setting (repeatable)")

    p_ver = sub.add_parser("verify")
    p_ver.add_argument("file", type=Path)

    p_up = sub.add_parser("upload")
    p_up.add_argument("file", type=Path)

    p_pr = sub.add_parser("print")
    p_pr.add_argument("file", type=Path)
    p_pr.add_argument("--ams-slot", type=int, default=0,
                      help="AMS slot for a single-filament print")
    p_pr.add_argument("--trays",
                      help="comma-separated tray per sliced filament, e.g. "
                           "'2,ext' = filament 1 from AMS slot 2, filament 2 "
                           "from the aux nozzle's external spool")
    p_pr.add_argument("--yes", action="store_true", help="skip confirmation")

    sub.add_parser("status")

    args = ap.parse_args()

    if args.cmd == "slice":
        overrides = dict(kv.split("=", 1) for kv in getattr(args, "set"))
        slice_stl(args.stl, args.name, args.supports, args.support_type, overrides,
                  aux=args.aux)
    elif args.cmd == "verify":
        sys.exit(0 if verify(args.file) else 1)
    elif args.cmd == "upload":
        upload(args.file)
    elif args.cmd == "status":
        s = get_status()
        for k in ("gcode_state", "mc_percent", "mc_remaining_time",
                  "layer_num", "total_layer_num", "nozzle_temper", "bed_temper",
                  "subtask_name"):
            if k in s:
                print(f"{k}: {s[k]}")
    elif args.cmd == "print":
        if not verify(args.file, plot=False):
            print("Refusing to print a file that fails verification.")
            sys.exit(1)
        if not args.yes:
            answer = input(
                f"Start printing {args.file.name} on the printer at {IP}?\n"
                "Make sure the build plate is EMPTY and correct filament is "
                "loaded. Type 'yes' to start: "
            )
            if answer.strip().lower() != "yes":
                print("Aborted")
                sys.exit(0)
        trays = args.trays.split(",") if args.trays else [str(args.ams_slot)]
        start_print(args.file.name, trays)
