"""Create a new sketch: one 1k resistor plugged into a breadboard (no wires)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import fzz

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "resistor_on_breadboard.fzz")
root = fzz.new_sketch()

bb = fzz.add_part(root, "Breadboard-RSR03MB102-ModuleID", "Breadboard1", {"breadboardView": (0, 0)}, z=1.5)

# Put the resistor so its connector0 leg end sits exactly on hole pin41I (legs are 0.4 in apart -> pin45I).
hole_x, hole_y = fzz.connector_pos(bb, "breadboardView", "pin41I")
leg_dx, leg_dy = fzz.connector_offset("ResistorModuleID", "breadboardView", "connector0")
r1 = fzz.add_part(root, "ResistorModuleID", "R1",
                  {"breadboardView": (hole_x - leg_dx, hole_y - leg_dy),
                   "schematicView": (0, 200),      # omit a view and the part is absent from that tab
                   "pcbView": (0, 0)},
                  props={"resistance": "1k"})

# Being on top of a hole is only visual; the electrical link is the <connects> pair.
for rc, pin in (("connector0", "pin41I"), ("connector1", "pin45I")):
    fzz.connect("breadboardView", fzz.end(r1, "breadboardView", rc), fzz.end(bb, "breadboardView", pin))

fzz.write_fzz(out, root)
print("wrote", out)
