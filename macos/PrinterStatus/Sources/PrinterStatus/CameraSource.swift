import AppKit
import Foundation

/// Live frames from the printer's chamber camera. The X2D serves RTSPS on
/// port 322, which AVFoundation cannot play, so a long-lived ffmpeg
/// subprocess transcodes the stream to MJPEG on stdout and frames are split
/// on the JPEG SOI/EOI markers. Read-only, like the MQTT source.
final class CameraSource {
    var onFrame: ((NSImage) -> Void)?
    var onStatus: ((String) -> Void)?

    /// Frames delivered per second. The camera itself streams 30 fps H.264;
    /// 5 fps MJPEG is plenty for monitoring and keeps CPU/decode cost low.
    private static let frameRate = 5

    private let config: PrinterConfig
    private let queue = DispatchQueue(label: "PrinterStatus.camera")
    private var process: Process?
    private var buffer = Data()
    private var stopped = false

    init(config: PrinterConfig) {
        self.config = config
    }

    func start() {
        queue.async { self.launch() }
    }

    func stop() {
        queue.async {
            self.stopped = true
            self.process?.terminate()
            self.process = nil
        }
    }

    // Homebrew (Apple Silicon and Intel) and MacPorts locations; the
    // installed app doesn't inherit a shell PATH, so search explicitly.
    private static let ffmpegCandidates = [
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/opt/local/bin/ffmpeg",
    ]

    private static func findFFmpeg() -> String? {
        ffmpegCandidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private func launch() {
        guard !stopped else { return }
        guard let ffmpeg = Self.findFFmpeg() else {
            onStatus?("ffmpeg not found — brew install ffmpeg")
            return
        }
        let url = "rtsps://bblp:\(config.accessCode)@\(config.ip):322/streaming/live/1"
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: ffmpeg)
        proc.arguments = [
            "-hide_banner", "-loglevel", "quiet",
            "-rtsp_transport", "tcp",
            "-i", url,
            "-an", "-f", "mjpeg", "-q:v", "4", "-r", "\(Self.frameRate)",
            "pipe:1",
        ]
        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = FileHandle.nullDevice
        out.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard let self, !data.isEmpty else { return }
            self.queue.async { self.consume(data) }
        }
        proc.terminationHandler = { [weak self] proc in
            out.fileHandleForReading.readabilityHandler = nil
            ChildReaper.unregister(proc.processIdentifier)
            guard let self else { return }
            self.queue.asyncAfter(deadline: .now() + 3) {
                guard !self.stopped else { return }
                self.buffer.removeAll()
                self.onStatus?("Camera reconnecting…")
                self.launch()
            }
        }
        do {
            try proc.run()
            ChildReaper.register(proc.processIdentifier)
            process = proc
            onStatus?("Camera connecting…")
        } catch {
            onStatus?("Camera failed: \(error.localizedDescription)")
        }
    }

    /// Append stream bytes and emit every complete JPEG. Inside a JPEG's
    /// entropy-coded data 0xFF is always stuffed with 0x00 or an RST marker,
    /// so scanning for the raw SOI/EOI byte pairs is safe here.
    private func consume(_ data: Data) {
        buffer.append(data)
        while true {
            guard let start = buffer.range(of: Data([0xFF, 0xD8, 0xFF])) else {
                // the marker may straddle a chunk boundary, so keep the last
                // two bytes — dropping them would swallow the next frame
                if buffer.count > 2 {
                    buffer.removeSubrange(
                        buffer.startIndex..<buffer.index(buffer.endIndex, offsetBy: -2))
                }
                return
            }
            guard let end = buffer.range(of: Data([0xFF, 0xD9]),
                                         in: start.upperBound..<buffer.endIndex) else {
                if start.lowerBound > buffer.startIndex {
                    buffer.removeSubrange(buffer.startIndex..<start.lowerBound)
                }
                // no complete frame yet; cap the buffer in case the stream
                // degenerates and never produces an end marker
                if buffer.count > 8 << 20 { buffer.removeAll(keepingCapacity: true) }
                return
            }
            let frame = buffer.subdata(in: start.lowerBound..<end.upperBound)
            buffer.removeSubrange(buffer.startIndex..<end.upperBound)
            if let image = NSImage(data: frame) {
                onFrame?(image)
            }
        }
    }
}
