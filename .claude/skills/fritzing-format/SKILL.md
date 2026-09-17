---
name: fritzing-format
description: Generating or editing Fritzing .fzz/.fz circuit sketch files programmatically, and reloading Fritzing to show the result (or rendering SVGs headlessly). Use when scripting breadboard/schematic/PCB diagrams for build docs, changing part properties or wire colours in an existing sketch, adding parts or wires, looking up Fritzing moduleIds/connectorIds, or when Fritzing does not show an externally edited sketch.
---

# Fritzing sketch format (.fzz / .fz)

Verified against the locally built Fritzing 1.0.8 at `/Applications/Fritzing.app`
(source: `/Users/claus/Repos/fritzing-app`, branch `develop`) on 2026-09-17.
Tags: **[verified]** = tested against the running app; **[source]** = read from
source only; **[unverified]** = not tested.

## Quick reference

| Need | Do |
|---|---|
| Render a sketch for docs, no GUI | `Fritzing -svg DIR` → `<name>_breadboard.svg`, `_schematic.svg`, `_pcb.svg` for every `.fzz` in DIR, then exits (~4 s) **[verified]** |
| Open a sketch in the GUI | `Fritzing file.fzz --debug > log 2>&1 &` or `open -a Fritzing file.fzz`. **The file goes BEFORE `--debug`**: `--debug file.fzz` writes the log INTO the .fzz **[verified]** |
| Show an external edit | Quit Fritzing (Cmd+Q), edit, relaunch. Or `open -a Fritzing file.fzz` again (opens a fresh window) and close the stale one **[verified]** |
| Things that do NOT reload | File watching (none), File > Open of the same path (raises the stale window) **[verified]** |
| Container | Plain ZIP. Any compression works; the inner `.fz` name doesn't matter **[verified]** |
| Minimum XML | `<module fritzingVersion="1.0.8"><instances>…</instances></module>` **[verified]** |
| Electrical connection | `<connects>` entries on BOTH connectors. Geometry never creates or checks connections **[verified]** |
| Coordinates | Scene px at 90 dpi (0.1 in = 9.0), y down, per view **[verified]** |
| Find parts | `sqlite3 …/fritzing-parts/parts.db` (tables `parts`, `connectors`, `properties`), `.fzp` under `fritzing-parts/core/` |
| Helper lib | `scripts/fzz.py` (stdlib only): `read_fzz`, `write_fzz`, `new_sketch`, `add_part`, `connect`, `add_wire`, `connector_pos`, `part_info`, `search_parts` |

```bash
FRITZING=/Applications/Fritzing.app/Contents/MacOS/Fritzing
```

## 1. Container

- A `.fzz` is a ZIP. A core-parts-only sketch holds one `<name>.fz` (UTF-8 XML).
  Sketches with Arduino code also hold `.ino` files. Sketches with non-library
  parts bundle `part.<file>.fzp_<hash>_N.fzp` and `svg.<view>.<file>…svg` members.
  Sample of 125 bundled sketches: 125 `.fz`, 58 `.ino`, 7 `.fzp`, 28 `.svg`.
- Loading unzips into `~/Library/Application Support/Fritzing/Fritzing/fzz/<random>/`
  and takes the first `*.fz` that `QDir::entryInfoList` returns. **[source]**
  With two `.fz` members, the alphabetically first one loaded. **[verified]**
- Inner name ≠ outer basename: opens fine. **[verified]** Fritzing renames it to
  `<outer>.fz` on its next save. **[verified]**
- `ZIP_DEFLATED`, `ZIP_STORED`, `python3 -m zipfile -c`, a `.fz` inside a
  subfolder, and a member with `-r--------` permissions all open identically. **[verified]**
- A bundled `.fzp` is only used when its moduleId is missing from the parts
  library (or its SVGs are). It is then copied into the user's `partfactory/contrib` folder. **[source]**

## 2. XML schema

```xml
<?xml version="1.0" encoding="UTF-8"?>
<module fritzingVersion="1.0.8.2026-07-28…" icon=".png">      <!-- only fritzingVersion matters -->
  <project_properties>…simulator settings…</project_properties> <!-- optional -->
  <boards><board moduleId=… title=… instance="PCB1" width="8.46667cm" height="5.64444cm"/></boards> <!-- optional, informational -->
  <views><view name="breadboardView" backgroundColor="#ffffff" gridSize="0.1in" showGrid="1" alignToGrid="1" viewFromBelow="0" colorWiresByLength="0"/>…</views> <!-- optional -->
  <programs pid="…"><program language="Arduino" programmer="">relative/path.ino</program></programs> <!-- optional -->
  <instances>
    <instance moduleIdRef="ResistorModuleID" modelIndex="6021" path="resistor.fzp">
      <property name="resistance" value="220"/>          <!-- 0..n, overrides the fzp default -->
      <title>R1</title>                                    <!-- label / Inspector name -->
      <views>
        <breadboardView layer="breadboard">
          <geometry z="2.5" x="367.69" y="49.46"/>
          <titleGeometry …/>                               <!-- part label, optional -->
          <connectors>                                     <!-- only connectors that have connections -->
            <connector connectorId="connector0" layer="breadboard">
              <geometry x="0" y="0"/>
              <leg><point x="0" y="0"/><bezier/><point x="-1.31" y="0"/><bezier/></leg> <!-- bendable legs only -->
              <connects><connect connectorId="pin41I" modelIndex="5796" layer="breadboardbreadboard"/></connects>
            </connector>
          </connectors>
        </breadboardView>
        <schematicView layer="schematic">…</schematicView>
        <pcbView layer="copper0">…</pcbView>
      </views>
    </instance>
  </instances>
</module>
```

### Reference table

Views: B = breadboardView, S = schematicView, P = pcbView. Example values come from
a survey of the 125 bundled sketches plus `simple.fzz`.

| Element / attribute | Meaning | Example | Views |
|---|---|---|---|
| `module@fritzingVersion` | Version that saved the file. Missing → modal warning; newer than the app → modal warning **[source]** | `1.0.8` works **[verified]** | – |
| `module@icon`, `module/title` | Bin/sketch metadata, written by Fritzing | `.png` | – |
| `project_properties/<key value>` | Simulator settings | `simulator_time_step_s value="1us"` | – |
| `boards/board` | Summary of PCB boards (moduleId, title, instance, width/height in cm) | `TwoLayerRectanglePCBModuleID` | P |
| `views/view@name` + `backgroundColor gridSize showGrid alignToGrid viewFromBelow colorWiresByLength` | Per-view canvas settings. PCB adds `DRC_Keepout GPG_Keepout autorouteTraceWidth autorouteViaHoleSize autorouteViaRingThickness` | `gridSize="0.1in"` | B S P |
| `programs/program@language` | Linked code files (text = path) | `Arduino` | – |
| `instance@moduleIdRef` | Part definition id (`fzp <module moduleId>`). Unknown → modal "Unable to find N part(s)" | `ResistorModuleID` | – |
| `instance@modelIndex` | Instance id; `<connect modelIndex>` refers to it. Fritzing keeps your numbers on save **[verified]** | `6021` | – |
| `instance@path` | fzp **file name** only (informational; lookup is by moduleId). Omitting it works **[verified]** | `resistor.fzp` | – |
| `instance@flippedSMD` | SMD part placed on the bottom | `true` | P |
| `instance/property@name,value` | Instance property override. Empty values are ignored on load **[source]** | `resistance`/`4.7k`, `color`/`Red (633nm)`, `voltage`, `label` | – |
| `instance/title` | Instance title (R1, Wire3, Note1) | `R1` | – |
| `instance/text` | Note body (HTML, XML-escaped) or logo text | `&lt;!DOCTYPE HTML…` | – |
| `instance/localConnectors/localConnector@id,name` | Per-instance connector renames (e.g. on generic ICs) | `connector6`/`Q7` | – |
| `views/<view>@layer` | View layer the item sits on (see layer list below) | `breadboard`, `schematic`, `copper0` | B S P |
| `<view>@locked` | Move-locked | `true` | B S P |
| `<view>@bottom` | Placed on the bottom side | `true` | P |
| `<view>@superpart` | modelIndex of the parent part (schematic subparts) **[source]** | `1234` | S |
| `<view>/geometry@x,y` | Item position (top-left of the unrotated SVG) in 90-dpi scene px | `x="367.69"` | B S P |
| `geometry@z` | Stacking order within the view: breadboard ≈1.5, parts ≈2.5, wires ≈3.5, notes ≈6.5 | `2.50001` | B S P |
| `geometry@x1,y1,x2,y2` | Wire line relative to x,y (x1,y1 are always 0) | `x2="62.98" y2="-81"` | wires |
| `geometry@wireFlags` | Bit flags: 2 routed, 4 PCB trace, 16 ratsnest, 32 autoroutable, 64 normal (breadboard wire), 128 schematic trace | `64`, `128`, `4`, `36` | wires |
| `geometry@width,height` | Note/logo size | `351` | notes |
| `geometry/transform@m11…m33` | Rotation/flip QTransform. m31/m32 = translation. Absent = identity **[source]**; rotation not tested | `m11="0" m12="1" m21="-1" m22="0"` | B S P |
| `wireExtras@color,mils,opacity,banded` | Wire colour, width in mils, opacity, striped look | `#418dd9`, `22.2222` | wires |
| `wireExtras/bezier/cp0,cp1@x,y` | Curvy wire control points | | wires |
| `titleGeometry@visible,x,y,z,xOffset,yOffset,textColor,fontSize` + `displayKey@key` | Part label position/visibility; `displayKey` = which properties show in the label | `displayKey key="resistance"` | S P (B rare) |
| `titleGeometry/transform` | Rotated label | | S P |
| `layerHidden@layer` | A part layer hidden by the user | `silkscreen` | P |
| `connectors/connector@connectorId,layer` | Connector of this item that has connections | `pin41Z` | B S P |
| `connector@groundFillSeed` | Ground-fill seed flag | `true` | P |
| `connector/geometry@x,y` | Written by Fritzing, usually `0 0`. **Not** used to place wires | | B S P |
| `connector/leg/point,bezier(cp0,cp1)` | Rubber-band leg polyline (resistors, LEDs…) | | B |
| `connects/connect@connectorId,modelIndex,layer` | Other end of a connection (connector id, instance, that connector's layer) | | B S P |

Layers seen in `<view layer>` / `connect@layer`: breadboard: `breadboard`,
`breadboardbreadboard` (breadboards), `breadboardWire`, `breadboardNote`. Schematic:
`schematic`, `schematicTrace`. PCB: `copper0`, `copper1`, `copper0trace`,
`copper1trace`, `board`, `silkscreen`, `silkscreen0`, `groundplane`, `groundplane1`,
`partimage`, `pcbNote`.

Special moduleIds (fzp compiled into the app, path `:/resources/parts/core/…`):
`WireModuleID` (wire.fzp), `NoteModuleID` (note.fzp), plus logo/ruler/via/hole/
ground/net-label parts (`LogoTextModuleID`, `ViaModuleID`, `HoleModuleID`,
`NetLabelModuleID`, `PowerLabelModuleID`, `GroundModuleID`). No groups: the
format has no group element, and none of the 125 samples contain one.

### Per-view presence (important)

- A part appears only in the views that have a `<xxxView>` element under its
  `<views>`. Give a hand-made part all three views, or it's missing from those
  tabs. Example (a) exports correctly in all three. **[verified]**
- A breadboard wire (flags 64) drawn only in `breadboardView` stays
  breadboard-only after a Fritzing save. The other views show ratsnest lines
  derived from the connections. **[verified]**
  Files Fritzing saves itself copy each wire into all three views with the same flags.
- An instance whose `<views>` is empty or absent is skipped on load. **[source]**

### modelIndex, ids, titles

- Missing `modelIndex`, gaps, huge values (900000) and duplicate values all load
  without complaint, and both parts appear. **[verified]** A `<connect>` targets an
  instance by modelIndex, so keep them unique. What happens to connections
  under duplicates is **[unverified]**.
- Fritzing's internal item id is derived from modelIndex, so the same instance
  matches up across views. **[source]**
- Duplicate titles are **[unverified]**. Keep them unique (R1, R2…).

### Connections (important)

- Connectivity comes only from `<connects>`. A wire drawn nowhere near its
  connectors still connects if the `<connect>` pairs exist (the breadboard strip
  lights green). Geometry is kept exactly as written. **[verified]**
- The reverse also holds: a resistor placed exactly over breadboard holes with no
  `<connects>` is NOT plugged in. Its leg ends show red and nothing is
  auto-connected on load. **[verified]**
- Write the link on both connectors, as Fritzing does (`fzz.connect` does this).
  One-sided links are **[unverified]**.
- `connect@layer` is the other connector's layer from its fzp
  (`<connector><views><breadboardView><p layer=…>`). Wire ends use the wire's
  view layer (`breadboardWire` / `schematicTrace` / `copper1trace`).

## 3. Parts lookup (moduleIdRef + path)

- Library: `/Applications/Fritzing.app/Contents/MacOS/fritzing-parts/`:
  `core/*.fzp` (1797), `contrib/`, `user/`, `obsolete/` (398), SVGs in
  `svg/<core|contrib|obsolete>/<breadboard|schematic|pcb|icon>/`, index
  `parts.db`. User parts live in `~/Documents/Fritzing/parts` **[source]**; parts
  unpacked from `.fzz` files go to `~/Library/Application Support/Fritzing/Fritzing/partfactory` / `local_parts` **[source]**.
- `parts.db` (SQLite): `parts(id, moduleID, title, family, path, …)`,
  `connectors(connectorid, name, type, part_id)`,
  `properties(name, value, show_in_label, part_id)`.
  ```bash
  DB=/Applications/Fritzing.app/Contents/MacOS/fritzing-parts/parts.db
  sqlite3 "$DB" "select moduleID,title,path from parts where title like '%breadboard%'"
  sqlite3 "$DB" "select c.connectorid,c.name from connectors c join parts p on c.part_id=p.id where p.moduleID='ResistorModuleID'"
  ```
  Or from Python: `fzz.search_parts("battery")`, `fzz.part_info("ResistorModuleID")`.
- The fzp gives: `<properties>` (names are lowercased in instances, e.g.
  `Resistance` → `resistance`), `<views><xView><layers image="breadboard/x.svg"><layer layerId=…>`,
  and `<connectors><connector id name><views><xView><p svgId layer legId terminalId>`.
  Breadboards also have `<buses>` that tie rows/rails together internally.
- Useful ids: breadboard `Breadboard-RSR03MB102-ModuleID` (full, holes `pin<col><row>`,
  cols 1–63, rows A–J plus rail rows W/X/Y/Z; A–E = lower block, F–J = upper block,
  `Z` = a top rail row and `X` = a bottom rail row per `simple.fzz`),
  half breadboard `0152b316-ca6e-11ee-a6fa-8be78db221f8BreadboardModuleID`,
  resistor `ResistorModuleID`, battery `Electromechanical-BATTERY-2-AAA`.

### Connector coordinates

To land a wire end or leg on a connector: `part geometry (x,y)` + `SVG element
centre × scale`, where scale = scene px per SVG unit
= (SVG width in inches × 90) / viewBox width. A `px`/unitless width counts as
72 dpi for Adobe Illustrator SVGs (detected by the "Generator: Adobe Illustrator"
comment), otherwise 90 dpi (`TextUtils::convertToInches`). **[source]**
Bendable legs use the `legId` line's `x1,y1`.
`fzz.connector_offset()` implements this. It ignores rotation and SVG group
transforms. Checks: breadboard2 hole `pin41I` plus the resistor leg offset gives
(372.337, 49.4595) relative to the breadboard, the same value Fritzing saved in
`simple.fzz`. Example (c)'s wire ends render exactly on its holes. **[verified]**

## 4. Getting Fritzing to show an edit

Answers to the core questions, all **[verified]** unless tagged:

1. **File watching:** none. A rewritten `.fzz` stays stale in an open window
   indefinitely (checked 20 s+). Source has no `QFileSystemWatcher`.
2. **File > Open (Cmd+O) of the already-open path:** no prompt, no reload, no
   error, nothing logged. It raises the existing stale window (`MainWindow::alreadyOpen`
   compares the path string).
3. **File > Revert:** exists, but is greyed out until the sketch has an undo
   entry (enabled = `undoStack->canUndo()`). After an edit it asks "Go ahead
   and revert?" (Yes is the default button). It then reloads the file from disk
   into a new window, external changes included.
4. **Most reliable:** don't have the file open while editing. Quit, write,
   relaunch:
   ```bash
   # graceful quit of ONE instance (no prompt when the sketch is unmodified)
   PID=$(pgrep -x Fritzing | head -1)
   osascript -e "tell application \"System Events\" to set frontmost of (first process whose unix id is $PID) to true" \
             -e 'delay 0.4' \
             -e "tell application \"System Events\" to tell (first process whose unix id is $PID) to keystroke \"q\" using command down"
   while kill -0 $PID 2>/dev/null; do sleep 0.3; done      # exits in <2 s

   python3 my_edit.py sketch.fzz                             # write the new file

   /Applications/Fritzing.app/Contents/MacOS/Fritzing "$PWD/sketch.fzz" --debug > /tmp/fritzing.log 2>&1 &
   # or: open -a Fritzing sketch.fzz
   # poll until the window exists (2–3 s cold start), then give it ~3 s to finish drawing
   until peekaboo list windows --pid $(pgrep -x Fritzing | head -1) 2>/dev/null | grep -q "sketch.fzz - Fritzing - \["; do sleep 0.5; done
   sleep 3
   ```
   - Force-quit: `kill <pid>` (SIGTERM) exits in ~1–2 s with no prompt, so
     unsaved changes are lost. `kill -9` as a last resort.
   - `osascript -e 'tell application id "org.fritzing.Fritzing" to quit'`
     returned error -128 "User canceled" and did not quit (seen once, with the
     simulator running). Use the Cmd+Q keystroke instead.
   - Quick alternative without quitting: `open -a Fritzing sketch.fzz` while it is
     already open creates a **second** window with the fresh disk contents
     (FileOpen event → `FApplication::loadNew`, which skips `alreadyOpen`). Close
     the older, stale window yourself.
   - **For docs, skip the GUI entirely:** `Fritzing -svg DIR` exports all views of
     every `.fzz` in DIR, then quits. Ratsnest lines, labels and property changes
     are rendered. Convert with `rsvg-convert -w 1200 -b white x_breadboard.svg -o x.png`.
5. **Inner name vs outer name:** irrelevant for loading (Section 1).
6. **Zip settings:** irrelevant (Section 1). Python `zipfile` round-trips cleanly.
7. **Minimum viable XML:** `<module fritzingVersion=…>` + `<instances>` with
   instances that each have `moduleIdRef` and one `<xView><geometry x y z/></xView>`.
   `<project_properties>`, `<boards>`, `<views>`, `path`, `modelIndex` and `<title>` are all
   optional. See Section 6 for what fails.

## 5. Worked examples (stdlib only)

The scripts live in `scripts/examples/` and use `scripts/fzz.py`. Run them with
`python3` (no uv environment needed). All three were run, exported with
`-svg` and inspected, and (c) was also opened in the GUI.

### a. New sketch: resistor plugged into a breadboard

```python
import sys, pathlib
sys.path.insert(0, "<repo>/.claude/skills/fritzing-format/scripts")   # your checkout's path
import fzz

root = fzz.new_sketch()
bb = fzz.add_part(root, "Breadboard-RSR03MB102-ModuleID", "Breadboard1", {"breadboardView": (0, 0)}, z=1.5)

hole_x, hole_y = fzz.connector_pos(bb, "breadboardView", "pin41I")
leg_dx, leg_dy = fzz.connector_offset("ResistorModuleID", "breadboardView", "connector0")
r1 = fzz.add_part(root, "ResistorModuleID", "R1",
                  {"breadboardView": (hole_x - leg_dx, hole_y - leg_dy),
                   "schematicView": (0, 200), "pcbView": (0, 0)},
                  props={"resistance": "1k"})

for rc, pin in (("connector0", "pin41I"), ("connector1", "pin45I")):   # 400 mil = 4 holes
    fzz.connect("breadboardView", fzz.end(r1, "breadboardView", rc), fzz.end(bb, "breadboardView", pin))

fzz.write_fzz("resistor_on_breadboard.fzz", root)
```

### b. Change a property and a wire colour in an existing sketch

```python
root, extras = fzz.read_fzz("in.fzz")          # extras = bundled fzp/svg/ino; pass them back
fzz.set_property(fzz.find_instance(root, title="R1"), "resistance", "10k")
fzz.find_instance(root, title="Wire1").find("views/breadboardView/wireExtras").set("color", "#cc1f1a")
fzz.write_fzz("out.fzz", root, extras)
```

No helper needed, plain stdlib:

```python
import zipfile, xml.etree.ElementTree as ET
with zipfile.ZipFile("in.fzz") as z:
    name = sorted(n for n in z.namelist() if n.endswith(".fz"))[0]
    root = ET.fromstring(z.read(name)); others = {n: z.read(n) for n in z.namelist() if n != name}
for inst in root.iter("instance"):
    if inst.findtext("title") == "R1":
        for p in inst.findall("property"):
            if p.get("name") == "resistance": p.set("value", "4.7k")
with zipfile.ZipFile("out.fzz", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("out.fz", ET.tostring(root, encoding="utf-8", xml_declaration=True))
    for n, d in others.items(): z.writestr(n, d)
```

The resistor's colour bands, the schematic label (`4.7kΩ`) and the Inspector
all follow the property. **[verified]**

### c. Add a wire between two existing connectors

```python
root, extras = fzz.read_fzz("resistor_on_breadboard.fzz")
bb = fzz.find_instance(root, title="Breadboard1")
fzz.add_wire(root, "breadboardView",
             fzz.end(bb, "breadboardView", "pin45J"),     # column 45 strip = R1.connector1
             fzz.end(bb, "breadboardView", "pin55J"),
             color="#22aa22")
fzz.write_fzz("with_wire.fzz", root, extras)
```

`add_wire` computes both endpoints, writes `x,y,x1=0,y1=0,x2,y2`, `wireFlags`
and `wireExtras` for the view, and links both ends in both directions. For a
schematic wire use `"schematicView"` (layer `schematicTrace`, flags 128). For a
PCB trace use `"pcbView"` (layer `copper1trace`, flags 4; untested).

Render to check: `mkdir out && cp *.fzz out/ && $FRITZING -svg out`.

## 6. Gotchas and troubleshooting

**Loud failures:** a modal dialog blocks the window, and Cmd+Q, until you dismiss
it. Automation sees no `<name>.fzz - Fritzing - [` window, only "Untitled Sketch".
All **[verified]**:
- XML not well-formed → "Parse error (1) at line N, column M". Nothing is loaded.
- No `<instances>` → "The file … is not a Fritzing file (3)".
- Unknown `moduleIdRef` → "Unable to find 1 part(s)" (Show Details lists the ids).
  The rest loads after OK **[source]**.
- Missing `fritzingVersion` → "The loaded sketch is missing its 'fritzingVersion' attribute".
- In automation, detect these by timing out on the window title, then screenshot
  the full screen. `kill <pid>` clears them.

**Silent problems:**
- Geometry ≠ connections (Section 2). Wires float or parts sit on holes without
  being connected, and nothing warns you.
- A part without a `<schematicView>`/`<pcbView>` element is simply absent from that tab.
- Hand-made parts without `<titleGeometry>` exported with no visible label in
  schematic SVG (example a). Add one or place labels in the GUI. **[verified, cause unconfirmed]**
- Duplicate `modelIndex` loads fine. Connections to it are ambiguous.
- Empty `property value=""` is ignored rather than clearing the value **[source]**.
- `ET.tostring` escapes `& < >` in text and attributes automatically. Never build
  XML by string concatenation, especially note `<text>`, which is escaped HTML.
- The zip isn't the problem: compression, member permissions (e.g. `0400` from a
  read-only unzip), a subfolder or an inner-name mismatch all load fine.

**Launching / automation:**
- `Fritzing --debug file.fzz` treats `file.fzz` as the debug log path and
  **overwrites your sketch with log text**. Always `Fritzing file.fzz --debug`.
- NEVER run `Fritzing -examples …`. It ignores the folder argument and
  re-saves every sketch bundled inside `/Applications/Fritzing.app` **[source]**.
- `-svg`, `-gerber`, `-all DIR` (gerber + BOM csv + IPC + SVGs) are batch
  services that exit when done. Only `-svg` is **[verified]**.
- Log noise: `module id … not found in database` lines at startup come from
  parts bins, not your sketch. `"finish up sketch loading"` marks the end of load.
- More than one Fritzing process (including one another agent session started)
  confuses peekaboo's focus checks and makes keystrokes land in the wrong app.
  Check `ps -axo pid,command | grep '[F]ritzing.app'` first. Target by PID
  (`peekaboo list windows --pid N`, `peekaboo image --pid N --window-id W`), never
  `pkill -x Fritzing` blindly, and keep one instance running.
- Fritzing's window list includes many `[Untitled]`/`Loading...` helper windows.
  Match the title `"<file>.fzz - Fritzing - ["`.
- `peekaboo image --mode screen` captures only the current Space. Per-window
  capture (`--window-id`) works even when Fritzing isn't visible.
- System Events: `click menu item "Save" of menu "File" of menu bar item "File" of menu bar 1`
  works only while the process is frontmost. Qt message-box buttons are not
  exposed (`click button "Yes"` fails), so press Return for the default button.
  A `peekaboo click` on the Revert dialog did not register.
- Keystrokes sent right after launch can land in the zoom-percentage field
  instead of the canvas. Click the canvas first, or use menu items.
- The macOS user may be working in another app. GUI automation steals focus, so
  prefer `-svg` export whenever a picture is all you need.

**Saving from Fritzing** (Cmd+S on a hand-made file) **[verified]**: keeps your
modelIndex values, titles, geometry and connections. It adds `icon=".png"`,
autoroute attributes on the pcb `<view>`, and self-closing tags, and renames the
inner `.fz` to match the file.

## 7. Source map (fritzing-app/src)

- Load: `mainwindow/mainwindow_menu.cpp` (`mainLoad`, `mainLoadAux`, `loadWhich`,
  `revert`/`revertAux`, `alreadyOpen`), `mainwindow/mainwindow.cpp`
  (`loadBundledSketch`), `model/modelbase.cpp` (`loadFromFile`, `loadInstances`),
  `sketch/sketchwidget.cpp` (`loadFromModelParts`: per-view geometry, wires, labels).
- Save: `model/modelpart.cpp` (`saveInstances`, `saveInstance`),
  `items/itembase.cpp` (`saveInstance`, `writeGeometry`), `items/wire.cpp`,
  `connectors/connectoritem.cpp` (`saveInstance`, `writeConnector`),
  `items/partlabel.cpp`, `items/note.cpp`, `utils/graphicsutils.cpp`
  (`saveTransform`), `mainwindow/mainwindow_menu.cpp` (views/boards/programs header),
  `model/modelbase.cpp` (`saveToZip`).
- CLI: `fapplication.cpp` (argument parsing, `FileOpen` event → `loadNew`,
  `runSvgService`, `runExampleService`); usage text in `main.cpp`.
- Wire flags: `viewgeometry.h`. There is also a `--ftesting` probe server
  (`src/testing`, `FProbeCurrentSketchXml` returns the live sketch XML) **[unverified]**.
