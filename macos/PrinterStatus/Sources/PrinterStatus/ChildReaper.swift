import Foundation

/// Guarantees spawned helper processes (the camera's ffmpeg) die with the
/// app. Without this, quitting leaks an orphan that streams from the camera
/// forever — Foundation's Process does not tie a child's lifetime to ours.
/// Covers normal exit (atexit) and the catchable termination signals; only
/// SIGKILL can still leave an orphan behind.
enum ChildReaper {
    private static let lock = NSLock()
    private static var pids: Set<pid_t> = []
    private static var installed = false
    private static var signalSources: [any DispatchSourceSignal] = []

    static func register(_ pid: pid_t) {
        lock.lock()
        defer { lock.unlock() }
        installOnce()
        pids.insert(pid)
    }

    static func unregister(_ pid: pid_t) {
        lock.lock()
        defer { lock.unlock() }
        pids.remove(pid)
    }

    static func killAll() {
        lock.lock()
        let doomed = pids
        pids.removeAll()
        lock.unlock()
        // SIGKILL, not SIGTERM: ffmpeg holds no state worth a graceful stop,
        // and one blocked in a pipe write can shrug off SIGTERM (seen live).
        for pid in doomed { kill(pid, SIGKILL) }
    }

    private static func installOnce() {
        guard !installed else { return }
        installed = true
        atexit { ChildReaper.killAll() }
        for sig in [SIGTERM, SIGINT, SIGHUP] {
            signal(sig, SIG_IGN)  // route through the dispatch source instead
            let source = DispatchSource.makeSignalSource(signal: sig, queue: .global())
            source.setEventHandler {
                killAll()
                exit(128 + sig)
            }
            source.resume()
            signalSources.append(source)
        }
    }
}
