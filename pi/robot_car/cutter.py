"""robot_car's cutter: the Canon motor on the TB6612's channel A.

The TB6612's AIN2 is wired to ground, so the cutter turns one way only:
AIN1 high runs it, PWMA sets the speed, and STBY low switches the driver
off. Swap the motor's leads on AO1/AO2 to change its direction.

Cutter takes a speed in [0, 1] and moves toward it at SLEW_PER_S at most,
so switching on spins the disc up over a second instead of drawing the
motor's stall current from the pack all at once. stop() skips the ramp and
lets the disc coast down.
"""

from gpiozero import DigitalOutputDevice, PWMOutputDevice

STBY = 26  # header pin 37
PWMA = 20  # header pin 38
AIN1 = 21  # header pin 40
PWM_HZ = 2000
SLEW_PER_S = 1.0
MAX_STEP_S = 0.05


class Cutter:
    def __init__(self):
        self.stby = DigitalOutputDevice(STBY)
        self.ain1 = DigitalOutputDevice(AIN1)
        self.pwm = PWMOutputDevice(PWMA, frequency=PWM_HZ)
        self.speed = 0.0

    def step(self, target, dt):
        """Move toward `target` by at most SLEW_PER_S * dt."""
        target = max(0.0, min(1.0, target))
        limit = SLEW_PER_S * min(dt, MAX_STEP_S)
        change = max(-limit, min(limit, target - self.speed))
        if not change:
            return
        self.speed += change
        if self.speed > 0:
            self.stby.on()
            self.ain1.on()
            self.pwm.value = self.speed
        else:
            self.stop()

    def stop(self):
        self.speed = 0.0
        self.pwm.off()
        self.ain1.off()
        self.stby.off()

    def close(self):
        self.stop()
        for device in (self.pwm, self.ain1, self.stby):
            device.close()
