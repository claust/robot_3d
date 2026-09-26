"""DRV8833 tray coupons (parts library D2).

Copies of chassis.py's drv_tray, each on its own small base, for the
18.5 x 15.6 x 1.6 mm board. Two plates:

FIT (uv run robot_car/drv_coupons.py fit) varies the two numbers a caliper
can't settle:

    A  end fit 0.05  preload 0.10       D  end fit 0.15  preload 0.10
    B  end fit 0.05  preload 0.20       E  end fit 0.15  preload 0.20
    C  end fit 0.05  preload 0.30       F  end fit 0.15  preload 0.30

- END FIT (drv_end_fit, per end) is the gap between the 18.5 mm board and
  the two corner end stops. It sets the play along the long axis.
- PRELOAD (drv_latch_preload) is how far the latch barb's 45 deg lower face
  would cut into the seated board's top edge, so the arm stays bent by that
  much and pushes the board down and against the tongues. It sets the play
  across the short axis and vertically. Board thickness adds straight onto
  it: a 1.4 mm board gets 0.2 less preload than the 1.6 it is drawn for.

RESULT (black PLA Basic, X2D): C fits best -- no wiggle, and a fingernail
on the latch still pops the board out. C's 0.05 end fit and 0.30 preload
are ChassisDims' defaults. C is the tight corner of the grid, so if the
board ever loosens (PLA creep), the next step is more preload. On that
print the latch arm (then 1.0 x 4 mm, square root) snapped off at the
plate on two of the six coupons, which is what the current arm fixes.

LATCH (uv run robot_car/drv_coupons.py, the default) is three identical
copies, H I J, of the tray at ChassisDims defaults: C's fit with the 0.8 x
7 mm latch arm and its 1 mm root radii, checking that the arm survives
repeated fitting and removal and that the fit still feels like C. RESULT
(green PLA Basic, X2D): all three fit nicely, and the arm is the car's.

Everything else is drv_tray at ChassisDims defaults -- the same 7 mm
standoff (so the latch arm has its on-car length), tongues, corners and
latch. Each coupon is the tray in its canonical frame: tongues at +X, latch
at -X, the board's 18.5 mm axis along Y. The label sits on the tongue side.

Fitting: tilt the board about 15 deg, tuck the long edge under the two
tongues, rotate it down until the latch clicks over. Judge per coupon: does
it go in by hand, does it rattle when shaken, can you push it along either
axis, can you still pop it out with a fingernail on the latch.

Run with:  uv run robot_car/drv_coupons.py [latch|fit]
Exports drv_latch_coupons.stl/.step (latch) or drv_coupons.stl/.step (fit)
into the cwd.
"""

import sys
from dataclasses import replace

from build123d import (
    Align,
    Box,
    FontStyle,
    Part,
    Plane,
    Pos,
    Text,
    export_step,
    export_stl,
    extrude,
)

from chassis import ChassisDims, drv_latch_geometry, drv_tray

END_FITS = (0.05, 0.15)
PRELOADS = (0.10, 0.20, 0.30)

BASE_X = (-14.0, 21.0)  # latch side has fingernail room, tongue side the label
BASE_Y = 27.0
GAP = 3.0  # between bases
LABEL_X = 16.5
TEXT_HEIGHT = 0.6
# Bold 8 mm: ~1 mm strokes, over the 0.8 mm legibility floor (bore_coupons)
FONT, FONT_SIZE = "Arial", 8.0


def coupon(d: ChassisDims, letter: str) -> Part:
    base = Pos(sum(BASE_X) / 2, 0, 0) * Box(
        BASE_X[1] - BASE_X[0], BASE_Y, d.plate_thickness,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    part = base + drv_tray(d, placed=False)
    text = Text(letter, font_size=FONT_SIZE, font=FONT, font_style=FontStyle.BOLD)
    part += extrude(Plane.XY.offset(d.plate_thickness) * Pos(LABEL_X, 0) * text,
                    amount=TEXT_HEIGHT)
    return part


def fit_plate() -> list[tuple[str, ChassisDims]]:
    """The FIT grid: rows are end fit, columns preload."""
    letters = iter("ABCDEF")
    return [
        (next(letters), replace(ChassisDims(), drv_end_fit=e, drv_latch_preload=p))
        for e in END_FITS for p in PRELOADS
    ]


def latch_plate() -> list[tuple[str, ChassisDims]]:
    """Three copies of the tray as the car has it."""
    return [(letter, ChassisDims()) for letter in "HIJ"]


def make_coupons(entries, cols=3) -> Part:
    pitch_x = BASE_X[1] - BASE_X[0] + GAP
    pitch_y = BASE_Y + GAP
    rows = (len(entries) + cols - 1) // cols
    plate = Part()
    for i, (letter, d) in enumerate(entries):
        row, col = divmod(i, cols)
        x = (col - (cols - 1) / 2) * pitch_x
        y = ((rows - 1) / 2 - row) * pitch_y
        plate += Pos(x, y, 0) * coupon(d, letter)
    return plate


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "latch"
    table = {"fit": fit_plate, "latch": latch_plate}[which]()
    plate = make_coupons(table)
    print(f"DRV8833 tray coupons, {which} plate")
    for letter, d in table:
        g = drv_latch_geometry(d)
        print(
            f"  {letter}: end fit {d.drv_end_fit:.2f}, preload "
            f"{d.drv_latch_preload:.2f}, arm {d.drv_latch_t:g} x {d.drv_latch_w:g} "
            f"r{d.drv_latch_root_r:g} -> insertion {g['deflection']:.2f} mm "
            f"({g['strain'] * 100:.2f}% strain), barb reaches {g['reach']:.2f} "
            f"over the board, holds it at {g['rest_force']:.1f} N"
        )
    n = len(plate.solids())
    print(f"Solids: {n} (expect {len(table)})")
    bbox = plate.bounding_box()
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {plate.volume / 1000:.2f} cm^3")
    name = "drv_coupons" if which == "fit" else "drv_latch_coupons"
    export_stl(plate, f"{name}.stl")
    export_step(plate, f"{name}.step")
    print(f"Exported {name}.stl and {name}.step")
