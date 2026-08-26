# Printer status data — research notes

What the Bambu Lab X2D exposes over the LAN, measured live against our printer
(2026-08-26, firmware ota 01.02.00.00, mid-print of `fit_test_02`) plus the
community docs (OpenBambuAPI, ha-bambulab/pybambu).

## Transport

- MQTT over TLS on port 8883, user `bblp` + LAN access code (same credentials
  as `cad/.env`). The printer's certificate is not publicly trusted: it
  chains to Bambu's own device CA (root shipped with Bambu Studio, vendored
  in `PrinterStatus/Sources/PrinterStatus/BambuTrust.swift`), and names the
  printer's serial rather than its IP.
- Subscribe to `device/<SERIAL>/report`. After one
  `{"pushing": {"command": "pushall"}}` request the X2D pushes a **full ~99-key
  report about once per second while printing** — no polling loop needed.
  When idle the push rate drops; send a `pushall` on reconnect and every few
  minutes as a keepalive refresh.
- Same MQTT channel accepts commands (`device/<SERIAL>/request`): pause /
  resume / stop, speed level, lights, target temps, AMS ops.

## Available fields (measured — `print.*` unless noted)

### Job & progress
| Field | Example | Meaning |
|---|---|---|
| `gcode_state` | `RUNNING` | IDLE / INIT / PREPARE / SLICING / RUNNING / PAUSE / FINISH / FAILED / OFFLINE |
| `subtask_name` | `fit_test_02` | job name |
| `gcode_file` | `/data/Metadata/plate_1.gcode` | file being printed |
| `mc_percent` | `92` | progress % |
| `layer_num` / `total_layer_num` | `37` / `45` | current / total layer |
| `mc_remaining_time` | `0` | minutes remaining |
| `mc_print_stage`, `stg_cur` | `2`, `0` | stage codes — `stg_cur`: 0 printing, 1 bed leveling, 2 bed preheat, 7 heating hotend, 10 first-layer inspect, 13 homing, 16 paused-by-user, 24 filament loading … (pybambu const.py `CURRENT_STAGE_IDS`; -1/255 = idle) |
| `print_error`, `mc_print_error_code` | `0` | error codes |
| `hms` | `[{attr, code, …}]` | active HMS health warnings; hex words of attr+code form the wiki code, e.g. `wiki.bambulab.com/en/x1/troubleshooting/hmscode/0300_0100_0001_0007` |

### Temperatures
| Field | Example | Meaning |
|---|---|---|
| `nozzle_temper` / `nozzle_target_temper` | `220.0` / `220.0` | **active** nozzle |
| `bed_temper` / `bed_target_temper` | `55.0` / `55.0` | bed |
| `device.extruder.info[i].temp` | `14418140` | per-nozzle, bit-packed: low 16 bits = current, high 16 = target (14418140 = 220/220 °C) |
| `device.bed.info.temp` | `3604535` | packed the same way (55/55 °C) |
| `device.ctc.info.temp` | `32` | chamber, packed the same way (heater off → target 0) |

The packed `device.*` fields are the only place both nozzles appear; the flat
`nozzle_temper` tracks whichever nozzle is active. Per pybambu: extruder
**id 0 = right, id 1 = left**; the active extruder index is
`(device.extruder.state >> 4) & 0xF` (low 4 bits = extruder count). Our
capture: `state = 0x8112` → 2 extruders, left one active at 220 °C while the
right sat at 41 °C. `info[i].snow` says which AMS slot feeds each nozzle
(low bits = tray, `>>8` = AMS unit; 255 = none, 254 = external spool).
If `device` is absent (older firmware), fall back to the flat fields.

### Fans, speed, environment
- `cooling_fan_speed`, `big_fan1_speed` (aux), `big_fan2_speed` (chamber),
  `heatbreak_fan_speed` — raw 0–15 PWM as strings; percent ≈ `v * 100 / 15`.
- `device.airduct.parts[]` — X2D's real fan/airduct percentages (`state`/`tar_state`).
- `spd_lvl` (1 silent / 2 standard / 3 sport / 4 ludicrous), `spd_mag` (%).
- `wifi_signal` (`-58dBm`), `lights_report` (chamber/work light on/off),
  `sdcard`, `xcam` (spaghetti detection etc. settings + `printing_monitor`).

### AMS (`ams.ams[]`)
Per unit: `humidity` (bucket 1–5), `humidity_raw` (%), `temp` (°C),
`dry_time`/`dry_setting` (drying state on AMS 2 Pro/HT), and per tray:
`tray_type` (PLA…), `tray_sub_brands`, `tray_color` (RRGGBBAA hex),
`remain` (%), `tray_info_idx` (profile code, GFA00 = Bambu PLA Basic),
nozzle temp range. An empty slot sends just `{"id": …}`. Matches our 4 slots
(black/white/blue/green). On dual-nozzle printers the active tray per nozzle
comes from `device.extruder.info[].snow`, not the classic `tray_now`.

### Hardware info (`device.nozzle`, `info.module[]`)
Both nozzles' `diameter` (0.4), `type` (HS01), `wear`; firmware versions per
module via `{"info": {"command": "get_version"}}`.

### Camera
`ipcam.rtsp_url` = `rtsps://<printer-ip>:322/streaming/live/1` — 1080p chamber
live view (user `bblp` + access code, self-signed TLS; playable with ffmpeg).
The field reads `"disable"` if "LAN Mode Liveview" is toggled off on the
touchscreen — ours has it enabled. Not needed for v1.

## Commands (topic `device/<SERIAL>/request`)

- `{"print": {"command": "pause" | "resume" | "stop", "param": ""}}`
- `{"print": {"command": "print_speed", "param": "1".."4"}}` (silent→ludicrous)
- `{"system": {"command": "ledctrl", "led_node": "chamber_light", "led_mode": "on"|"off"}}`
- `{"print": {"command": "gcode_line", "param": "M104 S220\n"}}` — temps via
  gcode: M104 nozzle, M140 bed, M141 chamber
- `{"pushing": {"command": "pushall"}}`, `{"info": {"command": "get_version"}}`
- AMS: `ams_control`, `ams_change_filament`, `ams_filament_drying`, …
- Caveat: newest firmware gates *some* control commands behind an "MQTT
  signature" in LAN mode; status reads are unaffected.

## Sources

- Live capture: `pushall` dump against our X2D (see `cad/printer_status.py`).
- https://github.com/Doridian/OpenBambuAPI/blob/main/mqtt.md (also video.md,
  ftp.md — FTPS port 990 implicit TLS).
- https://github.com/greghesp/ha-bambulab — pybambu `models.py` / `const.py` /
  `commands.py`: field decoding incl. H2D/X2D dual-nozzle handling.
