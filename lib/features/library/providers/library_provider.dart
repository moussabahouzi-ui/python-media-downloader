import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/media_library_models.dart';
import '../../../services/engine_service.dart';

/// View-model state for the Library screen.
@immutable
class LibraryState {
  const LibraryState({
    this.items = const [],
    this.isLoading = false,
    this.error,
    this.selectedCategory,
    this.searchQuery = '',
    this.favoritesOnly = false,
  });

  final List<MediaItem> items;
  final bool isLoading;
  final String? error;
  final MediaCategory? selectedCategory;
  final String searchQuery;
  final bool favoritesOnly;

  LibraryState copyWith({
    List<MediaItem>? items,
    bool? isLoading,
    String? error,
    bool clearError = false,
    MediaCategory? selectedCategory,
    bool clearCategory = false,
    String? searchQuery,
    bool? favoritesOnly,
  }) {
    return LibraryState(
      items: items ?? this.items,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      selectedCategory:
          clearCategory ? null : (selectedCategory ?? this.selectedCategory),
      searchQuery: searchQuery ?? this.searchQuery,
      favoritesOnly: favoritesOnly ?? this.favoritesOnly,
    );
  }
}

/// View-model for the Library screen.
class LibraryNotifier extends StateNotifier<LibraryState> {
  LibraryNotifier(this._engine) : super(const LibraryState(isLoading: true)) {
    refresh();
  }

  final EngineService _engine;

  /// Reloads the media list from the engine, applying current filters.
  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, clearError: true);

    final Result<List<MediaItem>> result;
    if (state.searchQuery.isNotEmpty) {
      result = await _engine.searchLibrary(state.searchQuery);
    } else {
      result = await _engine.listLibrary(
        category: state.selectedCategory?.name,
        favoriteOnly: state.favoritesOnly,
      );
    }

    result.fold(
      onSuccess: (items) =>
          state = state.copyWith(items: items, isLoading: false),
      onFailure: (f) =>
          state = state.copyWith(isLoading: false, error: f.message),
    );
  }

  void setCategory(MediaCategory? category) {
    state = state.copyWith(
      selectedCategory: category,
      clearCategory: category == null,
    );
    refresh();
  }

  void setFavoritesOnly(bool value) {
    state = state.copyWith(favoritesOnly: value);
    refresh();
  }

  void setSearchQuery(String query) {
    state = state.copyWith(searchQuery: query);
    refresh();
  }

  Future<void> toggleFavorite(MediaItem item) async {
    if (item.favorite) {
      await _engine.removeFavorite(item.itemId);
    } else {
      await _engine.addFavorite(item.itemId);
    }
    await refresh();
  }

  Future<void> recycleItem(String itemId) async {
    await _engine.recycleFile(itemId);
    await refresh();
  }
}

final StateNotifierProvider<LibraryNotifier, LibraryState> libraryProvider =
    StateNotifierProvider<LibraryNotifier, LibraryState>(
  (ref) => LibraryNotifier(ref.watch(engineServiceProvider)),
  name: 'libraryProvider',
);
