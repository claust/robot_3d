#!/usr/bin/env python3
"""Cutter bring-up for robot_car: Pi Zero 2 W -> TB6612 channel A -> the Canon.

Pins and drive scheme are cutter.py's. This drives the pins directly,
without Cutter's ramp, so stop the remote service first: remote.py holds
the cutter's pins too.

    cutter_test.py               ramp up to --speed in 10 % steps, hold, stop
    cutter_test.py --creep       ramp 0-100 % in 5 % steps to find where it starts
    cutter_test.py --check       claim the three pins, hold them low, exit

Run it with no blades on the disc. Every mode ends by itself, and SIGTERM
and SIGHUP stop the motor before exiting; SIGKILL can't, which is what the
power switch is for.
"""

import argparse
import signal
import time

from gpiozero import DigitalOutputDevice, PWMOutputDevice

from cutter import AIN1, PWM_HZ, PWMA, STBY


def ramp(pwm, top, step, seconds):
    for percent in range(step, top + 1, step):
        print(f"cutter {percent:3d} %", flush=True)
        pwm.value = percent / 100
        time.sleep(seconds)


def _exit_on_signal(signum, frame):
    raise SystemExit(128 + signum)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--creep", action="store_true", help="ramp from 0 to 100 %% in 5 %% steps")
    mode.add_argument("--check", action="store_true", help="claim the pins and exit")
    parser.add_argument("--speed", type=int, default=60, help="top duty for the ramp, %% (default 60)")
    parser.add_argument("--hold", type=float, default=3, help="seconds at the top duty (default 3)")
    parser.add_argument("--seconds", type=float, default=1.0, help="seconds per step (default 1)")
    args = parser.parse_args()
    # Range checks, written so NaN fails them too, before any pin is claimed.
    if not 10 <= args.speed <= 100:
        parser.error("--speed must be in [10, 100]")
    if not 0 < args.seconds <= 10:
        parser.error("--seconds must be in (0, 10]")
    if not 0 <= args.hold <= 30:
        parser.error("--hold must be in [0, 30] seconds")

    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, _exit_on_signal)

    stby = DigitalOutputDevice(STBY)
    ain1 = DigitalOutputDevice(AIN1)
    pwm = PWMOutputDevice(PWMA, frequency=PWM_HZ)
    try:
        if args.check:
            print(f"STBY GPIO{STBY}, PWMA GPIO{PWMA}, AIN1 GPIO{AIN1} claimed, low, {PWM_HZ} Hz")
            return
        stby.on()
        ain1.on()
        if args.creep:
            ramp(pwm, 100, 5, args.seconds)
        else:
            ramp(pwm, args.speed, 10, args.seconds)
            pwm.value = args.speed / 100
            print(f"cutter {args.speed:3d} % for {args.hold:g} s", flush=True)
            time.sleep(args.hold)
    finally:
        pwm.off()
        ain1.off()
        stby.off()
        for device in (pwm, ain1, stby):
            device.close()
        print("stopped", flush=True)


if __name__ == "__main__":
    main()
