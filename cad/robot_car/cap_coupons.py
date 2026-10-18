"""Fit coupons for mounting the Canon motor (parts library M1) on the
spindle tower without screws.

The Canon sits on a cap on top of the tower with its shaft pointing down,
so gravity already holds it in, and the cap on the tower. Each joint only
has to keep things centred, stop them rattling and carry the motor's small
torque, about 11 mN·m at most on the 2S pack: a snug fit does all three.
These coupons find the snug fit for each joint, one step per letter
(radial clearance in mm, positive = looser):

  Rings A-D, slip over the printed tower's top (Ø32.1):
      A 0.05   B 0.10   C 0.15   D 0.20
  Cups E-H, take the Canon's can (Ø34.3, calipered), shaft down:
      E 0.00   F 0.05   G 0.10   H 0.15
  Hubs I-L, push onto the Canon's Ø2 shaft:
      I 0.00   J 0.05   K 0.10   L 0.15

- Ring: a short tube with a lip that lands on the tower's top rim, as the
  cap will. The lip reaches in to Ø24, over the upper bearing's outer
  ring, so the cap also holds that bearing down; it stays clear of the
  inner ring, which turns. Prints lip-down; turn it over to use it.
- Cup: the can drops in face first and stands on a ledge outside its
  mounting holes. Prints ledge-down.
- Hub: the part that grips the Canon's shaft. Rest the shaft's short rear
  stub on the table while pushing a hub on, so the shaft isn't driven into
  the motor.

What to look for: the right ring and cup go on by hand with a little
force, sit without rocking, and come off again by hand. The right hub
needs a firm push and then won't turn on the shaft when you twist it.

RESULT (dark blue PLA Basic, X2D, 2026-10-18): ring A fits the tower
best, cup F the Canon, and hub L is the only one that goes onto the shaft,
a bit tight: the Ø2.30 hole prints near Ø2. canon_mount.py uses all three.

Run with:  uv run robot_car/cap_coupons.py
Exports cap_coupons.stl (print orientation) and runs the PASS/FAIL checks.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "parts"))

from build123d import Box, Cylinder, Part, Pos, export_stl  # noqa: E402

from ck35_motor import MEASURED_DIMS  # noqa: E402
from spindle_coupons import (  # noqa: E402
    ALIGN_BOTTOM, SpindleDims, mouth, raised, tube,
)

RINGS = (("A", 0.05), ("B", 0.10), ("C", 0.15), ("D", 0.20))
CUPS = (("E", 0.00), ("F", 0.05), ("G", 0.10), ("H", 0.15))
HUBS = (("I", 0.00), ("J", 0.05), ("K", 0.10), ("L", 0.15))

WALL = 2.5
RING_H = 6.5
LIP_T = 1.5
LIP_D = 24.0  # over the bearing's outer ring (Ø22.6-26), clear of the inner (Ø14.8)
CUP_H = 6.0
LEDGE_T = 1.5
LEDGE_D = 30.0  # the can's face outside its holes (Ø25.7 circle, holes up to Ø3)
CAN_D = MEASURED_DIMS["can_diameter"]
SHAFT_D = MEASURED_DIMS["shaft_diameter"]
HUB_D, HUB_H = 8.0, 8.0
TAB_T, TAB_W, TAB_L = 2.0, 10.0, 10.0
FONT_SIZE = 7.0


def tab(r: float, letter: str) -> Part:
    """A flat tab off the part's -Y side, its letter on top."""
    part = Pos(0, -(r + TAB_L / 2 - 1), 0) * Box(TAB_W, TAB_L, TAB_T, align=ALIGN_BOTTOM)
    return part + raised(letter, FONT_SIZE, 0, -(r + TAB_L / 2), TAB_T)


def make_ring(tower_od: float, letter: str, c: float) -> Part:
    r_b = tower_od / 2 + c
    r_o = r_b + WALL
    ring = tube(r_o, LIP_D / 2, LIP_T) + tube(r_o, r_b, RING_H - LIP_T, LIP_T)
    ring -= mouth(r_b, 0.5, RING_H, up=False)
    return ring + tab(r_o, letter)


def make_cup(letter: str, c: float) -> Part:
    r_b = CAN_D / 2 + c
    r_o = r_b + WALL
    cup = tube(r_o, LEDGE_D / 2, LEDGE_T) + tube(r_o, r_b, CUP_H - LEDGE_T, LEDGE_T)
    cup -= mouth(r_b, 0.5, CUP_H, up=False)
    return cup + tab(r_o, letter)


def make_hub(letter: str, c: float) -> Part:
    r_b = SHAFT_D / 2 + c
    hub = tube(HUB_D / 2, r_b, HUB_H)
    hub -= mouth(r_b, 0.3, HUB_H, up=False)
    hub -= mouth(r_b, 0.3, 0.0, up=True)
    return hub + tab(HUB_D / 2, letter)


def build() -> tuple[Part, int]:
    s = SpindleDims()
    plate, n = Part(), 0
    pitch = s.tower_od + 2 * WALL + 6
    for i, (letter, c) in enumerate(RINGS):
        plate += Pos(i * pitch, 0, 0) * make_ring(s.tower_od, letter, c)
        n += 1
    pitch_c = CAN_D + 2 * WALL + 6
    for i, (letter, c) in enumerate(CUPS):
        plate += Pos(i * pitch_c, 58, 0) * make_cup(letter, c)
        n += 1
    for i, (letter, c) in enumerate(HUBS):
        plate += Pos(i * 16, -40, 0) * make_hub(letter, c)
        n += 1
    return plate, n


def main() -> None:
    s = SpindleDims()
    print("Rings over the tower (Ø%.2f):" % s.tower_od,
          ", ".join(f"{k} Ø{s.tower_od + 2 * c:.2f}" for k, c in RINGS))
    print("Cups for the can (Ø%.1f):" % CAN_D,
          ", ".join(f"{k} Ø{CAN_D + 2 * c:.2f}" for k, c in CUPS))
    print("Hubs for the shaft (Ø%.1f):" % SHAFT_D,
          ", ".join(f"{k} Ø{SHAFT_D + 2 * c:.2f}" for k, c in HUBS))
    plate, n = build()
    bb = plate.bounding_box()
    ok = True
    for good, text in (
        (len(plate.solids()) == n, f"plate: {len(plate.solids())} separate parts (expect {n})"),
        (LIP_D / 2 > 14.8 / 2 + 1, f"ring lip (Ø{LIP_D:g}) clears the bearing's inner ring (Ø14.8)"),
        (LIP_D <= 26.0 - 2, f"ring lip lands 1 mm onto the bearing's outer ring (Ø{LIP_D:g} to Ø26)"),
        (LEDGE_D / 2 >= 25.7 / 2 + 1.5 + 0.5, f"cup ledge (Ø{LEDGE_D:g}) stays outside the can's holes"),
        (bb.size.X < 240 and bb.size.Y < 240, f"plate {bb.size.X:.0f} x {bb.size.Y:.0f} mm"),
    ):
        print(f"  [{'PASS' if good else 'FAIL'}] {text}")
        ok &= good
    print(f"Volume {plate.volume / 1000:.1f} cm^3")
    export_stl(plate, HERE / "cap_coupons.stl")
    print("Exported cap_coupons.stl")
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
