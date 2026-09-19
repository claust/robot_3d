cmake_minimum_required(VERSION 3.22)

# Shared components for all esp32-c5 projects (pwm_led, ...).
set(EXTRA_COMPONENT_DIRS ../components)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(led_fade)
