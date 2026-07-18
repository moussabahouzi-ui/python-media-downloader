#!/usr/bin/env bash
#
# package_engine.sh — Package the Python runtime + engine + dependencies into APK assets
#
# This script takes the output of build_cpython_android.sh and produces:
#
#   android/app/src/main/jniLibs/<abi>/libpython3.11.so  — the interpreter
#   android/app/src/main/jniLibs/<abi>/libssl.so          — OpenSSL
#   android/app/src/main/jniLibs/<abi>/libcrypto.so       — OpenSSL
#   android/app/src/main/jniLibs/<abi>/libsqlite3.so      — SQLite
#   android/app/src/main/jniLibs/<abi>/libffi.so          — libffi
#   android/app/src/main/jniLibs/<abi>/libffmpeg.so       — FFmpeg
#
#   android/app/src/main/assets/python_stdlib.zip         — stdlib .py + lib-dynload .so
#   android/app/src/main/assets/python_packages.zip       — yt-dlp + gallery-dl + instaloader + pydantic + mediahub_engine
#
# Prerequisites:
#   - Run build_cpython_android.sh first
#   - Run build_ffmpeg_android.sh first
#   - Python 3.11+ on the host (for pip install)
#   - pip, virtualenv
#
# Usage:
#   ./scripts/package_engine.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON_BUILD="$PROJECT_ROOT/build/python-output"
FFMPEG_BUILD="$PROJECT_ROOT/build/ffmpeg-output"
ENGINE_SRC="$PROJECT_ROOT/python_engine"

JNI_DIR="$PROJECT_ROOT/android/app/src/main/jniLibs"
ASSETS_DIR="$PROJECT_ROOT/android/app/src/main/assets"
ABIS=("arm64-v8a" "x86_64")

echo "================================================================"
echo " Packaging Python engine for APK"
echo "================================================================"

mkdir -p "$ASSETS_DIR"

# ---------------------------------------------------------------------------
# Step 1: Copy native libraries to jniLibs
# ---------------------------------------------------------------------------

echo ""
echo "Step 1: Copying native libraries to jniLibs..."

for abi in "${ABIS[@]}"; do
    echo "  $abi:"
    mkdir -p "$JNI_DIR/$abi"

    # Python interpreter + dependencies
    src_lib="$PYTHON_BUILD/$abi/lib"
    if [[ -d "$src_lib" ]]; then
        for so in "$src_lib"/*.so*; do
            [[ -f "$so" ]] || continue
            # Resolve symlinks and copy the actual file
            cp -L "$so" "$JNI_DIR/$abi/" 2>/dev/null || true
            echo "    $(basename "$so")"
        done
    else
        echo "    WARNING: $src_lib not found. Run build_cpython_android.sh first."
    fi

    # FFmpeg
    ffmpeg_so="$FFMPEG_BUILD/$abi/libffmpeg.so"
    if [[ -f "$ffmpeg_so" ]]; then
        cp "$ffmpeg_so" "$JNI_DIR/$abi/"
        echo "    libffmpeg.so"
    else
        echo "    WARNING: $ffmpeg_so not found. Run build_ffmpeg_android.sh first."
    fi
done

# ---------------------------------------------------------------------------
# Step 2: Create python_stdlib.zip (pure-Python stdlib + C extensions)
# ---------------------------------------------------------------------------

echo ""
echo "Step 2: Creating python_stdlib.zip..."

# Use arm64-v8a as the canonical ABI for the stdlib (pure Python is ABI-agnostic).
# C extension .so files ARE ABI-specific, so we include the arm64-v8a lib-dynload.
# For x86_64 devices, a separate build variant would include x86_64 lib-dynload.
# For now, we ship arm64-v8a C extensions (covers >99% of devices).
STDLIB_SRC="$PYTHON_BUILD/arm64-v8a/stdlib"
LIB_DYNLOAD_SRC="$PYTHON_BUILD/arm64-v8a/lib-dynload"

if [[ ! -d "$STDLIB_SRC" ]]; then
    echo "  ERROR: Stdlib source not found at $STDLIB_SRC"
    echo "  Run build_cpython_android.sh first."
    exit 1
fi

STDLIB_ZIP="$ASSETS_DIR/python_stdlib.zip"
rm -f "$STDLIB_ZIP"

# Create a temporary staging directory with the correct structure:
#   python_stdlib.zip/
#     *.py                ← stdlib root (will be extracted to lib/python3.11/)
#     lib-dynload/
#       *.so              ← C extension modules
#     cacert.pem          ← CA certificates for HTTPS
STAGING=$(mktemp -d)
cp -r "$STDLIB_SRC/"* "$STAGING/"
if [[ -d "$LIB_DYNLOAD_SRC" ]]; then
    mkdir -p "$STAGING/lib-dynload"
    cp "$LIB_DYNLOAD_SRC/"*.so "$STAGING/lib-dynload/"
fi

cd "$STAGING"
zip -r -q "$STDLIB_ZIP" .
cd "$PROJECT_ROOT"
rm -rf "$STAGING"

echo "  Created: $STDLIB_ZIP ($(du -h "$STDLIB_ZIP" | cut -f1))"

# ---------------------------------------------------------------------------
# Step 3: Create python_packages.zip (third-party packages + mediahub_engine)
# ---------------------------------------------------------------------------

echo ""
echo "Step 3: Creating python_packages.zip..."

PACKAGES_ZIP="$ASSETS_DIR/python_packages.zip"
rm -f "$PACKAGES_ZIP"

# Create a virtualenv to install the exact package versions that will ship
# in the APK. This ensures consistency between development and production.
VENV_DIR="$PROJECT_ROOT/build/venv-packaging"
python3 -m venv "$VENV_DIR" 2>/dev/null || python -m venv "$VENV_DIR"
PIP="$VENV_DIR/bin/pip"

echo "  Installing packages into packaging venv..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet \
    "yt-dlp>=2024.8.6" \
    "gallery-dl>=1.27.5" \
    "instaloader>=4.13" \
    "ffmpeg-python>=0.2.0" \
    "pydantic>=2.7.0"

# Stage the site-packages
STAGING=$(mktemp -d)
SITE_PACKAGES="$VENV_DIR/lib/python3.*/site-packages"

# Copy third-party packages (exclude pip, setuptools, etc.)
for pkg_dir in "$SITE_PACKAGES"/{yt_dlp,gallery_dl,instaloader,ffmpeg,pydantic}; do
    if [[ -d "$pkg_dir" ]]; then
        cp -r "$pkg_dir" "$STAGING/"
    fi
done

# Copy .dist-info directories (for metadata)
for dist_dir in "$SITE_PACKAGES"/*.dist-info; do
    pkg_name=$(basename "$dist_dir" | sed 's/-[0-9].*//')
    case "$pkg_name" in
        yt_dlp|gallery_dl|instaloader|ffmpeg|pydantic|pydantic_core)
            cp -r "$dist_dir" "$STAGING/"
            ;;
    esac
done

# Copy the mediahub_engine source
if [[ -d "$ENGINE_SRC/mediahub_engine" ]]; then
    cp -r "$ENGINE_SRC/mediahub_engine" "$STAGING/"
    echo "  Added mediahub_engine to packages"
else
    echo "  WARNING: mediahub_engine source not found at $ENGINE_SRC/mediahub_engine"
fi

# Zip the staging directory
cd "$STAGING"
zip -r -q "$PACKAGES_ZIP" .
cd "$PROJECT_ROOT"
rm -rf "$STAGING"

echo "  Created: $PACKAGES_ZIP ($(du -h "$PACKAGES_ZIP" | cut -f1))"

# Clean up the venv
rm -rf "$VENV_DIR"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "================================================================"
echo " Packaging complete!"
echo ""
echo " jniLibs:"
for abi in "${ABIS[@]}"; do
    echo "   $abi/: $(ls "$JNI_DIR/$abi/" 2>/dev/null | wc -l) files"
    ls "$JNI_DIR/$abi/" 2>/dev/null | sed 's/^/     /'
done
echo ""
echo " assets:"
echo "   python_stdlib.zip  ($(du -h "$STDLIB_ZIP" | cut -f1))"
echo "   python_packages.zip ($(du -h "$PACKAGES_ZIP" | cut -f1))"
echo ""
echo " Next: run 'flutter build apk --flavor standard --release'"
echo "================================================================"
