#include "pwm_led.h"

#include <math.h>

#include "driver/ledc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define SPEED_MODE LEDC_LOW_SPEED_MODE
#define TIMER LEDC_TIMER_0
#define FREQ_HZ 5000
#define DUTY_RESOLUTION LEDC_TIMER_13_BIT
#define DUTY_MAX ((1 << DUTY_RESOLUTION) - 1)

// Perceived brightness ~ duty^(1/GAMMA), so duty = level^GAMMA undoes it.
#define GAMMA 2.8f
// A gamma fade is split into this many straight-line hardware segments.
#define GAMMA_FADE_SEGMENTS 12

// ESP-IDF stack sizes are in bytes.
#define BREATHE_STACK 3072
#define BREATHE_PRIORITY 5

struct pwm_led {
    ledc_channel_t channel;
    bool gamma;
    uint32_t level;  // brightness on the 0..DUTY_MAX scale, before gamma
    TaskHandle_t breathe_task;  // NULL unless breathing
    TaskHandle_t stopper;       // task waiting for the breathing task to exit
    uint32_t breathe_ms;
};

static struct pwm_led s_leds[SOC_LEDC_CHANNEL_NUM];
static int s_led_count;

static uint32_t percent_to_level(uint8_t percent)
{
    if (percent > 100) {
        percent = 100;
    }
    return (uint32_t)percent * DUTY_MAX / 100;
}

// Matches the uint32_t (*)(uint32_t) operator the LEDC gamma fade expects.
static uint32_t gamma_duty(uint32_t level)
{
    return (uint32_t)lroundf(powf((float)level / DUTY_MAX, GAMMA) * DUTY_MAX);
}

static uint32_t level_to_duty(const struct pwm_led *led, uint32_t level)
{
    return led->gamma ? gamma_duty(level) : level;
}

static uint32_t duty_to_level(const struct pwm_led *led, uint32_t duty)
{
    if (!led->gamma) {
        return duty;
    }
    return (uint32_t)lroundf(powf((float)duty / DUTY_MAX, 1.0f / GAMMA) * DUTY_MAX);
}

// The shared timer and the fade service are set up with the first LED.
static esp_err_t init_shared(void)
{
    ledc_timer_config_t timer = {
        .speed_mode = SPEED_MODE,
        .timer_num = TIMER,
        .duty_resolution = DUTY_RESOLUTION,
        .freq_hz = FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    esp_err_t err = ledc_timer_config(&timer);
    if (err != ESP_OK) {
        return err;
    }
    return ledc_fade_func_install(0);
}

esp_err_t pwm_led_new(const pwm_led_config_t *config, pwm_led_handle_t *ret_led)
{
    if (config == NULL || ret_led == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (s_led_count == SOC_LEDC_CHANNEL_NUM) {
        return ESP_ERR_NO_MEM;
    }
    if (s_led_count == 0) {
        esp_err_t err = init_shared();
        if (err != ESP_OK) {
            return err;
        }
    }

    struct pwm_led *led = &s_leds[s_led_count];
    *led = (struct pwm_led){
        .channel = (ledc_channel_t)s_led_count,
        .gamma = config->gamma,
    };

    ledc_channel_config_t channel = {
        .gpio_num = config->gpio,
        .speed_mode = SPEED_MODE,
        .channel = led->channel,
        .timer_sel = TIMER,
        .duty = 0,
        .hpoint = 0,
    };
    esp_err_t err = ledc_channel_config(&channel);
    if (err != ESP_OK) {
        return err;
    }

    s_led_count++;
    *ret_led = led;
    return ESP_OK;
}

static esp_err_t fade(struct pwm_led *led, uint32_t target, uint32_t ms, bool wait)
{
    ledc_fade_mode_t mode = wait ? LEDC_FADE_WAIT_DONE : LEDC_FADE_NO_WAIT;
    esp_err_t err;

    if (!led->gamma) {
        err = ledc_set_fade_time_and_start(SPEED_MODE, led->channel, target, ms, mode);
    } else {
        // Hardware fades are straight lines, so approximate the gamma curve
        // with a chain of short ones that the LEDC runs back to back.
        ledc_fade_param_config_t segments[SOC_LEDC_GAMMA_CURVE_FADE_RANGE_MAX];
        uint32_t segment_count;
        err = ledc_fill_multi_fade_param_list(SPEED_MODE, led->channel, led->level, target,
                                              GAMMA_FADE_SEGMENTS, ms, gamma_duty,
                                              SOC_LEDC_GAMMA_CURVE_FADE_RANGE_MAX,
                                              segments, &segment_count);
        if (err == ESP_OK) {
            err = ledc_set_multi_fade_and_start(SPEED_MODE, led->channel, gamma_duty(led->level),
                                                segments, segment_count, mode);
        }
    }

    // Record the target now: a later call waits for this fade to finish, so
    // it starts from here even when this one is still running.
    if (err == ESP_OK) {
        led->level = target;
    }
    return err;
}

// Fades run without waiting, and the pause between them doubles as the check
// for a stop request. The task never blocks inside a driver call with
// WAIT_DONE, which holds a driver lock that deleting the task would leak.
static void breathe_task(void *arg)
{
    struct pwm_led *led = arg;
    uint32_t target = DUTY_MAX;

    while (true) {
        fade(led, target, led->breathe_ms, false);
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(led->breathe_ms)) > 0) {
            break;
        }
        target = (target == 0) ? DUTY_MAX : 0;
    }

    led->breathe_task = NULL;
    xTaskNotifyGive(led->stopper);
    vTaskDelete(NULL);
}

esp_err_t pwm_led_stop(pwm_led_handle_t led)
{
    if (led == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (led->breathe_task == NULL) {
        return ESP_OK;
    }

    led->stopper = xTaskGetCurrentTaskHandle();
    xTaskNotifyGive(led->breathe_task);
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

    // Freeze the fade the task left running, and pick up where it got to.
    esp_err_t err = ledc_fade_stop(SPEED_MODE, led->channel);
    if (err == ESP_OK) {
        led->level = duty_to_level(led, ledc_get_duty(SPEED_MODE, led->channel));
    }
    return err;
}

esp_err_t pwm_led_breathe(pwm_led_handle_t led, uint32_t fade_ms)
{
    if (led == NULL || fade_ms == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t err = pwm_led_stop(led);
    if (err != ESP_OK) {
        return err;
    }

    led->breathe_ms = fade_ms;
    if (xTaskCreate(breathe_task, "pwm_led_breathe", BREATHE_STACK, led, BREATHE_PRIORITY,
                    &led->breathe_task) != pdPASS) {
        led->breathe_task = NULL;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

esp_err_t pwm_led_set(pwm_led_handle_t led, uint8_t percent)
{
    esp_err_t err = pwm_led_stop(led);
    if (err != ESP_OK) {
        return err;
    }
    uint32_t level = percent_to_level(percent);
    err = ledc_set_duty_and_update(SPEED_MODE, led->channel, level_to_duty(led, level), 0);
    if (err == ESP_OK) {
        led->level = level;
    }
    return err;
}

esp_err_t pwm_led_fade(pwm_led_handle_t led, uint8_t percent, uint32_t ms, bool wait)
{
    esp_err_t err = pwm_led_stop(led);
    if (err != ESP_OK) {
        return err;
    }
    return fade(led, percent_to_level(percent), ms, wait);
}
