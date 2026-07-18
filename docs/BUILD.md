# Build Guide

MediaHub is an Android application built from three coordinated layers: Flutter
(Dart UI), Android Kotlin (native services + bridge), and an embedded CPython
media engine. This guide explains how to produce debug and release builds.

> **Prerequisites**: Flutter SDK ≥ 3.27, Android Studio with Android SDK
> platform 34, JDK 17, Python 3.11+ (host), Android NDK r26+.

## 1. First-time setup

### 1.1 Clone and install Flutter dependencies

```bash
git clone <repo-url> mediahub
cd mediahub
flutter pub get
```

### 1.2 Configure the Flutter SDK path

```bash
cd android
cp local.properties.example local.properties
# Edit local.properties:
#   flutter.sdk=/path/to/your/flutter
#   sdk.dir=/path/to/your/Android/Sdk
```

### 1.3 Build the embedded Python runtime (one-time, ~30 min)

The Python interpreter, standard library, third-party packages (yt-dlp,
gallery-dl, Instaloader, pydantic), and FFmpeg must be cross-compiled for
Android and packaged into the APK. This is done once and cached in `build/`.

```bash
# Set the NDK path
export ANDROID_NDK_HOME=/path/to/android-ndk-r26d

# Run the orchestrator (builds CPython + FFmpeg + packages)
./scripts/prepare_python_runtime.sh
```

This produces:

| Output | Location | Purpose |
|--------|----------|---------|
| `libpython3.11.so` | `jniLibs/<abi>/` | CPython interpreter |
| `libssl.so`, `libcrypto.so` | `jniLibs/<abi>/` | OpenSSL for HTTPS |
| `libsqlite3.so` | `jniLibs/<abi>/` | SQLite C extension |
| `libffi.so` | `jniLibs/<abi>/` | ctypes C extension |
| `libffmpeg.so` | `jniLibs/<abi>/` | FFmpeg binary |
| `python_stdlib.zip` | `assets/` | Python stdlib + C extensions |
| `python_packages.zip` | `assets/` | yt-dlp + gallery-dl + instaloader + pydantic + mediahub_engine |

> Re-running the script only rebuilds what's missing (incremental). To force
> a full rebuild, delete the `build/` directory first.

### 1.4 Python engine (for standalone development/debugging)

```bash
cd python_engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Smoke test the engine standalone:
echo '{"jsonrpc":"2.0","id":1,"method":"engine.ping","params":{}}' | \
  python -m mediahub_engine
```

## 2. Debug build

```bash
flutter run --flavor standard -t lib/main.dart

# Or produce a debug APK
flutter build apk --flavor standard --debug -t lib/main.dart
```

## 3. Release build

### 3.1 Create a release keystore (one-time)

```bash
keytool -genkey -v -keystore ~/mediahub.jks \
  -keyalg RSA -keysize 4096 -validity 10000 -alias mediahub
```

### 3.2 Configure `android/key.properties`

```properties
storePassword=your-store-password
keyPassword=your-key-password
keyAlias=mediahub
storeFile=/Users/you/mediahub.jks
```

### 3.3 Build

```bash
flutter build apk --flavor standard --release -t lib/main.dart
# Or App Bundle:
flutter build appbundle --flavor standard --release -t lib/main.dart
```

## 4. How the Python runtime works on Android

### 4.1 Packaging

Android packages native code as `.so` files in `lib/<abi>/`. The CPython
interpreter is compiled as a PIE executable, renamed to `libpython3.11.so`,
and included in the APK. At install time, Android extracts it to
`nativeLibraryDir` (read-only).

### 4.2 First-run extraction (`PythonBootstrap`)

On first launch, `PythonBootstrap.prepare()`:

1. **Copies** `libpython3.11.so` from `nativeLibraryDir` to `filesDir/bin/python3`
   and marks it executable (`setExecutable(true)`).
2. **Extracts** `python_stdlib.zip` from assets to `filesDir/python/lib/python3.11/`.
   This includes pure-Python `.py` files and C extension `.so` files in
   `lib-dynload/`.
3. **Extracts** `python_packages.zip` from assets to `filesDir/python/lib/python3.11/site-packages/`.
4. **Copies** `libffmpeg.so` to `filesDir/bin/ffmpeg` and marks it executable.
5. **Writes** a version marker file so subsequent launches skip extraction.

### 4.3 Process launch (`PythonRuntime`)

`PythonRuntime` launches the engine via `ProcessBuilder` with:

```kotlin
ProcessBuilder("filesDir/bin/python3", "-u", "-m", "mediahub_engine")
```

Environment variables (critical for CPython on Android):

| Variable | Value | Purpose |
|----------|-------|---------|
| `PYTHONHOME` | `filesDir/python` | Tells CPython where to find its stdlib |
| `PYTHONPATH` | stdlib + lib-dynload + site-packages | Tells CPython where to find importable modules |
| `LD_LIBRARY_PATH` | `nativeLibraryDir` | Lets CPython `dlopen` C extensions (`_ssl.so`, etc.) |
| `PYTHONUNBUFFERED` | `1` | Unbuffered stdio for JSON-RPC line framing |
| `PYTHONIOENCODING` | `utf-8` | Deterministic encoding |
| `PYTHONDONTWRITEBYTECODE` | `1` | No `.pyc` files (saves disk) |
| `MEDIAHUB_WORKDIR` | `filesDir/engine` | Engine work directory |
| `PATH` | `filesDir/bin:$PATH` | So yt-dlp can find `ffmpeg` |
| `FFMPEG_BINARY` | `filesDir/bin/ffmpeg` | Explicit FFmpeg path |

### 4.4 Communication

The engine communicates via **line-delimited JSON-RPC 2.0 over stdio**:
- Kotlin writes requests to the process's stdin
- Python writes responses to stdout
- Python writes structured JSON logs to stderr (forwarded to logcat)
- Progress notifications flow as JSON-RPC notifications (no `id`)

All 73 engine methods, the JSON-RPC dispatcher, the provider system, the
download manager, and all repositories are **completely unchanged** — only
the transport layer (ProcessBuilder + environment) was fixed.

## 5. Running tests

```bash
# Python
cd python_engine && pytest -q

# Flutter
flutter test

# Lint
flutter analyze
cd python_engine && ruff check .
```

## 6. Troubleshooting

See `docs/TROUBLESHOOTING.md`.
