// Range with the SRF08 ultrasonic rangefinder (parts library S1) and print
// every echo to the USB console.
//
// Circuit: the SRF08 is a 5 V part, but it fits no I2C pull-ups of its own, so
// pulling the bus up to 3.3 V keeps the XIAO's pins safe. See README.md.
//
//   XIAO 5V  -> SRF08 pin 1 (+5V, red), and 100 uF + 100 nF at the module
//   XIAO D4  -> SRF08 pin 2 (SDA, yellow), 4.7k to 3V3
//   XIAO D5  -> SRF08 pin 3 (SCL, blue),   4.7k to 3V3
//   XIAO GND -> SRF08 pin 5 (0V, black)

#include <stdio.h>

#include "driver/i2c_master.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "soc/gpio_num.h"
#include "srf08.h"

// XIAO pads D4/D5 are GPIO 23/24, the board's labelled I2C pins.
#define I2C_SDA GPIO_NUM_23
#define I2C_SCL GPIO_NUM_24

#define PING_PERIOD_MS 250

// (68 * 43 mm) + 43 mm = 2967 mm. Past the ~6 m the SRF08 can reach, echoes are
// noise anyway, and a shorter window means a faster ranging cycle.
#define RANGE_REGISTER 68
#define GAIN_REGISTER 31

static const char *TAG = "srf08_range";

// The SRF08's address range (0x70-0x7F) runs into the I2C reserved block at
// 0x78, so scan the whole space rather than the usual 0x08-0x77.
static int scan_bus(i2c_master_bus_handle_t bus, uint8_t *found, int max_found)
{
    int count = 0;
    for (uint8_t addr = 0x03; addr <= 0x7F && count < max_found; addr++) {
        if (i2c_master_probe(bus, addr, 50) == ESP_OK) {
            ESP_LOGI(TAG, "  found device at 0x%02X (8-bit write address 0x%02X)", addr, (uint8_t)(addr << 1));
            found[count++] = addr;
        }
    }
    return count;
}

void app_main(void)
{
    const i2c_master_bus_config_t bus_config = {
        .i2c_port = -1,  // let the driver pick a free port
        .sda_io_num = I2C_SDA,
        .scl_io_num = I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        // The internal pull-ups are ~45k, far too weak for this bus; R1/R2
        // on the board are the real ones.
        .flags.enable_internal_pullup = false,
    };
    i2c_master_bus_handle_t bus;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &bus));

    // S1 came off an old robot and may have been readdressed, so find it
    // rather than assuming the factory 0xE0.
    ESP_LOGI(TAG, "scanning I2C bus on SDA=GPIO%d SCL=GPIO%d...", I2C_SDA, I2C_SCL);
    uint8_t found[8];
    const int count = scan_bus(bus, found, sizeof(found));
    if (count == 0) {
        ESP_LOGE(TAG, "no I2C devices at all - check wiring, pull-ups and the 5 V supply");
        return;
    }

    uint8_t addr = 0;
    for (int i = 0; i < count; i++) {
        if (found[i] >= SRF08_ADDR_MIN && found[i] <= SRF08_ADDR_MAX) {
            addr = found[i];
            break;
        }
    }
    if (addr == 0) {
        ESP_LOGE(TAG, "no device in the SRF08 range 0x%02X-0x%02X", SRF08_ADDR_MIN, SRF08_ADDR_MAX);
        return;
    }
    ESP_LOGI(TAG, "using SRF08 at 0x%02X", addr);

    srf08_handle_t srf08;
    ESP_ERROR_CHECK(srf08_new(bus, addr, &srf08));

    uint8_t revision = 0;
    ESP_ERROR_CHECK(srf08_read_revision(srf08, &revision));
    ESP_LOGI(TAG, "software revision %u", revision);

    ESP_ERROR_CHECK(srf08_set_gain(srf08, GAIN_REGISTER));
    ESP_ERROR_CHECK(srf08_set_range(srf08, RANGE_REGISTER));
    ESP_LOGI(TAG, "ranging to %d mm, gain %d", (RANGE_REGISTER * 43) + 43, GAIN_REGISTER);

    while (true) {
        srf08_result_t result;
        const esp_err_t err = srf08_ping(srf08, &result);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "ping failed: %s", esp_err_to_name(err));
        } else if (result.echo_count == 0) {
            ESP_LOGI(TAG, "light %3u | no echo", result.light);
        } else {
            printf("I (%lu) %s: light %3u | %d echo%s:", (unsigned long)(esp_log_timestamp()), TAG,
                   result.light, result.echo_count, result.echo_count == 1 ? "" : "es");
            for (int i = 0; i < result.echo_count; i++) {
                printf(" %u cm", result.echo_cm[i]);
            }
            printf("\n");
        }
        vTaskDelay(pdMS_TO_TICKS(PING_PERIOD_MS));
    }
}
