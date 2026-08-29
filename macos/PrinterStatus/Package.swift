// swift-tools-version:6.0
import PackageDescription

let package = Package(
    name: "PrinterStatus",
    platforms: [.macOS(.v14)],
    dependencies: [
        // The protocol layer, shared with the iOS app. See shared/BambuKit.
        .package(path: "../../shared/BambuKit")
    ],
    targets: [
        .executableTarget(
            name: "PrinterStatus",
            dependencies: [.product(name: "BambuKit", package: "BambuKit")],
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
