#include "pwm_led.h"

#include <math.h>

#include "driver/ledc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
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
    SemaphoreHandle_t lock;     // serializes the public calls on this LED
    StaticSemaphore_t lock_buf;
    TaskHandle_t breathe_task;  // NULL unless breathing
    // Given by the breathing task as it exits. A private semaphore, not the
    // stopper's task notification, which belongs to the caller's own code.
    SemaphoreHandle_t exited;
    StaticSemaphore_t exited_buf;
    uint32_t breathe_ms;
};

static struct pwm_led s_leds[SOC_LEDC_CHANNEL_NUM];
static int s_led_count;
// Separate from s_led_count: a first LED whose channel setup fails must not
// leave the fade service installed with a count of 0, or every retry would
// try to install it again and fail.
static bool s_shared_ready;

// Guards s_leds/s_led_count and the shared setup, so pwm_led_new can be
// called from several tasks. Created on first use; the spinlock only
// settles which task's mutex wins if two get here at once.
static SemaphoreHandle_t s_new_lock;
static portMUX_TYPE s_new_lock_init = portMUX_INITIALIZER_UNLOCKED;

static bool take_new_lock(void)
{
    if (s_new_lock == NULL) {
        SemaphoreHandle_t lock = xSemaphoreCreateMutex();
        if (lock == NULL) {
            return false;
        }
        taskENTER_CRITICAL(&s_new_lock_init);
        if (s_new_lock == NULL) {
            s_new_lock = lock;
            lock = NULL;
        }
        taskEXIT_CRITICAL(&s_new_lock_init);
        if (lock != NULL) {
            vSemaphoreDelete(lock);
        }
    }
    xSemaphoreTake(s_new_lock, portMAX_DELAY);
    return true;
}

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

// The shared timer and the fade service are set up once, with the first LED
// that gets this far.
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

static esp_err_t new_locked(const pwm_led_config_t *config, pwm_led_handle_t *ret_led)
{
    if (s_led_count == SOC_LEDC_CHANNEL_NUM) {
        return ESP_ERR_NO_MEM;
    }
    if (!s_shared_ready) {
        esp_err_t err = init_shared();
        if (err != ESP_OK) {
            return err;
        }
        s_shared_ready = true;
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

    led->lock = xSemaphoreCreateMutexStatic(&led->lock_buf);
    led->exited = xSemaphoreCreateBinaryStatic(&led->exited_buf);
    s_led_count++;
    *ret_led = led;
    return ESP_OK;
}

esp_err_t pwm_led_new(const pwm_led_config_t *config, pwm_led_handle_t *ret_led)
{
    if (config == NULL || ret_led == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!take_new_lock()) {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t err = new_locked(config, ret_led);
    xSemaphoreGive(s_new_lock);
    return err;
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
    xSemaphoreGive(led->exited);
    vTaskDelete(NULL);
}

// The public calls below take led->lock; the *_locked helpers assume it's
// held. The breathing task never takes it, so stop can wait for the task
// while holding it.
static esp_err_t stop_locked(struct pwm_led *led)
{
    if (led->breathe_task == NULL) {
        return ESP_OK;
    }

    // The breathing task is ours, so its notification slot is free to use.
    xTaskNotifyGive(led->breathe_task);
    xSemaphoreTake(led->exited, portMAX_DELAY);

    // Freeze the fade the task left running, and pick up where it got to.
    esp_err_t err = ledc_fade_stop(SPEED_MODE, led->channel);
    if (err == ESP_OK) {
        led->level = duty_to_level(led, ledc_get_duty(SPEED_MODE, led->channel));
    }
    return err;
}

static esp_err_t breathe_locked(struct pwm_led *led, uint32_t fade_ms)
{
    esp_err_t err = stop_locked(led);
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

static esp_err_t set_locked(struct pwm_led *led, uint8_t percent)
{
    esp_err_t err = stop_locked(led);
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

static esp_err_t fade_locked(struct pwm_led *led, uint8_t percent, uint32_t ms, bool wait)
{
    esp_err_t err = stop_locked(led);
    if (err != ESP_OK) {
        return err;
    }
    return fade(led, percent_to_level(percent), ms, wait);
}

esp_err_t pwm_led_stop(pwm_led_handle_t led)
{
    if (led == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreTake(led->lock, portMAX_DELAY);
    esp_err_t err = stop_locked(led);
    xSemaphoreGive(led->lock);
    return err;
}

esp_err_t pwm_led_breathe(pwm_led_handle_t led, uint32_t fade_ms)
{
    if (led == NULL || fade_ms == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreTake(led->lock, portMAX_DELAY);
    esp_err_t err = breathe_locked(led, fade_ms);
    xSemaphoreGive(led->lock);
    return err;
}

esp_err_t pwm_led_set(pwm_led_handle_t led, uint8_t percent)
{
    if (led == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreTake(led->lock, portMAX_DELAY);
    esp_err_t err = set_locked(led, percent);
    xSemaphoreGive(led->lock);
    return err;
}

esp_err_t pwm_led_fade(pwm_led_handle_t led, uint8_t percent, uint32_t ms, bool wait)
{
    if (led == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreTake(led->lock, portMAX_DELAY);
    esp_err_t err = fade_locked(led, percent, ms, wait);
    xSemaphoreGive(led->lock);
    return err;
}
