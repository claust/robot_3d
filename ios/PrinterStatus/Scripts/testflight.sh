#!/usr/bin/env bash
#
# Archive Printer Status for the App Store and upload it to TestFlight.
# Adapted from the MeTube repo's Scripts/testflight.sh (tvOS → iOS).
#
# A TestFlight build is signed for distribution, installs through the
# TestFlight app on the phone, lasts 90 days, and is replaced by simply
# uploading again — no cable, no expiring development profile.
#
# Configuration is read from the environment, falling back to .testflight.env
# in this directory (gitignored — it names your API key, which is a credential).
#
# Usage — run from ios/PrinterStatus/:
#   Scripts/testflight.sh              # archive, export, validate, upload
#   Scripts/testflight.sh --validate   # everything except the upload
#   Scripts/testflight.sh --archive    # stop after producing the .ipa

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

# Fill in only what the environment has not already set, so CI — where the
# values arrive as secrets — wins over a stale local file. Indirect
# expansion (${!key-}) instead of eval, and only well-formed identifiers,
# so a malformed env file cannot inject commands.
if [ -f "$ROOT/.testflight.env" ]; then
	while IFS='=' read -r key value; do
		case "$key" in ''|\#*) continue ;; esac
		[[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
		[ -z "${!key-}" ] && export "$key=$value"
	done < "$ROOT/.testflight.env"
fi

SCHEME=PrinterStatus
PROJECT=PrinterStatus.xcodeproj
ARCHIVE_DIR=build-archive

# CFBundleVersion has to increase with every upload or App Store Connect
# rejects the build as a duplicate. The commit count is monotonic on master
# and needs no state outside git. Override with BUILD_NUMBER=<n> when
# uploading from a branch whose count has drifted.
BUILD_NUMBER="${BUILD_NUMBER:-$(git rev-list --count HEAD)}"

MODE=upload
case "${1:-}" in
	--validate) MODE=validate ;;
	--archive) MODE=archive ;;
	"") ;;
	*) echo "Unknown option: $1" >&2; exit 2 ;;
esac

# --- credentials -------------------------------------------------------------
# altool and xcodebuild both authenticate with an App Store Connect API key:
# an issuer UUID, a key ID, and the .p8 private key that Apple lets you
# download exactly once. The .p8 goes in ~/.private_keys, where altool looks.
need() {
	if [ -z "${!1:-}" ]; then
		echo "Missing $1. Set it in .testflight.env or the environment." >&2
		exit 1
	fi
}

need DEVELOPMENT_TEAM
if [ "$MODE" != archive ]; then
	need ASC_KEY_ID
	need ASC_ISSUER_ID
fi

KEY_PATH=""
if [ -n "${ASC_KEY_ID:-}" ]; then
	for dir in "$ROOT/private_keys" "$HOME/private_keys" "$HOME/.private_keys" \
		"$HOME/.appstoreconnect/private_keys"; do
		if [ -f "$dir/AuthKey_$ASC_KEY_ID.p8" ]; then
			KEY_PATH="$dir/AuthKey_$ASC_KEY_ID.p8"
			break
		fi
	done
	if [ -z "$KEY_PATH" ] && [ "$MODE" != archive ]; then
		echo "Could not find AuthKey_$ASC_KEY_ID.p8 in ~/.private_keys (or ./private_keys)." >&2
		echo "Download it from App Store Connect → Users and Access → Integrations." >&2
		exit 1
	fi
fi

# --- build -------------------------------------------------------------------
BEAUTIFY="cat"
command -v xcbeautify >/dev/null 2>&1 && BEAUTIFY=xcbeautify

echo "==> Generating Xcode project"
xcodegen generate

ARCHIVE="$ARCHIVE_DIR/$SCHEME.xcarchive"
rm -rf "$ARCHIVE_DIR"
mkdir -p "$ARCHIVE_DIR"

# -allowProvisioningUpdates lets xcodebuild register the bundle ID and mint
# the distribution profile on first run, so nothing has to be clicked in the
# portal. It needs the API key to do that, hence the -authenticationKey*
# flags.
AUTH=()
if [ -n "$KEY_PATH" ]; then
	AUTH=(-authenticationKeyPath "$KEY_PATH"
		-authenticationKeyID "$ASC_KEY_ID"
		-authenticationKeyIssuerID "$ASC_ISSUER_ID")
fi

echo "==> Archiving $SCHEME (build $BUILD_NUMBER)"
set -o pipefail
xcodebuild archive \
	-project "$PROJECT" \
	-scheme "$SCHEME" \
	-configuration Release \
	-destination 'generic/platform=iOS' \
	-archivePath "$ARCHIVE" \
	-allowProvisioningUpdates \
	${AUTH[@]+"${AUTH[@]}"} \
	DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM" \
	CURRENT_PROJECT_VERSION="$BUILD_NUMBER" \
	| $BEAUTIFY

# manageAppVersionAndBuildNumber=false keeps Xcode from silently rewriting
# the build number we just set; we own it, via the commit count.
cat > "$ARCHIVE_DIR/ExportOptions.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>method</key>
	<string>app-store-connect</string>
	<key>signingStyle</key>
	<string>automatic</string>
	<key>destination</key>
	<string>export</string>
	<key>uploadSymbols</key>
	<true/>
	<key>manageAppVersionAndBuildNumber</key>
	<false/>
</dict>
</plist>
PLIST

echo "==> Exporting .ipa"
xcodebuild -exportArchive \
	-archivePath "$ARCHIVE" \
	-exportPath "$ARCHIVE_DIR" \
	-exportOptionsPlist "$ARCHIVE_DIR/ExportOptions.plist" \
	-allowProvisioningUpdates \
	${AUTH[@]+"${AUTH[@]}"} \
	| $BEAUTIFY

IPA="$(find "$ARCHIVE_DIR" -maxdepth 1 -name '*.ipa' | head -1)"
[ -n "$IPA" ] || { echo "Export produced no .ipa" >&2; exit 1; }
echo "==> Built $IPA"

if [ "$MODE" = archive ]; then
	exit 0
fi

# --- upload ------------------------------------------------------------------
# Validation catches the cheap rejections (missing icon, bad entitlements, a
# build number App Store Connect has already seen) before spending the upload.
echo "==> Validating with App Store Connect"
xcrun altool --validate-app -f "$IPA" -t ios \
	--apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID"

if [ "$MODE" = validate ]; then
	echo "==> Validation passed (upload skipped)"
	exit 0
fi

echo "==> Uploading to TestFlight"
xcrun altool --upload-app -f "$IPA" -t ios \
	--apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID"

echo
echo "Uploaded build $BUILD_NUMBER. App Store Connect takes a few minutes to"
echo "finish processing before it shows up in TestFlight on the phone."
