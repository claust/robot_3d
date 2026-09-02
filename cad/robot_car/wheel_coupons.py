"""O-ring fit-test plate: three complete drive wheels (robot_car/wheel.py)
differing only in groove ROOT diameter, i.e. how much the 40 mm ID tire is
stretched when installed:

    P1  root Ø40.8  (2% stretch)  -- loosest, ring nearly relaxed
    P2  root Ø41.6  (4% stretch)  -- wheel.py's default
    P3  root Ø42.4  (6% stretch)  -- tightest

Everything else (rim, V-groove profile, hub, D-bore) is identical to
wheel.py, so these are not throwaway coupons: whichever wheel holds the
ring snugly without a fight to install IS a production wheel -- print one
more of that size for the pair. The same print also gives three shots at
the shaft press fit (all at wheel.py's default 0.05 mm bore clearance).

Each wheel carries raised text (0.6 mm proud) on the web face inside the
rim bowl -- the groove root diameter and the coupon number -- so the
printed parts can't be mixed up. The text faces up in print orientation
(web on the bed), so it prints cleanly without support.

What to feel for when testing: the ring should need a definite stretch to
seat, sit fully down in the V, and not walk off when rolled under load or
twisted by hand. Too loose = spins/walks on the wheel; too tight = hard to
install and bows the shoulders.

Run with:  uv run robot_car/wheel_coupons.py [bore_clearance_mm]
Exports wheel_coupons.stl (all three, in a row, print-ready) into the cwd.
"""

import sys
from dataclasses import dataclass

from build123d import Part, Plane, Pos, Text, export_stl, extrude

from wheel import WheelDims, make_wheel

STRETCHES = (1.02, 1.04, 1.06)
TEXT_HEIGHT = 0.6  # raised above the web face
FONT_SIZE = 5.5
TEXT_OFFSET_Y = 11.5  # lines above/below the hub, inside the rim bowl
PLATE_GAP = 10.0  # clearance between adjacent rims on the build plate


@dataclass
class CouponDims(WheelDims):
    """WheelDims with the groove root pinned directly instead of derived
    from oring_id x the module-level STRETCH constant."""

    groove_root: float = 41.6

    @property
    def groove_root_diameter(self) -> float:  # type: ignore[override]
        return self.groove_root


def make_coupon(number: int, stretch: float, bore_clearance: float) -> tuple[Part, CouponDims]:
    d = CouponDims(bore_clearance=bore_clearance)
    d.groove_root = d.oring_id * stretch
    wheel = make_wheel(d)

    for line, y in ((f"{d.groove_root_diameter:.1f}", TEXT_OFFSET_Y),
                    (f"P{number}", -TEXT_OFFSET_Y)):
        label = Plane.XY.offset(d.web_thickness) * Pos(0, y) * Text(
            line, font_size=FONT_SIZE
        )
        wheel += extrude(label, amount=TEXT_HEIGHT)

    return wheel, d


if __name__ == "__main__":
    bore_clearance = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05

    plate = Part()
    print(f"O-ring fit coupons, bore clearance {bore_clearance:g} mm radial")
    for i, stretch in enumerate(STRETCHES, start=1):
        wheel, d = make_coupon(i, stretch, bore_clearance)
        pitch = d.rim_shoulder_diameter + PLATE_GAP
        plate += Pos((i - (len(STRETCHES) + 1) / 2) * pitch, 0, 0) * wheel
        print(
            f"  P{i}: root Ø{d.groove_root_diameter:.2f} mm "
            f"({(stretch - 1) * 100:.0f}% stretch), shoulder OD "
            f"{d.rim_shoulder_diameter:.2f} mm, rolling Ø{d.rolling_diameter:.2f} mm"
        )

    export_stl(plate, "wheel_coupons.stl")
    bbox = plate.bounding_box()
    print(f"Plate bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Total volume: {plate.volume / 1000:.1f} cm^3")
    print("Exported wheel_coupons.stl")
