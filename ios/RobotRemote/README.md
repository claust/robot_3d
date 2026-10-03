# Robot Remote (iOS)

Drives the robot car from an iPhone over Bluetooth LE, one thumb on a
floating stick. Wherever the thumb lands in the bottom panel becomes the
centre. Up drives both wheels forward, down both back, sideways spins the car
on the spot, and anything between is an arc. Lifting the thumb stops the car.
The two bars show what each wheel is being told, and "Top speed" caps both.

The first time, iOS asks for a pairing code: the car only takes commands
from a phone that has paired with the passkey its Pi logs. See
[Pairing a phone](../../pi/robot_car/README.md#pairing-a-phone).

With VoiceOver, Voice Control or Switch Control the stick is one
adjustable control named Drive. Swipe up or down to step the speed by a
quarter, use its actions to turn left, turn right, go straight or stop,
or stop with the escape or magic-tap gesture. That command holds until it
is changed, and stops when the app leaves the screen.

The app connects to the first car advertising the drive service and goes
back to scanning when the link drops. When the app leaves the screen it lets
go of the car. It keeps the screen awake while connected. The Bluetooth
logic is in [shared/RobotLink](../../shared/RobotLink). The car's end,
including the 300 ms watchdog that stops the wheels when the phone goes
quiet, is [pi/robot_car/remote.py](../../pi/robot_car/remote.py).

## Build and install on the phone

The Simulator has no Bluetooth, so the real thing needs the phone, plugged in
or on the same network with developer mode on. Requires Xcode and
[XcodeGen](https://github.com/yonaskolb/XcodeGen); the `.xcodeproj` is
generated, not committed. `xcrun devicectl list devices` gives the phone's
identifier.

```sh
xcodegen generate
xcodebuild -project RobotRemote.xcodeproj -scheme RobotRemote \
  -destination "id=$PHONE" -derivedDataPath build \
  -allowProvisioningUpdates DEVELOPMENT_TEAM=$TEAM build
xcrun devicectl device install app --device "$PHONE" build/Build/Products/Debug-iphoneos/RobotRemote.app
xcrun devicectl device process launch --device "$PHONE" dk.delectosoft.robotremote
```

The first launch asks for Bluetooth permission.

## Simulator

In the Simulator the app drives a simulated car, which connects after a
moment and shows the stick and wheel bars working. Launching on the phone
with `--simulate` does the same.

```sh
xcodebuild -project RobotRemote.xcodeproj -scheme RobotRemote \
  -sdk iphonesimulator -destination 'name=iPhone 17 Pro' \
  -derivedDataPath build build
xcrun simctl install booted build/Build/Products/Debug-iphonesimulator/RobotRemote.app
xcrun simctl launch booted dk.delectosoft.robotremote
```
