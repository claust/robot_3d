"""robot_car's two drive motors: pins, PWM, and the corrections every driver needs.

Pins and drive scheme follow cad/robot_car/WIRING.md: fast decay (PWM the
forward pin, hold the other low) at 2 kHz, software PWM through gpiozero's
lgpio backend. "Forward" means the car's forward: the top of the wheel rolls
toward the nose.

Drivetrain takes signed wheel speeds in [-1, 1] and applies two corrections:

- Minimum duty. The N20s don't turn below MIN_DUTY, so a speed just above
  zero maps to MIN_DUTY and full speed to 100 %. Without it the first
  quarter of a thumbstick's travel does nothing.
- Slew limit. Each wheel moves toward its target at SLEW_PER_S at most, so
  full forward to full reverse takes 2 / SLEW_PER_S seconds instead of
  slamming the gearbox and spiking the motor buck. One step covers at most
  MAX_STEP_S, so a caller that stalls and then steps with a long dt still
  ramps instead of jumping. stop() skips the ramp.
"""

from gpiozero import Motor

PWM_HZ = 2000
# (forward, backward). On the built car both motors run backward with IN1/IN3
# high, so forward is IN2 on the left and IN4 on the right.
PINS = {
    "left": (13, 12),   # IN2, IN1
    "right": (16, 19),  # IN4, IN3
}
# motor_test.py --creep: both wheels start at 25-30 % duty, off the ground.
MIN_DUTY = 0.25
SLEW_PER_S = 4.0
MAX_STEP_S = 0.05


def make_motor(name):
    motor = Motor(*PINS[name], pwm=True)
    motor.forward_device.frequency = PWM_HZ
    motor.backward_device.frequency = PWM_HZ
    return motor


def duty(speed):
    """Signed speed in [-1, 1] -> signed PWM duty, with the minimum-duty jump."""
    if speed == 0:
        return 0.0
    magnitude = MIN_DUTY + (1 - MIN_DUTY) * min(abs(speed), 1.0)
    return magnitude if speed > 0 else -magnitude


class Drivetrain:
    def __init__(self):
        self.motors = {name: make_motor(name) for name in PINS}
        self.speed = {name: 0.0 for name in PINS}

    def step(self, target, dt):
        """Move each wheel toward target[name] by at most SLEW_PER_S * dt."""
        limit = SLEW_PER_S * min(dt, MAX_STEP_S)
        for name, motor in self.motors.items():
            change = max(-limit, min(limit, target[name] - self.speed[name]))
            if change:
                self.speed[name] += change
                self._apply(motor, self.speed[name])

    def stop(self):
        for name, motor in self.motors.items():
            self.speed[name] = 0.0
            motor.stop()

    def close(self):
        self.stop()
        for motor in self.motors.values():
            motor.close()

    @staticmethod
    def _apply(motor, speed):
        d = duty(speed)
        if d > 0:
            motor.forward(d)
        elif d < 0:
            motor.backward(-d)
        else:
            motor.stop()
