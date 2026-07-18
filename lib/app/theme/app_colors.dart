import 'package:flutter/material.dart';

/// Hand-tuned seed colors used as the fallback when the platform does not
/// support Material You dynamic color (Android < 12).
///
/// Deliberately **not** indigo/blue. A warm amber-coral primary anchors the
/// brand while staying legible in both light and dark schemes.
class AppColors {
  const AppColors._();

  /// Brand seed used for dynamic color fallback.
  static const Color seed = Color(0xFFE8590C);

  static const Color primaryLight = Color(0xFF9C3618);
  static const Color primaryDark = Color(0xFFFFB698);

  static const Color secondaryLight = Color(0xFF5C5848);
  static const Color secondaryDark = Color(0xFFD5CFC2);

  static const Color surfaceLight = Color(0xFFFBF8F4);
  static const Color surfaceDark = Color(0xFF171311);
  static const Color surfaceAmoled = Color(0xFF000000);

  static const Color errorLight = Color(0xFFBA1A1A);
  static const Color errorDark = Color(0xFFFFB4AB);
}
