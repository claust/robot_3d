import Foundation

/// Fake data source that emits reports in the printer's own JSON schema,
/// so the whole decode path is exercised. Simulates a 45-layer print.
final class SimulatedSource {
    private var task: Task<Void, Never>?
    var onReport: (([String: Any]) -> Void)?

    func start() {
        stop()  // idempotent: never run two simulation loops
        // detached: don't inherit the caller's (Main)actor — onReport hops
        // back to the main actor itself
        task = Task.detached { [weak self] in
            var tick = 0
            while !Task.isCancelled {
                self?.onReport?(SimulatedSource.report(tick: tick))
                tick += 1
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }

    func stop() {
        task?.cancel()
        task = nil
    }

    static func report(tick: Int) -> [String: Any] {
        let totalLayers = 45
        let secondsPerLayer = 8
        let layer = min(totalLayers, 1 + tick / secondsPerLayer)
        let percent = min(100, layer * 100 / totalLayers)
        let finished = layer >= totalLayers
        let wiggle = { (base: Double) in base + Double((tick * 7) % 10) / 10.0 - 0.5 }

        let pack = { (cur: Int, tar: Int) in (tar << 16) | cur }
        let nozzleCur = finished ? 180 : Int(wiggle(220))
        let bedCur = finished ? 50 : Int(wiggle(55))

        return [
            "gcode_state": finished ? "FINISH" : "RUNNING",
            "subtask_name": "simulated_print",
            "mc_percent": percent,
            "layer_num": layer,
            "total_layer_num": totalLayers,
            "mc_remaining_time": max(0, (totalLayers - layer) * secondsPerLayer / 60 + 1),
            "stg_cur": 0,
            "spd_lvl": 2,
            "spd_mag": 100,
            "wifi_signal": "-58dBm",
            "cooling_fan_speed": "14",
            "big_fan1_speed": "11",
            "big_fan2_speed": "9",
            "print_error": 0,
            "hms": [] as [[String: Any]],
            "device": [
                "extruder": [
                    // two extruders, left (id 1) active
                    "state": 0x8112,
                    "info": [
                        ["id": 0, "temp": pack(41, 0), "snow": 0xFF00],
                        ["id": 1, "temp": pack(nozzleCur, finished ? 0 : 220), "snow": 1],
                    ],
                ],
                "nozzle": [
                    "info": [
                        ["id": 0, "diameter": 0.4, "type": "HS01"],
                        ["id": 1, "diameter": 0.4, "type": "HS01"],
                    ]
                ],
                "bed": ["info": ["temp": pack(bedCur, finished ? 0 : 55)]],
                "ctc": ["info": ["temp": pack(Int(wiggle(32)), 0)]],
            ],
            "ams": [
                "ams": [
                    [
                        "id": "0", "humidity": "2", "humidity_raw": "39", "temp": "29.7",
                        "tray": [
                            ["id": "0", "tray_type": "PLA", "tray_color": "000000FF", "remain": 82],
                            ["id": "1", "tray_type": "PLA", "tray_color": "FFFFFFFF", "remain": 100],
                            ["id": "2", "tray_type": "PLA", "tray_color": "0A2989FF", "remain": 64],
                            ["id": "3", "tray_type": "PLA", "tray_color": "16C344FF", "remain": 91],
                        ],
                    ]
                ]
            ],
        ]
    }
}
