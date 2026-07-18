#!/usr/bin/env bash
#
# prepare_python_runtime.sh — Orchestrate the full Python runtime build
#
# This is the one-shot script that runs all three build steps in sequence:
#   1. Cross-compile CPython + dependencies (OpenSSL, SQLite, libffi)
#   2. Cross-compile FFmpeg
#   3. Package everything into jniLibs/ + assets/
#
# Run this before building the APK. The output is cached in build/ —
# re-running only rebuilds what's missing.
#
# Prerequisites:
#   - Android NDK r26+ → export ANDROID_NDK_HOME=/path/to/ndk
#   - Host Python 3.11+ (for pip packaging)
#   - Build tools: autoconf, automake, libtool, make, gcc, pkg-config, curl
#
# Usage:
#   export ANDROID_NDK_HOME=/path/to/android-ndk-r26d
#   ./scripts/prepare_python_runtime.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  MediaHub — Python Runtime Build Orchestrator               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
if [[ -z "$NDK" ]]; then
    echo "❌ ANDROID_NDK_HOME is not set."
    echo ""
    echo "   Download the NDK from:"
    echo "     https://developer.android.com/ndk/downloads"
    echo "   Then set it:"
    echo "     export ANDROID_NDK_HOME=/path/to/android-ndk-r26d"
    exit 1
fi
echo "✓ NDK: $NDK"

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 not found in PATH."
    exit 1
fi
echo "✓ Host Python: $(python3 --version)"

for tool in make gcc curl zip; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "⚠ $tool not found (may be needed)"
    fi
done
echo ""

# Step 1: Build CPython
echo "━━━ Step 1/3: Building CPython for Android ━━━"
echo ""
bash "$SCRIPT_DIR/build_cpython_android.sh"

echo ""

# Step 2: Build FFmpeg
echo "━━━ Step 2/3: Building FFmpeg for Android ━━━"
echo ""
bash "$SCRIPT_DIR/build_ffmpeg_android.sh"

echo ""

# Step 3: Package everything
echo "━━━ Step 3/3: Packaging for APK ━━━"
echo ""
bash "$SCRIPT_DIR/package_engine.sh"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Python runtime build complete!                          ║"
echo "║                                                              ║"
echo "║  Next steps:                                                 ║"
echo "║    1. flutter pub get                                        ║"
echo "║    2. flutter build apk --flavor standard --release          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
