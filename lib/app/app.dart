import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/settings/providers/settings_providers.dart';
import 'router.dart';
import 'theme/app_theme.dart';

/// Root widget for MediaHub.
///
/// Wires Riverpod, the GoRouter, and the theming system together. Theme mode
/// is driven by a Riverpod-backed settings notifier so that the entire app
/// rebuilds when the user changes the appearance preference.
class MediaHubApp extends ConsumerWidget {
  const MediaHubApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(goRouterProvider);
    final themePreference = ref.watch(themeModePreferenceProvider);

    return MaterialApp.router(
      title: 'MediaHub',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.build(ThemeModePreference.light),
      darkTheme: AppTheme.build(ThemeModePreference.dark),
      themeMode: _resolveMaterialThemeMode(themePreference),
      routerConfig: router,
      builder: (context, child) {
        // AMOLED overrides darkTheme with a true-black variant.
        if (themePreference == ThemeModePreference.amoled && child != null) {
          return Theme(
            data: AppTheme.build(ThemeModePreference.amoled),
            child: child,
          );
        }
        return child ?? const SizedBox.shrink();
      },
    );
  }

  ThemeMode _resolveMaterialThemeMode(ThemeModePreference preference) {
    switch (preference) {
      case ThemeModePreference.system:
        return ThemeMode.system;
      case ThemeModePreference.light:
        return ThemeMode.light;
      case ThemeModePreference.dark:
      case ThemeModePreference.amoled:
        return ThemeMode.dark;
    }
  }
}
