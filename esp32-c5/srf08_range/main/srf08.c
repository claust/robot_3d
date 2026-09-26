#include "srf08.h"

#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// Write-side registers.
#define SRF08_REG_COMMAND 0
#define SRF08_REG_GAIN 1
#define SRF08_REG_RANGE 2

// Ranging commands.
#define SRF08_CMD_RANGE_CM 0x51

// Read-side register 0 reads 0xFF while a ranging is still in flight, and the
// software revision once it has finished.
#define SRF08_BUSY 0xFF

// Read registers 0..35: revision, light, then 17 high/low echo pairs.
#define SRF08_RESULT_LEN (2 + SRF08_MAX_ECHOES * 2)

#define SRF08_TIMEOUT_MS 100

struct srf08_t {
    i2c_master_dev_handle_t dev;
};

static esp_err_t srf08_write_reg(srf08_handle_t handle, uint8_t reg, uint8_t value)
{
    const uint8_t buf[2] = {reg, value};
    return i2c_master_transmit(handle->dev, buf, sizeof(buf), SRF08_TIMEOUT_MS);
}

static esp_err_t srf08_read_regs(srf08_handle_t handle, uint8_t reg, uint8_t *buf, size_t len)
{
    return i2c_master_transmit_receive(handle->dev, &reg, 1, buf, len, SRF08_TIMEOUT_MS);
}

esp_err_t srf08_new(i2c_master_bus_handle_t bus, uint8_t addr, srf08_handle_t *out_handle)
{
    if (bus == NULL || out_handle == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    srf08_handle_t handle = calloc(1, sizeof(struct srf08_t));
    if (handle == NULL) {
        return ESP_ERR_NO_MEM;
    }

    const i2c_device_config_t config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = addr,
        // The SRF08's PIC is an older part; Devantech rate the bus at 100 kHz.
        .scl_speed_hz = 100000,
    };
    esp_err_t err = i2c_master_bus_add_device(bus, &config, &handle->dev);
    if (err != ESP_OK) {
        free(handle);
        return err;
    }

    *out_handle = handle;
    return ESP_OK;
}

void srf08_del(srf08_handle_t handle)
{
    if (handle == NULL) {
        return;
    }
    i2c_master_bus_rm_device(handle->dev);
    free(handle);
}

esp_err_t srf08_read_revision(srf08_handle_t handle, uint8_t *out_revision)
{
    if (handle == NULL || out_revision == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    return srf08_read_regs(handle, 0, out_revision, 1);
}

esp_err_t srf08_set_range(srf08_handle_t handle, uint8_t range)
{
    if (handle == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    return srf08_write_reg(handle, SRF08_REG_RANGE, range);
}

esp_err_t srf08_set_gain(srf08_handle_t handle, uint8_t gain)
{
    if (handle == NULL || gain > 31) {
        return ESP_ERR_INVALID_ARG;
    }
    return srf08_write_reg(handle, SRF08_REG_GAIN, gain);
}

esp_err_t srf08_ping(srf08_handle_t handle, srf08_result_t *out_result)
{
    if (handle == NULL || out_result == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t err = srf08_write_reg(handle, SRF08_REG_COMMAND, SRF08_CMD_RANGE_CM);
    if (err != ESP_OK) {
        return err;
    }

    // The module is deaf to I2C while it ranges, so wait the window out rather
    // than polling it.
    vTaskDelay(pdMS_TO_TICKS(SRF08_PING_MS));

    uint8_t buf[SRF08_RESULT_LEN];
    err = srf08_read_regs(handle, 0, buf, sizeof(buf));
    if (err != ESP_OK) {
        return err;
    }
    if (buf[0] == SRF08_BUSY) {
        // Still ranging: the wait was short, or the range register is longer
        // than the default.
        return ESP_ERR_TIMEOUT;
    }

    memset(out_result, 0, sizeof(*out_result));
    out_result->light = buf[1];
    for (int i = 0; i < SRF08_MAX_ECHOES; i++) {
        const uint16_t cm = (uint16_t)(buf[2 + i * 2] << 8) | buf[3 + i * 2];
        if (cm == 0) {
            break;  // First empty slot ends the list.
        }
        out_result->echo_cm[out_result->echo_count++] = cm;
    }
    return ESP_OK;
}
