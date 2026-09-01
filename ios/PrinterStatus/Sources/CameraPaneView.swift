import SwiftUI

/// The chamber camera as one card in the phone's scrolling column. The Mac
/// gives the stream half the window; here it keeps a 16:9 box so the cards
/// below it stay reachable, and tapping opens a full-screen viewer for a
/// closer look. The app is portrait-only, so that viewer is portrait too.
struct CameraPaneView: View {
    @ObservedObject var model: PrinterViewModel
    @State private var fullScreen = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            header
            videoArea
                .onTapGesture { if model.cameraFrame != nil { fullScreen = true } }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemGroupedBackground)))
        .fullScreenCover(isPresented: $fullScreen) {
            CameraFullScreenView(model: model)
        }
    }

    private var header: some View {
        HStack(spacing: 6) {
            Label("Chamber", systemImage: "video.fill")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
            // `isCameraLive` is a function of the clock, and SwiftUI only
            // re-evaluates on a publish. A stalled stream stops publishing —
            // which is exactly when the badge needs to drop — so it gets its
            // own clock. Only this two-element subtree ticks; a 2 s cadence
            // is enough for a 5 s freshness window.
            TimelineView(.periodic(from: .now, by: 2)) { _ in
                if model.isCameraLive {
                    HStack(spacing: 6) {
                        Circle().fill(.red).frame(width: 7, height: 7)
                        Text("LIVE")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.secondary)
                    }
                } else if let time = model.lastFrame {
                    Text(time.formatted(date: .omitted, time: .standard))
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                        .monospacedDigit()
                }
            }
        }
    }

    private var videoArea: some View {
        ZStack {
            if let frame = model.cameraFrame {
                // CGImage, not UIImage: the source is shared with the Mac app,
                // so it cannot hand back a UIKit type. The label goes in the
                // initializer: `decorative:` builds an image that is not an
                // accessibility element, which a later modifier should not
                // have to undo.
                Image(frame, scale: 1, label: Text("Live view of the printer's chamber"))
                    .resizable()
                    .scaledToFit()
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            } else {
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color(.tertiarySystemFill))
                    .aspectRatio(16 / 9, contentMode: .fit)
                    .overlay {
                        VStack(spacing: 8) {
                            Image(systemName: "video.slash")
                                .font(.title2)
                                .foregroundStyle(.tertiary)
                            Text(model.cameraStatus)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding(8)
                    }
            }
        }
    }
}

/// Full-screen chamber view: black background, image scaled to fit, so a
/// 1080p frame gets the whole screen instead of a card-sized slice.
struct CameraFullScreenView: View {
    @ObservedObject var model: PrinterViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if let frame = model.cameraFrame {
                Image(frame, scale: 1, label: Text("Live view of the printer's chamber"))
                    .resizable()
                    .scaledToFit()
            } else {
                Text(model.cameraStatus)
                    .font(.callout)
                    .foregroundStyle(.white.opacity(0.6))
            }
            VStack {
                HStack {
                    Spacer()
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2)
                            .symbolRenderingMode(.palette)
                            .foregroundStyle(.white, .white.opacity(0.25))
                    }
                    .padding()
                    .accessibilityLabel("Close the full-screen chamber view")
                }
                Spacer()
            }
        }
        .statusBarHidden()
    }
}
