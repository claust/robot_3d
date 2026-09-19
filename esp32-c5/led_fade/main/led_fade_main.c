// Breathe an external LED on pad D0, using the shared pwm_led component.
//
// Circuit: D0 -> LED anode (long leg), LED cathode -> 330 ohm -> GND.

#include "pwm_led.h"
#include "soc/gpio_num.h"

// XIAO pad D0 is GPIO 1 on the chip.
#define LED_GPIO GPIO_NUM_1
#define FADE_MS 500

void app_main(void)
{
    pwm_led_config_t config = {
        .gpio = LED_GPIO,
        .gamma = true,  // false: raw linear duty, which looks bright too early
    };
    pwm_led_handle_t led;
    ESP_ERROR_CHECK(pwm_led_new(&config, &led));

    // Runs in its own task, so app_main can return.
    ESP_ERROR_CHECK(pwm_led_breathe(led, FADE_MS));
}
