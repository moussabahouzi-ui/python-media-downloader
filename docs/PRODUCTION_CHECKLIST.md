# Production Release Checklist

Use this checklist before every MediaHub release. Every item must be ✅.

## 1. Source code

- [ ] All Python tests pass: `cd python_engine && pytest -q` (372 tests)
- [ ] Python ruff clean: `cd python_engine && ruff check .`
- [ ] Flutter analyze clean: `flutter analyze`
- [ ] Flutter tests pass: `flutter test`
- [ ] No `TODO` / `FIXME` / `HACK` comments in release-critical paths
- [ ] Bridge version (`kBridgeVersion`) is consistent across Dart, Kotlin, Python
- [ ] `CHANGELOG.md` updated with the release version + date
- [ ] `pubspec.yaml` version bumped (semantic versioning)
- [ ] `mediahub_engine/__init__.py` `__version__` matches
- [ ] `gradle.properties` `mediahub.versionName` / `versionCode` matches

## 2. Flutter layer

- [ ] `flutter pub get` succeeds without conflicts
- [ ] `flutter analyze` reports zero warnings/errors
- [ ] All `import` paths resolve (no broken relative imports)
- [ ] `pubspec.yaml` `assets:` entries point to existing directories
- [ ] `main.dart` overrides `appConfigProvider` + `playerBackendProvider`
- [ ] All `context.go()` / `context.push()` calls use valid route paths
- [ ] No `substring()` calls on potentially short strings without length guards
- [ ] `EngineService._guard` returns `Result<T>` (not throws)
- [ ] No duplicate enum definitions across model files
- [ ] Flutter SDK constraint in `pubspec.yaml` matches actual API usage (≥ 3.27)

## 3. Kotlin / Android layer

- [ ] `local.properties` exists with `flutter.sdk` + `sdk.dir` set
- [ ] `settings.gradle.kts` includes the Flutter Gradle Plugin loader
- [ ] `app/build.gradle.kts` applies `dev.flutter.flutter-gradle-plugin`
- [ ] `compileSdk` = 34, `minSdk` = 24, `targetSdk` = 34
- [ ] JDK 17 set in `JAVA_HOME`
- [ ] All `libs.xxx` references resolve to `libs.versions.toml` entries
- [ ] `themes.xml` declares `xmlns:tools` if using `tools:targetApi`
- [ ] Parent theme (`Theme.AppCompat.DayNight.NoActionBar`) is available
- [ ] `AndroidManifest.xml` declares all needed permissions
- [ ] `WRITE_EXTERNAL_STORAGE` has `maxSdkVersion="28"`
- [ ] `foregroundServiceType="dataSync"` matches `FOREGROUND_SERVICE_DATA_SYNC` permission
- [ ] All `<activity>` / `<service>` have `android:exported` set
- [ ] `android:supportsPictureInPicture="true"` on `MainActivity`
- [ ] `data_extraction_rules.xml` excludes `mediahub_secure.xml` from backup
- [ ] Release `signingConfig` reads from `key.properties`
- [ ] R8 full mode + resource shrinking enabled for release
- [ ] `proguard-rules.pro` keeps `io.flutter.**` + `com.mediahub.app.bridge.**`
- [ ] All Kotlin `suspend` functions are marked `suspend`
- [ ] `PythonRuntime.doStart()` is `suspend`
- [ ] `DownloadForegroundService.onDestroy()` calls `unbind()`
- [ ] `ensureRuntime()` is `@Synchronized`
- [ ] `EngineMethodChannel` uses `DownloadForegroundService.start()` (not bare `startService`)
- [ ] Event-channel collector `Job` is cancelled in `onCancel`
- [ ] `JSONObject.NULL` is handled in `toMap()` / `toList()` helpers
- [ ] `MainActivity` PiP `isInPipMode()` called with parentheses

## 4. Python engine

- [ ] Engine boots standalone: `echo '{"jsonrpc":"2.0","id":1,"method":"engine.ping","params":{}}' | python -m mediahub_engine`
- [ ] `stdout` contains only JSON-RPC (no stray prints)
- [ ] `stderr` contains structured JSON logs only
- [ ] All 13 platform providers register successfully (check log on startup)
- [ ] `provider.list` returns 14 providers (13 platforms + generic)
- [ ] SQLite database auto-creates on first run (`mediahub.db`)
- [ ] All 6 tables present: `download_tasks`, `media_items`, `download_history`,
      `collections`, `collection_items`, `playlists`, `playlist_items`,
      `app_settings`, `scheduled_tasks`, `credentials`
- [ ] Settings `get_all` returns 16 default keys
- [ ] Credentials are encrypted at rest (password column is base64, not plaintext)

## 5. Security

- [ ] No hardcoded secrets / API keys in source
- [ ] `SecurePreferences` initializes `EncryptedSharedPreferences` on startup
- [ ] Engine encryption key generated via `SecureRandom` and stored in Keystore
- [ ] `credentials.get` never returns passwords in plaintext (only `hasPassword`)
- [ ] R8 obfuscation enabled for release
- [ ] `android:allowBackup` does not back up `mediahub_secure.xml`
- [ ] No `MANAGE_EXTERNAL_STORAGE` in `standard` flavor
- [ ] All network traffic uses HTTPS (cleartext off by default)

## 6. Background services

- [ ] `DownloadForegroundService` starts with a notification on `onCreate`
- [ ] `startForeground` uses `FOREGROUND_SERVICE_TYPE_DATA_SYNC` on API 29+
- [ ] Notification channels registered in `MediaHubApplication.onCreate`
- [ ] WorkManager `ScheduleCheckWorker` registered with 15-min periodic interval
- [ ] `DownloadScheduler.start()` called in `MediaHubApplication.onCreate`
- [ ] Service survives Activity recreation (singleton `instance` pattern)
- [ ] `onDestroy` disposes `PythonRuntime` + calls `unbind()`

## 7. Storage

- [ ] Downloads land under app-specific external storage (no permission needed on API 29+)
- [ ] `WRITE_EXTERNAL_STORAGE` declared for API 24-28 public Downloads fallback
- [ ] Recycle bin directory created under app-internal storage
- [ ] SQLite uses WAL journal mode for concurrent reads
- [ ] Media items auto-indexed on download completion
- [ ] File manager operations (rename/move/copy/delete) keep index in sync

## 8. Release APK verification

- [ ] `flutter build apk --flavor standard --release` succeeds
- [ ] APK is signed (verify with `jarsigner -verify -verbose app-standard-release.apk`)
- [ ] APK installs on a real Android 14 device
- [ ] App launches without crash
- [ ] Home screen renders with engine health card
- [ ] Download Center accepts a URL and detects the provider
- [ ] Library screen loads (empty state if no downloads)
- [ ] Settings screen loads and persists changes
- [ ] Scheduler screen loads and can create a schedule
- [ ] Background download completes with the app backgrounded
- [ ] Notification appears during download
- [ ] PiP mode works (video player → home button → PiP)
- [ ] App survives kill + restart (downloads resume from partial files)

## 9. Documentation

- [ ] `README.md` is up to date
- [ ] `CHANGELOG.md` has the release entry
- [ ] `docs/ARCHITECTURE.md` reflects the current state
- [ ] `docs/BRIDGE_CONTRACT.md` matches the implemented method surface
- [ ] `docs/BUILD.md` has accurate build instructions
- [ ] `docs/TROUBLESHOOTING.md` covers known issues
- [ ] `docs/PROVIDERS.md` lists all 14 providers
- [ ] `docs/DOWNLOAD_MANAGER.md` reflects the FSM + persistence
- [ ] `docs/MEDIA_LIBRARY.md` reflects the library + file manager
- [ ] `docs/PLAYERS.md` reflects the player + PiP + playlists

## 10. Git / release

- [ ] `main` branch is green (CI passing)
- [ ] Release tag created: `git tag -a v0.1.0 -m "Release 0.1.0"`
- [ ] Tag pushed: `git push origin v0.1.0`
- [ ] Release notes drafted from `CHANGELOG.md`
- [ ] APK/AAB uploaded to the distribution channel
