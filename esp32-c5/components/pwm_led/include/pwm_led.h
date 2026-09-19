// Dimmable LEDs on any GPIO, driven by the LEDC PWM peripheral.
//
// Brightness is a percentage (0-100). With `gamma` on, the percentage is
// perceived brightness: 50 looks half as bright as 100, and fades look even
// from start to finish. With it off, the percentage is the raw PWM duty.
//
// All LEDs share one 5 kHz, 13-bit LEDC timer; each takes one LEDC channel
// (6 on the ESP32-C5).
//
// Every call is safe from any task, including several tasks at once. Calls on
// the same LED are serialized, so one waits while another's fade is running.

#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

typedef struct {
    int gpio;    // GPIO number the LED's anode (through its resistor) is on
    bool gamma;  // true: perceptual brightness; false: linear duty
} pwm_led_config_t;

typedef struct pwm_led *pwm_led_handle_t;

// Set up an LED, starting dark. Returns ESP_ERR_NO_MEM when all channels are taken.
esp_err_t pwm_led_new(const pwm_led_config_t *config, pwm_led_handle_t *ret_led);

// Jump straight to a brightness. Stops breathing first.
esp_err_t pwm_led_set(pwm_led_handle_t led, uint8_t percent);

// Fade from the current brightness to `percent` over `ms` milliseconds.
// With `wait`, block until the fade is done; otherwise return at once and let
// the hardware fade in the background (the next set/fade then waits for it).
// Stops breathing first.
esp_err_t pwm_led_fade(pwm_led_handle_t led, uint8_t percent, uint32_t ms, bool wait);

// Fade up to 100% and down to 0% forever, `fade_ms` each way, from a
// background task. Returns at once; the caller (even app_main) may return.
esp_err_t pwm_led_breathe(pwm_led_handle_t led, uint32_t fade_ms);

// Stop breathing and hold the brightness it had reached. Does nothing if the
// LED isn't breathing.
esp_err_t pwm_led_stop(pwm_led_handle_t led);
