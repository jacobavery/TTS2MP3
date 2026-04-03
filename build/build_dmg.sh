#!/bin/bash
set -e

# ── TTS2MP3 Studio DMG Builder ──────────────────────────────────────
APP_NAME="TTS2MP3 Studio"
VERSION="1.0.0"
DMG_NAME="TTS2MP3-Studio-${VERSION}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${PROJECT_ROOT}/dist"
APP_PATH="${BUILD_DIR}/${APP_NAME}.app"
DMG_PATH="${BUILD_DIR}/${DMG_NAME}.dmg"
DMG_TEMP="${BUILD_DIR}/${DMG_NAME}-temp.dmg"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Building ${APP_NAME} v${VERSION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: Clean previous builds ───────────────────────────────────
echo ""
echo "[1/5] Cleaning previous builds..."
rm -rf "${BUILD_DIR}" "${PROJECT_ROOT}/build/__pycache__"
rm -rf "${PROJECT_ROOT}/build/TTS2MP3 Studio"  # PyInstaller work dir

# ── Step 2: Build .app with PyInstaller ────────────────────────────
echo ""
echo "[2/5] Building .app bundle with PyInstaller..."
cd "${PROJECT_ROOT}"
/usr/local/bin/python3.13 -m PyInstaller \
    --distpath "${BUILD_DIR}" \
    --workpath "${SCRIPT_DIR}/pyinstaller-work" \
    --noconfirm \
    "${SCRIPT_DIR}/TTS2MP3.spec"

if [ ! -d "${APP_PATH}" ]; then
    echo "ERROR: .app bundle was not created!"
    exit 1
fi
echo "  .app bundle created: ${APP_PATH}"

# Clean up PyInstaller work directory
rm -rf "${SCRIPT_DIR}/pyinstaller-work"

# ── Step 3: Generate DMG background ─────────────────────────────────
echo ""
echo "[3/5] Generating DMG background..."
/usr/local/bin/python3.13 "${SCRIPT_DIR}/gen_dmg_bg.py"

# ── Step 4: Create DMG ──────────────────────────────────────────────
echo ""
echo "[4/5] Creating DMG..."
DMG_SIZE_MB=$(du -sm "${APP_PATH}" | awk '{print $1}')
DMG_SIZE_MB=$((DMG_SIZE_MB + 20))  # Add padding

# Create temporary DMG
hdiutil create \
    -srcfolder "${APP_PATH}" \
    -volname "${APP_NAME}" \
    -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" \
    -format UDRW \
    -size "${DMG_SIZE_MB}m" \
    "${DMG_TEMP}"

# Mount it
MOUNT_DIR=$(hdiutil attach -readwrite -noverify "${DMG_TEMP}" | \
    grep "Apple_HFS" | sed 's/.*Apple_HFS[[:space:]]*//')

if [ -z "${MOUNT_DIR}" ]; then
    echo "ERROR: Failed to mount DMG"
    exit 1
fi

echo "  Mounted at: ${MOUNT_DIR}"

# Add Applications symlink
ln -s /Applications "${MOUNT_DIR}/Applications"

# Set DMG background and icon layout
BG_PATH="${SCRIPT_DIR}/dmg_background.png"
if [ -f "${BG_PATH}" ]; then
    mkdir -p "${MOUNT_DIR}/.background"
    cp "${BG_PATH}" "${MOUNT_DIR}/.background/background.png"
fi

# Use AppleScript to set DMG window appearance
echo "  Configuring DMG window layout..."
osascript <<APPLESCRIPT
tell application "Finder"
    tell disk "${APP_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 800, 480}
        set theViewOptions to the icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 96
        set text size of theViewOptions to 13
        try
            set background picture of theViewOptions to file ".background:background.png"
        end try
        set position of item "${APP_NAME}.app" of container window to {150, 200}
        set position of item "Applications" of container window to {450, 200}
        close
        open
        update without registering applications
        delay 1
        close
    end tell
end tell
APPLESCRIPT

# Ensure Finder writes .DS_Store
sync
sleep 2

# Detach
hdiutil detach "${MOUNT_DIR}" -quiet

# ── Step 5: Compress final DMG ──────────────────────────────────────
echo ""
echo "[5/5] Compressing final DMG..."
rm -f "${DMG_PATH}"
hdiutil convert "${DMG_TEMP}" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "${DMG_PATH}"
rm -f "${DMG_TEMP}"

# Print summary
DMG_SIZE=$(du -h "${DMG_PATH}" | awk '{print $1}')
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Build complete!"
echo "  DMG: ${DMG_PATH}"
echo "  Size: ${DMG_SIZE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
