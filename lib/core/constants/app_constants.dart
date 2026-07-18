/// Application-wide constants for MediaHub.
///
/// These are compile-time constants only. Runtime-configurable values live in
/// [AppConfig].
library;

/// Public package name / application id.
const String kApplicationId = 'com.mediahub.app';

/// Semantic version, single source of truth for the Flutter layer.
/// Keep in sync with `pubspec.yaml`, the Android `build.gradle.kts`, and
/// `python_engine/mediahub_engine/__init__.py`.
const String kAppVersion = '0.1.0';

/// Method channel bridge version. See `docs/BRIDGE_CONTRACT.md`.
const int kBridgeVersion = 1;

/// Method channel name shared between Dart and Kotlin.
const String kEngineMethodChannelName = '$kApplicationId/engine';

/// Event channel name for engine notifications (progress, state changes).
const String kEngineEventChannelName = '$kApplicationId/engine/events';

/// Default JSON-RPC call timeout when communicating with the Python engine.
const Duration kEngineDefaultTimeout = Duration(seconds: 30);

/// Maximum progress-event frequency crossing the bridge (events per second).
const double kMaxProgressEventsPerSecond = 4;

/// Hive box names.
const String kHiveBoxSettings = 'mediahub_settings';
const String kHiveBoxFavorites = 'mediahub_favorites';
const String kHiveBoxRecents = 'mediahub_recents';

/// SQLite database file name.
const String kSqliteDbName = 'mediahub.db';

/// Supported download categories.
const List<String> kMediaCategories = ['video', 'audio', 'image', 'gallery'];
