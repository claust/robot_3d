# Fritzing parts

Download parts that are missing from Fritzing's own library into this folder
(the `.fzpz` files are gitignored). You only need them to start a new sketch or to
import a part into Fritzing: every `.fzz` in the repo carries its own copy of the
parts it uses.

## Devantech SRF08

Fritzing has no SRF08, so `esp32-c5/srf08_range/srf08_range.fzz` carries a hand-made
one (moduleId `robot3d_srf08_ModuleID`): the 5-way connector with its pins named, and
a **schematic view only** — it has no breadboard or PCB view. To use it in a new
sketch, `fzz.read_fzz()` that sketch first, which registers every part bundled in it.

## Seeed Studio XIAO ESP32C5

Download `XIAO Boards/Seeed Studio XIAO ESP32C5.fzpz` from
[Seeed-Studio/fritzing_parts](https://github.com/Seeed-Studio/fritzing_parts)
(the version added on 2026-01-22) into this folder.

**Bug in Seeed's part:** Fritzing draws only the SVG group whose `id` matches the
part's layer, and the breadboard and icon SVGs have no `<g id="breadboard">` /
`<g id="icon">`. The board then shows up blank in breadboard view and in the parts
bin. The fritzing-format skill's `fzz.load_fzpz` adds the missing groups when it loads
the part. Before importing the part into Fritzing (Parts → MINE → Import…, or open the
`.fzpz` with Fritzing), fix the file in place with this command, run from this
folder. It is safe to run twice:

```bash
python3 - "Seeed Studio XIAO ESP32C5.fzpz" <<'EOF'
import re, sys, zipfile
path = sys.argv[1]
with zipfile.ZipFile(path) as z:
    members = {n: z.read(n) for n in z.namelist()}
for name, layer in (("svg.breadboard.", "breadboard"), ("svg.icon.", "icon")):
    n = next(m for m in members if m.startswith(name))
    t = members[n].decode()
    if f'id="{layer}"' not in t:
        s, e = re.search(r"<svg\b[^>]*>", t).end(), t.rindex("</svg>")
        members[n] = (t[:s] + f'<g id="{layer}">' + t[s:e] + "</g>" + t[e:]).encode()
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
    for n, d in members.items():
        z.writestr(n, d)
EOF
```

Other things to know about this part: its schematic symbol has only the 14 pads
(D0–D10, 5V, GND, 3V3), and its breadboard pads aren't on an exact 0.1 in grid, so it
won't seat on breadboard holes. Wire straight to the pads.
