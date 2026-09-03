# robot_car — drivetrain wiring

How the prototype's electronics hang together: B2 LiPo → two P1 bucks → C1
(Pi Zero 2 W) for logic and D2 (DRV8833) for power, driving two M2 N20
gearmotors. Part IDs are the ones in `parts/index.html`.

Nothing here has been powered up yet — D2, M2, P1 and B2 are all still
`untested` in the parts library, and C1 is `verify`. Treat this as the plan to
bring up, in the order given under [Bring-up](#bring-up), not as a tested
circuit.

## What the D2 pins actually are

D2 is a DRV8833 breakout: 12 pins in two 6-pin rows, silkscreened on the face
*opposite* the chip. The board is a thin wrapper around the IC — every pin goes
more or less straight to a chip pin, so the datasheet (TI SLVSAR1E) is the real
reference.

| D2 pin | DRV8833 pin | What it is |
| --- | --- | --- |
| `VCC` | VM | Single supply: motor rail *and* chip supply. 2.7–10.8 V |
| `GND` | GND | Ground, shared with the Pi |
| `IN1` / `IN2` | AIN1 / AIN2 | Logic inputs for bridge A |
| `OUT1` / `OUT2` | AOUT1 / AOUT2 | Bridge A outputs → motor A |
| `IN3` / `IN4` | BIN1 / BIN2 | Logic inputs for bridge B |
| `OUT3` / `OUT4` | BOUT1 / BOUT2 | Bridge B outputs → motor B |
| `ULT` / `EEP` | nFAULT / nSLEEP — **or the other way round** | See below |

`ULT` and `EEP` read like silkscreen with the first letters clipped off:
(FA)`ULT` = nFAULT, (SL)`EEP` = nSLEEP. Two things support that reading: the
`en` / `sleep` solder jumpers sit right next to the `EEP` pin, which is where
you'd put a default-state selector for nSLEEP; and the front side carries a
`473` (47 kΩ) resistor, which is exactly the 20–75 kΩ nSLEEP pull-up TI asks
for in §7.3.4. The seller's listing says the opposite (`ULT` = sleep select,
`EEP` = "output protection"), so this is not settled — see
[Open questions](#open-questions) for the meter test that settles it.

It doesn't block the first build: the `en` jumper is bridged from the factory,
which is what leaves the chip awake, and neither pin needs a wire for basic
two-motor drive.

Board features worth knowing, from the back-side photo
(`parts/photos/d2-drv8833-back.jpg`):

- `en` solder jumper: **bridged** (factory default). `sleep` jumper: open.
  `J1`, a 2-pad SMD footprint next to `EEP`, is unpopulated.
- The 12 header holes are bare — the two 6-pin strips still need soldering.
- No current-sense resistors on the board, so AISEN/BISEN are grounded and
  the chip's PWM current chopping is unused. The only current limit is
  overcurrent protection at 2–3.3 A, which the M2 motors (0.2 A stall) will
  never reach.

## Connections

```
                B2 2S LiPo 7.4 V  (XT60)
                  +                      -
                  |                      |
        +---------+----------+           |
        |                    |           |
   +----+-----+        +-----+----+      |
   | P1 buck 1|        | P1 buck 2|      |
   |  5.1 V   |        |  6.0 V   |      |
   +--+----+--+        +--+----+--+      |
      |    |              |    |         |
    5V1  GND1           VCC2  GND2       |
      |    +---------------+----+--------+---- one common ground
      |                    |                   (star at the pack minus)
      |                    |
 C1 Pi Zero 2 W       D2 DRV8833            M2 N20 gearmotors
 ┌──────────────┐     ┌──────────┐
 │ hdr 2   5V   │◄────┤          │
 │ hdr 6   GND  │     │ VCC  GND │
 │              │     │          │
 │ hdr 32 GPIO12├────►│ IN1 OUT1 ├───────────► left  (+)
 │ hdr 33 GPIO13├────►│ IN2 OUT2 ├───────────► left  (−)
 │ hdr 35 GPIO19├────►│ IN3 OUT3 ├───────────► right (+)
 │ hdr 36 GPIO16├────►│ IN4 OUT4 ├───────────► right (−)
 │ hdr 34 GND   ├─────┤ GND      │
 └──────────────┘     └──────────┘
```

### Pi Zero 2 W → D2 (5 wires)

| Pi header pin | BCM | D2 pin | Note |
| --- | --- | --- | --- |
| 32 | GPIO12 | `IN1` | left motor, forward |
| 33 | GPIO13 | `IN2` | left motor, reverse |
| 35 | GPIO19 | `IN3` | right motor, forward |
| 36 | GPIO16 | `IN4` | right motor, reverse |
| 34 | — | `GND` | signal ground; **not optional** |

Why these four GPIOs: they sit in one block at the far end of the header (one
5-wire ribbon, no fan-out), none of them has a competing default function
(I²C on GPIO2/3 is left free for the S1 rangefinder later, UART on GPIO14/15
for the console, SPI on GPIO7–11), and — the reason that matters — every GPIO
from 9 up idles with an internal *pull-down* at boot. GPIO0–8 idle pulled
*high*, which against the DRV8833's 150 kΩ input pull-downs would put ~2.5 V
on an input: above the 2 V VIH, i.e. a motor twitching before Linux has
even booted. Don't move the inputs onto those.

The Pi's 3.3 V logic is enough on its own: VIH is 2 V on the IN pins (2.5 V on
nSLEEP), and the inputs are rated to 7 V absolute max, so no level shifting and
no series resistors are needed. Every unconnected input pulls itself low
(150 kΩ internal, 500 kΩ on nSLEEP), so anything you leave floating reads as
"off".

#### Finding those pins on the board

From the top-face photo (`parts/photos/c1-pi-zero-2w-top.jpg`): the 40-pin
header is **already populated** — ten 4-way plastic blocks in one strip,
2 × 20 on 2.54 mm pitch — so unlike D2, the Pi end needs no soldering. What
the photo can't tell you is whether those are female sockets or male pins
soldered pointing down; from straight above both look like black wells with a
recessed contact. Look at the board edge-on before ordering jumper wires:
male-ended leads go into sockets, female-ended leads onto pins.

Orientation, then, with the header along the far edge and the connector edge
(mini-HDMI, `USB`, `PWR IN`) toward you:

- Header **pin 1 is at the microSD end** — the left end in that view. Pins
  32–36 are at the other end, beside the CSI camera connector and roughly
  above the `PWR IN` jack.
- The 5 V and GND pins that feed the Pi (2, 4, 6) are at the *pin-1* end, i.e.
  the opposite end of the header from the driver ribbon. Buck feed in at one
  end, signals out at the other; plan the cable runs that way rather than
  bundling them.
- Confirm the numbering with a meter before the first wire, because which of
  the two rows carries the odd numbers is easy to get backwards. Continuity
  from a header pin to a micro-USB shell finds the grounds — pins 6, 9, 14,
  20, 25, 30, 34, 39. At the far end from the SD card, the last pair is 39
  (GND) and 40 (GPIO21): the one that beeps is 39, and that fixes both rows.
  Pin 34, the ground for our ribbon, is then three pairs back along the even
  row (40, 38, 36, 34) — and it should beep too.

### D2 → M2 motors (4 wires)

| D2 pin | Motor |
| --- | --- |
| `OUT1` | left motor tab (+) |
| `OUT2` | left motor tab (−) |
| `OUT3` | right motor tab (+) |
| `OUT4` | right motor tab (−) |

The (+)/(−) marks on the N20 can only fix which way "forward" comes out; they
carry no polarity requirement, so if a wheel turns the wrong way, swap the pair
in software rather than resoldering. `chassis.py` mirrors the motor cradle for
±Y, so the two motors point in opposite directions and one side's sense is
inverted by construction — handle that in the motor object, not at the
terminals.

Solder a 100 nF ceramic across each motor's two tabs, as close to the can as
you can get it, and twist each motor pair. Brushed motors are broadband noise
sources and the Pi's WiFi and microSD are both nearby.

### Power

| From | To | Value |
| --- | --- | --- |
| B2 XT60 (+) | both P1 `IN+` | 7.4 V nominal, 8.4 V full |
| B2 XT60 (−) | both P1 `IN−` | star point for all grounds |
| P1 #1 `OUT+` | Pi header pin 2 (or 4) | set to 5.1 V |
| P1 #1 `OUT−` | Pi header pin 6 | |
| P1 #2 `OUT+` | D2 `VCC` | set to 6.0 V |
| P1 #2 `OUT−` | D2 `GND` | |

Two bucks rather than one shared 5 V rail: a stalling motor drags its rail
down, and the thing on the other end of a shared rail would be the Pi's SD
card. We have five P1s; separating the rails is cheaper than a corrupted card.
(One buck plus a fat bulk cap does work — it's just the variant to fall back
to, not the one to start with.)

Why 6.0 V on the driver, and why not the raw pack:

- The M2 motors are the 6 V/1:100 variant, so a 6.0 V rail makes PWM duty map
  straight onto rated voltage — 100% duty is rated speed, nothing to
  remember. Raw 2S would be 8.4 V on a 6 V motor, correct only while you
  remember to cap duty at ~70%.
- 6.0 V also keeps every pin on the chip inside spec whatever the `en`
  jumper turns out to tie nSLEEP to. If it's a hard tie to VM (rather than
  through the 47 kΩ), nSLEEP sits at the rail: fine at 6.0 V (7 V absolute
  max, internal 6.5 V clamp), not fine at 8.4 V. Until the meter says
  otherwise, **keep `VCC` at or below 6.5 V**.
- Bridge drop is irrelevant at these currents: 360 mΩ HS+LS × 0.04 A running
  is 14 mV, and 72 mV at the 0.2 A stall. No need to over-volt to compensate.

Add a 100–220 µF electrolytic (≥16 V) across D2's `VCC`/`GND` if the wires
back to the buck are longer than a few centimetres — the board's own 10 µF
ceramic covers the chip, not the wiring inductance (§9.1).

Set both trimpots and measure the output with a meter **before** either board
is connected. The P1 ships at an arbitrary trimpot position, and the Pi's 5 V
header pins go straight to the SoC's regulators with no input protection.

`EEP` and `ULT` need no wires. Once you know which is nFAULT, a 10 kΩ pull-up
to the Pi's *3.3 V* (pin 1 or 17) plus a spare GPIO gets you fault reporting —
it's open-drain, low on overcurrent or thermal shutdown, and it retries by
itself every 1.35 ms while the fault lasts.

## Control logic

Per bridge, from the datasheet's Table 1 and Table 2:

| IN1 | IN2 | OUT1 | OUT2 | Result |
| --- | --- | --- | --- | --- |
| 0 | 0 | Z | Z | coast (free-wheel) |
| 1 | 0 | H | L | forward, full speed |
| 0 | 1 | L | H | reverse, full speed |
| 1 | 1 | L | L | brake (both outputs shorted low) |

For speed control you PWM one input and hold the other:

| IN1 | IN2 | Result |
| --- | --- | --- |
| PWM | 0 | forward, fast decay (coasts between pulses) |
| 1 | PWM | forward, slow decay (brakes between pulses) |
| 0 | PWM | reverse, fast decay |
| PWM | 1 | reverse, slow decay |

Fast decay is the simpler scheme and what `gpiozero`'s `Motor` does: PWM the
"forward" pin, hold "backward" low. Slow decay gives a more linear
duty→speed curve at low duty, at the cost of inverted logic (duty *D* forward
means driving the PWM pin at 1−*D*). Start with fast decay; only reach for
slow decay if the motors won't creep smoothly.

No maximum input PWM frequency is specified, but the input deglitch is 450 ns
and INx→OUTx propagation is 1.1 µs, so keep the period well clear of those:
2 kHz is a good starting point, and gives 100 duty steps under pigpio's
default 5 µs sampling.

Software PWM on the Pi is fine here — these are brushed gearmotors, not a
servo loop. `pigpio`'s DMA-timed PWM works on any pin:

```python
import pigpio

pi = pigpio.pi()
LEFT = (12, 13)   # (forward, reverse) → IN1, IN2
RIGHT = (19, 16)  # → IN3, IN4

for gpio in LEFT + RIGHT:
    pi.set_mode(gpio, pigpio.OUTPUT)
    pi.set_PWM_frequency(gpio, 2000)
    pi.set_PWM_range(gpio, 100)      # duty in percent

def drive(motor, percent):           # -100..100, fast decay
    fwd, rev = motor if percent >= 0 else motor[::-1]
    pi.set_PWM_dutycycle(rev, 0)
    pi.set_PWM_dutycycle(fwd, min(abs(percent), 100))
```

The Pi's two hardware PWM channels are not worth chasing: PWM0 is GPIO12
*and* GPIO18, PWM1 is GPIO13 *and* GPIO19, so keeping one independent channel
per motor across both directions forces the pairs to be
(GPIO12, GPIO18) and (GPIO13, GPIO19) — and then the pin that carries PWM
changes with direction, which means re-muxing a pin between PWM and plain
output on every reversal. DMA-timed software PWM avoids the whole problem.

## Bring-up

In this order. Steps 1–4 need no battery.

1. **Solder D2's headers.** Two 6-pin strips. Check for bridges under
   magnification — the pitch is 2.54 mm but the pads are close to the
   silkscreen.
2. **Meter the unpowered board** (see [Open questions](#open-questions)):
   `EEP`→`VCC`, `ULT`→`VCC`, and each of `IN1`–`IN4`→`GND`. The IN pins
   should read around 150 kΩ. Write the numbers into `parts/d2.html`.
3. **Bench supply, no motor.** 6.0 V into `VCC`/`GND`, current limit at
   100 mA. Quiescent draw should be ~2 mA (1.7 mA typical). Nothing hot.
4. **Bench supply, one motor on OUT1/OUT2.** Jumper `IN1` to 3.3 V (or to
   `VCC` through 10 kΩ if you have no 3.3 V handy) with `IN2` open: the motor
   should run. Swap to `IN2`: it should run the other way. Both inputs high:
   it should brake. Repeat on `IN3`/`IN4` with `OUT3`/`OUT4`. This is the
   step that confirms the `en` jumper really does leave the chip awake.
5. **Pi first, motors on the bench supply.** Pi on its normal USB power (the
   jack silkscreened `PWR IN`, not the `USB` one next to it), D2
   on the bench supply, grounds tied together, `IN1`–`IN4` on the four GPIOs.
   Run the snippet above. Check both wheels for direction and creep
   threshold before either buck is in the picture.
6. **Set the bucks.** Both P1s fed from the pack, outputs unloaded, meter
   on the output pads: #1 to 5.1 V, #2 to 6.0 V. Leave them a minute and
   re-check — the trimpots are multi-turn and easy to nudge.
7. **Battery power.** Buck #2 to the driver first, motors running from it,
   then buck #1 to the Pi. Watch the pack voltage under a stall; the 2S pack
   must not go below 6.4 V.

Only after step 7 does D2 move from `untested` to `ok` in
`parts/index.html`.

## Open questions

- **Which of `EEP`/`ULT` is nSLEEP?** With the board unpowered, measure each
  to `VCC`. ~47 kΩ (or ~0 Ω) on one of them and open on the other identifies
  the sleep pin — the `en` jumper is bridged, so nSLEEP is tied to the rail
  one way or the other, while nFAULT is open-drain and connects to nothing
  but the chip. A 47 kΩ reading is the good outcome (TI's recommended
  20–75 kΩ pull-up, current-limited into the pin's 6.5 V clamp); ~0 Ω means
  a hard tie, and then `VCC` above 6.5 V would push current through that
  clamp — over 250 µA damages the input.
- **A hardware kill switch**, if we want one, means opening the `en` jumper
  and driving nSLEEP from a fifth GPIO instead. Worth doing once the pin is
  identified: nSLEEP low disables both bridges and resets the chip's logic,
  and it needs up to 1 ms after release before the bridges come back.
- **What `J1` is for.** Unpopulated 2-pad footprint next to `EEP`; likely the
  alternative to the `en` jumper (a pull-up resistor position). Cosmetic
  until we care.
- **The green part with the `472` resistor** on the front looks like a power
  LED and its 4.7 kΩ series resistor. Untested; if it lights when `VCC` comes
  up in step 3, that's confirmation and a free supply indicator.
- **Low-voltage cutoff.** Nothing here watches the pack. The Pi can't read an
  analog voltage without help, so this needs either a divider into an ADC or
  a standalone LiPo alarm on the balance lead. Open design item, tracked on
  `parts/b2.html`.

## References

- TI DRV8833 datasheet, SLVSAR1E (July 2015): §6.1/6.3 ratings, §6.5
  electrical characteristics, §7.3.2 bridge control and decay modes, §7.3.4
  nSLEEP, §7.3.5 protection, §9.1 bulk capacitance, §9.2 sequencing.
- `parts/d2.html`, `parts/c1.html`, `parts/m2.html`, `parts/p1.html`,
  `parts/b2.html` — the part-level notes and their own to-verify lists.
- `cad/parts/d2_drv8833.py`, `cad/parts/pi_zero_2w.py`,
  `cad/parts/n20_motor.py` — CAD reference models, for where these boards
  physically sit in the chassis.
