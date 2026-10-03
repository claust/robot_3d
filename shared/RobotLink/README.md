# RobotLink

The Bluetooth side of the robot car remote ([ios/RobotRemote](../../ios/RobotRemote)):

| | |
|---|---|
| `DriveProtocol` | the GATT contract with [pi/robot_car/remote.py](../../pi/robot_car/remote.py): UUIDs, rate, the 3-byte command |
| `WheelSpeeds` | signed wheel speeds, and `arcade(x:y:)`, the one-thumb stick-to-wheels mix |
| `CarLink` | what the UI holds: the link's state and signal strength, and `wheels` to set; `simulated` for the iOS Simulator |
| `LinkMachine` | the connection logic as a pure state machine: scan, connect, find the drive service, time out, search again (internal) |
| `Radio` | CoreBluetooth on its own serial queue, running `LinkMachine`'s effects and the 20 Hz command stream off the main thread (internal) |

No UI, and declared for macOS 14 as well as iOS 17, so the mix, the
encoding and the connection logic are unit-tested on the Mac:

```sh
swift test --package-path shared/RobotLink
```
