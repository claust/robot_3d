"""Tests for the car's command handling, watchdog and drivetrain, on mock pins.

    uv run --no-project --with gpiozero --with bluez-peripheral python -m unittest -v test_remote

from this folder (or the venv's Python on the Pi, with the service stopped).
"""

import asyncio
import logging
import os
import socket
import tempfile
import unittest
from unittest import mock

from bluez_peripheral.gatt.characteristic import CharacteristicFlags
from dbus_next.errors import DBusError
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin

import drivetrain
from drivetrain import Drivetrain, duty
from remote import (HANDOVER_S, PAIRING_WINDOW_S, WATCHDOG_S, Car, DriveService, PairingAgent,
                    Systemd, wait_for_adapter)

PHONE = "/org/bluez/hci0/dev_AA"
OTHER = "/org/bluez/hci0/dev_BB"
TICK = 0.02


def cmd(seq, left, right):
    return bytes([seq, left & 0xFF, right & 0xFF])


class MockPins(unittest.TestCase):
    def setUp(self):
        Device.pin_factory = MockFactory(pin_class=MockPWMPin)
        self.drivetrain = Drivetrain()
        self.car = Car(self.drivetrain)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        self.drivetrain.close()
        Device.pin_factory.reset()
        logging.disable(logging.NOTSET)

    def run_ticks(self, start, seconds):
        """Tick the car from `start` for `seconds`; returns the end time."""
        now = start
        for _ in range(round(seconds / TICK)):
            now += TICK
            self.car.tick(now, TICK)
        return now

    def pin(self, number):
        return Device.pin_factory.pin(number).state


class DutyTests(unittest.TestCase):
    def test_zero_is_off(self):
        self.assertEqual(duty(0.0), 0.0)

    def test_smallest_command_jumps_to_min_duty(self):
        self.assertAlmostEqual(duty(0.01), drivetrain.MIN_DUTY + (1 - drivetrain.MIN_DUTY) * 0.01)
        self.assertAlmostEqual(duty(-0.01), -duty(0.01))

    def test_full_scale(self):
        self.assertEqual(duty(1.0), 1.0)
        self.assertEqual(duty(-1.0), -1.0)
        self.assertEqual(duty(3.0), 1.0)


class DrivetrainTests(MockPins):
    def test_ramps_and_lands_exactly(self):
        target = {"left": 1.0, "right": -0.37}
        for _ in range(20):
            self.drivetrain.step(target, TICK)
        self.assertEqual(self.drivetrain.speed, target)

    def test_ramp_rate(self):
        self.drivetrain.step({"left": 1.0, "right": 0.0}, TICK)
        self.assertAlmostEqual(self.drivetrain.speed["left"], drivetrain.SLEW_PER_S * TICK)

    def test_long_dt_after_a_stall_still_ramps(self):
        self.drivetrain.step({"left": 1.0, "right": 0.0}, 0.5)
        self.assertAlmostEqual(self.drivetrain.speed["left"], drivetrain.SLEW_PER_S * drivetrain.MAX_STEP_S)

    def test_forward_drives_the_forward_pin(self):
        for _ in range(20):
            self.drivetrain.step({"left": 1.0, "right": -1.0}, TICK)
        self.assertEqual(self.pin(13), 1.0)   # left forward, IN2
        self.assertEqual(self.pin(12), 0.0)
        self.assertEqual(self.pin(19), 1.0)   # right backward, IN3
        self.assertEqual(self.pin(16), 0.0)

    def test_stop_is_immediate(self):
        for _ in range(20):
            self.drivetrain.step({"left": 1.0, "right": 1.0}, TICK)
        self.drivetrain.stop()
        self.assertEqual(self.drivetrain.speed, {"left": 0.0, "right": 0.0})
        self.assertEqual([self.pin(n) for n in (12, 13, 16, 19)], [0, 0, 0, 0])


class CarTests(MockPins):
    def test_command_sets_target_and_clamps(self):
        self.car.command(cmd(0, 50, -128), PHONE, 0.0)
        self.assertEqual(self.car.target, {"left": 0.5, "right": -1.0})

    def test_wrong_length_is_ignored_and_claims_nothing(self):
        self.car.command(b"\x00\x10", OTHER, 0.0)
        self.assertIsNone(self.car.driver)
        self.car.command(cmd(0, 10, 10), PHONE, 0.0)
        self.assertEqual(self.car.driver, PHONE)

    def test_drives_while_commands_arrive(self):
        now = 0.0
        for seq in range(10):
            self.car.command(cmd(seq, 100, 100), PHONE, now)
            now = self.run_ticks(now, 0.05)
        self.assertEqual(self.drivetrain.speed, {"left": 1.0, "right": 1.0})

    def test_watchdog_stops_a_silent_driver(self):
        self.car.command(cmd(0, 100, 100), PHONE, 0.0)
        now = self.run_ticks(0.0, WATCHDOG_S - 0.04)
        self.assertGreater(self.drivetrain.speed["left"], 0)
        self.run_ticks(now, 0.06)
        self.assertEqual(self.drivetrain.speed, {"left": 0.0, "right": 0.0})
        self.assertEqual(self.car.target, {"left": 0.0, "right": 0.0})

    def test_second_device_is_ignored_while_driver_drives(self):
        self.car.command(cmd(0, 100, 100), PHONE, 0.0)
        self.car.command(cmd(0, -100, -100), OTHER, 0.01)
        self.assertEqual(self.car.target, {"left": 1.0, "right": 1.0})
        self.assertEqual(self.car.driver, PHONE)

    def test_other_device_leaving_does_not_stop_the_car(self):
        self.car.command(cmd(0, 100, 100), PHONE, 0.0)
        self.run_ticks(0.0, 0.1)
        self.car.disconnected(OTHER)
        self.assertGreater(self.drivetrain.speed["left"], 0)

    def test_driver_leaving_stops_and_hands_over(self):
        self.car.command(cmd(0, 100, 100), PHONE, 0.0)
        self.run_ticks(0.0, 0.1)
        self.car.disconnected(PHONE)
        self.assertEqual(self.drivetrain.speed, {"left": 0.0, "right": 0.0})
        self.car.command(cmd(0, -50, -50), OTHER, 0.2)
        self.assertEqual(self.car.driver, OTHER)

    def test_silent_driver_is_released_after_handover_time(self):
        self.car.command(cmd(0, 0, 0), PHONE, 0.0)
        now = self.run_ticks(0.0, HANDOVER_S - 0.1)
        self.assertEqual(self.car.driver, PHONE)
        self.run_ticks(now, 0.2)
        self.assertIsNone(self.car.driver)

    def test_counts_skipped_ticks(self):
        for seq, t in ((1, 0.0), (2, 0.05), (5, 0.1)):
            self.car.command(cmd(seq, 0, 0), PHONE, t)
        self.assertEqual(self.car.skipped, 2)

    def test_verify_write_then_stream_counts_no_skips(self):
        # The app's verifying write is seq 255; its stream starts at 0.
        self.car.command(cmd(255, 0, 0), PHONE, 0.0)
        self.car.command(cmd(0, 0, 0), PHONE, 0.05)
        self.car.command(cmd(1, 0, 0), PHONE, 0.10)
        self.assertEqual(self.car.skipped, 0)

    def test_restarted_stream_does_not_count_as_skipped(self):
        self.car.command(cmd(200, 0, 0), PHONE, 0.0)
        self.run_ticks(0.0, WATCHDOG_S + 0.1)
        self.car.command(cmd(0, 0, 0), PHONE, 0.5)
        self.assertEqual(self.car.skipped, 0)

    def test_report_is_quiet_when_idle_and_healthy(self):
        for seq in range(20):
            self.car.command(cmd(seq, 0, 0), PHONE, seq * 0.05)
        self.assertIsNone(self.car.report())

    def test_report_while_moving_or_when_the_link_is_slow(self):
        self.car.command(cmd(0, 30, 30), PHONE, 0.0)
        self.assertIn("cmd/s", self.car.report())
        self.car.command(cmd(1, 0, 0), PHONE, 0.05)
        self.car.command(cmd(2, 0, 0), PHONE, 0.25)
        self.assertIn("max gap 200 ms", self.car.report())


class PairingTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_drive_writes_need_an_encrypted_link(self):
        flags = DriveService.drive.flags
        self.assertTrue(flags & CharacteristicFlags.ENCRYPT_WRITE)
        self.assertTrue(flags & CharacteristicFlags.WRITE)
        self.assertTrue(flags & CharacteristicFlags.WRITE_WITHOUT_RESPONSE)
        self.assertFalse(flags & CharacteristicFlags.READ)

    def test_pairs_inside_the_window_after_boot(self):
        PairingAgent(uptime=lambda: PAIRING_WINDOW_S - 1).allow(PHONE)

    def test_refuses_to_pair_once_the_window_closed(self):
        agent = PairingAgent(uptime=lambda: PAIRING_WINDOW_S + 600)
        with self.assertRaises(DBusError):
            agent.allow(PHONE)


class SystemdTests(unittest.TestCase):
    def test_notifies_the_socket_systemd_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "notify")
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
                listener.bind(path)
                with mock.patch.dict(os.environ, {"NOTIFY_SOCKET": path}):
                    Systemd().notify("WATCHDOG=1")
                self.assertEqual(listener.recv(64), b"WATCHDOG=1")

    def test_outside_systemd_does_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            Systemd().notify("READY=1")


class WaitForAdapterTests(unittest.TestCase):
    def test_gives_up_when_asked_to_stop(self):
        class NoBluez:
            async def introspect(self, *_):
                raise DBusError("org.freedesktop.DBus.Error.ServiceUnknown", "no bluez")

            def get_proxy_object(self, *_):
                raise AssertionError("introspect failed, so no proxy")

        async def run():
            stopping = asyncio.Event()
            asyncio.get_running_loop().call_later(0.1, stopping.set)
            return await asyncio.wait_for(wait_for_adapter(NoBluez(), stopping), 2)

        logging.disable(logging.CRITICAL)
        try:
            self.assertIsNone(asyncio.run(run()))
        finally:
            logging.disable(logging.NOTSET)


if __name__ == "__main__":
    unittest.main()
