# robot_car — design overview

A small two-wheel robot car: two N20 gearmotors drive O-ring-tyred wheels at
the rear corners, a bought swivel caster carries the front, and a Raspberry
Pi Zero 2 W drives the motors through a DRV8833, all on one 3D-printed plate
powered by a 2S LiPo. The current design is **PROTO-05**, the text engraved
on the plate's underside.

This page is the map. It says what the car is made of, which script owns
each part, what has been settled on the printer, and where the details
live. The scripts are the source of truth for every dimension. Where a
number appears here, the field that owns it is named next to it, and the
field wins if they ever disagree.

## Bought parts on the car

IDs and status come from the parts library, [parts/index.html](../../parts/index.html).

| ID | Part | On the car | Status |
|----|------|------------|--------|
| M2 | N20 micro gearmotor, 6 V 1:100 | two, rear corners | ok |
| D2 | DRV8833 dual H-bridge module | one, rear left | ok |
| C1 | Raspberry Pi Zero 2 W | one, front | ok |
| P1 | MP1584EN buck converter | two: 5.1 V for the Pi, 6.0 V for the motor driver | ok |
| B2 | 2S LiPo 7.4 V 2200 mAh, XT60 | one, centre | ok |
| — | KCD1-style mini rocker switch, 3 bent terminals ([kcd1_rocker.py](../parts/kcd1_rocker.py)) | one, left, between the motor and the motor buck | not yet in the parts library |
| — | Swivel caster: 40.2 mm square steel plate, Ø24.7 wheel, 34 mm tall ([swivel_caster.py](../parts/swivel_caster.py)) | one, front, under the Pi | not yet in the parts library |

Two O-rings, OD 60 / ID 40 with a 10 mm cord, serve as tyres. They came off
an old wooden toy wheel, and the printed wheel copies that wheel's groove.

## Printed parts

| Part | Qty | Made by | Notes |
|------|-----|---------|-------|
| Chassis plate | 1 | [chassis.py](chassis.py) | about 139 x 94 x 3 mm (the nose is the caster pocket's mouth, `ChassisDims.nose_x`), prints flat, no supports |
| Motor lid | 2 | [chassis.py](chassis.py), exports `motor_lid.stl` | geometry from [lid_coupons.py](lid_coupons.py) |
| Skid | 1 | [chassis.py](chassis.py), exports `skid.stl` | fits the rear hole; not needed with the caster. Print it as its own job, with a brim |
| Drive wheel | 2 | [wheel.py](wheel.py) | spoked web outboard, hub reaches in to the shaft |
| Stand-in dummies | as needed | [dummies.py](dummies.py) | white stand-ins for motors and boards, for dry fits |

The chassis docstring is the full design description: layout, the rules
behind each position, and how the board trays work. Read it before moving
anything on the plate.

## How it holds together

- **Motors** sit in rigid U-channel cradles at the rear, output shafts out
  past the plate edge. The gearbox face lands on an end wall at the edge.
  A separate lid slides on from the inboard side along dovetail rails on
  the outside of the cradle walls, clicks into a detent, and clamps the
  motor down with a pad on its top. The lid stops short of the can's rear
  face, so the solder tabs and wires stay free.
- **Wheels** press onto the motors' D-shaft. The O-ring sits in a round
  groove, seated relaxed, and needs only a short stretch over the shoulder
  to install.
- **Boards** (DRV8833 and both bucks) stand 7 mm off the plate on one
  tray design: tuck a long edge under two fixed tongues, rotate down, and
  a preloaded latch on the other long edge clicks over, so the board cannot
  rattle. Nothing reaches over the short ends, where every board carries
  its headers. The bucks ride components down.
- **Switch** snaps into a raised panel on two end walls
  ([switch_well.py](switch_well.py)). Its terminals come bent over, so it
  goes in held toward the motor, slides forward once the bent legs are
  under the panel, and presses down until the clips catch.
- **Pi** screws onto four bosses with self-tapping M2.5 screws.
- **Battery** sits between four corner guides and is held by one
  hook-and-loop strap through a pair of slots.
- **Caster** slides in from the nose, fork turned so the wheel trails
  forward, until its plate meets the stop. Ledges in the plate's bottom
  layers carry it when the car is lifted, and the car's weight presses its
  plate up against two lips beside the slot. The fit alone holds it, no
  bolts ([caster_mount_coupons.py](caster_mount_coupons.py)). The caster is
  taller than the space under the plate, so it lifts the nose.
- **Skid** push-snaps up from underneath through the hole at the rear. The
  car runs without it now that the caster carries the front.

### Assembly order

The motor lids slide on across the battery bay, so **fit the motors and
their lids before the battery**, and take the battery out before removing a
motor. Nothing else on the car depends on order.

## Settled fits

Each of these was chosen by printing a coupon with several variants on the
X2D and testing it by hand. Re-test if the printer, filament or nozzle
changes.

| Fit | Value | Owned by | Coupon | Result |
|-----|-------|----------|--------|--------|
| Motor lid on its rails | 0.10 mm clearance on every dovetail face | `ChassisDims.lid_rail_clearance` | [lid_coupons.py](lid_coupons.py), round 1 | 0.10 fit best of 0.10 / 0.20 / 0.30 |
| Lid pad on the motor | 0.30 mm preload | `ChassisDims.lid_pad_preload` | [lid_coupons.py](lid_coupons.py), round 2 (lid E) | holds the motor; 0.40 and 0.50 would not slide on |
| Wheel bore on the N20 shaft | 0.10 mm radial | `WheelDims.bore_clearance` | [bore_coupons.py](bore_coupons.py), station B3 | firm push-on, no play; 0.15 and 0.20 dropped on loose |
| DRV8833 in its tray | 0.05 mm end fit, 0.30 mm latch preload | `ChassisDims.drv_end_fit`, `drv_latch_preload` | [drv_coupons.py](drv_coupons.py), coupon C | no wiggle, still pops out by hand |
| MP1584 in its tray | 0.15 mm end fit (latch as the DRV8833's) | `ChassisDims.buck_end_fit` | [buck_coupons.py](buck_coupons.py), coupon N | sits flat, holds well; 0.05 was tight |
| Switch in its well | 3.0 mm panel under the flange | `WellDims.panel_t` | [switch_well.py](switch_well.py), coupon C | best of 2.0 / 2.5 / 3.0 |
| O-ring groove | copy of the ring's wooden wheel: root Ø39, shoulder Ø46 | root: `WheelDims.oring_id` x `STRETCH` (wheel.py); shoulder: root + 2 x `WheelDims.groove_depth_factor` x cord | printed wheels P7 and P8 | rings mount by hand and stay seated; the coupon rounds before it were too tight to mount |
| Caster plate in its pocket | slot 1.8 over the 1.5 plate, 0.20 mm per side, 2.0 mm lands | `MountDims.slot_h`, `side_fit`, `lip_land` | [caster_mount_coupons.py](caster_mount_coupons.py), coupon J | slides in by hand and stays put; 0.10 per side was snug, zero spread the walls |
| Running fit, general | 0.2 mm radial | project-wide | `demo_04` fit test | moves freely; use for anything that turns |

## Checks to run before printing

```bash
uv run robot_car/chassis.py
```

Builds the plate, lids and skid, then checks every pair of parts on the
plate for overlap on the real geometry and confirms the plate is one solid.
The only allowed overlap is each lid's pad pressing on its motor, which is
checked against a range. It also checks the caster pocket: it matches the
coupon that fit, and the caster slides in, sits, and swivels a full turn
clear of the plate.

```bash
uv run robot_car/assembly.py
```

Places everything on the car, wheels, caster and electronics included, and
runs the full-car PASS/FAIL table. It reports how far the caster lifts the
nose and the drive-wheel size that would level it.

```bash
uv run robot_car/lid_coupons.py
```

Checks the lid on its own: it clears the cradle all along the slide,
touches the motor only through its pad, and its detent rides only on the
rails.

```bash
uv run robot_car/switch_well.py
```

Checks the switch in its well and searches for a way to put it in past the
panel, the cradle and the motor buck, with room left to solder the
terminals.

```bash
uv run robot_car/caster_mount_coupons.py
```

Builds the caster pocket's fit coupons and checks the caster in each: its
clearances, the bearing ring clear of the ledges, sliding out of the mouth,
and swivelling a full turn. Writes `caster_mount_render.png`.

Then look at the result before slicing. [render_assembly.py](render_assembly.py)
draws a colour-coded plan and elevations, and [twin.py](twin.py) writes a
USDZ of the whole car that macOS Quick Look opens.

## How the design got here

- **PROTO-01** (built as `cad/demo_06`) was 80 mm wide. The battery landed
  on the motor cans, the board trays' rigid corner hooks could not be
  assembled, and the underside label was unreadable.
- **PROTO-02** widened the plate to 94 mm, moved the boards to
  tilt-and-slide trays and fixed the strap slots and label. In use the
  motors popped out of their snap-lip cradles, and the DRV8833 wiggled in
  its tray.
- **PROTO-03** replaced the snap lips with the slide-on lids, moving the
  motors 4 mm forward so the lids clear the driver tray. It gave the
  DRV8833 its own preloaded tray, and added a second buck so the Pi and the
  motors have separate supplies.
- **PROTO-04** added the power switch well. The bucks' old tray had a
  fragile latch and corner posts that fought the headers soldered onto
  every corner, so all three boards now share the DRV8833's tray, and the
  bucks moved forward to make room for the switch.
- **Caster, first iteration** replaces the front skid with a Ø40 swivel
  caster on a 10 mm trail, on a nose arm that snaps into the front skid
  hole, so it fits PROTO-04 as printed. In use the arm wobbles on its
  single rivet and lets the nose sag, and the pivot has so much friction
  that the wheel doesn't turn to follow the car. It drags like the skid.
- **PROTO-05** takes a bought swivel caster in place of the skid and the
  printed caster. Its plate slides into a pocket in the chassis underside,
  under the Pi. The pocket can't reach back past the battery's guide nubs,
  so the plate grew 9.3 mm forward. Three coupon rounds settled it: a roof
  bridged over the slot sagged into it and jammed the plate, a lip across
  the back sagged into spaghetti, and a slot drawn at the plate's nominal
  40.0 bound once the plate measured 40.2. On the printed plate the caster
  slides in by hand and stays put.

The commit messages for each step carry the measurements behind them.

## Where the details live

- [chassis.py](chassis.py) docstring: plate layout, design rules, board trays.
- [wheel.py](wheel.py) docstring: wheel, groove and bore.
- [WIRING.md](WIRING.md): power tree, every connection, control logic,
  bring-up order and open electrical questions.
- [pi/robot_car/](../../pi/robot_car/): the Pi's drive code: the motors,
  the Bluetooth LE server the phone drives them through, and the
  `motor_test.py` bring-up script.
- [ios/RobotRemote/](../../ios/RobotRemote/): the iPhone app that drives the
  car, one thumb on a floating stick.
- [parts/index.html](../../parts/index.html): the bought parts, with photos,
  datasheets and test status.
- [../README.md](../README.md): the slice, verify and print pipeline.

## Open items

- The electrical open questions are listed in [WIRING.md](WIRING.md#open-questions),
  including a low-voltage cutoff for the pack.
- The 2 A fuse: the harness carries a 10 A until one is on hand, so the car
  runs only while someone is watching.
- WIRING.md bring-up step 7 still needs its stall checks: pack voltage and
  the Pi–D2 ground offset with both motors held.
- Drive wheels: the caster lifts the nose about 10.5 mm on the Ø59
  wheels, a tilt of about 8 deg driving forward (the caster trails behind
  its swivel) and 6 deg in reverse. Wheels of about Ø80 would level the
  car (assembly.py, check 1). Bigger wheels need new tyres: the O-rings fit only the Ø59
  groove.
