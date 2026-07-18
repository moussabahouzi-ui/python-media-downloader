# Troubleshooting Guide

Common issues and their solutions when building and running MediaHub.

## Build issues

### `MethodChannel` not implemented

**Symptom**: Flutter UI loads but engine calls return `ENGINE_NOT_READY`.

**Fix**: Ensure `MainActivity` registers the `EngineMethodChannel` in
`configureFlutterEngine` and the `DownloadForegroundService` is started. The
service is started automatically by `EngineMethodChannel.attach()`.

### Python runtime "command not found" on device

**Symptom**: `PythonRuntime` logs "Python runtime exited immediately".

**Fix**: The Python engine packaging pipeline (Phase 6 packaging) bundles the
interpreter into `jniLibs/`. During development, point
`PythonRuntimeConfig.devPythonPath` at an on-device Python, or run the engine
standalone on the host for debugging:

```bash
cd python_engine
python -m mediahub_engine
```

### `build_runner` conflicts

**Symptom**: Code generation fails with conflicting outputs.

**Fix**:
```bash
dart run build_runner build --delete-conflicting-outputs
```

### ktlint / detekt failures

**Fix**: Run from `android/`:
```bash
./gradlew ktlintFormat detekt
```

## Runtime issues

### Downloads stuck in "queued"

**Cause**: The foreground service isn't running, or the engine failed to start.

**Fix**:
1. Check `dev.log` / logcat for `PythonRuntime` errors.
2. Verify the engine is healthy via the Home screen's "Media engine" card.
3. If offline, downloads will queue until connectivity returns.

### Provider not found for a URL

**Symptom**: `PROVIDER_NOT_FOUND` error when downloading.

**Cause**: The URL doesn't match any provider's `url_patterns`, and it's not a
direct media file (no `.mp4`/`.mp3`/etc. extension).

**Fix**: Check `provider.list` output (Home → Settings → About) to see
supported platforms. For direct media URLs, ensure the URL ends with a
recognized extension.

### yt-dlp / gallery-dl not available

**Symptom**: `BackendNotAvailableError` when downloading from a platform.

**Cause**: The extraction library isn't bundled in the APK (Phase 6 packaging
step not yet run, or the library failed to import).

**Fix**: The generic HTTP provider still works for direct media URLs. For
platform URLs, ensure the Python packaging step includes yt-dlp / gallery-dl /
instaloader in the embedded site-packages.

### Paused download doesn't resume

**Cause**: The partial `.part` file was deleted, or the dest_dir changed.

**Fix**: Resume requires the same `dest_dir` as the original download. The
`RecoveryManager` scans for `.part` files (yt-dlp) and known output paths. If
the partial file is gone, the download restarts from scratch.

### Credentials not working

**Symptom**: Auth-required provider (e.g. Twitter/X) returns 401/403.

**Fix**:
1. Go to Settings → Security and verify credentials are set.
2. Use `credentials.has` to confirm the provider has stored credentials.
3. For Instagram, a `cookies_path` (Netscape-format cookies file) is often
   more reliable than username/password.

### Scheduled downloads not firing

**Cause**: WorkManager's minimum periodic interval is 15 minutes; schedules
may take up to 15 min to fire after their `next_run_at`.

**Fix**:
- Check `scheduler.due` returns the schedule.
- Verify the foreground service is running (WorkManager calls into it).
- For one-time schedules, use a short delay for testing.

### App crashes on startup

**Cause**: Corrupted SQLite database (rare; usually after a force-kill during
a write).

**Fix**: Clear app data or delete `mediahub.db` under the engine work_dir.
Download history and media index will be lost, but downloaded files remain.

## Performance issues

### High battery usage

**Cause**: Too many concurrent downloads or frequent progress notifications.

**Fix**:
- Settings → Downloads → Max concurrent: reduce to 2-3.
- The progress emit interval (default 4 Hz / 250 ms) can be increased via
  `download.progressInterval` setting.

### Slow library scrolling

**Cause**: Large library (>1000 items) loaded at once.

**Fix**: The library uses pagination (default 500 items). Increase
`limit` on `library.list` only if needed; the grid is virtualized.

### Duplicate files taking up space

**Fix**: Settings → Storage → "Find duplicates" runs the two-pass SHA-256
scanner. Review and delete duplicates from the results.

## Security

### Forgot app lock

**Symptom**: Auto-lock enabled and biometric unavailable.

**Fix**: Clear app data (this also clears credentials and settings). Re-configure
credentials after re-launching.

### Credentials appear in plain text

**Verification**: They should NOT. The `CredentialsRepository` encrypts
passwords and tokens at rest with a key derived from Android Keystore (in
production) or the DB path (dev). The `credentials.get` engine method never
returns the password — only `hasPassword: true`.

If you see plain text in the DB, the `encryption_key` is wrong or the
`SecurePreferences` fell back to plain prefs (check logcat for
`SecurePreferences` warnings).

## Getting help

- Check the engine logs: Home → Settings → About shows the engine version.
  Structured JSON logs go to stderr (logcat tag: `PythonRuntime`).
- Run the engine standalone to isolate IPC issues:
  ```bash
  echo '{"jsonrpc":"2.0","id":1,"method":"engine.ping","params":{}}' | \
    python -m mediahub_engine
  ```
- File issues with the engine version, bridge version, and relevant log
  excerpts.
