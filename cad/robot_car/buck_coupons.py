"""MP1584 tray coupons (parts library P1).

Two copies of chassis.py's buck_tray, each on its own small base, for the
22.5 x 17 mm board carried components down with a 2-pin header on every
corner pad pair. The tray is the DRV8833's, proven on drv_coupons.py (fit
C, latch H-J); what's new here is where its shelves sit under the MP1584
and the 22.5 mm axis the end stops close on, so the two coupons differ
only in end fit:

    M  end fit 0.05                  N  end fit 0.15

RESULT (green PLA Basic, X2D, 2026-09-27): N fits best, and 0.15 is the
car's buck_end_fit.

Fitting: components down, the SS34 diode's long edge toward the tongues,
so the tongue columns land between the end of the diode and the OUT
pads. Tilt it about 15 deg, tuck that edge under the tongues, rotate it
down until the latch clicks over. Judge: does it sit flat on its shelves without a
component touching, does it rattle, can you push it along the 22.5 mm
axis, can you pop it out with a fingernail on the latch.

Run with:  uv run robot_car/buck_coupons.py
Exports buck_coupons.stl/.step into the cwd.
"""

from dataclasses import replace

from build123d import Align, Box, Part, Plane, Pos, Text, export_step, export_stl, extrude

from chassis import ChassisDims, buck_tray

END_FITS = (("M", 0.05), ("N", 0.15))
BASE_X = (-14.0, 20.0)  # latch side has fingernail room, tongue side the label
BASE_Y = 30.0
GAP = 3.0
LABEL_X = 16.0
TEXT_HEIGHT = 0.8
FONT, FONT_SIZE = "Arial Black", 6.0  # ~1.2 mm strokes, over the 0.8 mm floor


def coupon(d: ChassisDims, letter: str) -> Part:
    base = Pos(sum(BASE_X) / 2, 0, 0) * Box(
        BASE_X[1] - BASE_X[0], BASE_Y, d.plate_thickness,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    part = base + buck_tray(d, +1, placed=False)
    text = Text(letter, font_size=FONT_SIZE, font=FONT)
    return part + extrude(Plane.XY.offset(d.plate_thickness) * Pos(LABEL_X, 0) * text,
                          amount=TEXT_HEIGHT)


if __name__ == "__main__":
    pitch = BASE_Y + GAP
    plate = Part()
    for i, (letter, fit) in enumerate(END_FITS):
        d = replace(ChassisDims(), buck_end_fit=fit)
        plate += Pos(0, (i - (len(END_FITS) - 1) / 2) * pitch, 0) * coupon(d, letter)
        print(f"  {letter}: end fit {fit:.2f} per end on the 22.5 mm axis")
    bb = plate.bounding_box()
    print(f"Solids: {len(plate.solids())} (expect {len(END_FITS)})")
    print(f"Bounding box (mm): {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f}")
    export_stl(plate, "buck_coupons.stl")
    export_step(plate, "buck_coupons.step")
    print("Exported buck_coupons.stl and buck_coupons.step")
