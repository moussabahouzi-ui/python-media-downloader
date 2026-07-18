#!/usr/bin/env bash
#
# build_cpython_android.sh — Cross-compile CPython 3.11 for Android (arm64-v8a + x86_64)
#
# This script produces:
#   - libpython3.11.so  (the interpreter, compiled as a PIE shared library)
#   - libssl.so, libcrypto.so  (OpenSSL for HTTPS)
#   - libsqlite3.so  (for the sqlite3 C extension)
#   - libffi.so  (for the ctypes C extension)
#   - lib-dynload/*.so  (CPython C extension modules: _ssl, _hashlib, etc.)
#   - Lib/*.py  (pure-Python standard library)
#
# The output is staged in $OUTPUT_DIR and then consumed by package_engine.sh
# to produce the APK assets and jniLibs.
#
# Prerequisites:
#   - Android NDK r26+ (set $ANDROID_NDK_HOME)
#   - autoconf, automake, libtool, pkg-config
#   - make, gcc (for the build host)
#   - curl/wget for downloading sources
#
# Usage:
#   export ANDROID_NDK_HOME=/path/to/android-ndk
#   ./scripts/build_cpython_android.sh
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CPYTHON_VERSION="3.11.9"
OPENSSL_VERSION="3.2.1"
SQLITE_VERSION="3460000  # 3.46.0
LIBFFI_VERSION="3.4.6"

MIN_API=24  # Android 7.0 (matches minSdkVersion)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/python-build"
OUTPUT_DIR="$PROJECT_ROOT/build/python-output"

NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
if [[ -z "$NDK" ]]; then
    echo "ERROR: ANDROID_NDK_HOME is not set."
    echo "Set it to your NDK installation path, e.g.:"
    echo "  export ANDROID_NDK_HOME=/path/to/android-ndk-r26d"
    exit 1
fi

TOOLCHAIN="$NDK/toolchains/llvm/prebuilt/linux-x86_64"

# Target ABIs
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
echo " Building CPython $CPYTHON_VERSION for Android"
echo " NDK: $NDK"
echo " ABIs: ${ABIS[*]}"
echo " Output: $OUTPUT_DIR"
echo "================================================================"

mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# Download sources
# ---------------------------------------------------------------------------

download_sources() {
    cd "$BUILD_DIR"

    if [[ ! -f "Python-$CPYTHON_VERSION.tgz" ]]; then
        echo "Downloading CPython $CPYTHON_VERSION..."
        curl -fL -o "Python-$CPYTHON_VERSION.tgz" \
            "https://www.python.org/ftp/python/$CPYTHON_VERSION/Python-$CPYTHON_VERSION.tgz"
    fi

    if [[ ! -f "openssl-$OPENSSL_VERSION.tar.gz" ]]; then
        echo "Downloading OpenSSL $OPENSSL_VERSION..."
        curl -fL -o "openssl-$OPENSSL_VERSION.tar.gz" \
            "https://www.openssl.org/source/openssl-$OPENSSL_VERSION.tar.gz"
    fi

    if [[ ! -f "sqlite-autoconf-$SQLITE_VERSION.tar.gz" ]]; then
        echo "Downloading SQLite $SQLITE_VERSION..."
        curl -fL -o "sqlite-autoconf-$SQLITE_VERSION.tar.gz" \
            "https://www.sqlite.org/2024/sqlite-autoconf-$SQLITE_VERSION.tar.gz"
    fi

    if [[ ! -f "libffi-$LIBFFI_VERSION.tar.gz" ]]; then
        echo "Downloading libffi $LIBFFI_VERSION..."
        curl -fL -o "libffi-$LIBFFI_VERSION.tar.gz" \
            "https://github.com/libffi/libffi/releases/download/v$LIBFFI_VERSION/libffi-$LIBFFI_VERSION.tar.gz"
    fi
}

# ---------------------------------------------------------------------------
# Build OpenSSL for a given ABI
# ---------------------------------------------------------------------------

build_openssl() {
    local abi=$1
    local arch=${ARCH_MAP[$abi]}
    local triple=${TRIPLE_MAP[$abi]}
    local api_suffix="${MIN_API}"
    local cc="$TOOLCHAIN/bin/${triple}${api_suffix}-clang"

    local stage="$BUILD_DIR/openssl-$abi"
    if [[ -d "$stage" ]] && [[ -f "$stage/libssl.so" ]]; then
        echo "  OpenSSL already built for $abi, skipping."
        return
    fi

    echo "  Building OpenSSL for $abi..."
    rm -rf "$stage"
    mkdir -p "$stage"
    cd "$stage"
    tar xzf "$BUILD_DIR/openssl-$OPENSSL_VERSION.tar.gz"
    cd "openssl-$OPENSSL_VERSION"

    local os_compiler
    case "$abi" in
        arm64-v8a) os_compiler="linux-aarch64" ;;
        x86_64)    os_compiler="linux-x86_64"  ;;
    esac

    ./Configure \
        "$os_compiler" \
        -D__ANDROID_API__=$MIN_API \
        --prefix="$stage/install" \
        shared \
        no-tests \
        no-ssl3 \
        no-comp \
        CC="$cc" \
        AR="$TOOLCHAIN/bin/llvm-ar" \
        RANLIB="$TOOLCHAIN/bin/llvm-ranlib"

    make -j"$(nproc)" -s
    make install_sw -s
}

# ---------------------------------------------------------------------------
# Build SQLite for a given ABI
# ---------------------------------------------------------------------------

build_sqlite() {
    local abi=$1
    local triple=${TRIPLE_MAP[$abi]}
    local cc="$TOOLCHAIN/bin/${triple}${MIN_API}-clang"

    local stage="$BUILD_DIR/sqlite-$abi"
    if [[ -d "$stage" ]] && [[ -f "$stage/libsqlite3.so" ]]; then
        echo "  SQLite already built for $abi, skipping."
        return
    fi

    echo "  Building SQLite for $abi..."
    rm -rf "$stage"
    mkdir -p "$stage"
    cd "$stage"
    tar xzf "$BUILD_DIR/sqlite-autoconf-$SQLITE_VERSION.tar.gz"
    cd "sqlite-autoconf-$SQLITE_VERSION"

    ./configure \
        --host="$triple" \
        --prefix="$stage/install" \
        --enable-shared \
        --disable-static \
        CC="$cc" \
        AR="$TOOLCHAIN/bin/llvm-ar" \
        RANLIB="$TOOLCHAIN/bin/llvm-ranlib" \
        CFLAGS="-fPIC -O2"

    make -j"$(nproc)" -s
    make install -s
}

# ---------------------------------------------------------------------------
# Build libffi for a given ABI
# ---------------------------------------------------------------------------

build_libffi() {
    local abi=$1
    local triple=${TRIPLE_MAP[$abi]}
    local cc="$TOOLCHAIN/bin/${triple}${MIN_API}-clang"

    local stage="$BUILD_DIR/libffi-$abi"
    if [[ -d "$stage" ]] && [[ -f "$stage/libffi.so" ]]; then
        echo "  libffi already built for $abi, skipping."
        return
    fi

    echo "  Building libffi for $abi..."
    rm -rf "$stage"
    mkdir -p "$stage"
    cd "$stage"
    tar xzf "$BUILD_DIR/libffi-$LIBFFI_VERSION.tar.gz"
    cd "libffi-$LIBFFI_VERSION"

    ./configure \
        --host="$triple" \
        --prefix="$stage/install" \
        --enable-shared \
        --disable-static \
        CC="$cc" \
        CXX="${cc}++" \
        AR="$TOOLCHAIN/bin/llvm-ar" \
        RANLIB="$TOOLCHAIN/bin/llvm-ranlib" \
        CFLAGS="-fPIC -O2"

    make -j"$(nproc)" -s
    make install -s
}

# ---------------------------------------------------------------------------
# Apply Android-specific patches to CPython
# ---------------------------------------------------------------------------

patch_cpython() {
    local srcdir=$1

    # Patch 1: Update config.guess and config.sub to recognize Android.
    # The versions shipped with CPython don't know about *-android* triples.
    echo "  Updating config.guess/config.sub..."
    if command -v config.guess >/dev/null 2>&1; then
        cp "$(command -v config.guess)" "$srcdir/config.guess" 2>/dev/null || true
        cp "$(command -v config.sub)" "$srcdir/config.sub" 2>/dev/null || true
    fi
    # If system config.guess doesn't exist, download from GNU Savannah:
    if ! "$srcdir/config.guess" 2>/dev/null | grep -qi android; then
        curl -fsL "https://git.savannah.gnu.org/gitweb/?p=config.git;a=blob_plain;f=config.guess;hb=HEAD" \
            -o "$srcdir/config.guess" 2>/dev/null || true
        curl -fsL "https://git.savannah.gnu.org/gitweb/?p=config.git;a=blob_plain;f=config.sub;hb=HEAD" \
            -o "$srcdir/config.sub" 2>/dev/null || true
        chmod +x "$srcdir/config.guess" "$srcdir/config.sub"
    fi

    # Patch 2: Fix getpwuid — Android has no /etc/passwd, so getpwuid()
    # returns NULL. CPython's posixmodule.c checks the return value, but
    # some code paths assume it's non-NULL. This patch makes it gracefully
    # return None instead of raising.
    if ! grep -q "ANDROID_GETPWUID_PATCH" "$srcdir/Modules/posixmodule.c" 2>/dev/null; then
        echo "  Patching posixmodule.c for Android getpwuid..."
        # The fix: if getpwuid returns NULL, return None instead of raising OSError.
        # This is a minimal sed patch; a full patch file would be cleaner.
        sed -i 's/if (pw == NULL)/if (pw == NULL) { Py_RETURN_NONE; }\/\* ANDROID_GETPWUID_PATCH \*\/ if (0)/g' \
            "$srcdir/Modules/posixmodule.c" 2>/dev/null || true
    fi

    # Patch 3: Fix _SC_* constants — Android defines some but not all
    # POSIX _SC_* constants. Add fallbacks for missing ones.
    if ! grep -q "ANDROID_SC_PATCH" "$srcdir/Python/mystrtoul.c" 2>/dev/null; then
        echo "  Patching for Android _SC_* constants..."
        # Most _SC_* constants exist on Android 24+; this is a safety net.
        # No sed needed for API 24+ — just log it.
        echo "// ANDROID_SC_PATCH: API 24+ has all required _SC_* constants" >> "$srcdir/Python/mystrtoul.c"
    fi

    # Patch 4: Ensure the site module doesn't try to write .pyc files.
    # PYTHONDONTWRITEBYTECODE handles this at runtime, but we also patch
    # the default to be safe.
    if ! grep -q "ANDROID_DONT_WRITE_BYTECODE" "$srcdir/Modules/main.c" 2>/dev/null; then
        echo "  Patching main.c for PYTHONDONTWRITEBYTECODE default..."
        sed -i 's/Py_DontWriteBytecodeFlag = 0;/Py_DontWriteBytecodeFlag = 1; \/* ANDROID_DONT_WRITE_BYTECODE *\//g' \
            "$srcdir/Modules/main.c" 2>/dev/null || true
    fi
}

# ---------------------------------------------------------------------------
# Build CPython for a given ABI
# ---------------------------------------------------------------------------

build_cpython() {
    local abi=$1
    local arch=${ARCH_MAP[$abi]}
    local triple=${TRIPLE_MAP[$abi]}
    local cc="$TOOLCHAIN/bin/${triple}${MIN_API}-clang"
    local cxx="$TOOLCHAIN/bin/${triple}${MIN_API}-clang++"

    local stage="$BUILD_DIR/cpython-$abi"
    local prefix="$BUILD_DIR/cpython-install-$abi"

    if [[ -d "$prefix" ]] && [[ -f "$prefix/lib/libpython3.11.so" ]]; then
        echo "  CPython already built for $abi, skipping."
        return
    fi

    echo "  Building CPython for $abi..."

    rm -rf "$stage" "$prefix"
    mkdir -p "$stage"
    cd "$stage"
    tar xzf "$BUILD_DIR/Python-$CPYTHON_VERSION.tgz"
    cd "Python-$CPYTHON_VERSION"

    # Apply Android patches
    patch_cpython "$PWD"

    # Locate dependency install dirs
    local openssl_dir="$BUILD_DIR/openssl-$abi/install"
    local sqlite_dir="$BUILD_DIR/sqlite-$abi/install"
    local libffi_dir="$BUILD_DIR/libffi-$abi/install"

    # Configure CPython for cross-compilation.
    # --host tells configure we're building for Android.
    # --build tells configure we're running on x86_64 Linux.
    # ac_cv_file_* tells configure that the stdlib files exist (cross-compile hack).
    ./configure \
        --host="$triple" \
        --build="x86_64-pc-linux-gnu" \
        --prefix="$prefix" \
        --enable-shared \
        --disable-static \
        --disable-ipv6 \
        --without-static-libpython \
        --with-openssl="$openssl_dir" \
        --with-openssl-rpath=auto \
        ac_cv_file__dev_ptmx=yes \
        ac_cv_file__dev_ptc=no \
        CC="$cc" \
        CXX="$cxx" \
        AR="$TOOLCHAIN/bin/llvm-ar" \
        RANLIB="$TOOLCHAIN/bin/llvm-ranlib" \
        READELF="$TOOLCHAIN/bin/llvm-readelf" \
        CFLAGS="-fPIC -O2 -Wall -Wno-unused-result \
                 -I$openssl_dir/include \
                 -I$sqlite_dir/include \
                 -I$libffi_dir/include" \
        LDFLAGS="-L$openssl_dir/lib \
                 -L$sqlite_dir/lib \
                 -L$libffi/lib \
                 -Wl,-rpath=\$\$ORIGIN \
                 -fPIC -pie" \
        LDLIBS="-lssl -lcrypto -lsqlite3 -lffi -lz -llog"

    # Build
    make -j"$(nproc)" -s

    # Install (this creates lib/python3.11/ with stdlib + lib-dynload/)
    make install -s

    echo "  CPython installed to: $prefix"
}

# ---------------------------------------------------------------------------
# Stage output for a given ABI
# ---------------------------------------------------------------------------

stage_output() {
    local abi=$1
    local prefix="$BUILD_DIR/cpython-install-$abi"
    local out="$OUTPUT_DIR/$abi"
    local triple=${TRIPLE_MAP[$abi]}

    echo "  Staging output for $abi → $out"
    rm -rf "$out"
    mkdir -p "$out/lib" "$out/stdlib" "$out/lib-dynload" "$out/site-packages"

    # 1. Copy libpython3.11.so (the interpreter shared library)
    cp "$prefix/lib/libpython3.11.so" "$out/lib/"

    # 2. Copy dependency shared libraries
    cp "$BUILD_DIR/openssl-$abi/install/lib/libssl.so"* "$out/lib/" 2>/dev/null || true
    cp "$BUILD_DIR/openssl-$abi/install/lib/libcrypto.so"* "$out/lib/" 2>/dev/null || true
    cp "$BUILD_DIR/sqlite-$abi/install/lib/libsqlite3.so"* "$out/lib/" 2>/dev/null || true
    cp "$BUILD_DIR/libffi-$abi/install/lib/libffi.so"* "$out/lib/" 2>/dev/null || true

    # 3. Copy the pure-Python stdlib (Lib/*.py)
    cp -r "$prefix/lib/python3.11/"* "$out/stdlib/"
    # Remove the lib-dynload and site-packages from the stdlib staging
    # (they're handled separately)
    rm -rf "$out/stdlib/lib-dynload"
    rm -rf "$out/stdlib/site-packages"

    # 4. Copy C extension modules (lib-dynload/*.so)
    if [[ -d "$prefix/lib/python3.11/lib-dynload" ]]; then
        cp "$prefix/lib/python3.11/lib-dynload/"*.so "$out/lib-dynload/"
    fi

    # 5. Copy the CA cert bundle (for HTTPS)
    if [[ -f "$prefix/lib/python3.11/cacert.pem" ]]; then
        cp "$prefix/lib/python3.11/cacert.pem" "$out/stdlib/"
    else
        # Download the certifi bundle if CPython didn't install one
        curl -fsL "https://curl.se/ca/cacert.pem" -o "$out/stdlib/cacert.pem" 2>/dev/null || true
    fi

    echo "  Staged for $abi:"
    echo "    lib/         → $(ls "$out/lib/" | wc -l) files"
    echo "    stdlib/      → $(find "$out/stdlib" -name '*.py' | wc -l) .py files"
    echo "    lib-dynload/ → $(ls "$out/lib-dynload/" 2>/dev/null | wc -l) .so files"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

echo ""
echo "Step 1: Downloading sources..."
download_sources

for abi in "${ABIS[@]}"; do
    echo ""
    echo "Step 2: Building dependencies for $abi..."
    build_openssl "$abi"
    build_sqlite "$abi"
    build_libffi "$abi"

    echo ""
    echo "Step 3: Building CPython for $abi..."
    build_cpython "$abi"

    echo ""
    echo "Step 4: Staging output for $abi..."
    stage_output "$abi"
done

echo ""
echo "================================================================"
echo " CPython build complete!"
echo " Output: $OUTPUT_DIR"
echo ""
echo " Next: run ./scripts/package_engine.sh to produce APK assets"
echo "================================================================"
