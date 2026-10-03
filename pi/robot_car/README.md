# robot_car — Pi drive code

Python for the car's Pi Zero 2 W: the two drive motors, and the Bluetooth LE
server the iPhone app ([ios/RobotRemote](../../ios/RobotRemote)) drives them
through. Wiring, pins and the DRV8833's control logic are in
[cad/robot_car/WIRING.md](../../cad/robot_car/WIRING.md).

| File | What it does |
|------|--------------|
| `drivetrain.py` | Pins, 2 kHz PWM, and the `Drivetrain` class: signed wheel speeds in, with a minimum-duty jump and a slew limit |
| `remote.py` | BLE GATT server: advertises as `RobotCar`, turns the phone's drive commands into wheel speeds, stops the car when they stop |
| `motor_test.py` | Bring-up script: each motor in turn, creep ramp, stall hold |
| `robot-car-remote@.service` | systemd unit that runs `remote.py` at boot |
| `test_remote.py` | Tests for the watchdog, the driver hand-over, the ramp and the duty mapping, on mock pins |

## The link

The phone writes a 3-byte command to the drive characteristic 20 times a
second, without response: a sequence number, then the left and right wheel
speeds as signed bytes, -100…100. It keeps sending zeros while the thumb is
off the stick, so the stream is also the heartbeat. The UUIDs live in
`remote.py` and in `DriveProtocol.swift` in
[shared/RobotLink](../../shared/RobotLink); change both together.

Only a bonded phone can drive: the drive characteristic needs a link that
was authenticated by passkey pairing, and BlueZ rejects writes over any
other link. One bonded phone drives at a time: the first to send a command
is the driver, and other devices' commands are ignored until the driver
disconnects or has been silent for 2 s.

### Pairing a phone

Once per phone. The Pi has no screen, so `remote.py` registers itself as
BlueZ's pairing agent and logs the passkey. Follow the log:

```bash
ssh robot-pi 'journalctl -u robot-car-remote@$USER -f'
```

then open the app near the car. iOS asks for a Bluetooth pairing code;
type the six digits from the `pairing dev_…: passkey 123456` line. The
dialog names the Pi by its Bluetooth name, which is its hostname. If you
cancel or mistype, the app shows "Couldn't pair" with a Try again button.
Pairing without a passkey (Just Works) is refused.

If the Pi loses its bonds (a new SD card, or `bluetoothctl remove`), the
phone's old bond no longer works: forget the Pi under Settings › Bluetooth
on the phone, then pair again.

The car stops by itself when the driver's commands stop for 300 ms, when the
driver disconnects, and when `remote.py` exits. The 300 ms watchdog does the
real work. BLE retransmits until a packet gets through, so a failing link
shows up as commands arriving late, and BlueZ reports the disconnect
anywhere from a fraction of a second to about 5 s after the phone is gone.
If `remote.py` itself stalls, systemd's watchdog kills it (below).

## Setup on the Pi

`remote.py` needs `bluez-peripheral` on top of the system's `gpiozero` and
`lgpio`. It lives in a venv that can see the system packages:

```bash
ssh robot-pi 'cd robot_car && python3 -m venv --system-site-packages .venv && .venv/bin/pip install bluez-peripheral'
```

No root is needed: BlueZ's D-Bus policy lets any user register a GATT
service and an advert, and the Pi user is in the `gpio` group.

## Running at boot

`robot-car-remote@.service` runs `remote.py` as the Pi user named after the
`@`. It hangs off `bluetooth.service` rather than the network: it starts as
soon as bluetoothd does, and stops and restarts with it, since a restarted
bluetoothd forgets the GATT service and the advert. It unblocks Bluetooth
first (Raspberry Pi OS can boot with it soft-blocked), `remote.py` waits for
the adapter to power up, and `Restart=always` never gives up.

`remote.py` pings systemd's watchdog from the same 50 Hz tick that runs the
motor watchdog. If that loop stalls for a second, systemd kills the process,
and after any exit, clean or not, `ExecStopPost` runs `motor_test.py --check`
to claim the four motor pins low. If BlueZ drops the advert or the adapter
goes away, `remote.py` exits with status 1 so systemd restarts it and it
registers again.

Install the unit with sudo, and again whenever it changes:

```bash
ssh -t robot-pi 'sudo cp robot_car/robot-car-remote@.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now robot-car-remote@$USER'
```

From the kernel starting, bluetoothd starts at about 19 s, the car advertises
at 22 s and an open app connects at 24 s, ahead of the network and SSH. Most
of the wait before bluetoothd is cloud-init (about 5 s), which the Pi only
needs on its first boot.

`journalctl -u robot-car-remote@$USER -f` on the Pi follows the log. It
logs connections, the driver, and every stop with the speed it stopped from.
While the car moves, or when commands arrive late or ticks are skipped, it
also prints a line a second: the rate, the longest gap between commands, how
many ticks the phone skipped, and the target and actual wheel speeds. On the
bench, 20 commands a second arrive with gaps of 60–120 ms.

The service holds the motor pins, so stop it (`sudo systemctl stop
robot-car-remote@$USER`) before running `motor_test.py` or `remote.py` by
hand, and start it again afterwards.

## Deploy

The scripts import each other, so copy the folder rather than one file. Give
remote paths relative to the Pi's home; a bare `~` is expanded by the Mac's
shell first. The running service keeps the old code until it restarts.

```bash
tar cf - -C pi/robot_car drivetrain.py remote.py motor_test.py test_remote.py robot-car-remote@.service | ssh robot-pi 'mkdir -p robot_car && tar xf - -C robot_car'
```

`remote.py --dry-run` serves the same link with the motor pins mocked, for
testing the phone side with the service stopped. It runs the real
`Drivetrain`, so the log shows the same ramp the car would follow.

## Tests

`test_remote.py` covers the car's logic without a Bluetooth stack, on
gpiozero's mock pins, so it runs on the Mac:

```bash
cd pi/robot_car && uv run --no-project --with gpiozero --with bluez-peripheral python -m unittest -v test_remote
```
