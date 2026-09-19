"""Stdlib-only helpers for reading, editing and writing Fritzing .fzz sketches.

Import from an example script with:
    sys.path.insert(0, "<repo>/.claude/skills/fritzing-format/scripts"); import fzz
"""
import math
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
NOTE_LAYER = {"breadboardView": "breadboardNote", "schematicView": "schematicNote", "pcbView": "pcbNote"}

# Parts that are not in parts.db: loaded from a .fzpz or found bundled in a .fzz.
# moduleId -> {"fzp": Element, "path": fzp file name, "members": {zip member name: bytes}}
_LOCAL = {}


# ---------- container ----------

def read_fzz(path):
    """Return (root_element, extras) where extras maps the non-.fz members (fzp/svg/ino) to bytes.

    Parts bundled in the sketch (part.*.fzp + svg.*) are registered, so connector_pos() and
    friends work on them like on library parts.
    """
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        fz = sorted(n for n in names if n.endswith(".fz"))[0]  # Fritzing loads the first *.fz
        root = ET.fromstring(z.read(fz))
        # Drop every .fz: a leftover one that sorts before the rewritten member would be loaded instead.
        extras = {n: z.read(n) for n in names if not n.endswith(".fz")}
    _register_members(extras, repair=False)
    return root, extras


def write_fzz(path, root, extras=None):
    """Write the sketch. Registered non-library parts used by an instance are bundled automatically."""
    path = pathlib.Path(path)
    members = dict(extras or {})
    used = {i.get("moduleIdRef") for i in instances(root)}
    for module_id, part in _LOCAL.items():
        if module_id in used:
            members.update(part["members"])
    ET.indent(root, space="    ")
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    tmp = path.with_suffix(".fzz.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(path.stem + ".fz", data)
        for n, d in members.items():
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


# ---------- non-library parts (.fzpz) ----------

def load_fzpz(path, repair=True):
    """Register a part from a .fzpz file (e.g. a vendor download); returns its moduleId.

    A .fzpz is a zip of one part.<name>.fzp plus svg.<view>.<file>.svg members, where the fzp's
    image="breadboard/<file>.svg" is the member "svg.breadboard.<file>.svg". The same members
    are bundled into any .fzz written with this part, so the sketch opens without importing it.

    repair=True wraps a single-layer SVG that lacks a group with the fzp's layerId (Fritzing
    then draws nothing for the part in that view) in such a group.
    """
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist()}
    ids = _register_members(members, repair)
    if len(ids) != 1:
        raise ValueError(f"{path}: expected one part.*.fzp, found {len(ids)}")
    return ids[0]


def _register_members(members, repair):
    ids = []
    for name in members:
        if not (name.startswith("part.") and name.endswith(".fzp")):
            continue
        fzp = ET.fromstring(members[name])
        module_id = fzp.get("moduleId")
        own = {name: members[name]}
        for layers in fzp.iter("layers"):
            member = _svg_member(layers.get("image") or "")
            if member in members:
                own[member] = members[member]
        if repair:
            _repair_layer_groups(fzp, own)
        _LOCAL[module_id] = {"fzp": fzp, "path": name[len("part."):], "members": own}
        ids.append(module_id)
    return ids


def _svg_member(image):
    return "svg." + image.replace("/", ".", 1)


def _repair_layer_groups(fzp, members):
    for view in fzp.find("views"):
        layers = view.find("layers")
        if layers is None or len(layers.findall("layer")) != 1:
            continue
        layer_id = layers.find("layer").get("layerId")
        name = _svg_member(layers.get("image") or "")
        if name not in members:
            continue
        text = members[name].decode("utf-8")
        if re.search(rf'\bid=["\']{re.escape(layer_id)}["\']', text):
            continue
        start = re.search(r"<svg\b[^>]*>", text).end()
        end = text.rindex("</svg>")
        members[name] = (text[:start] + f'<g id="{layer_id}">' + text[start:end] + "</g>" + text[end:]).encode("utf-8")


def part_members(module_id):
    """The part.*/svg.* members of a registered non-library part (write_fzz adds these itself)."""
    return dict(_LOCAL[module_id]["members"])


# ---------- parts library ----------

def part_info(module_id):
    """Look a part up in the bundled parts.db (or the registered .fzpz parts): fzp path, title, connectors, properties.

    "fzp" is None for parts compiled into Fritzing (wire, note, net label...) and for registered
    parts; "path" is always the fzp file name to write in <instance path=...>.
    """
    if module_id in _LOCAL:
        fzp = _LOCAL[module_id]["fzp"]
        conns = [(c.get("id"), c.get("name")) for c in fzp.find("connectors").findall("connector")]
        props = {p.get("name"): (p.text or "") for p in fzp.iter("property")}
        return {"moduleId": module_id, "title": fzp.findtext("title"), "fzp": None,
                "path": _LOCAL[module_id]["path"], "local": True, "connectors": conns, "properties": props}
    db = sqlite3.connect(PARTS / "parts.db")
    row = db.execute("select id, title, path from parts where moduleID=?", (module_id,)).fetchone()
    if row is None:
        raise KeyError(f"{module_id} is not in parts.db; register a downloaded part with load_fzpz()")
    pid, title, rel = row
    conns = db.execute("select connectorid, name from connectors where part_id=? order by id", (pid,)).fetchall()
    props = dict(db.execute("select name, value from properties where part_id=?", (pid,)).fetchall())
    path = None if rel.startswith(":") else PARTS / rel  # ":/resources/..." = compiled into the app (wire, note, ...)
    return {"moduleId": module_id, "title": title, "fzp": path, "path": path.name if path else rel,
            "local": False, "connectors": conns, "properties": props}


def search_parts(pattern):
    db = sqlite3.connect(PARTS / "parts.db")
    q = f"%{pattern}%"
    return db.execute("select moduleID, title, path from parts where title like ? or moduleID like ? limit 50", (q, q)).fetchall()


def _fzp(module_id):
    if module_id in _LOCAL:
        return _LOCAL[module_id]["fzp"]
    info = part_info(module_id)
    if info["fzp"] is None:
        raise ValueError(f"{module_id} is compiled into Fritzing; it has no .fzp on disk")
    return ET.parse(info["fzp"]).getroot()


def _svg_text(module_id, view):
    image = _fzp(module_id).find(f"views/{view}/layers").get("image")
    if module_id in _LOCAL:
        return _LOCAL[module_id]["members"][_svg_member(image)].decode("utf-8", "replace")
    svg_path = next((PARTS / "svg" / d / image for d in ("core", "contrib", "user", "obsolete")
                     if (PARTS / "svg" / d / image).exists()), None)
    if svg_path is None:
        raise FileNotFoundError(image)
    return svg_path.read_text(encoding="utf-8", errors="replace")


def connector_id(module_id, name):
    """Connector id for a connector name ("D0", "anode", "GND"); ids pass through unchanged."""
    conns = part_info(module_id)["connectors"]
    if name in {c for c, _ in conns}:
        return name
    matches = [c for c, n in conns if n == name]
    if len(matches) != 1:
        raise KeyError(f"{module_id}: {len(matches)} connectors named {name!r}")
    return matches[0]


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
    vb_w = float(vb.replace(",", " ").split()[2]) if vb else val
    return inches * SCENE_DPI / vb_w


# ---------- SVG geometry (transform-aware) ----------

_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # SVG matrix(a b c d e f)
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def _mul(a, b):
    """Affine a·b (apply b first), in SVG matrix(a b c d e f) order."""
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
            a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


def _apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _parse_transform(text):
    m = _IDENTITY
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        v = [float(n) for n in re.findall(_NUM, args)]
        if name == "matrix":
            t = tuple(v)
        elif name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            r = math.radians(v[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(v) == 3:  # rotate(a, cx, cy)
                t = _mul(_mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            raise ValueError(f"unsupported SVG transform {name}")
        m = _mul(m, t)
    return m


def _find(el, target, m=_IDENTITY):
    """(element, accumulated transform including its own) for id=target, or None."""
    m = _mul(m, _parse_transform(el.get("transform")))
    if el.get("id") == target:
        return el, m
    for child in el:
        hit = _find(child, target, m)
        if hit:
            return hit
    return None


def _path_points(d):
    """End and control points of an SVG path (a bounding box of these contains the curve)."""
    pts, x, y, sx, sy = [], 0.0, 0.0, 0.0, 0.0
    for cmd, args in re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)", d):
        v = [float(n) for n in re.findall(_NUM, args)]
        rel = cmd.islower()
        c = cmd.upper()
        if c == "Z":
            x, y = sx, sy
            continue
        step = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7}[c]
        for i in range(0, len(v) - step + 1, step):
            a = v[i:i + step]
            ox, oy = (x, y) if rel else (0.0, 0.0)
            if c == "H":
                x = a[0] + (x if rel else 0)
            elif c == "V":
                y = a[0] + (y if rel else 0)
            elif c == "A":  # endpoint only; a full arc can bulge past it (pads are closed shapes)
                x, y = a[5] + ox, a[6] + oy
            else:
                for j in range(0, step - 2, 2):
                    pts.append((a[j] + ox, a[j + 1] + oy))
                x, y = a[step - 2] + ox, a[step - 1] + oy
            pts.append((x, y))
            if c == "M" and i == 0:
                sx, sy = x, y
    return pts


def _bbox(el, m):
    """Bounding box (x0, y0, x1, y1) of el and its children in root user units, or None."""
    tag = el.tag.split("}")[-1]
    f = lambda k: float(el.get(k, 0) or 0)  # noqa: E731
    local = []
    if tag == "rect":
        local = [(f("x"), f("y")), (f("x") + f("width"), f("y") + f("height"))]
    elif tag == "circle":
        local = [(f("cx") - f("r"), f("cy") - f("r")), (f("cx") + f("r"), f("cy") + f("r"))]
    elif tag == "ellipse":
        local = [(f("cx") - f("rx"), f("cy") - f("ry")), (f("cx") + f("rx"), f("cy") + f("ry"))]
    elif tag == "line":
        local = [(f("x1"), f("y1")), (f("x2"), f("y2"))]
    elif tag in ("polygon", "polyline"):
        nums = [float(n) for n in re.findall(_NUM, el.get("points", ""))]
        local = list(zip(nums[0::2], nums[1::2]))
    elif tag == "path":
        local = _path_points(el.get("d", ""))
    boxes = []
    if local:
        if tag in ("rect", "circle", "ellipse"):  # transform all four corners
            (x0, y0), (x1, y1) = local
            local = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
        xs, ys = zip(*(_apply(m, x, y) for x, y in local))
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    for child in el:
        b = _bbox(child, _mul(m, _parse_transform(child.get("transform"))))
        if b:
            boxes.append(b)
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def connector_offset(module_id, view, connector_id):
    """Where a wire attaches to a connector, in scene px from the part's <geometry x y> (unrotated part).

    Follows Fritzing: a bendable leg's free end (the leg line's end farther from the SVG centre,
    FSvgRenderer::calcLeg); else the centre of the terminalId element (pin end, schematic);
    else the centre of the svgId element. SVG group transforms are applied. <path> shapes use the
    box of their end and control points, which matches Fritzing's bounds for pads and pins.
    """
    fzp = _fzp(module_id)
    raw = _svg_text(module_id, view)
    svg = ET.fromstring(raw.encode())
    scale = _svg_scale(svg, raw)
    vb = [float(n) for n in (svg.get("viewBox") or "0 0 0 0").replace(",", " ").split()]
    c = next((c for c in fzp.find("connectors").findall("connector") if c.get("id") == connector_id), None)
    if c is None:
        raise KeyError(f"{module_id} has no connector {connector_id}")
    p = c.find(f"views/{view}/p")
    what = f"{module_id} {view} {connector_id}"

    if p.get("legId"):
        el, m = _find(svg, p.get("legId")) or (None, None)
        if el is None:
            raise ValueError(f"{what}: leg {p.get('legId')} not in SVG")
        cx, cy = vb[0] + vb[2] / 2, vb[1] + vb[3] / 2
        ends = [_apply(m, float(el.get("x1")), float(el.get("y1"))), _apply(m, float(el.get("x2")), float(el.get("y2")))]
        x, y = max(ends, key=lambda e: (e[0] - cx) ** 2 + (e[1] - cy) ** 2)
    else:
        box = None
        for target in (p.get("terminalId"), p.get("svgId")):
            hit = target and _find(svg, target)
            if hit:
                box = _bbox(*hit)
                if box:
                    break
        if box is None:
            raise ValueError(f"{what}: no measurable terminal/svg element ({p.get('terminalId')}, {p.get('svgId')})")
        x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return (x - vb[0]) * scale, (y - vb[1]) * scale


def part_size(module_id, view):
    """Width, height of the part in scene px (unrotated)."""
    raw = _svg_text(module_id, view)
    svg = ET.fromstring(raw.encode())
    vb = [float(n) for n in svg.get("viewBox").replace(",", " ").split()]
    s = _svg_scale(svg, raw)
    return vb[2] * s, vb[3] * s


NET_LABEL_HEIGHT = 9.0  # NetLabel::makeSvg: 300/3 = 100 mils tall, connector at mid-height


def connector_pos(inst, view, connector_id):
    g = inst.find(f"views/{view}/geometry")
    module_id = inst.get("moduleIdRef")
    if module_id == WIRE_MODULE:  # wire ends come from its own line, not an SVG
        if connector_id == "connector0":
            end_x, end_y = "x1", "y1"
        elif connector_id == "connector1":
            end_x, end_y = "x2", "y2"
        else:
            raise KeyError(connector_id)
        return float(g.get("x")) + float(g.get(end_x)), float(g.get("y")) + float(g.get(end_y))
    if module_id in ("NetLabelModuleID", "LeftNetLabelModuleID"):
        direction = next((p.get("value") for p in inst.findall("property") if p.get("name") == "direction"), None)
        if direction != "left":
            raise ValueError("only direction=left net labels have a fixed connector point (their width follows the text)")
        return float(g.get("x")), float(g.get("y")) + NET_LABEL_HEIGHT / 2
    dx, dy = connector_offset(module_id, view, connector_id)
    return float(g.get("x")) + dx, float(g.get("y")) + dy


# ---------- building ----------

def add_part(root, module_id, title, positions, props=None, index=None, z=2.5):
    """positions: {view: (x, y)}; a part only appears in the views you give it.

    Works for library parts and for parts registered with load_fzpz().
    z orders items within a view: breadboards ~1.5, parts ~2.5, wires ~3.5 (Fritzing's own values).
    """
    info = part_info(module_id)
    if info["fzp"] is None and not info["local"]:
        raise ValueError(f"{module_id} is compiled into Fritzing (no .fzp on disk); use add_wire(), "
                         "add_note() or add_net_label(), or copy a Fritzing-saved instance")
    idx = next_model_index(root) if index is None else index
    inst = ET.SubElement(root.find("instances"), "instance", moduleIdRef=module_id,
                         modelIndex=str(idx), path=info["path"])
    for k, v in (props or {}).items():
        ET.SubElement(inst, "property", name=k, value=str(v))
    ET.SubElement(inst, "title").text = title
    views = ET.SubElement(inst, "views")
    for view, (x, y) in positions.items():
        v = ET.SubElement(views, view, layer=view_layer(module_id, view))
        ET.SubElement(v, "geometry", z=f"{z:g}", x=f"{x:g}", y=f"{y:g}")
    return inst


def place_at(module_id, view, connector, x, y):
    """The part position (for add_part) that puts connector (id or name) exactly on (x, y)."""
    dx, dy = connector_offset(module_id, view, connector_id(module_id, connector))
    return x - dx, y - dy


def set_label(inst, view, x, y, keys=(), font_size=5):
    """Show the part label at (x, y) (scene px). keys = property names shown on extra lines
    (e.g. "resistance"); the title line is always kept. Without a label, hand-made parts often
    export with no visible label in schematic view."""
    v = inst.find(f"views/{view}")
    old = v.find("titleGeometry")
    if old is not None:
        v.remove(old)
    tg = ET.Element("titleGeometry", visible="true", x=f"{x:g}", y=f"{y:g}", z="12.5",
                    xOffset="0", yOffset="0", textColor="#000000", fontSize=f"{font_size:g}")
    for key in ("", *keys):  # "" is PartLabel's LabelTextKey (the title); a key list without it drops the title
        ET.SubElement(tg, "displayKey", key=key)
    v.insert(list(v).index(v.find("geometry")) + 1, tg)  # after <geometry>, where Fritzing writes it


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


def end(inst, view, connector):
    """(instance, connectorId, layer) triple for connect()/add_wire(). connector may be an id
    ("connector0") or a name ("D0", "anode"). Works for parts, net labels and existing wires."""
    module_id = inst.get("moduleIdRef")
    if module_id == WIRE_MODULE:
        v = inst.find(f"views/{view}")
        if v is None:
            raise ValueError(f"wire {inst.findtext('title')} has no {view}")
        return inst, connector, v.get("layer")  # a wire's connectors sit on the wire's own layer
    if module_id in ("NetLabelModuleID", "LeftNetLabelModuleID"):
        return inst, "connector0", "schematic"
    cid = connector_id(module_id, connector)
    return inst, cid, connector_layer(module_id, view, cid)


def add_wire(root, view, a, b, color=None, title=None, via=()):
    """Wire from end a to end b (triples from end()), endpoints placed on the connectors.

    via = bend points [(x, y), ...]: one wire per segment, chained end to end (as Fritzing does
    when you drag a bendpoint). Returns the list of wire instances.
    """
    layer, flags, default_color, mils = WIRE_STYLE[view]
    pts = [connector_pos(a[0], view, a[1]), *via, connector_pos(b[0], view, b[1])]
    wires, prev = [], a
    for n, ((x1, y1), (x2, y2)) in enumerate(zip(pts, pts[1:])):
        idx = next_model_index(root)
        w = ET.SubElement(root.find("instances"), "instance", moduleIdRef=WIRE_MODULE,
                          modelIndex=str(idx), path="wire.fzp")
        ET.SubElement(w, "title").text = (title if n == 0 else f"{title}.{n}") if title else f"Wire{idx}"
        v = ET.SubElement(ET.SubElement(w, "views"), view, layer=layer)
        ET.SubElement(v, "geometry", z="3.5", x=f"{x1:g}", y=f"{y1:g}", x1="0", y1="0",
                      x2=f"{x2 - x1:g}", y2=f"{y2 - y1:g}", wireFlags=flags)
        ET.SubElement(v, "wireExtras", mils=mils, color=color or default_color, opacity="1", banded="0")
        connect(view, (w, "connector0", layer), prev)
        prev = (w, "connector1", layer)
        wires.append(w)
    connect(view, prev, b)
    return wires


def add_net_label(root, text, x, y):
    """Schematic net label whose connector (its left, pointed end) sits at (x, y). Labels with the
    same text are connected. Returns the instance; use end(label, "schematicView", "connector0")."""
    idx = next_model_index(root)
    inst = ET.SubElement(root.find("instances"), "instance", moduleIdRef="LeftNetLabelModuleID",
                         modelIndex=str(idx), path=":/resources/parts/core/netlabel_left.fzp")
    ET.SubElement(inst, "property", name="label", value=text)
    ET.SubElement(inst, "property", name="direction", value="left")
    ET.SubElement(inst, "title").text = text
    v = ET.SubElement(ET.SubElement(inst, "views"), "schematicView", layer="schematic")
    ET.SubElement(v, "geometry", z="3", x=f"{x:g}", y=f"{y - NET_LABEL_HEIGHT / 2:g}")
    return inst


def add_note(root, view, x, y, width, height, *paragraphs):
    """Sticky note. paragraphs are HTML snippets. The -svg export draws ~9pt text whatever font
    size you set and drops <b>, so size the box for the text: roughly 30 chars per 180 px width,
    14 px per line plus 8 px between paragraphs."""
    idx = next_model_index(root)
    inst = ET.SubElement(root.find("instances"), "instance", moduleIdRef="NoteModuleID",
                         modelIndex=str(idx), path="note.fzp")
    ET.SubElement(inst, "title").text = f"Note{idx}"
    body = "".join(f'<p style="margin:0 0 4px 0;">{p}</p>' for p in paragraphs)
    ET.SubElement(inst, "text").text = (  # Qt rich text; ET escapes it on save
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">'
        '<html><head><meta name="qrichtext" content="1" /></head>'
        f'<body style="font-family:\'Droid Sans\'; font-size:9pt;">{body}</body></html>')
    v = ET.SubElement(ET.SubElement(inst, "views"), view, layer=NOTE_LAYER[view])
    ET.SubElement(v, "geometry", z="6.5", x=f"{x:g}", y=f"{y:g}", width=f"{width:g}", height=f"{height:g}")
    return inst
