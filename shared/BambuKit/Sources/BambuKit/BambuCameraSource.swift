import CoreGraphics
import CoreMedia
import CoreVideo
import Foundation
import IPCamKit
import VideoToolbox

/// Live frames from the printer's chamber camera, decoded in-process.
///
/// The X2D serves RTSPS on port 322 — RTSP over TLS, which AVFoundation cannot
/// play on any Apple platform. The stream is read with our IPCamKit fork
/// (RTP interleaved over the same TLS connection, so no UDP and no second
/// socket), depacketized to H.264 and decoded by VideoToolbox. Read-only, like
/// the MQTT source: the session only ever sends DESCRIBE/SETUP/PLAY/TEARDOWN.
///
/// Emitting `CGImage` rather than a platform image type is what lets both apps
/// share this: `NSImage`/`UIImage` would drag AppKit or UIKit into BambuKit.
public final class BambuCameraSource {
    /// Called on a background task for each delivered frame.
    public var onFrame: ((CGImage) -> Void)?
    public var onStatus: ((String) -> Void)?

    /// Frames handed to the UI per second. The camera streams H.264 at ~30 fps
    /// and every frame is decoded to keep the reference chain intact, but only
    /// this many become images — the rest are decoded with
    /// `kVTDecodeFrame_DoNotOutputFrame`, which is where the savings are. A
    /// monitoring view gains nothing from 30 fps, and a phone pays for it.
    private static let emitFrameRate: Double = 12

    /// Delay before redialing a dropped stream. The old ffmpeg-based source
    /// used the same 3 s.
    private static let reconnectDelay: Duration = .seconds(3)

    private let config: PrinterConfig
    private var task: Task<Void, Never>?
    private var stream: Stream?

    public init(config: PrinterConfig) {
        self.config = config
    }

    /// Stops the stream if the owner simply lets the source go. Reachable only
    /// because the task holds the `Stream`, not `self` — see `start()`.
    deinit {
        task?.cancel()
        stream?.tearDown()
    }

    public func start() {
        guard task == nil else { return }
        // The running task must not hold `self`. `Task { await self.run() }`
        // would: the source owns the task and the task's frame owns the source
        // for as long as the loop runs, which is forever. An owner that just
        // dropped the source would then never see `deinit`, and the stream
        // would keep decoding and holding the network for the life of the
        // process. The `Stream` owns everything the loop needs instead, so the
        // source stays free to deallocate — and its `deinit` can stop things.
        let stream = Stream(config: config, onFrame: onFrame, onStatus: onStatus)
        self.stream = stream
        task = Task { await stream.run() }
    }

    public func stop() {
        task?.cancel()
        task = nil
        stream?.tearDown()
        stream = nil
    }
}

/// The streaming loop and everything it needs, owned by the task rather than
/// by ``BambuCameraSource``. The callbacks are taken once at `start()`.
private final class Stream: @unchecked Sendable {
    /// Frames handed to the UI per second. The camera streams H.264 at ~30 fps
    /// and every frame is decoded to keep the reference chain intact, but only
    /// this many become images — the rest are decoded with
    /// `kVTDecodeFrame_DoNotOutputFrame`, which is where the savings are. A
    /// monitoring view gains nothing from 30 fps, and a phone pays for it.
    private static let emitFrameRate: Double = 12

    /// Delay before redialing a dropped stream. The old ffmpeg-based source
    /// used the same 3 s.
    private static let reconnectDelay: Duration = .seconds(3)

    private let config: PrinterConfig
    private let onFrame: ((CGImage) -> Void)?
    private let onStatus: ((String) -> Void)?
    /// The live session, so `tearDown()` can end it instead of waiting for the
    /// streaming task to notice it was cancelled.
    private let live = LiveSession()
    /// Harvested once and reused across reconnects; cleared when a connection
    /// fails before delivering anything, in case the printer's CA rotated.
    private var deviceCA: [Data]?

    init(
        config: PrinterConfig,
        onFrame: ((CGImage) -> Void)?,
        onStatus: ((String) -> Void)?
    ) {
        self.config = config
        self.onFrame = onFrame
        self.onStatus = onStatus
    }

    /// Ends the RTSP session now. Cancellation unwinds the loop, but the
    /// session is state held on the printer — an unsent TEARDOWN leaves it
    /// streaming to nobody. `Task` here is unstructured, so it is not itself
    /// cancelled.
    func tearDown() {
        if let session = live.take() {
            Task { await session.stop() }
        }
    }

    func run() async {
        while !Task.isCancelled {
            var delivered = false
            do {
                try await connectAndStream(delivered: &delivered)
            } catch is CancellationError {
                return
            } catch {
                if Task.isCancelled { return }
                if !delivered { deviceCA = nil }
                onStatus?(Self.describe(error))
            }
            if Task.isCancelled { return }
            do {
                try await Task.sleep(for: Self.reconnectDelay)
            } catch {
                return  // cancelled while waiting to retry
            }
        }
    }

    private func connectAndStream(delivered: inout Bool) async throws {
        let anchors = try await anchorCertificates()
        try Task.checkCancellation()

        let session = RTSPClientSession(
            url: "rtsps://\(config.ip):322/streaming/live/1",
            credentials: Credentials(username: "bblp", password: config.accessCode),
            transport: .tcp,
            userAgent: "PrinterStatus",
            // The leaf names the printer's serial rather than its address, so
            // the hostname check has to be off; the chain itself is verified
            // against Bambu's roots plus the harvested device CA.
            tls: TLSOptions(trust: .pinnedRoots(anchors), verifyHostname: false)
        )
        // Registered before `start()`: a cancellation or a throw in the
        // handshake would otherwise leave a session nothing could reach, since
        // a `defer` placed after it is never installed.
        live.set(session)
        defer {
            if let session = live.take() {
                Task { await session.stop() }
            }
        }
        onStatus?("Camera connecting…")
        let description = try await session.start()

        let decoder = H264Decoder()
        // Parameter sets normally arrive in the SDP's sprop-parameter-sets; the
        // per-frame ones only appear when they change mid-stream.
        decoder.update(sps: description.video?.sps, pps: description.video?.pps)

        var lastEmit = ContinuousClock.now
        let emitInterval = Duration.seconds(1 / Self.emitFrameRate)

        for try await item in session.frames() {
            try Task.checkCancellation()
            guard case .video(let frame) = item else { continue }
            decoder.update(sps: frame.sps, pps: frame.pps)

            let now = ContinuousClock.now
            let emit = now - lastEmit >= emitInterval
            guard let image = decoder.decode(frame.nalus, emit: emit) else { continue }
            lastEmit = now
            delivered = true
            onFrame?(image)
        }
    }

    private func anchorCertificates() async throws -> [Data] {
        if let deviceCA {
            return BambuTrust.rootCertificateDERs + deviceCA
        }
        onStatus?("Camera: checking certificate…")
        let intermediates = try await BambuDeviceCA.harvest(host: config.ip)
        deviceCA = intermediates
        return BambuTrust.rootCertificateDERs + intermediates
    }

    private static func describe(_ error: Error) -> String {
        if let harvest = error as? BambuDeviceCA.HarvestError {
            return "Camera: \(harvest.description)"
        }
        return "Camera reconnecting — \(error.localizedDescription)"
    }
}

/// Holder for the session in flight, so `stop()` on one thread and the
/// streaming task on another agree on who tears it down. `take()` hands it
/// over exactly once, which is what keeps a stop and a normal unwind from both
/// calling `stop()` on the same session.
private final class LiveSession: @unchecked Sendable {
    private let lock = NSLock()
    private var session: RTSPClientSession?

    func set(_ session: RTSPClientSession) {
        lock.lock()
        self.session = session
        lock.unlock()
    }

    func take() -> RTSPClientSession? {
        lock.lock()
        defer { lock.unlock() }
        let session = self.session
        self.session = nil
        return session
    }
}

/// Minimal H.264 decoder: parameter sets in, `CGImage` out.
private final class H264Decoder {
    private var session: VTDecompressionSession?
    private var format: CMVideoFormatDescription?
    private var sps: Data?
    private var pps: Data?

    deinit {
        if let session {
            VTDecompressionSessionInvalidate(session)
        }
    }

    /// Adopt new parameter sets, dropping any session built on the old ones.
    /// `nil` arguments mean "unchanged", which is how the stream signals that
    /// this frame carries no new parameter set.
    func update(sps newSPS: Data?, pps newPPS: Data?) {
        var changed = false
        if let newSPS, newSPS != sps {
            sps = newSPS
            changed = true
        }
        if let newPPS, newPPS != pps {
            pps = newPPS
            changed = true
        }
        guard changed else { return }
        if let session {
            VTDecompressionSessionInvalidate(session)
        }
        session = nil
        format = nil
    }

    /// Decode one access unit. Pass `emit: false` to keep the reference chain
    /// current without paying for an image.
    func decode(_ nalus: [Data], emit: Bool) -> CGImage? {
        guard let sampleBuffer = makeSampleBuffer(nalus) else { return nil }
        guard let session = decompressionSession() else { return nil }

        // Only the emitting path needs somewhere to put an image; a throttled
        // frame is decoded for the reference chain alone. The box's presence is
        // then what tells the handler whether to produce one.
        let box = emit ? ImageBox() : nil
        let flags: VTDecodeFrameFlags = emit ? [] : [._DoNotOutputFrame]
        let status = VTDecompressionSessionDecodeFrame(
            session, sampleBuffer: sampleBuffer, flags: flags, infoFlagsOut: nil
        ) { status, _, imageBuffer, _, _ in
            guard status == noErr, let box, let imageBuffer else { return }
            var image: CGImage?
            guard VTCreateCGImageFromCVPixelBuffer(imageBuffer, options: nil, imageOut: &image)
                == noErr
            else { return }
            box.image = image
        }
        guard status == noErr else {
            // A decoder that has lost its session (parameter change, hardware
            // reset) is rebuilt on the next frame rather than failing the run.
            VTDecompressionSessionInvalidate(session)
            self.session = nil
            return nil
        }
        // Nothing to collect on the throttled path: the frame was decoded with
        // `_DoNotOutputFrame` purely to keep the reference chain current.
        guard let box else { return nil }
        // Without the asynchronous flag the handler runs before this returns;
        // waiting makes that a guarantee rather than an assumption.
        VTDecompressionSessionWaitForAsynchronousFrames(session)
        return box.image
    }

    private func decompressionSession() -> VTDecompressionSession? {
        if let session { return session }
        guard let format = formatDescription() else { return nil }
        var created: VTDecompressionSession?
        let status = VTDecompressionSessionCreate(
            allocator: kCFAllocatorDefault, formatDescription: format,
            decoderSpecification: nil,
            imageBufferAttributes: [
                kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
            ] as CFDictionary,
            outputCallback: nil, decompressionSessionOut: &created)
        guard status == noErr else { return nil }
        session = created
        return created
    }

    private func formatDescription() -> CMVideoFormatDescription? {
        if let format { return format }
        guard let sps, let pps else { return nil }
        var created: CMVideoFormatDescription?
        let status: OSStatus = sps.withUnsafeBytes { spsBytes in
            pps.withUnsafeBytes { ppsBytes in
                guard let spsBase = spsBytes.baseAddress, let ppsBase = ppsBytes.baseAddress
                else { return OSStatus(-1) }
                let pointers = [
                    spsBase.assumingMemoryBound(to: UInt8.self),
                    ppsBase.assumingMemoryBound(to: UInt8.self),
                ]
                let sizes = [sps.count, pps.count]
                return CMVideoFormatDescriptionCreateFromH264ParameterSets(
                    allocator: kCFAllocatorDefault, parameterSetCount: 2,
                    parameterSetPointers: pointers, parameterSetSizes: sizes,
                    nalUnitHeaderLength: 4, formatDescriptionOut: &created)
            }
        }
        guard status == noErr else { return nil }
        format = created
        return created
    }

    private func makeSampleBuffer(_ nalus: [Data]) -> CMSampleBuffer? {
        guard let format = formatDescription() else { return nil }
        var payload = Self.avcc(nalus)
        guard !payload.isEmpty else { return nil }

        var blockBuffer: CMBlockBuffer?
        // The block buffer copies (kCFAllocatorDefault as the block allocator),
        // so `payload` may go out of scope while the sample buffer lives on.
        let blockStatus = payload.withUnsafeMutableBytes { bytes -> OSStatus in
            CMBlockBufferCreateWithMemoryBlock(
                allocator: kCFAllocatorDefault, memoryBlock: nil,
                blockLength: bytes.count, blockAllocator: kCFAllocatorDefault,
                customBlockSource: nil, offsetToData: 0, dataLength: bytes.count,
                flags: 0, blockBufferOut: &blockBuffer)
        }
        guard blockStatus == kCMBlockBufferNoErr, let blockBuffer else { return nil }
        let copyStatus = payload.withUnsafeBytes { bytes -> OSStatus in
            guard let base = bytes.baseAddress else { return OSStatus(-1) }
            return CMBlockBufferReplaceDataBytes(
                with: base, blockBuffer: blockBuffer, offsetIntoDestination: 0,
                dataLength: bytes.count)
        }
        guard copyStatus == kCMBlockBufferNoErr else { return nil }

        var sampleBuffer: CMSampleBuffer?
        var sampleSize = payload.count
        let status = CMSampleBufferCreateReady(
            allocator: kCFAllocatorDefault, dataBuffer: blockBuffer,
            formatDescription: format, sampleCount: 1, sampleTimingEntryCount: 0,
            sampleTimingArray: nil, sampleSizeEntryCount: 1,
            sampleSizeArray: &sampleSize, sampleBufferOut: &sampleBuffer)
        guard status == noErr else { return nil }
        return sampleBuffer
    }

    /// Concatenate NAL units in AVCC form (4-byte big-endian length prefix).
    /// IPCamKit documents `nalus` as already prefixed but yields raw NAL bytes
    /// (upstream issue #9), so each unit is measured rather than trusted.
    private static func avcc(_ nalus: [Data]) -> Data {
        var out = Data()
        // One allocation rather than a growth curve: this runs for every
        // decoded frame, and a 1080p keyframe here is ~100 kB. The 4 bytes per
        // unit over-reserve slightly for units that already carry their
        // prefix, which is the harmless direction for a capacity hint.
        out.reserveCapacity(nalus.reduce(0) { $0 + $1.count + 4 })
        for nalu in nalus where !nalu.isEmpty {
            let prefixed =
                nalu.count >= 4
                && Int(nalu.prefix(4).reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }) == nalu.count - 4
            if prefixed {
                out.append(nalu)
            } else {
                var length = UInt32(nalu.count).bigEndian
                withUnsafeBytes(of: &length) { out.append(contentsOf: $0) }
                out.append(nalu)
            }
        }
        return out
    }

    /// The decode handler is invoked before `DecodeFrame` returns, but it is
    /// still a closure crossing a C boundary, so the result travels in a box.
    private final class ImageBox: @unchecked Sendable {
        var image: CGImage?
    }
}
