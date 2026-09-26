"""DRV8833 tray fit coupons (parts library D2).

Six copies of chassis.py's drv_tray, each on its own small base, varying the
two numbers a caliper can't settle for the 18.5 x 15.6 x 1.6 mm board:

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

RESULT (black PLA Basic, X2D, 1.6 mm board): C fits best -- no wiggle, and
a fingernail on the latch still pops the board out. C's 0.05 end fit and
0.30 preload are ChassisDims' defaults. C is the tight corner of the grid,
so if the board ever loosens (PLA creep), the next step is more preload.
Reprint only if the printer, filament or board changes.

Everything else is drv_tray at ChassisDims defaults -- the same 7 mm
standoff (so the latch arm has its on-car length), tongues, corners and
latch. Each coupon is the tray in its canonical frame: tongues at +X, latch
at -X, the board's 18.5 mm axis along Y. The label sits on the tongue side.

Fitting: tilt the board about 15 deg, tuck the long edge under the two
tongues, rotate it down until the latch clicks over. Judge per coupon: does
it go in by hand, does it rattle when shaken, can you push it along either
axis, can you still pop it out with a fingernail on the latch.

Run with:  uv run robot_car/drv_coupons.py
Exports drv_coupons.stl and drv_coupons.step into the cwd.
"""

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


def make_coupons() -> tuple[Part, list]:
    pitch_x = BASE_X[1] - BASE_X[0] + GAP
    pitch_y = BASE_Y + GAP
    plate = Part()
    table = []
    letters = iter("ABCDEF")
    for row, end_fit in enumerate(END_FITS):
        for col, preload in enumerate(PRELOADS):
            d = replace(ChassisDims(), drv_end_fit=end_fit,
                        drv_latch_preload=preload)
            letter = next(letters)
            x = (col - (len(PRELOADS) - 1) / 2) * pitch_x
            y = ((len(END_FITS) - 1) / 2 - row) * pitch_y
            plate += Pos(x, y, 0) * coupon(d, letter)
            table.append((letter, d))
    return plate, table


if __name__ == "__main__":
    plate, table = make_coupons()
    print("DRV8833 tray fit coupons")
    for letter, d in table:
        g = drv_latch_geometry(d)
        print(
            f"  {letter}: end fit {d.drv_end_fit:.2f}, preload "
            f"{d.drv_latch_preload:.2f} -> insertion {g['deflection']:.2f} mm "
            f"({g['strain'] * 100:.2f}% strain), barb reaches {g['reach']:.2f} "
            f"over the board, holds it at {g['rest_force']:.1f} N"
        )
    n = len(plate.solids())
    print(f"Solids: {n} (expect {len(table)})")
    bbox = plate.bounding_box()
    print(f"Bounding box (mm): {bbox.size.X:.2f} x {bbox.size.Y:.2f} x {bbox.size.Z:.2f}")
    print(f"Volume: {plate.volume / 1000:.2f} cm^3")
    export_stl(plate, "drv_coupons.stl")
    export_step(plate, "drv_coupons.step")
    print("Exported drv_coupons.stl and drv_coupons.step")
