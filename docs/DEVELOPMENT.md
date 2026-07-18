# Development Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Flutter SDK | >= 3.22 stable | `flutter --version` |
| Dart | >= 3.4 | bundled with Flutter |
| Android Studio | Hedgehog+ or latest | includes Android SDK + platform tools |
| Android SDK | API 34 (Android 14) | minSdk 24, targetSdk 34 |
| JDK | 17 | required by AGP 8.x |
| Python | 3.11+ | for the embedded engine + tests |
| `uv` or `pip` | latest | Python dependency management |
| FFmpeg | 6.x | bundled into the app at packaging time |

## Environment setup

```bash
# 1. Clone
git clone <repo-url> mediahub
cd mediahub

# 2. Flutter deps
flutter pub get
dart run build_runner build --delete-conflicting-outputs

# 3. Python engine (dev)
cd python_engine
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
cd ..

# 4. Generate Flutter platform scaffolding (first run only)
flutter create --platforms=android --org com.mediahub --project-name mediahub .
```

> The `android/` directory in this repo is hand-authored to integrate the
> Kotlin bridge. Running `flutter create .` will only fill in missing files;
# it will not overwrite existing Kotlin sources.
# Re-run codegen after editing any `@riverpod` or `@freezed` annotated file:
```bash
dart run build_runner watch --delete-conflicting-outputs
```

## Running

```bash
# Device
flutter run --flavor standard -t lib/main.dart

# Python engine standalone (for IPC debugging)
cd python_engine
echo '{"jsonrpc":"2.0","id":1,"method":"engine.ping","params":{}}' | \
  python -m mediahub_engine
```

## Code generation

| Generator | Trigger | Output |
|-----------|---------|--------|
| `build_runner` | `@freezed`, `@json_serializable`, `@riverpod` | `*.g.dart`, `*.freezed.dart` |
| `riverpod_generator` | `@riverpod` | `*.g.dart` |

Generated files are git-ignored locally but **must** be regenerated on every
checkout before building.

## Linting

```bash
# Dart
flutter analyze
dart run custom_lint

# Python
ruff check python_engine
ruff format --check python_engine

# Kotlin (run from Android Studio)
# ktlint + detekt via Gradle tasks: ./gradlew ktlintCheck detekt
```

## Testing

```bash
# Flutter
flutter test --coverage

# Python
cd python_engine && pytest -q
```

## Committing

- Conventional Commits only (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`, `perf:`).
- Scope per layer: `feat(flutter):`, `feat(android):`, `feat(engine):`.
- Every commit must pass `flutter analyze`, `ruff check`, and all tests on CI.

## Branching

- `main` — always green, releasable.
- `feature/<phase>-<topic>` — feature branches.
- `fix/<topic>` — bug fixes.
- `release/vX.Y.Z` — release prep.

See `docs/CONTRIBUTING.md` for the full contribution workflow.
