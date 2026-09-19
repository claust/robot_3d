idf_component_register(SRCS "pwm_led.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES esp_driver_ledc)
