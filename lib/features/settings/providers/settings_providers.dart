import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_theme.dart';
import '../../../services/engine_service.dart';

/// Immutable settings state backing the Settings screen.
///
/// In Phase 1 this was a simple in-memory notifier. In Phase 6 it is backed by
/// the Python engine's `settings.*` methods, so settings persist across app
/// restarts and are shared with the engine (e.g. `download.maxConcurrent`).
@immutable
class SettingsState {
  const SettingsState({
    this.themeMode = ThemeModePreference.system,
    this.useDynamicColor = true,
    this.language = 'en',
    this.defaultDestDir = '',
    this.maxConcurrent = 4,
    this.maxRetries = 3,
    this.encryptStorage = true,
    this.autoLock = false,
    this.isLoading = false,
    this.error,
  });

  final ThemeModePreference themeMode;
  final bool useDynamicColor;
  final String language;
  final String defaultDestDir;
  final int maxConcurrent;
  final int maxRetries;
  final bool encryptStorage;
  final bool autoLock;
  final bool isLoading;
  final String? error;

  SettingsState copyWith({
    ThemeModePreference? themeMode,
    bool? useDynamicColor,
    String? language,
    String? defaultDestDir,
    int? maxConcurrent,
    int? maxRetries,
    bool? encryptStorage,
    bool? autoLock,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return SettingsState(
      themeMode: themeMode ?? this.themeMode,
      useDynamicColor: useDynamicColor ?? this.useDynamicColor,
      language: language ?? this.language,
      defaultDestDir: defaultDestDir ?? this.defaultDestDir,
      maxConcurrent: maxConcurrent ?? this.maxConcurrent,
      maxRetries: maxRetries ?? this.maxRetries,
      encryptStorage: encryptStorage ?? this.encryptStorage,
      autoLock: autoLock ?? this.autoLock,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

/// Notifier owning the full settings state, backed by the engine settings store.
class SettingsNotifier extends StateNotifier<SettingsState> {
  SettingsNotifier(this._engine) : super(const SettingsState(isLoading: true));

  final EngineService _engine;

  /// Loads all settings from the engine.
  Future<void> load() async {
    state = state.copyWith(isLoading: true, clearError: true);
    final result = await _engine.getAllSettings();
    result.fold(
      onSuccess: (settings) {
        final themeModeStr = settings['appearance.themeMode'] as String? ?? 'system';
        final themeMode = ThemeModePreference.values.firstWhere(
          (m) => m.name == themeModeStr,
          orElse: () => ThemeModePreference.system,
        );
        state = SettingsState(
          themeMode: themeMode,
          useDynamicColor: settings['appearance.useDynamicColor'] as bool? ?? true,
          language: settings['appearance.language'] as String? ?? 'en',
          defaultDestDir: settings['download.defaultDestDir'] as String? ?? '',
          maxConcurrent: (settings['download.maxConcurrent'] as num?)?.toInt() ?? 4,
          maxRetries: (settings['download.maxRetries'] as num?)?.toInt() ?? 3,
          encryptStorage: settings['security.encryptStorage'] as bool? ?? true,
          autoLock: settings['security.autoLock'] as bool? ?? false,
          isLoading: false,
        );
      },
      onFailure: (f) => state = state.copyWith(isLoading: false, error: f.message),
    );
  }

  Future<void> setThemeMode(ThemeModePreference mode) async {
    state = state.copyWith(themeMode: mode);
    await _engine.setSetting('appearance.themeMode', mode.name);
  }

  Future<void> setDynamicColor(bool enabled) async {
    state = state.copyWith(useDynamicColor: enabled);
    await _engine.setSetting('appearance.useDynamicColor', enabled);
  }

  Future<void> setLanguage(String lang) async {
    state = state.copyWith(language: lang);
    await _engine.setSetting('appearance.language', lang);
  }

  Future<void> setMaxConcurrent(int value) async {
    state = state.copyWith(maxConcurrent: value);
    await _engine.setSetting('download.maxConcurrent', value);
  }

  Future<void> setMaxRetries(int value) async {
    state = state.copyWith(maxRetries: value);
    await _engine.setSetting('download.maxRetries', value);
  }

  Future<void> setEncryptStorage(bool enabled) async {
    state = state.copyWith(encryptStorage: enabled);
    await _engine.setSetting('security.encryptStorage', enabled);
  }

  Future<void> setAutoLock(bool enabled) async {
    state = state.copyWith(autoLock: enabled);
    await _engine.setSetting('security.autoLock', enabled);
  }

  Future<void> reset() async {
    await _engine.resetSettings();
    await load();
  }
}

final StateNotifierProvider<SettingsNotifier, SettingsState> settingsProvider =
    StateNotifierProvider<SettingsNotifier, SettingsState>(
  (ref) => SettingsNotifier(ref.watch(engineServiceProvider)),
  name: 'settingsProvider',
);

/// A second provider that mirrors the Phase 1 name used by [MediaHubApp] for
/// the theme mode. The app widget watches this for rebuilds.
final Provider<ThemeModePreference> themeModePreferenceProvider =
    Provider<ThemeModePreference>(
  (ref) => ref.watch(settingsProvider.select((s) => s.themeMode)),
  name: 'themeModePreferenceProvider',
);

/// Alias for the Settings screen — it uses the same notifier but under the
/// name the screen imports.
final StateNotifierProvider<SettingsNotifier, SettingsState> settingsStoreProvider =
    settingsProvider;
