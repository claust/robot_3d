# Printer Status

Small macOS window app showing the Bambu X2D's live state: job + progress +
layers, left/right nozzle / bed / chamber temperatures, AMS slots (color,
type, remaining filament, humidity), fans, speed profile, and HMS alerts
(linked to the Bambu wiki). Read-only — it never sends print commands.

Data comes straight from the printer's LAN MQTT report stream (~1 update/s
while printing); see [../RESEARCH.md](../RESEARCH.md) for the protocol notes.

## Run

```
cd macos/PrinterStatus
swift run PrinterStatus              # live data (needs credentials, see below)
swift run PrinterStatus --simulate   # fake animated print, no printer needed
```

The window has a Live/Simulate toggle. Credentials are the same ones the
print pipeline uses: `BAMBU_PRINTER_IP`, `BAMBU_PRINTER_SERIAL`,
`BAMBU_ACCESS_CODE` from the environment, or found by walking up from the
working directory to the repo's `cad/.env`.

## Standalone app

```
./make_app.sh    # -> ../PrinterStatus.app (ad-hoc signed, gitignored)
```

## Headless checks (used by tooling)

```
swift run PrinterStatus --dump               # print one decoded status, exit
swift run PrinterStatus --snapshot out.png   # render the dashboard (simulated) to PNG
```
