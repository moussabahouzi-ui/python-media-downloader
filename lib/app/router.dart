import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/download_center/presentation/download_center_screen.dart';
import '../features/history/presentation/history_screen.dart';
import '../features/home/presentation/home_screen.dart';
import '../features/library/presentation/library_screen.dart';
import '../features/player/presentation/audio_player_screen.dart';
import '../features/player/presentation/video_player_screen.dart';
import '../features/playlists/presentation/playlists_screen.dart';
import '../features/scheduler/presentation/scheduler_screen.dart';
import '../features/settings/presentation/settings_screen.dart';

/// Named routes used across the app.
class AppRoutes {
  const AppRoutes._();

  static const String home = '/';
  static const String downloadCenter = '/download';
  static const String library = '/library';
  static const String history = '/history';
  static const String playlists = '/playlists';
  static const String videoPlayer = '/player/video';
  static const String audioPlayer = '/player/audio';
  static const String settings = '/settings';
  static const String scheduler = '/scheduler';
}

/// The single [GoRouter] instance. Refresh listeners are wired up in later
/// phases to react to auth/permission state.
final Provider<GoRouter> goRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: AppRoutes.home,
    debugLogDiagnostics: false,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.home,
        name: 'home',
        builder: (context, state) => const HomeScreen(),
      ),
      GoRoute(
        path: AppRoutes.downloadCenter,
        name: 'downloadCenter',
        builder: (context, state) => const DownloadCenterScreen(),
      ),
      GoRoute(
        path: AppRoutes.library,
        name: 'library',
        builder: (context, state) => const LibraryScreen(),
      ),
      GoRoute(
        path: AppRoutes.history,
        name: 'history',
        builder: (context, state) => const HistoryScreen(),
      ),
      GoRoute(
        path: AppRoutes.playlists,
        name: 'playlists',
        builder: (context, state) => const PlaylistsScreen(),
      ),
      GoRoute(
        path: AppRoutes.videoPlayer,
        name: 'videoPlayer',
        builder: (context, state) => const VideoPlayerScreen(),
      ),
      GoRoute(
        path: AppRoutes.audioPlayer,
        name: 'audioPlayer',
        builder: (context, state) => const AudioPlayerScreen(),
      ),
      GoRoute(
        path: AppRoutes.settings,
        name: 'settings',
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        path: AppRoutes.scheduler,
        name: 'scheduler',
        builder: (context, state) => const SchedulerScreen(),
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      appBar: AppBar(title: const Text('Not found')),
      body: Center(child: Text('Route not found: ${state.uri}')),
    ),
  );
}, name: 'goRouterProvider');
