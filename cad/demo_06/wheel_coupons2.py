"""O-ring fit coupons, round 2: groove DEPTH sweep at fixed 6% seated
stretch.

Round 1 (wheel_coupons.py, P1-P3) swept the groove root diameter at the
original 0.6-cord burial — and found the design flaw the hard way: a
Ø52.6 mm shoulder means the ID-40 ring must stretch 32% to get over the
rim, which a 10 mm cord won't do by hand. Lesson: the binding constraint
is INSTALLATION stretch over the shoulder, not seated stretch in the
groove.

Round 2 pins the root at 6% seated stretch (root Ø42.4 — ring tension does
the gripping now) and sweeps how deep the cord is buried:

    P4  depth 2.0  shoulder Ø46.4  install stretch ~16%
    P5  depth 2.5  shoulder Ø47.4  install stretch ~18%
    P6  depth 3.0  shoulder Ø48.4  install stretch ~21%

Deeper = better sideways retention but harder to mount. The winner is the
DEEPEST one you can still mount by hand without a fight (warm the ring in
hot tap water and roll it on like a bicycle tire; never heat the wheel —
PLA softens at those temperatures).

Rolling diameter is root + 2 x cord = Ø62.4 for all three (independent of
groove depth), so the chassis skid height is unaffected by the choice.

Like round 1, these are complete wheels: same hub, same D-bore (0.05 mm
clearance), so the winner is a production wheel.

Run with:  uv run demo_06/wheel_coupons2.py [bore_clearance_mm]
Exports wheel_coupons2.stl into the cwd.
"""

import sys
from dataclasses import dataclass

from build123d import Part, Plane, Pos, Text, export_stl, extrude

from wheel import WheelDims, make_wheel

SEATED_STRETCH = 1.06
DEPTH_FACTORS = (0.20, 0.25, 0.30)  # x cord -> 2.0 / 2.5 / 3.0 mm
FIRST_NUMBER = 4  # continues P1-P3 from round 1
TEXT_HEIGHT = 0.6
FONT_SIZE = 5.5
TEXT_OFFSET_Y = 11.5
PLATE_GAP = 10.0


@dataclass
class CouponDims(WheelDims):
    groove_root: float = 42.4

    @property
    def groove_root_diameter(self) -> float:  # type: ignore[override]
        return self.groove_root


def make_coupon(number: int, depth_factor: float, bore_clearance: float):
    d = CouponDims(bore_clearance=bore_clearance, groove_depth_factor=depth_factor)
    d.groove_root = d.oring_id * SEATED_STRETCH
    wheel = make_wheel(d)
    for line, y in ((f"D{d.groove_depth:.1f}", TEXT_OFFSET_Y), (f"P{number}", -TEXT_OFFSET_Y)):
        label = Plane.XY.offset(d.web_thickness) * Pos(0, y) * Text(line, font_size=FONT_SIZE)
        wheel += extrude(label, amount=TEXT_HEIGHT)
    return wheel, d


if __name__ == "__main__":
    bore_clearance = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05

    plate = Part()
    print(f"O-ring fit coupons round 2, root Ø{40 * SEATED_STRETCH:.1f} "
          f"({(SEATED_STRETCH - 1) * 100:.0f}% seated stretch), bore clearance "
          f"{bore_clearance:g} mm")
    for i, f in enumerate(DEPTH_FACTORS):
        n = FIRST_NUMBER + i
        wheel, d = make_coupon(n, f, bore_clearance)
        pitch = d.rim_shoulder_diameter + PLATE_GAP
        plate += Pos((i - (len(DEPTH_FACTORS) - 1) / 2) * pitch, 0, 0) * wheel
        install = d.rim_shoulder_diameter / d.oring_id - 1
        print(
            f"  P{n}: groove {d.groove_depth:.1f} deep, shoulder "
            f"Ø{d.rim_shoulder_diameter:.2f}, install stretch {install * 100:.0f}%, "
            f"rolling Ø{d.rolling_diameter:.2f}"
        )

    export_stl(plate, "wheel_coupons2.stl")
    bbox = plate.bounding_box()
    print(f"Plate bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Total volume: {plate.volume / 1000:.1f} cm^3")
    print("Exported wheel_coupons2.stl")
