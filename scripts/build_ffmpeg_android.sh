#!/usr/bin/env bash
#
# build_ffmpeg_android.sh — Cross-compile FFmpeg for Android (arm64-v8a + x86_64)
#
# Produces a static FFmpeg binary (no shared library dependencies) suitable
# for execution on Android via ProcessBuilder. The binary is packaged as
# libffmpeg.so (Android convention for including native executables in APKs)
# and extracted at runtime by PythonBootstrap.
#
# Prerequisites:
#   - Android NDK r26+ (set $ANDROID_NDK_HOME)
#   - make, pkg-config
#   - curl/wget, tar
#
# Usage:
#   export ANDROID_NDK_HOME=/path/to/android-ndk
#   ./scripts/build_ffmpeg_android.sh
#
set -euo pipefail

FFMPEG_VERSION="n7.0"
MIN_API=24

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/ffmpeg-build"
OUTPUT_DIR="$PROJECT_ROOT/build/ffmpeg-output"

NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
if [[ -z "$NDK" ]]; then
    echo "ERROR: ANDROID_NDK_HOME is not set."
    exit 1
fi

TOOLCHAIN="$NDK/toolchains/llvm/prebuilt/linux-x86_64"
ABIS=("arm64-v8a" "x86_64")
declare -A ARCH_MAP=(
    ["arm64-v8a"]="aarch64"
    ["x86_64"]="x86_64"
)
declare -A TRIPLE_MAP=(
    ["arm64-v8a"]="aarch64-linux-android"
    ["x86_64"]="x86_64-linux-android"
)

echo "================================================================"
echo " Building FFmpeg $FFMPEG_VERSION for Android"
echo " NDK: $NDK"
echo " ABIs: ${ABIS[*]}"
echo "================================================================"

mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

# Download FFmpeg source
if [[ ! -d "$BUILD_DIR/ffmpeg" ]]; then
    echo "Downloading FFmpeg $FFMPEG_VERSION..."
    cd "$BUILD_DIR"
    curl -fL -o ffmpeg.tar.xz \
        "https://github.com/FFmpeg/FFmpeg/releases/download/$FFMPEG_VERSION/ffmpeg-$FFMPEG_VERSION.tar.xz" 2>/dev/null || \
    git clone --depth 1 --branch "$FFMPEG_VERSION" https://github.com/FFmpeg/FFmpeg.git ffmpeg
    if [[ -f ffmpeg.tar.xz ]]; then
        tar xf ffmpeg.tar.xz
        mv "ffmpeg-$FFMPEG_VERSION" ffmpeg 2>/dev/null || true
    fi
fi

build_ffmpeg() {
    local abi=$1
    local arch=${ARCH_MAP[$abi]}
    local triple=${TRIPLE_MAP[$abi]}
    local cc="$TOOLCHAIN/bin/${triple}${MIN_API}-clang"

    local stage="$BUILD_DIR/build-$abi"
    local prefix="$OUTPUT_DIR/$abi"

    if [[ -f "$prefix/libffmpeg.so" ]]; then
        echo "  FFmpeg already built for $abi, skipping."
        return
    fi

    echo "  Building FFmpeg for $abi..."
    rm -rf "$stage" "$prefix"
    mkdir -p "$stage" "$prefix"

    cd "$BUILD_DIR/ffmpeg"

    # Configure for Android cross-compilation.
    # --enable-cross-compile + --target-os=android is the official way.
    # --disable-shared + --enable-static produces a single self-contained binary.
    # We enable the codecs/formats commonly needed for media downloads.
    ./configure \
        --prefix="$prefix" \
        --enable-cross-compile \
        --target-os=android \
        --arch="$arch" \
        --cc="$cc" \
        --ar="$TOOLCHAIN/bin/llvm-ar" \
        --ranlib="$TOOLCHAIN/bin/llvm-ranlib" \
        --strip="$TOOLCHAIN/bin/llvm-strip" \
        --extra-cflags="-fPIC -O2 -D__ANDROID_API__=$MIN_API" \
        --extra-ldflags="-pie -fPIE -lm -lz" \
        --enable-pic \
        --enable-pie \
        --disable-shared \
        --enable-static \
        --disable-doc \
        --disable-programs \
        --disable-avdevice \
        --disable-swscale \
        --disable-postproc \
        --disable-avfilter \
        --disable-network \
        --disable-everything \
        --enable-decoder=h264 \
        --enable-decoder=hevc \
        --enable-decoder=aac \
        --enable-decoder=mp3 \
        --enable-decoder=vp8 \
        --enable-decoder=vp9 \
        --enable-decoder=opus \
        --enable-decoder=vorbis \
        --enable-decoder=flac \
        --enable-decoder=pcm_s16le \
        --enable-encoder=aac \
        --enable-encoder=libmp3lame \
        --enable-encoder=h264 \
        --enable-muxer=mp4 \
        --enable-muxer=matroska \
        --enable-muxer=mp3 \
        --enable-muxer=flac \
        --enable-demuxer=mov \
        --enable-demuxer=matroska \
        --enable-demuxer=mp3 \
        --enable-demuxer=aac \
        --enable-demuxer=flac \
        --enable-demuxer=wav \
        --enable-parser=h264 \
        --enable-parser=hevc \
        --enable-parser=aac \
        --enable-parser=opus \
        --enable-protocol=file \
        --enable-protocol=pipe

    make -j"$(nproc)" -s
    make install -s

    # Build the standalone ffmpeg binary (links all static libs)
    echo "  Linking ffmpeg binary for $abi..."
    "$cc" -pie -fPIE -o "$prefix/ffmpeg" \
        -Wl,--start-group \
        "$prefix/lib/libavcodec.a" \
        "$prefix/lib/libavformat.a" \
        "$prefix/lib/libavutil.a" \
        "$prefix/lib/libswresample.a" \
        -Wl,--end-group \
        -lm -lz -llog

    # Rename to libffmpeg.so (Android APK convention for native executables)
    # and strip debug symbols to reduce size.
    cp "$prefix/ffmpeg" "$prefix/libffmpeg.so"
    "$TOOLCHAIN/bin/llvm-strip" "$prefix/libffmpeg.so"
    rm "$prefix/ffmpeg"

    # Clean up static libraries (not needed in the APK)
    rm -rf "$prefix/lib" "$prefix/include" "$prefix/share"

    echo "  FFmpeg for $abi: $(ls -lh "$prefix/libffmpeg.so" | awk '{print $5}')"
}

for abi in "${ABIS[@]}"; do
    echo ""
    build_ffmpeg "$abi"
done

echo ""
echo "================================================================"
echo " FFmpeg build complete!"
echo " Output: $OUTPUT_DIR"
echo "================================================================"
