import 'package:flutter/foundation.dart';

import '../constants/app_constants.dart';

/// Runtime configuration for MediaHub.
///
/// In debug builds the engine can be pointed at an on-device Python for live
/// iteration; in release builds the values are fixed. This object is provided
/// to the rest of the app via Riverpod.
@immutable
class AppConfig {
  const AppConfig({
    required this.applicationId,
    required this.appVersion,
    required this.bridgeVersion,
    required this.environment,
    required this.enableDevLogging,
  });

  /// Production configuration.
  factory AppConfig.production() => const AppConfig(
        applicationId: kApplicationId,
        appVersion: kAppVersion,
        bridgeVersion: kBridgeVersion,
        environment: Environment.production,
        enableDevLogging: false,
      );

  /// Development configuration with verbose logging.
  factory AppConfig.development() => const AppConfig(
        applicationId: kApplicationId,
        appVersion: kAppVersion,
        bridgeVersion: kBridgeVersion,
        environment: Environment.development,
        enableDevLogging: true,
      );

  final String applicationId;
  final String appVersion;
  final int bridgeVersion;
  final Environment environment;
  final bool enableDevLogging;

  bool get isProduction => environment == Environment.production;
  bool get isDevelopment => environment == Environment.development;

  AppConfig copyWith({
    String? applicationId,
    String? appVersion,
    int? bridgeVersion,
    Environment? environment,
    bool? enableDevLogging,
  }) {
    return AppConfig(
      applicationId: applicationId ?? this.applicationId,
      appVersion: appVersion ?? this.appVersion,
      bridgeVersion: bridgeVersion ?? this.bridgeVersion,
      environment: environment ?? this.environment,
      enableDevLogging: enableDevLogging ?? this.enableDevLogging,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AppConfig &&
          runtimeType == other.runtimeType &&
          applicationId == other.applicationId &&
          appVersion == other.appVersion &&
          bridgeVersion == other.bridgeVersion &&
          environment == other.environment &&
          enableDevLogging == other.enableDevLogging;

  @override
  int get hashCode => Object.hash(
        applicationId,
        appVersion,
        bridgeVersion,
        environment,
        enableDevLogging,
      );

  @override
  String toString() => 'AppConfig(appVersion: $appVersion, '
      'bridgeVersion: $bridgeVersion, environment: $environment, '
      'enableDevLogging: $enableDevLogging)';
}

/// Deployment environments.
enum Environment { development, production }
