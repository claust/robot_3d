idf_component_register(SRCS "srf08_range_main.c" "srf08.c"
                       PRIV_REQUIRES esp_driver_i2c
                       INCLUDE_DIRS ".")
