import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/media_library_models.dart';
import '../../../services/engine_service.dart';

/// View-model state for the Playlists screen.
@immutable
class PlaylistsState {
  const PlaylistsState({
    this.playlists = const [],
    this.isLoading = false,
    this.error,
  });

  final List<Playlist> playlists;
  final bool isLoading;
  final String? error;

  PlaylistsState copyWith({
    List<Playlist>? playlists,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return PlaylistsState(
      playlists: playlists ?? this.playlists,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

/// View-model for the Playlists screen.
class PlaylistsNotifier extends StateNotifier<PlaylistsState> {
  PlaylistsNotifier(this._engine) : super(const PlaylistsState());

  final EngineService _engine;

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, clearError: true);
    final result = await _engine.listPlaylists();
    result.fold(
      onSuccess: (playlists) =>
          state = state.copyWith(playlists: playlists, isLoading: false),
      onFailure: (f) =>
          state = state.copyWith(isLoading: false, error: f.message),
    );
  }

  Future<void> createPlaylist(String name) async {
    final result = await _engine.createPlaylist(name: name);
    result.fold(
      onSuccess: (_) => refresh(),
      onFailure: (_) {}, // ignore — the UI can show a snackbar
    );
  }

  Future<void> deletePlaylist(String playlistId) async {
    await _engine.deletePlaylist(playlistId);
    await refresh();
  }

  void openPlaylist(BuildContext context, Playlist playlist) {
    // Phase 5+: navigate to a playlist detail screen with the ordered items.
    // For now, this is a placeholder; the player can load a playlist's items
    // via `_engine.playlistItems(playlist.playlistId)`.
  }
}

final StateNotifierProvider<PlaylistsNotifier, PlaylistsState>
    playlistsProvider =
    StateNotifierProvider<PlaylistsNotifier, PlaylistsState>(
  (ref) => PlaylistsNotifier(ref.watch(engineServiceProvider)),
  name: 'playlistsProvider',
);
