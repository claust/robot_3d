// Blink the XIAO ESP32-C5 user LED and report each toggle on the USB console.

#include <stdbool.h>
#include <stdio.h>

#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// User LED on the XIAO ESP32-C5. Wired active-low: driving the pin low lights it.
#define LED_GPIO GPIO_NUM_27
#define BLINK_PERIOD_MS 1000

void app_main(void)
{
    gpio_reset_pin(LED_GPIO);
    gpio_set_direction(LED_GPIO, GPIO_MODE_OUTPUT);

    bool on = false;
    while (true) {
        on = !on;
        gpio_set_level(LED_GPIO, on ? 0 : 1);
        printf("LED %s\n", on ? "ON" : "OFF");
        vTaskDelay(pdMS_TO_TICKS(BLINK_PERIOD_MS));
    }
}
