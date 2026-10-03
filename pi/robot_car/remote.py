#!/usr/bin/env python3
"""Bluetooth LE remote control for robot_car: the iPhone app drives the wheels.

The Pi advertises as "RobotCar" with one GATT service, SERVICE_UUID. The
phone app (ios/RobotRemote) writes 3 bytes to the drive characteristic
about 20 times a second, without response: a sequence number, then the left
and right wheel speeds as signed bytes, -100..100. It keeps sending while
connected, zeros included, so the stream doubles as a heartbeat.

Only a bonded phone can drive. The drive characteristic needs an
authenticated, encrypted link, so BlueZ rejects writes from anything that
hasn't paired with the passkey. The Pi has no screen, so the pairing agent
logs that passkey ("pairing dev_..: passkey 123456") for the user to type
on the phone, once per phone. The app's first write on each connection goes
with response, which is what makes iOS pair, or re-encrypt with its bond,
before the 20 Hz stream starts.

One phone drives at a time. The first bonded device to write a command
becomes the driver, and commands from any other device are ignored until
the driver disconnects or has been silent for HANDOVER_S.

The car stops by itself:

- when no command has arrived from the driver for WATCHDOG_S. BLE
  retransmits until a packet gets through, so a fading link shows up as
  commands arriving late, and the disconnect can be reported anywhere from
  a fraction of a second to about 5 s later. The watchdog is what stops a
  car that lost its phone;
- when the driver disconnects;
- when this process stalls: under systemd it pings the service watchdog
  from the same tick that runs the motor watchdog, so a stalled loop gets
  killed and the unit's ExecStopPost drives the motor pins low;
- on SIGTERM, SIGHUP or SIGINT, and on any other exit.

If BlueZ drops the advert or the adapter goes away (a controller reset, a
power-off, bluetoothd restarting), the car can no longer be found, so this
exits with status 1 for systemd to restart it.

    remote.py             serve until stopped
    remote.py --dry-run   the same, with the motor pins mocked

Run it with the venv's Python (~/robot_car/.venv, see README.md), which adds
bluez-peripheral to the system's gpiozero and lgpio.
"""

import argparse
import asyncio
import logging
import os
import signal
import socket
import struct
import sys
import time

from bluez_peripheral.agent import AgentCapability, BaseAgent
from bluez_peripheral.gatt.characteristic import CharacteristicFlags, characteristic
from bluez_peripheral.gatt.service import Service
from bluez_peripheral.util import Adapter, get_message_bus
from dbus_next import Message, MessageType
from dbus_next.constants import PropertyAccess
from dbus_next.errors import DBusError, InterfaceNotFoundError
from dbus_next.service import ServiceInterface, dbus_property, method

NAME = "RobotCar"
SERVICE_UUID = "0bf63e73-edac-4f6d-b68e-d6b8f42e2e47"
DRIVE_UUID = "93f818be-a53d-4aeb-b292-bf122d178473"
WATCHDOG_S = 0.3
HANDOVER_S = 2.0
TICK_S = 0.02
# A report line goes out while the car moves, or when the link degrades.
SLOW_GAP_S = 0.15
ADAPTER = "/org/bluez/hci0"

log = logging.getLogger("remote")
STOP = {"left": 0.0, "right": 0.0}


def device_name(path):
    return path.rsplit("/", 1)[-1] if path else "?"


class Car:
    """The phone's commands applied to the drivetrain, and the watchdog.

    Everything takes `now` from the caller, so the logic runs in tests
    without a clock or a Bluetooth stack.
    """

    def __init__(self, drivetrain):
        self.drivetrain = drivetrain
        self.target = dict(STOP)
        self.driver = None
        self.last_rx = None
        self.seq = None
        self.quiet = True
        self.ignored = set()
        self._reset_stats()

    def command(self, data, device, now):
        """One drive write from `device`."""
        if len(data) != 3:
            log.warning("ignored a %d-byte drive write from %s", len(data), device_name(device))
            return
        if self.driver is None:
            self.driver = device
            self.ignored.clear()
            log.info("driver: %s", device_name(device))
        elif device != self.driver:
            if device not in self.ignored:
                self.ignored.add(device)
                log.info("ignoring %s: %s is driving", device_name(device), device_name(self.driver))
            return
        seq, left, right = struct.unpack("Bbb", bytes(data))
        if not self.quiet:
            self.max_gap = max(self.max_gap, now - self.last_rx)
            self.skipped += (seq - self.seq - 1) % 256
        self.quiet = False
        self.seq = seq
        self.last_rx = now
        self.count += 1
        self.target = {
            "left": max(-100, min(100, left)) / 100,
            "right": max(-100, min(100, right)) / 100,
        }

    def disconnected(self, device):
        if device != self.driver:
            log.info("disconnected: %s", device_name(device))
            return
        self._stop(f"driver {device_name(device)} disconnected")
        self.driver = None

    def tick(self, now, dt):
        """Run the drivetrain toward the target, or stop it if the driver went quiet."""
        silent = self.last_rx is None or now - self.last_rx > WATCHDOG_S
        if not silent:
            self.drivetrain.step(self.target, dt)
            return
        if not self.quiet:
            self._stop(f"no command for {WATCHDOG_S * 1000:.0f} ms")
        if self.driver is not None and (self.last_rx is None or now - self.last_rx > HANDOVER_S):
            log.info("driver %s silent for %.0f s, released", device_name(self.driver), HANDOVER_S)
            self.driver = None

    def report(self):
        """A once-a-second line on the link and the wheels, or None when idle and healthy."""
        moving = any(self.target.values()) or any(self.drivetrain.speed.values())
        line = None
        if self.count and (moving or self.max_gap > SLOW_GAP_S or self.skipped):
            line = (
                f"{self.count:2d} cmd/s, max gap {self.max_gap * 1000:3.0f} ms, "
                f"{self.skipped} skipped | target L {self.target['left']:+.2f} "
                f"R {self.target['right']:+.2f} | speed {speeds(self.drivetrain)}")
        self._reset_stats()
        return line

    def _stop(self, why):
        was = speeds(self.drivetrain)
        self.drivetrain.stop()
        self.target = dict(STOP)
        self.quiet = True
        self.seq = None
        log.info("%s, stopped from %s", why, was)

    def _reset_stats(self):
        self.count = 0
        self.skipped = 0
        self.max_gap = 0.0


def speeds(drivetrain):
    return "L {left:+.2f} R {right:+.2f}".format(**drivetrain.speed)


class Systemd:
    """sd_notify(3) without libsystemd: READY=1 and WATCHDOG=1.

    Does nothing when not started by systemd. Never blocks: a ping that
    can't be sent now is dropped, since the next tick sends another.
    """

    def __init__(self):
        self.sock = None
        path = os.environ.get("NOTIFY_SOCKET")
        if path:
            if path.startswith("@"):
                path = "\0" + path[1:]
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.sock.setblocking(False)
            self.sock.connect(path)

    def notify(self, message):
        if self.sock:
            try:
                self.sock.send(message.encode())
            except OSError:
                pass


class DriveService(Service):
    def __init__(self, car):
        self._car = car
        super().__init__(SERVICE_UUID, True)

    # Without response for the stream, with response for the app's first
    # write; both only over a link authenticated by passkey pairing.
    @characteristic(DRIVE_UUID, CharacteristicFlags.WRITE_WITHOUT_RESPONSE
                    | CharacteristicFlags.WRITE
                    | CharacteristicFlags.ENCRYPT_AUTHENTICATED_WRITE).setter
    def drive(self, value, options):
        self._car.command(value, options.device, time.monotonic())


class PairingAgent(BaseAgent):
    """BlueZ's default agent, with DisplayOnly capability.

    A phone that can type gets Passkey Entry, which authenticates the bond.
    The passkey goes to the log, the Pi's only display. Anything that would
    pair without a passkey (Just Works) is refused, so no unauthenticated
    bond is made either.
    """

    PATH = "/robot_car_agent"

    def __init__(self):
        super().__init__(AgentCapability.DISPLAY_ONLY)

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
        if entered == 0:
            log.warning("pairing %s: passkey %s", device_name(device), passkey_text(passkey))

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        raise refused("PIN pairing")

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        raise refused("typing a passkey")

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):
        raise refused("numeric comparison")

    @method()
    def RequestAuthorization(self, device: "o"):
        raise refused("pairing without a passkey")

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        raise refused(f"service {uuid}")

    @method()
    def Cancel(self):
        log.info("pairing cancelled")


def passkey_text(passkey):
    return f"{passkey:06d}"


def refused(what):
    log.warning("refused %s", what)
    return DBusError("org.bluez.Error.Rejected", f"robot_car refuses {what}")


class Advertisement(ServiceInterface):
    """A connectable LE advert: the name and our service UUID, nothing else.

    Flags (3 bytes), the 128-bit UUID (18) and an 8-letter name (10) fill
    the 31-byte advert exactly, so NAME can't grow and no appearance or TX
    power field fits.
    """

    PATH = "/robot_car_advert"

    def __init__(self, on_release):
        self._on_release = on_release
        super().__init__("org.bluez.LEAdvertisement1")

    @method()
    def Release(self):
        self._on_release("BlueZ released the advertisement")

    @dbus_property(PropertyAccess.READ)
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        return [SERVICE_UUID]

    @dbus_property(PropertyAccess.READ)
    def LocalName(self) -> "s":
        return NAME

    @dbus_property(PropertyAccess.READ)
    def Discoverable(self) -> "b":
        return True


async def wait_for_adapter(bus, stopping):
    """The adapter's proxy once BlueZ has it powered, powering it if need be,
    or None if asked to stop first.

    At boot this runs as soon as bluetoothd is up, which can be before
    bluetoothd has found the adapter or while the adapter is still busy
    powering on.
    """
    waiting = False
    while not stopping.is_set():
        try:
            proxy = bus.get_proxy_object(
                "org.bluez", ADAPTER, await bus.introspect("org.bluez", ADAPTER))
            adapter = proxy.get_interface("org.bluez.Adapter1")
            if await adapter.get_powered():
                return proxy
            await adapter.set_powered(True)
        except (DBusError, InterfaceNotFoundError):
            pass
        if not waiting:
            log.info("waiting for %s to power up", ADAPTER)
            waiting = True
        try:
            await asyncio.wait_for(stopping.wait(), 0.5)
        except asyncio.TimeoutError:
            pass
    return None


async def watch_bluez(bus, on_disconnect, on_lost):
    """Report phones leaving, and the adapter or bluetoothd going away."""
    rules = [
        "type='signal',sender='org.bluez',interface='org.freedesktop.DBus.Properties',"
        "member='PropertiesChanged',arg0='org.bluez.Device1'",
        "type='signal',sender='org.bluez',interface='org.freedesktop.DBus.Properties',"
        f"member='PropertiesChanged',arg0='org.bluez.Adapter1',path='{ADAPTER}'",
        "type='signal',sender='org.bluez',interface='org.freedesktop.DBus.ObjectManager',"
        "member='InterfacesRemoved'",
        "type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',"
        "member='NameOwnerChanged',arg0='org.bluez'",
    ]
    for rule in rules:
        await bus.call(Message(
            destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus", member="AddMatch",
            signature="s", body=[rule]))

    def handler(msg):
        if msg.message_type != MessageType.SIGNAL:
            return
        if msg.member == "PropertiesChanged":
            interface, changed = msg.body[0], msg.body[1]
            if interface == "org.bluez.Device1" and "Connected" in changed:
                if not changed["Connected"].value:
                    on_disconnect(msg.path)
                else:
                    log.info("connected: %s", device_name(msg.path))
            elif (interface == "org.bluez.Adapter1" and msg.path == ADAPTER
                    and "Powered" in changed and not changed["Powered"].value):
                on_lost(f"{ADAPTER} powered off")
        elif msg.member == "InterfacesRemoved" and msg.body[0] == ADAPTER:
            on_lost(f"{ADAPTER} removed")
        elif msg.member == "NameOwnerChanged" and msg.body[0] == "org.bluez" and not msg.body[2]:
            on_lost("bluetoothd went away")

    bus.add_message_handler(handler)


async def serve(car, stopping):
    """Serve the car until asked to stop. Returns why the link was lost, or None."""
    systemd = Systemd()
    lost = []
    registered = False

    def on_lost(why):
        # Before registration the adapter may still be settling, which is
        # wait_for_adapter's business.
        if registered and not lost:
            lost.append(why)
            stopping.set()

    bus = await get_message_bus()
    await watch_bluez(bus, car.disconnected, on_lost)
    # Named outright: Adapter.get_first() takes every child of /org/bluez for
    # an adapter, and BlueZ 5.82 has children that aren't.
    adapter = await wait_for_adapter(bus, stopping)
    if adapter is None:
        bus.disconnect()
        return None
    await PairingAgent().register(bus, default=True, path=PairingAgent.PATH)
    adapter_props = adapter.get_interface("org.bluez.Adapter1")
    await adapter_props.set_pairable(True)
    await adapter_props.set_pairable_timeout(0)
    await DriveService(car).register(bus, path="/robot_car", adapter=Adapter(adapter))
    bus.export(Advertisement.PATH, Advertisement(on_lost))
    await adapter.get_interface("org.bluez.LEAdvertisingManager1") \
        .call_register_advertisement(Advertisement.PATH, {})
    registered = True
    log.info("advertising as %s, service %s", NAME, SERVICE_UUID)
    systemd.notify("READY=1")

    last = time.monotonic()
    report_at = last + 1.0
    while not stopping.is_set():
        await asyncio.sleep(TICK_S)
        now = time.monotonic()
        car.tick(now, now - last)
        systemd.notify("WATCHDOG=1")
        last = now
        if now >= report_at:
            line = car.report()
            if line:
                log.info("%s", line)
            report_at = now + 1.0
    bus.disconnect()
    return lost[0] if lost else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="mock the motor pins")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(message)s", datefmt="%H:%M:%S")

    if args.dry_run:
        # The real Drivetrain on mock pins, so the ramp and the duty mapping
        # behave exactly as on the car.
        from gpiozero import Device
        from gpiozero.pins.mock import MockFactory, MockPWMPin
        Device.pin_factory = MockFactory(pin_class=MockPWMPin)
    from drivetrain import Drivetrain
    drivetrain = Drivetrain()

    async def run():
        stopping = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            loop.add_signal_handler(signum, stopping.set)
        return await serve(Car(drivetrain), stopping)

    lost = None
    try:
        lost = asyncio.run(run())
    finally:
        drivetrain.close()
        log.info("stopped")
    if lost:
        log.error("%s, exiting for a restart", lost)
        sys.exit(1)


if __name__ == "__main__":
    main()
