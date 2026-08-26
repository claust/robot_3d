#!/bin/zsh
# Bundle PrinterStatus into a double-clickable .app (macos/PrinterStatus.app).
set -euo pipefail
cd "$(dirname "$0")"

swift build -c release

APP=../PrinterStatus.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp .build/release/PrinterStatus "$APP/Contents/MacOS/"
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>PrinterStatus</string>
    <key>CFBundleIdentifier</key><string>local.robot3d.PrinterStatus</string>
    <key>CFBundleName</key><string>Printer Status</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>0.1</string>
    <key>LSMinimumSystemVersion</key><string>14.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
codesign --force --sign - "$APP"
echo "Built $APP"
echo "Note: the app finds credentials by looking for cad/.env upward from its"
echo "own location, so keep it inside the repo (macos/) or set BAMBU_* env vars."
