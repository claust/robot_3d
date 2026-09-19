"""Open an existing sketch, change a resistor value and a wire colour, save to a new file."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import fzz

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
root, extras = fzz.read_fzz(src)          # keep bundled fzp/svg/ino members

r1 = fzz.find_instance(root, title="R1")
fzz.set_property(r1, "resistance", "10k")  # the Inspector/label/colour bands follow this value

wire = fzz.find_instance(root, module_id=fzz.WIRE_MODULE)  # the first wire
wire.find("views/breadboardView/wireExtras").set("color", "#cc1f1a")  # breadboard colour only

fzz.write_fzz(dst, root, extras)
print("wrote", dst)
