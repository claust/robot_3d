import Foundation

/// A decoded view of one Bambu `print` report (see ../RESEARCH.md for the
/// raw field reference). All decoding is tolerant: the printer mixes strings
/// and numbers freely between firmware versions.
struct PrinterSnapshot: Equatable {
    struct Nozzle: Equatable, Identifiable {
        let id: Int          // 0 = right, 1 = left
        var name: String { id == 1 ? "Left" : "Right" }
        var current: Double
        var target: Double
        var active: Bool
        var diameter: String
        var type: String
        var amsSlot: Int?    // 0-based AMS tray feeding this nozzle, nil if none
    }

    struct Tray: Equatable, Identifiable {
        let id: Int
        var type: String     // "PLA" or "" when empty
        var colorHex: String // RRGGBBAA
        var remainPercent: Int
        var isEmpty: Bool { type.isEmpty }
    }

    struct HMSAlert: Equatable, Identifiable {
        var id: String { code }
        let code: String     // "0300_0100_0001_0007"
        var wikiURL: URL? {
            URL(string: "https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/\(code)")
        }
    }

    var gcodeState = "UNKNOWN"     // IDLE / PREPARE / RUNNING / PAUSE / FINISH / FAILED …
    var jobName = ""
    var percent = 0
    var layer = 0
    var totalLayers = 0
    var remainingMinutes = 0
    var stageText: String?

    var nozzles: [Nozzle] = []
    var bedCurrent = 0.0
    var bedTarget = 0.0
    var chamberCurrent = 0.0

    var amsHumidityPercent: Int?
    var amsTemp: Double?
    var trays: [Tray] = []

    var partFanPercent = 0
    var auxFanPercent = 0
    var chamberFanPercent = 0
    var speedLevel = 2
    var speedMagnitude = 100
    var wifiSignal = ""
    var alerts: [HMSAlert] = []
    var printErrorCode = 0

    var isPrinting: Bool { ["RUNNING", "PREPARE", "PAUSE", "SLICING"].contains(gcodeState) }


    var speedLevelName: String {
        switch speedLevel {
        case 1: return "Silent"
        case 2: return "Standard"
        case 3: return "Sport"
        case 4: return "Ludicrous"
        default: return "—"
        }
    }
}

// Stage ids from pybambu const.py CURRENT_STAGE_IDS (subset we care about).
private let stageNames: [Int: String] = [
    1: "Auto bed leveling", 2: "Heatbed preheating", 3: "Sweeping XY mech mode",
    4: "Changing filament", 5: "M400 pause", 6: "Paused: filament runout",
    7: "Heating hotend", 8: "Calibrating extrusion", 9: "Scanning bed surface",
    10: "Inspecting first layer", 11: "Identifying build plate",
    12: "Calibrating micro lidar", 13: "Homing toolhead", 14: "Cleaning nozzle tip",
    15: "Checking extruder temperature", 16: "Paused by user",
    17: "Paused: front cover falling", 18: "Calibrating micro lidar",
    19: "Calibrating extrusion flow", 20: "Paused: nozzle temperature malfunction",
    21: "Paused: heat bed temperature malfunction", 22: "Filament unloading",
    23: "Paused: skipped step", 24: "Filament loading", 25: "Calibrating motor noise",
    26: "Paused: AMS lost", 27: "Paused: low fan speed (heat break)",
    28: "Paused: chamber temperature control error", 29: "Cooling chamber",
    30: "Paused by gcode", 31: "Motor noise showoff", 32: "Paused: nozzle filament covered",
    33: "Paused: cutter error", 34: "Paused: first layer error", 35: "Paused: nozzle clog",
]

/// Tolerant accessors — Bambu reports mix strings and numbers freely.
enum JSONValue {
    static func double(_ v: Any?) -> Double? {
        switch v {
        case let d as Double: return d
        case let i as Int: return Double(i)
        case let s as String: return Double(s)
        case let n as NSNumber: return n.doubleValue
        default: return nil
        }
    }
    static func int(_ v: Any?) -> Int? {
        double(v).map { Int($0) }
    }
    static func string(_ v: Any?) -> String? {
        switch v {
        case let s as String: return s
        case let n as NSNumber: return n.stringValue
        default: return nil
        }
    }
}

extension PrinterSnapshot {
    /// Decode from a merged `print` report dictionary.
    static func decode(from p: [String: Any]) -> PrinterSnapshot {
        var s = PrinterSnapshot()
        s.gcodeState = JSONValue.string(p["gcode_state"]) ?? "UNKNOWN"
        s.jobName = JSONValue.string(p["subtask_name"]) ?? ""
        s.percent = JSONValue.int(p["mc_percent"]) ?? 0
        s.layer = JSONValue.int(p["layer_num"]) ?? 0
        s.totalLayers = JSONValue.int(p["total_layer_num"]) ?? 0
        s.remainingMinutes = JSONValue.int(p["mc_remaining_time"]) ?? 0
        if let stg = JSONValue.int(p["stg_cur"]), let name = stageNames[stg] {
            s.stageText = name
        }

        // -- temperatures: prefer the new-schema packed `device` fields
        let device = p["device"] as? [String: Any]
        let unpack: (Int) -> (Double, Double) = { packed in
            (Double(packed & 0xFFFF), Double(packed >> 16))
        }
        if let bed = (device?["bed"] as? [String: Any])?["info"] as? [String: Any],
           let packed = JSONValue.int(bed["temp"]) {
            (s.bedCurrent, s.bedTarget) = unpack(packed)
        } else {
            s.bedCurrent = JSONValue.double(p["bed_temper"]) ?? 0
            s.bedTarget = JSONValue.double(p["bed_target_temper"]) ?? 0
        }
        if let ctc = (device?["ctc"] as? [String: Any])?["info"] as? [String: Any],
           let packed = JSONValue.int(ctc["temp"]) {
            s.chamberCurrent = unpack(packed).0
        } else {
            s.chamberCurrent = JSONValue.double(p["chamber_temper"]) ?? 0
        }

        // -- per-nozzle data (device.extruder + device.nozzle)
        var nozzleMeta: [Int: (String, String)] = [:]  // id -> (diameter, type)
        if let infos = (device?["nozzle"] as? [String: Any])?["info"] as? [[String: Any]] {
            for n in infos {
                guard let id = JSONValue.int(n["id"]) else { continue }
                let dia = JSONValue.double(n["diameter"]).map { String(format: "%.1f", $0) } ?? "?"
                nozzleMeta[id] = (dia, JSONValue.string(n["type"]) ?? "")
            }
        }
        if let ext = device?["extruder"] as? [String: Any],
           let infos = ext["info"] as? [[String: Any]] {
            let state = JSONValue.int(ext["state"]) ?? 0
            let activeID = (state >> 4) & 0xF
            for info in infos.sorted(by: { (JSONValue.int($0["id"]) ?? 0) < (JSONValue.int($1["id"]) ?? 0) }) {
                guard let id = JSONValue.int(info["id"]) else { continue }
                let packed = JSONValue.int(info["temp"]) ?? 0
                let (cur, tar) = unpack(packed)
                // snow: high byte = AMS unit (255 none, 254 external spool,
                // 128+ AMS HT), low byte = tray index (0-3 when real)
                var slot: Int? = nil
                if let snow = JSONValue.int(info["snow"]), snow >= 0 {
                    let ams = snow >> 8, tray = snow & 0xFF
                    if ams < 128, tray < 4 { slot = ams * 4 + tray }
                }
                let meta = nozzleMeta[id] ?? ("?", "")
                s.nozzles.append(Nozzle(id: id, current: cur, target: tar,
                                        active: id == activeID,
                                        diameter: meta.0, type: meta.1, amsSlot: slot))
            }
        }
        if s.nozzles.isEmpty {  // single-nozzle / old-schema fallback
            s.nozzles = [Nozzle(id: 0,
                                current: JSONValue.double(p["nozzle_temper"]) ?? 0,
                                target: JSONValue.double(p["nozzle_target_temper"]) ?? 0,
                                active: true,
                                diameter: JSONValue.string(p["nozzle_diameter"]) ?? "?",
                                type: JSONValue.string(p["nozzle_type"]) ?? "",
                                amsSlot: nil)]
        }

        // -- AMS
        if let units = (p["ams"] as? [String: Any])?["ams"] as? [[String: Any]],
           let unit = units.first {
            s.amsHumidityPercent = JSONValue.int(unit["humidity_raw"])
            s.amsTemp = JSONValue.double(unit["temp"])
            for tray in (unit["tray"] as? [[String: Any]]) ?? [] {
                guard let id = JSONValue.int(tray["id"]) else { continue }
                s.trays.append(Tray(id: id,
                                    type: JSONValue.string(tray["tray_type"]) ?? "",
                                    colorHex: JSONValue.string(tray["tray_color"]) ?? "00000000",
                                    remainPercent: JSONValue.int(tray["remain"]) ?? -1))
            }
        }

        // -- fans (raw 0-15 PWM), speed, misc
        let fanPercent: (String) -> Int = { key in
            let raw = JSONValue.int(p[key]) ?? 0
            return Int((Double(raw) * 100.0 / 15.0).rounded())
        }
        s.partFanPercent = fanPercent("cooling_fan_speed")
        s.auxFanPercent = fanPercent("big_fan1_speed")
        s.chamberFanPercent = fanPercent("big_fan2_speed")
        s.speedLevel = JSONValue.int(p["spd_lvl"]) ?? 2
        s.speedMagnitude = JSONValue.int(p["spd_mag"]) ?? 100
        s.wifiSignal = JSONValue.string(p["wifi_signal"]) ?? ""
        s.printErrorCode = JSONValue.int(p["print_error"]) ?? 0

        for alert in (p["hms"] as? [[String: Any]]) ?? [] {
            guard let attr = JSONValue.int(alert["attr"]),
                  let code = JSONValue.int(alert["code"]) else { continue }
            let hex = String(format: "%04X_%04X_%04X_%04X",
                             (attr >> 16) & 0xFFFF, attr & 0xFFFF,
                             (code >> 16) & 0xFFFF, code & 0xFFFF)
            s.alerts.append(HMSAlert(code: hex))
        }
        return s
    }
}

/// Merge an incoming report into an accumulated state dictionary.
/// Nested dictionaries merge recursively; everything else — arrays (e.g.
/// AMS trays) included — is replaced wholesale, and keys absent from the
/// incoming report are kept. The X2D usually sends full reports anyway.
func deepMerge(_ base: inout [String: Any], _ incoming: [String: Any]) {
    for (key, value) in incoming {
        if var baseDict = base[key] as? [String: Any],
           let newDict = value as? [String: Any] {
            deepMerge(&baseDict, newDict)
            base[key] = baseDict
        } else {
            base[key] = value
        }
    }
}
