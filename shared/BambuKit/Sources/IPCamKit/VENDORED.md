# IPCamKit — vendored

Pure-Swift RTSP client from https://github.com/steelbrain/IPCamKit (MIT, see
`LICENSE`), vendored at upstream commit `5d1a68eb03c1ba3c7fb8825313b0fc881d1e9761`
(2026-06-30).

Vendored rather than declared as a package dependency because it needs two
local changes to talk to a Bambu Lab printer, and SwiftPM cannot patch a
dependency. Both changes are worth sending upstream; the repo has open issues
with no maintainer reply, so nothing here waits on that.

## Local changes

1. **`Transport/RTSPTLS.swift` (new) + `Transport/RTSPConnection.swift`,
   `Client/RTSPSession.swift` — RTSPS support.** Upstream connects with
   `NWConnection(using: .tcp)` and has no TLS anywhere, so an `rtsps://` URL
   cannot be opened at all. `TLSOptions` adds a TLS posture (system trust,
   pinned anchors, or insecure) with optional hostname verification; an
   `rtsps://` URL now implies TLS and port 322.

2. **`Auth/RTSPAuth.swift` — do not send an unsolicited `algorithm=MD5`.**
   Upstream always emits `algorithm=` in the Digest response. RFC 7616 makes
   the parameter optional (absent means MD5), and the LIVE555 server on Bambu
   printers rejects an otherwise byte-identical, correctly computed digest
   when it is present — verified against an X2D with a controlled pair of
   requests differing only in that parameter:

       variant=plain     -> RTSP/1.0 200 OK
       variant=algorithm -> RTSP/1.0 401 Unauthorized

   It is now echoed back only when the server's own challenge named an
   algorithm.

Upstream's test suite is vendored alongside, minus `LiveIntegrationTests.swift`
and `RealCameraTests.swift` — those need a `mediamtx` binary and a physical
camera on the LAN.

## Known upstream quirk

`PublicVideoFrame.nalus` is documented as AVCC (4-byte length prefix) but
actually yields raw NAL bytes (upstream issue #9, unanswered). `BambuCameraSource`
detects and normalizes rather than trusting the doc comment.
