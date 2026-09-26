// Devantech SRF08 ultrasonic rangefinder (parts library S1) over I2C.
//
// The SRF08 reports up to 17 echoes per ping, nearest first, so you can see
// past a near obstacle to what is behind it. Every ping also updates the
// onboard light sensor for free.

#pragma once

#include "driver/i2c_master.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

// Factory address 0xE0 as an 8-bit address; ESP-IDF wants the 7-bit form.
#define SRF08_ADDR_DEFAULT 0x70
// Lowest and highest of the 16 addresses an SRF08 can be programmed to
// (0xE0-0xFE even, i.e. 0x70-0x7F as 7-bit).
#define SRF08_ADDR_MIN 0x70
#define SRF08_ADDR_MAX 0x7F

// Ranging takes 65 ms with the default range register, and less once the
// range is shortened. Waiting the full window is always safe.
#define SRF08_PING_MS 70

// Most echoes one ping can return.
#define SRF08_MAX_ECHOES 17

typedef struct srf08_t *srf08_handle_t;

typedef struct {
    uint8_t light;                      // 2-3 in the dark, ~248 in bright light
    int echo_count;                     // echoes actually returned, 0 if nothing was heard
    uint16_t echo_cm[SRF08_MAX_ECHOES]; // nearest first
} srf08_result_t;

// Attach to an SRF08 at a 7-bit address on an existing bus.
esp_err_t srf08_new(i2c_master_bus_handle_t bus, uint8_t addr, srf08_handle_t *out_handle);

void srf08_del(srf08_handle_t handle);

// Software revision from read register 0. Cheapest liveness check there is.
esp_err_t srf08_read_revision(srf08_handle_t handle, uint8_t *out_revision);

// Listening window, as (n * 43 mm) + 43 mm. Default 255, i.e. ~11 m of flight
// time. Shortening it cuts spurious far echoes and speeds up ranging.
esp_err_t srf08_set_range(srf08_handle_t handle, uint8_t range);

// Maximum analogue gain, 0-31 (default 31). Devantech's advice is to wind this
// down together with the range, so the amplifier is not at full tilt by the
// time the late reflections arrive.
esp_err_t srf08_set_gain(srf08_handle_t handle, uint8_t gain);

// One full ranging cycle in cm: fire, wait out the listening window, read back
// the light level and every echo.
esp_err_t srf08_ping(srf08_handle_t handle, srf08_result_t *out_result);

#ifdef __cplusplus
}
#endif
