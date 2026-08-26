#!/bin/zsh
# Build PrinterStatus and install it as a normal Mac app, so it can be
# launched from Spotlight / Launchpad instead of the terminal.
#
#   ./install.sh              # install to /Applications (or ~/Applications)
#   ./install.sh --local      # only build the bundle here, don't install
#
# Because the installed app lives outside the repo, it cannot find
# cad/.env by walking up from its own location. The installer therefore
# writes ~/Library/Application Support/PrinterStatus/config.env pointing at
# the repo's cad/.env — the credentials themselves stay in that one file.
set -euo pipefail
cd "$(dirname "$0")"

REPO_ROOT=$(cd ../.. && pwd)
STAGE="$PWD/.build/bundle/PrinterStatus.app"
CONFIG_DIR="$HOME/Library/Application Support/PrinterStatus"

# Prefer the main checkout's cad/.env: when this script runs from a git
# worktree, that worktree is temporary but the main checkout is not.
MAIN_ROOT=$(dirname "$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" 2>/dev/null || true)
if [[ -n "$MAIN_ROOT" && -f "$MAIN_ROOT/cad/.env" ]]; then
    ENV_FILE="$MAIN_ROOT/cad/.env"
elif [[ -f "$REPO_ROOT/cad/.env" ]]; then
    ENV_FILE="$REPO_ROOT/cad/.env"
else
    ENV_FILE="${MAIN_ROOT:-$REPO_ROOT}/cad/.env"
fi

echo "Building release binary…"
swift build -c release

rm -rf "$STAGE"
mkdir -p "$STAGE/Contents/MacOS"
cp .build/release/PrinterStatus "$STAGE/Contents/MacOS/"
cat > "$STAGE/Contents/Info.plist" <<'EOF'
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
codesign --force --sign - "$STAGE" 2>/dev/null

if [[ "${1:-}" == "--local" ]]; then
    rm -rf ../PrinterStatus.app
    cp -R "$STAGE" ../PrinterStatus.app
    echo "Built $(cd .. && pwd)/PrinterStatus.app"
    exit 0
fi

# /Applications is writable by admin users; fall back to ~/Applications.
DEST="/Applications"
[[ -w "$DEST" ]] || DEST="$HOME/Applications"
mkdir -p "$DEST"
rm -rf "$DEST/PrinterStatus.app"
cp -R "$STAGE" "$DEST/PrinterStatus.app"
echo "Installed $DEST/PrinterStatus.app"

# Point the installed app at the repo's credentials file.
mkdir -p "$CONFIG_DIR"
if [[ -f "$CONFIG_DIR/config.env" ]] && ! grep -q '^BAMBU_ENV_FILE=' "$CONFIG_DIR/config.env"; then
    echo "Keeping existing $CONFIG_DIR/config.env"
else
    printf '# Where PrinterStatus reads printer credentials from.\n# Replace this line with BAMBU_PRINTER_IP/SERIAL/ACCESS_CODE to set them here.\nBAMBU_ENV_FILE=%s\n' "$ENV_FILE" > "$CONFIG_DIR/config.env"
    chmod 600 "$CONFIG_DIR/config.env"
    echo "Wrote $CONFIG_DIR/config.env -> $ENV_FILE"
fi
if [[ ! -f "$ENV_FILE" ]]; then
    echo
    echo "WARNING: $ENV_FILE does not exist, so the app will start in"
    echo "Simulate mode. Create it (see cad/.env.example) and the app will"
    echo "pick it up on next launch — no reinstall needed."
fi

# Make sure Spotlight indexes it right away.
mdimport "$DEST/PrinterStatus.app" 2>/dev/null || true
echo
echo "Done — open Spotlight (cmd-space) and type 'Printer Status'."
