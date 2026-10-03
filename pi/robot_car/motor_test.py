#!/usr/bin/env python3
"""Drivetrain bring-up for robot_car: Pi Zero 2 W -> DRV8833 -> two N20s.

Pins and drive scheme follow cad/robot_car/WIRING.md: fast decay (PWM the
forward pin, hold the other low) at 2 kHz, software PWM through gpiozero's
lgpio backend. "Forward" means the car's forward: the top of the wheel rolls
toward the nose.

    motor_test.py               each motor forward, then reverse, one at a time
    motor_test.py --creep left  ramp one motor 0-100 % to find where it starts
    motor_test.py --hold 5      both motors forward at 100 % (stall ground check)
    motor_test.py --check       claim the four pins, hold them low, exit

Every mode ends by itself. A killed process can leave a pin mid-PWM, so
SIGTERM and SIGHUP stop the motors before exiting; SIGKILL can't, which is
what the power switch is for.
"""

import argparse
import signal
import time

from gpiozero import Motor

PWM_HZ = 2000
# (forward, backward). On the built car both motors run backward with IN1/IN3
# high, so forward is IN2 on the left and IN4 on the right.
PINS = {
    "left": (13, 12),   # IN2, IN1
    "right": (16, 19),  # IN4, IN3
}


def make_motor(name):
    motor = Motor(*PINS[name], pwm=True)
    motor.forward_device.frequency = PWM_HZ
    motor.backward_device.frequency = PWM_HZ
    return motor


def run(motor, name, direction, percent, seconds):
    print(f"{name:5} {direction:7} {percent:3.0f} % for {seconds:g} s", flush=True)
    getattr(motor, direction)(percent / 100)
    time.sleep(seconds)
    motor.stop()


def sequence(motors, percent, seconds):
    for name, motor in motors.items():
        for direction in ("forward", "backward"):
            run(motor, name, direction, percent, seconds)
            time.sleep(1.0)


def creep(motor, name, step, seconds):
    for percent in range(step, 101, step):
        print(f"{name} forward {percent:3d} %", flush=True)
        motor.forward(percent / 100)
        time.sleep(seconds)
    motor.stop()


def hold(motors, seconds):
    print(f"both forward 100 % for {seconds:g} s", flush=True)
    for motor in motors.values():
        motor.forward(1.0)
    time.sleep(seconds)


def _exit_on_signal(signum, frame):
    raise SystemExit(128 + signum)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--creep", choices=PINS, help="ramp one motor from 0 to 100 %%")
    mode.add_argument("--hold", type=float, metavar="S", help="both motors at 100 %% for S seconds")
    mode.add_argument("--check", action="store_true", help="claim the pins and exit")
    parser.add_argument("--speed", type=float, default=60, help="sequence duty, %% (default 60)")
    parser.add_argument("--seconds", type=float, default=1.5, help="seconds per step (default 1.5)")
    args = parser.parse_args()
    if not 0 < args.speed <= 100:
        parser.error("--speed must be in (0, 100]")
    if args.hold is not None and not 0 < args.hold <= 30:
        parser.error("--hold must be in (0, 30] seconds")

    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, _exit_on_signal)

    motors = {name: make_motor(name) for name in PINS}
    try:
        if args.check:
            for name, (fwd, back) in PINS.items():
                print(f"{name:5} GPIO{fwd}/GPIO{back} claimed, low, {PWM_HZ} Hz")
        elif args.creep:
            creep(motors[args.creep], args.creep, step=5, seconds=args.seconds)
        elif args.hold is not None:
            hold(motors, args.hold)
        else:
            sequence(motors, args.speed, args.seconds)
    finally:
        for motor in motors.values():
            motor.stop()
            motor.close()
        print("stopped", flush=True)


if __name__ == "__main__":
    main()
