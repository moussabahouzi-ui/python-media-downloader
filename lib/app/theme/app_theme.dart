import 'package:dynamic_color/dynamic_color.dart';
import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_typography.dart';

/// Visual density modes selectable by the user.
enum ThemeModePreference { system, light, dark, amoled }

/// The central theming system. Produces a [ThemeData] for each mode, honoring
/// Material You dynamic color on Android 12+ when available.
class AppTheme {
  const AppTheme._();

  /// Builds the [ThemeData] for the requested preference.
  static ThemeData build(ThemeModePreference preference) {
    return _resolve(preference);
  }

  static ThemeData _resolve(ThemeModePreference preference) {
    final isDark = preference == ThemeModePreference.dark ||
        preference == ThemeModePreference.amoled;
    final amoled = preference == ThemeModePreference.amoled;

    final scheme = _scheme(isDark: isDark, amoled: amoled);

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: amoled ? AppColors.surfaceAmoled : scheme.surface,
      visualDensity: VisualDensity.adaptivePlatformDensity,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      typography: Typography.material2021(),
      textTheme: AppTypography.build(scheme, amoled: amoled),
      appBarTheme: AppBarTheme(
        centerTitle: false,
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        foregroundColor: scheme.onSurface,
        titleTextStyle: AppTypography.build(scheme).titleLarge,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        clipBehavior: Clip.antiAlias,
        color: amoled
            ? scheme.surfaceContainerHighest.withValues(alpha: 0.4)
            : scheme.surfaceContainerLow,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        margin: EdgeInsets.zero,
      ),
      listTileTheme: ListTileThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: AppTypography.build(scheme).labelLarge,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: scheme.inverseSurface,
        contentTextStyle: TextStyle(color: scheme.onInverseSurface),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant.withValues(alpha: 0.6),
        thickness: 1,
        space: 1,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: amoled
            ? Colors.transparent
            : scheme.surfaceContainer.withValues(alpha: 0.9),
        elevation: 0,
        height: 80,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return AppTypography.build(scheme).labelMedium?.copyWith(
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: selected ? scheme.onSurface : scheme.onSurfaceVariant,
              );
        }),
      ),
    );
  }

  /// Tries dynamic color on supported platforms; otherwise returns the static
  /// fallback. Kept separate from [build] so unit tests stay deterministic.
  static ColorScheme _scheme({required bool isDark, bool amoled = false}) {
    return _fallbackScheme(isDark: isDark, amoled: amoled);
  }

  /// Deterministic fallback scheme (no platform calls — testable).
  static ColorScheme _fallbackScheme({
    required bool isDark,
    bool amoled = false,
  }) {
    if (isDark) {
      return ColorScheme.dark(
        primary: AppColors.primaryDark,
        onPrimary: Color(0xFF561F09),
        primaryContainer: Color(0xFF722C13),
        onPrimaryContainer: Color(0xFFFFDBCE),
        secondary: AppColors.secondaryDark,
        onSecondary: Color(0xFF2F2C22),
        secondaryContainer: Color(0xFF4B4838),
        onSecondaryContainer: Color(0xFFD5CFC2),
        tertiary: Color(0xFFB6CCAB),
        onTertiary: Color(0xFF22381C),
        error: AppColors.errorDark,
        onError: Color(0xFF690005),
        errorContainer: Color(0xFF93000A),
        onErrorContainer: Color(0xFFFFDAD6),
        surface: amoled ? AppColors.surfaceAmoled : AppColors.surfaceDark,
        onSurface: Color(0xFFEDE0DA),
        onSurfaceVariant: Color(0xFFD8C2B9),
        outline: Color(0xFFA08C84),
        outlineVariant: Color(0xFF53433D),
      );
    }
    return ColorScheme.light(
      primary: AppColors.primaryLight,
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFFFDBCE),
      onPrimaryContainer: Color(0xFF3A0B00),
      secondary: AppColors.secondaryLight,
      onSecondary: Color(0xFFFFFFFF),
      secondaryContainer: Color(0xFFE0DACB),
      onSecondaryContainer: Color(0xFF18140B),
      tertiary: Color(0xFF52634B),
      onTertiary: Color(0xFFFFFFFF),
      error: AppColors.errorLight,
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFFDAD6),
      onErrorContainer: Color(0xFF410002),
      surface: AppColors.surfaceLight,
      onSurface: Color(0xFF211A17),
      onSurfaceVariant: Color(0xFF53433D),
      outline: Color(0xFF85736C),
      outlineVariant: Color(0xFFD8C2B9),
    );
  }

  /// Convenience: resolves dynamic color asynchronously (used by the app
  /// widget when the platform supports it). Falls back to [_fallbackScheme].
  ///
  /// On Android 12+ the system provides a [CorePalette] with primary,
  /// secondary, tertiary, error, neutral, and neutralVariant tone palettes
  /// (each a `List<int>` of 101 tones indexed 0–100). We build a
  /// [ColorScheme] by selecting the M3 reference tones from each palette.
  static Future<ColorScheme> resolveDynamic({
    required bool isDark,
    bool amoled = false,
  }) async {
    try {
      final palette = await DynamicColorPlugin.getCorePalette();
      if (palette != null) {
        // M3 reference tones: primary/secondary/tertiary/error use tone 40
        // (light) or 80 (dark); their "on" counterparts use 100/20.
        // Containers use 90/30; onContainer uses 10/90.
        // Neutral palette provides surface/onSurface/outline.
        final primaryTone = isDark ? 80 : 40;
        final onPrimaryTone = isDark ? 20 : 100;
        final containerTone = isDark ? 30 : 90;
        final onContainerTone = isDark ? 90 : 10;
        final surfaceTone = isDark ? (amoled ? 0 : 10) : 99;
        final onSurfaceTone = isDark ? 90 : 10;
        final onSurfaceVariantTone = isDark ? 80 : 30;
        final outlineTone = isDark ? 60 : 50;
        final outlineVariantTone = isDark ? 30 : 80;

        final scheme = ColorScheme(
          brightness: isDark ? Brightness.dark : Brightness.light,
          primary: Color(palette.primary[primaryTone]),
          onPrimary: Color(palette.primary[onPrimaryTone]),
          primaryContainer: Color(palette.primary[containerTone]),
          onPrimaryContainer: Color(palette.primary[onContainerTone]),
          secondary: Color(palette.secondary[primaryTone]),
          onSecondary: Color(palette.secondary[onPrimaryTone]),
          secondaryContainer: Color(palette.secondary[containerTone]),
          onSecondaryContainer: Color(palette.secondary[onContainerTone]),
          tertiary: Color(palette.tertiary[primaryTone]),
          onTertiary: Color(palette.tertiary[onPrimaryTone]),
          tertiaryContainer: Color(palette.tertiary[containerTone]),
          onTertiaryContainer: Color(palette.tertiary[onContainerTone]),
          error: Color(palette.error[primaryTone]),
          onError: Color(palette.error[onPrimaryTone]),
          errorContainer: Color(palette.error[containerTone]),
          onErrorContainer: Color(palette.error[onContainerTone]),
          surface: Color(palette.neutral[surfaceTone]),
          onSurface: Color(palette.neutral[onSurfaceTone]),
          onSurfaceVariant: Color(palette.neutralVariant[onSurfaceVariantTone]),
          outline: Color(palette.neutralVariant[outlineTone]),
          outlineVariant: Color(palette.neutralVariant[outlineVariantTone]),
          shadow: const Color(0xFF000000),
          scrim: const Color(0xFF000000),
          inverseSurface: Color(palette.neutral[isDark ? 90 : 20]),
          onInverseSurface: Color(palette.neutral[isDark ? 20 : 95]),
          inversePrimary: Color(palette.primary[isDark ? 40 : 80]),
          surfaceTint: Color(palette.primary[primaryTone]),
        );
        return scheme;
      }
    } catch (_) {
      // Dynamic color unavailable; fall through to static scheme.
    }
    return _fallbackScheme(isDark: isDark, amoled: amoled);
  }
}
