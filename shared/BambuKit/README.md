# BambuKit

The protocol layer both status apps build on — the macOS window app
(`macos/PrinterStatus`) and its iPhone sibling (`ios/PrinterStatus`) each
depend on this package, so a protocol fix lands in both at once.

| | |
|---|---|
| `BambuMQTTSource` | LAN MQTT session: subscribe, `pushall`, reconnect forever |
| `BambuTrust` | Bambu's device-CA roots, vendored from Bambu Studio (internal) |
| `PrinterSnapshot` | tolerant decode of one `print` report, plus `deepMerge` |
| `PrinterConfig` | the three credentials; each app resolves them its own way |
| `PrinterDiscovery` / `DiscoveredPrinter` | find printers on the LAN by unicast M-SEARCH sweep; the `SSDP` wire format and probe behind it are internal |
| `PrinterNameSource` | the single-host case: the friendly name for a known IP |
| `SimulatedSource` | fake reports in the printer's own schema |

No UI. The package is declared for both macOS 14 and iOS 17, so an
accidental `import AppKit` fails here rather than in one app's build.

```sh
swift build --package-path shared/BambuKit
swift test --package-path shared/BambuKit   # SSDP parsing + subnet arithmetic
```

Discovery notes, including why it sweeps unicast instead of listening for
Bambu's broadcasts, are in [../../macos/RESEARCH.md](../../macos/RESEARCH.md)
and the doc comment on `PrinterDiscovery`.
