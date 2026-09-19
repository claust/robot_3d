"""Stdlib-only helpers for reading, editing and writing Fritzing .fzz sketches.

Import from an example script with:
    sys.path.insert(0, "<repo>/.claude/skills/fritzing-format/scripts"); import fzz
"""
import pathlib
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET

APP = pathlib.Path("/Applications/Fritzing.app/Contents/MacOS")
PARTS = APP / "fritzing-parts"
SCENE_DPI = 90.0  # sketch coordinates are pixels at 90 dpi: 0.1 in == 9.0

VIEW_TAGS = ("breadboardView", "schematicView", "pcbView")
WIRE_MODULE = "WireModuleID"
WIRE_STYLE = {  # view -> (layer, wireFlags, color, mils)
    "breadboardView": ("breadboardWire", "64", "#418dd9", "22.2222"),
    "schematicView": ("schematicTrace", "128", "#404040", "9.7222"),
    "pcbView": ("copper1trace", "4", "#f2c600", "24"),
}


# ---------- container ----------

def read_fzz(path):
    """Return (root_element, extras) where extras maps the non-.fz members (fzp/svg/ino) to bytes."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        fz = sorted(n for n in names if n.endswith(".fz"))[0]  # Fritzing loads the first *.fz
        root = ET.fromstring(z.read(fz))
        # Drop every .fz: a leftover one that sorts before the rewritten member would be loaded instead.
        extras = {n: z.read(n) for n in names if not n.endswith(".fz")}
    return root, extras


def write_fzz(path, root, extras=None):
    path = pathlib.Path(path)
    ET.indent(root, space="    ")
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    tmp = path.with_suffix(".fzz.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(path.stem + ".fz", data)
        for n, d in (extras or {}).items():
            if not n.endswith(".fz"):
                z.writestr(n, d)
    tmp.replace(path)


def new_sketch(version="1.0.8"):
    root = ET.Element("module", fritzingVersion=version)
    ET.SubElement(root, "instances")
    return root


# ---------- instances ----------

def instances(root):
    return root.find("instances").findall("instance")


def find_instance(root, title=None, index=None, module_id=None):
    for inst in instances(root):
        if title is not None and inst.findtext("title") != title:
            continue
        if index is not None and inst.get("modelIndex") != str(index):
            continue
        if module_id is not None and inst.get("moduleIdRef") != module_id:
            continue
        return inst
    raise KeyError(f"no instance title={title} index={index} module={module_id}")


def next_model_index(root):
    return max([int(i.get("modelIndex", 0)) for i in instances(root)] + [1000]) + 1


def set_property(inst, name, value):
    for p in inst.findall("property"):
        if p.get("name") == name:
            p.set("value", str(value))
            return
    # properties must precede <title>/<views>; Fritzing reads them in any order but writes them first
    inst.insert(0, ET.Element("property", name=name, value=str(value)))


# ---------- parts library ----------

def part_info(module_id):
    """Look a part up in the bundled parts.db: fzp path, title, connectors, properties."""
    db = sqlite3.connect(PARTS / "parts.db")
    row = db.execute("select id, title, path from parts where moduleID=?", (module_id,)).fetchone()
    if row is None:
        raise KeyError(module_id)
    pid, title, rel = row
    conns = db.execute("select connectorid, name from connectors where part_id=? order by id", (pid,)).fetchall()
    props = dict(db.execute("select name, value from properties where part_id=?", (pid,)).fetchall())
    path = None if rel.startswith(":") else PARTS / rel  # ":/resources/..." = compiled into the app (wire, note, ...)
    return {"moduleId": module_id, "title": title, "fzp": path, "connectors": conns, "properties": props}


def search_parts(pattern):
    db = sqlite3.connect(PARTS / "parts.db")
    q = f"%{pattern}%"
    return db.execute("select moduleID, title, path from parts where title like ? or moduleID like ? limit 50", (q, q)).fetchall()


def _fzp(module_id):
    info = part_info(module_id)
    return ET.parse(info["fzp"]).getroot()


def view_layer(module_id, view):
    """The layer attribute Fritzing writes on <{view} layer=...> for this part."""
    layers = [l.get("layerId") for l in _fzp(module_id).find(f"views/{view}/layers").findall("layer")]
    if view == "pcbView" and "copper0" in layers:
        return "copper0"  # THT parts sit on copper0; SMD parts only have copper1
    return layers[0]


def connector_layer(module_id, view, connector_id):
    for c in _fzp(module_id).find("connectors").findall("connector"):
        if c.get("id") == connector_id:
            return c.find(f"views/{view}/p").get("layer")
    raise KeyError(connector_id)


def _svg_scale(svg_root, raw_text):
    """Scene pixels per SVG user unit (Fritzing: px/unitless = 90 dpi, or 72 dpi for Illustrator files)."""
    w = svg_root.get("width")
    vb = svg_root.get("viewBox")
    m = re.match(r"([\d.]+)\s*([a-z%]*)", w or "")
    if not m:
        return 1.0
    val, unit = float(m.group(1)), m.group(2)
    per_inch = {"in": 1, "mm": 25.4, "cm": 2.54, "pt": 72, "pc": 6}.get(unit)
    if per_inch is None:  # px or unitless
        per_inch = 72.0 if "Generator: Adobe Illustrator" in raw_text else 90.0
    inches = val / per_inch
    vb_w = float(vb.split()[2]) if vb else val
    return inches * SCENE_DPI / vb_w


def connector_offset(module_id, view, connector_id):
    """Connector position relative to the part's <geometry x y> in scene px (unrotated parts only).

    Uses the leg end for bendable-leg parts, else the centre of the svgId element
    (rect/circle/ellipse/line/polygon/polyline, or the first such shape inside a <g>).
    Connectors drawn as <path> raise ValueError; place those by hand from the SVG.
    Ignores SVG group transforms — check the SVG if a part's numbers look off.
    """
    fzp = _fzp(module_id)
    image = fzp.find(f"views/{view}/layers").get("image")
    svg_path = next((PARTS / "svg" / d / image for d in ("core", "contrib", "user", "obsolete")
                     if (PARTS / "svg" / d / image).exists()), None)
    if svg_path is None:
        raise FileNotFoundError(image)
    raw = svg_path.read_text(encoding="utf-8", errors="replace")
    svg = ET.fromstring(raw.encode())
    scale = _svg_scale(svg, raw)
    p = next(c for c in fzp.find("connectors").findall("connector") if c.get("id") == connector_id).find(f"views/{view}/p")
    target = p.get("legId") or p.get("svgId")
    el = next(e for e in svg.iter() if e.get("id") == target)
    x, y = _shape_point(el, is_leg=target == p.get("legId"), what=f"{module_id} {view} {connector_id} ({target})")
    return x * scale, y * scale


_SHAPES = ("rect", "circle", "ellipse", "line", "polygon", "polyline")


def _shape_point(el, is_leg, what):
    tag = el.tag.split("}")[-1]
    if tag == "g":
        el = next((e for e in el.iter() if e.tag.split("}")[-1] in _SHAPES), None)
        if el is None:
            raise ValueError(f"connector {what}: group has no rect/circle/ellipse/line/polygon to measure")
        tag = el.tag.split("}")[-1]
    if tag == "line":
        if is_leg:  # leg: x1,y1 is the free end
            return float(el.get("x1")), float(el.get("y1"))
        return (float(el.get("x1")) + float(el.get("x2"))) / 2, (float(el.get("y1")) + float(el.get("y2"))) / 2
    if tag in ("circle", "ellipse"):
        return float(el.get("cx", 0)), float(el.get("cy", 0))
    if tag == "rect":
        return (float(el.get("x", 0)) + float(el.get("width", 0)) / 2,
                float(el.get("y", 0)) + float(el.get("height", 0)) / 2)
    if tag in ("polygon", "polyline"):
        nums = [float(n) for n in re.findall(r"-?[\d.]+(?:e-?\d+)?", el.get("points", ""))]
        xs, ys = nums[0::2], nums[1::2]
        return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    raise ValueError(f"connector {what}: unsupported SVG element <{tag}>; read its position from the SVG by hand")


def connector_pos(inst, view, connector_id):
    g = inst.find(f"views/{view}/geometry")
    if inst.get("moduleIdRef") == WIRE_MODULE:  # wire ends come from its own line, not an SVG
        if connector_id == "connector0":
            end_x, end_y = "x1", "y1"
        elif connector_id == "connector1":
            end_x, end_y = "x2", "y2"
        else:
            raise KeyError(connector_id)
        return float(g.get("x")) + float(g.get(end_x)), float(g.get("y")) + float(g.get(end_y))
    dx, dy = connector_offset(inst.get("moduleIdRef"), view, connector_id)
    return float(g.get("x")) + dx, float(g.get("y")) + dy


# ---------- building ----------

def add_part(root, module_id, title, positions, props=None, index=None, z=2.5):
    """positions: {view: (x, y)}; a part only appears in the views you give it.

    z orders items within a view: breadboards ~1.5, parts ~2.5, wires ~3.5 (Fritzing's own values).
    """
    info = part_info(module_id)
    if info["fzp"] is None:
        raise ValueError(f"{module_id} is compiled into Fritzing (no .fzp on disk); "
                         "use add_wire() for wires, or copy a Fritzing-saved instance for notes/logos")
    idx = next_model_index(root) if index is None else index
    inst = ET.SubElement(root.find("instances"), "instance", moduleIdRef=module_id,
                         modelIndex=str(idx), path=info["fzp"].name)
    for k, v in (props or {}).items():
        ET.SubElement(inst, "property", name=k, value=str(v))
    ET.SubElement(inst, "title").text = title
    views = ET.SubElement(inst, "views")
    for view, (x, y) in positions.items():
        v = ET.SubElement(views, view, layer=view_layer(module_id, view))
        ET.SubElement(v, "geometry", z=f"{z:g}", x=f"{x:g}", y=f"{y:g}")
    return inst


def _connector_el(inst, view, connector_id, layer):
    v = inst.find(f"views/{view}")
    conns = v.find("connectors")
    if conns is None:
        conns = ET.SubElement(v, "connectors")
    for c in conns.findall("connector"):
        if c.get("connectorId") == connector_id:
            return c
    c = ET.SubElement(conns, "connector", connectorId=connector_id, layer=layer)
    ET.SubElement(c, "geometry", x="0", y="0")
    ET.SubElement(c, "connects")
    return c


def connect(view, a, b):
    """a, b: (instance, connectorId, layer). Writes the link on BOTH sides, as Fritzing does."""
    for (i1, c1, l1), (i2, c2, l2) in ((a, b), (b, a)):
        el = _connector_el(i1, view, c1, l1)
        ET.SubElement(el.find("connects"), "connect", connectorId=c2, modelIndex=i2.get("modelIndex"), layer=l2)


def end(inst, view, connector_id):
    """(instance, connectorId, layer) triple for connect()/add_wire(). Works for parts and existing wires."""
    if inst.get("moduleIdRef") == WIRE_MODULE:
        v = inst.find(f"views/{view}")
        if v is None:
            raise ValueError(f"wire {inst.findtext('title')} has no {view}")
        return inst, connector_id, v.get("layer")  # a wire's connectors sit on the wire's own layer
    info = part_info(inst.get("moduleIdRef"))
    if info["fzp"] is None:
        raise ValueError(f"{info['moduleId']} is compiled into Fritzing; its connector layers aren't on disk")
    return inst, connector_id, connector_layer(inst.get("moduleIdRef"), view, connector_id)


def add_wire(root, view, a, b, color=None, title=None):
    """Wire from end a to end b (triples from end()), with endpoints placed on the connectors."""
    layer, flags, default_color, mils = WIRE_STYLE[view]
    x1, y1 = connector_pos(a[0], view, a[1])
    x2, y2 = connector_pos(b[0], view, b[1])
    idx = next_model_index(root)
    w = ET.SubElement(root.find("instances"), "instance", moduleIdRef=WIRE_MODULE,
                      modelIndex=str(idx), path="wire.fzp")
    ET.SubElement(w, "title").text = title or f"Wire{idx}"
    v = ET.SubElement(ET.SubElement(w, "views"), view, layer=layer)
    ET.SubElement(v, "geometry", z="3.5", x=f"{x1:g}", y=f"{y1:g}", x1="0", y1="0",
                  x2=f"{x2 - x1:g}", y2=f"{y2 - y1:g}", wireFlags=flags)
    ET.SubElement(v, "wireExtras", mils=mils, color=color or default_color, opacity="1", banded="0")
    connect(view, (w, "connector0", layer), a)
    connect(view, (w, "connector1", layer), b)
    return w
