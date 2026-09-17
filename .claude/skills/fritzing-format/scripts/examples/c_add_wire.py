"""Add a breadboard wire between two existing connectors (here: two breadboard holes)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import fzz

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
root, extras = fzz.read_fzz(src)

bb = fzz.find_instance(root, title="Breadboard1")
r1 = fzz.find_instance(root, title="R1")
a = fzz.end(bb, "breadboardView", "pin45J")      # same column strip as R1.connector1 (pin45I)
b = fzz.end(bb, "breadboardView", "pin55J")
fzz.add_wire(root, "breadboardView", a, b, color="#22aa22")

fzz.write_fzz(dst, root, extras)
print("wrote", dst)
