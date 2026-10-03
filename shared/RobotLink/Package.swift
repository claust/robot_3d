// swift-tools-version:6.0
import PackageDescription

// The Bluetooth side of the robot car remote: the drive protocol shared with
// pi/robot_car/remote.py, the thumbstick-to-wheels mix, and the CoreBluetooth
// link. UI-free and declared for both platforms, like BambuKit, so the iOS
// app holds only UI and the logic can be unit-tested on the Mac.
let package = Package(
    name: "RobotLink",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [
        .library(name: "RobotLink", targets: ["RobotLink"])
    ],
    targets: [
        .target(
            name: "RobotLink",
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
        .testTarget(
            name: "RobotLinkTests",
            dependencies: ["RobotLink"],
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
