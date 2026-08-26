// swift-tools-version:6.0
import PackageDescription

let package = Package(
    name: "PrinterStatus",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/swift-server-community/mqtt-nio.git", from: "2.11.0")
    ],
    targets: [
        .executableTarget(
            name: "PrinterStatus",
            dependencies: [.product(name: "MQTTNIO", package: "mqtt-nio")],
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
