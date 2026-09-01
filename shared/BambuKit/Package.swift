// swift-tools-version:6.0
import PackageDescription

// The protocol layer both status apps share: MQTT session and report decode,
// TLS trust roots, SSDP discovery, and the simulated source. Deliberately
// UI-free and declared for both platforms, so an accidental AppKit or UIKit
// import fails to build here rather than in one app's target later.
let package = Package(
    name: "BambuKit",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [
        .library(name: "BambuKit", targets: ["BambuKit"])
    ],
    dependencies: [
        .package(url: "https://github.com/swift-server-community/mqtt-nio.git", from: "2.11.0"),
        // BambuMQTTSource and BambuTrust import these directly (TLS config,
        // event loop groups), so they are declared products rather than
        // relied on as transitive dependencies of MQTTNIO.
        .package(url: "https://github.com/apple/swift-nio.git", from: "2.65.0"),
        .package(url: "https://github.com/apple/swift-nio-ssl.git", from: "2.27.0"),
        .package(url: "https://github.com/apple/swift-nio-transport-services.git", from: "1.20.0"),
        // RTSP client for the chamber camera. Our fork of steelbrain/IPCamKit
        // (MIT) on the `bambu-rtsps` branch: upstream has no TLS at all, so it
        // cannot open an rtsps:// URL, and its Digest auth sends an
        // `algorithm=MD5` the printer's LIVE555 server rejects. See that
        // branch's PATCHES.md. Pinned by revision, not branch, so the build is
        // reproducible and never moves underneath us.
        .package(
            url: "https://github.com/claust/IPCamKit.git",
            revision: "e1945a693ec0e573e953338073180374ed509d7f"),
    ],
    targets: [
        .target(
            name: "BambuKit",
            dependencies: [
                .product(name: "IPCamKit", package: "IPCamKit"),
                .product(name: "MQTTNIO", package: "mqtt-nio"),
                .product(name: "NIOCore", package: "swift-nio"),
                .product(name: "NIOPosix", package: "swift-nio"),
                .product(name: "NIOSSL", package: "swift-nio-ssl"),
                .product(name: "NIOTransportServices", package: "swift-nio-transport-services"),
            ],
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
        .testTarget(
            name: "BambuKitTests",
            dependencies: ["BambuKit", .product(name: "IPCamKit", package: "IPCamKit")],
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
