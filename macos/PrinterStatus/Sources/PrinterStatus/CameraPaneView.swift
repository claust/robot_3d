import SwiftUI

/// Right half of the split view: the live chamber camera. Styled like the
/// Glow schematic card — dark chamber, rounded, quiet border.
struct CameraPaneView: View {
    var model: PrinterViewModel

    var body: some View {
        VStack(spacing: 8) {
            header
            videoArea
            footer
        }
        .padding(12)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.black.opacity(0.82)))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(.quaternary, lineWidth: 1))
    }

    private var header: some View {
        HStack(spacing: 6) {
            Label("Chamber", systemImage: "video.fill")
                .font(.caption)
                .foregroundStyle(Color.white.opacity(0.55))
            Spacer()
            // `isLive` is a function of the clock, and SwiftUI only
            // re-evaluates on a publish. A stalled stream stops publishing —
            // which is exactly when the badge needs to drop — so it gets its
            // own clock. Only this two-element subtree ticks; a 2 s cadence
            // is enough for a 5 s freshness window.
            TimelineView(.periodic(from: .now, by: 2)) { _ in
                if isLive {
                    HStack(spacing: 6) {
                        Circle().fill(.red).frame(width: 7, height: 7)
                        Text("LIVE")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(Color.white.opacity(0.85))
                    }
                }
            }
        }
    }

    private var videoArea: some View {
        ZStack {
            if let frame = model.cameraFrame {
                // CGImage, not NSImage: the source is shared with the iOS
                // app, so it cannot hand back an AppKit type. The labeled
                // initializer, not `decorative:` — this is the pane's primary
                // content, and `decorative:` makes it no accessibility
                // element at all.
                Image(frame, scale: 1, label: Text("Live view of the printer's chamber"))
                    .resizable()
                    .scaledToFit()
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .transition(.opacity)
            } else {
                RoundedRectangle(cornerRadius: 6)
                    .fill(Color.white.opacity(0.06))
                    .aspectRatio(16 / 9, contentMode: .fit)
                    .overlay {
                        VStack(spacing: 8) {
                            Image(systemName: "video.slash")
                                .font(.title2)
                                .foregroundStyle(Color.white.opacity(0.3))
                            Text(model.cameraStatus)
                                .font(.caption)
                                .foregroundStyle(Color.white.opacity(0.5))
                                .multilineTextAlignment(.center)
                        }
                        .padding(8)
                    }
            }
        }
    }

    private var footer: some View {
        HStack {
            Spacer()
            if let time = model.lastFrame {
                Text(time.formatted(date: .omitted, time: .standard))
                    .font(.caption2)
                    .foregroundStyle(Color.white.opacity(0.4))
                    .monospacedDigit()
            } else {
                Text(" ")  // keep the row height stable before the first frame
                    .font(.caption2)
            }
        }
    }

    /// "Live" only while frames are actually fresh — the stream delivers
    /// several per second, so anything older than a few seconds is stale.
    private var isLive: Bool {
        guard let time = model.lastFrame else { return false }
        return Date().timeIntervalSince(time) < 5
    }
}
