import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'core/config/app_config.dart';
import 'features/player/providers/just_audio_backend.dart';
import 'features/player/providers/player_provider.dart';
import 'providers/app_providers.dart';

/// Entry point for MediaHub.
///
/// The [AppConfig] is overridden here so flavored builds can swap between
/// development and production without touching feature code. The
/// [playerBackendProvider] is also overridden with the production
/// [JustAudioBackend] so the player screens work out of the box.
void main() {
  runApp(
    ProviderScope(
      overrides: <Override>[
        appConfigProvider.overrideWithValue(AppConfig.development()),
        playerBackendProvider.overrideWithValue(JustAudioBackend()),
      ],
      child: const MediaHubApp(),
    ),
  );
}
