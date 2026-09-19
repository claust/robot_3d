// Flash an external LED on pad D0 and report each toggle on the USB console.
//
// Circuit: D0 -> LED anode (long leg), LED cathode -> 330 ohm -> GND.
// The pin sources the current, so the LED is active-high: driving it high lights it.
// A red LED drops about 2.0 V, leaving 1.3 V / 330 ohm = about 4 mA.

#include <stdbool.h>
#include <stdio.h>

#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// XIAO pad D0 is GPIO 1 on the chip; the silkscreen labels are not GPIO numbers.
#define LED_GPIO GPIO_NUM_1
#define FLASH_PERIOD_MS 500

static void flash_led(void *arg)
{
    bool on = false;
    while (true) {
        on = !on;
        gpio_set_level(LED_GPIO, on ? 1 : 0);
        printf("LED %s\n", on ? "ON" : "OFF");
        vTaskDelay(pdMS_TO_TICKS(FLASH_PERIOD_MS));
    }
}

void app_main(void)
{
    gpio_reset_pin(LED_GPIO);
    gpio_set_direction(LED_GPIO, GPIO_MODE_OUTPUT);

    // ESP-IDF stack sizes are in bytes, not words as in vanilla FreeRTOS.
    if (xTaskCreate(flash_led, "flash_led", 2048, NULL, 5, NULL) != pdPASS) {
        printf("failed to create flash_led task\n");
    }
}
