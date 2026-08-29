# Printer Status

Small macOS window app showing the Bambu X2D's live state: job + progress +
layers, left/right nozzle / bed / chamber temperatures, AMS slots (color,
type, remaining filament, humidity), fans, speed profile, and HMS alerts
(linked to the Bambu wiki). Read-only — it never sends print commands.

Data comes straight from the printer's LAN MQTT report stream (~1 update/s
while printing); see [../RESEARCH.md](../RESEARCH.md) for the protocol notes.
The protocol code itself lives in [BambuKit](../../shared/BambuKit), shared
with the iOS app; this package is the Mac's UI, config and camera on top of
it.

The right half of the window is the live chamber camera. The X2D serves it
as RTSPS on port 322, which AVFoundation can't play, so the app runs a small
`ffmpeg` subprocess that transcodes the stream to 5 fps MJPEG on a pipe
(`brew install ffmpeg` if missing — the pane says so). The stream
reconnects automatically if it drops; the LIVE badge is shown only while
frames are actually arriving.

The camera URL embeds the printer access code, so it is never passed as an
ffmpeg argument — `ps` would show it to anyone able to read this process's
arguments. It goes in over ffmpeg's stdin as a one-line concat playlist
instead, leaving the argument vector credential-free.

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

The TLS connection validates the printer's certificate chain against Bambu's
public device CA (vendored from Bambu Studio, see BambuKit's
`BambuTrust.swift`) —
hostname checks are off because the certificate names the printer's serial,
not its IP. Set `BAMBU_TLS_INSECURE=1` to skip verification (e.g. for a
non-Bambu test broker).

## Install as a Mac app

```
./install.sh
```

Builds a release bundle, installs it to `/Applications` (falling back to
`~/Applications`), and registers it with Spotlight — after that just
cmd-space and type "Printer Status". Use `./install.sh --local` to build the
bundle into `macos/` without installing.

On first launch macOS asks whether the app may find devices on the local
network — answer **Allow**, or it can't reach the printer. (It's granted per
app, which is why running from the terminal never asked.) You can change it
later in System Settings > Privacy & Security > Local Network.

Because the installed app lives outside the repo, it can't find `cad/.env`
by walking up from its own location. The installer writes
`~/Library/Application Support/PrinterStatus/config.env` containing a
`BAMBU_ENV_FILE=` line pointing at the repo's `cad/.env`, so the credentials
still live in exactly one place. Put the three `BAMBU_*` values directly in
that config file instead if you'd rather not depend on the repo.

## Headless checks (used by tooling)

```
swift run PrinterStatus --dump               # print one decoded status, exit
swift run PrinterStatus --discover           # sweep the LAN, list printers that answer
swift run PrinterStatus --snapshot out.png   # render the dashboard (simulated) to PNG
swift run PrinterStatus --snapshot out.png --live   # ...with live data + camera frame
```
