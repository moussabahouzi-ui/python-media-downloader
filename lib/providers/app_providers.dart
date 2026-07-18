import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/config/app_config.dart';
import '../core/platform/method_channels/engine_method_channel.dart';

/// Application configuration. Override in `main.dart` for flavored builds.
final Provider<AppConfig> appConfigProvider = Provider<AppConfig>(
  (ref) => throw UnimplementedError(
    'appConfigProvider must be overridden in main()',
  ),
  name: 'appConfigProvider',
);

/// Engine method channel. Override in tests with a fake.
final Provider<EngineMethodChannel> engineMethodChannelProvider =
    Provider<EngineMethodChannel>(
  (ref) => PlatformEngineMethodChannel(),
  name: 'engineMethodChannelProvider',
);
