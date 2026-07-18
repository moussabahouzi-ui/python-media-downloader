import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/config/app_config.dart';
import '../core/constants/app_constants.dart';
import '../core/errors/exceptions.dart';
import '../core/errors/failures.dart';
import '../core/platform/method_channels/engine_channel_types.dart';
import '../core/platform/method_channels/engine_method_channel.dart';
import '../core/result/result.dart';
import '../models/download_models.dart';
import '../models/media_library_models.dart';
import '../models/provider_models.dart';
import '../providers/app_providers.dart';

/// High-level engine service consumed by feature view-models.
///
/// Translates raw method-channel maps into typed [Result]s and surfaces engine
/// events as typed streams. This is the single entry point the presentation
/// layer uses to talk to the Python engine — it never touches the method
/// channel directly.
class EngineService {
  EngineService({
    required EngineMethodChannel channel,
    required AppConfig config,
    required FailureMapper failureMapper,
    Duration timeout = kEngineDefaultTimeout,
  })  : _channel = channel,
        _config = config,
        _failureMapper = failureMapper,
        _timeout = timeout;

  final EngineMethodChannel _channel;
  final AppConfig _config;
  final FailureMapper _failureMapper;
  final Duration _timeout;

  /// Pings the engine. Returns the engine version on success.
  Future<Result<EngineVersionInfo>> ping() async {
    return _guard(() async {
      final data = await _call(EngineMethods.ping, const {});
      return EngineVersionInfo(
        app: _config.appVersion,
        engine: data['version'] as String? ?? 'unknown',
        bridgeVersion: kBridgeVersion,
      );
    });
  }

  /// Returns version info across all three layers.
  Future<Result<EngineVersionInfo>> version() async {
    return _guard(() async {
      final data = await _call(EngineMethods.version, const {});
      return EngineVersionInfo(
        app: data['app'] as String? ?? _config.appVersion,
        engine: data['engine'] as String? ?? 'unknown',
        bridgeVersion: data['bridgeVersion'] as int? ?? kBridgeVersion,
      );
    });
  }

  /// Gracefully stops the engine.
  Future<Result<bool>> shutdown() async {
    return _guard(() async {
      final data = await _call(EngineMethods.shutdown, const {});
      return data['stopped'] as bool? ?? false;
    });
  }

  // ---- provider.* (Phase 2) ----

  /// Detects which provider handles [url].
  Future<Result<DetectionResult>> detectProvider(String url) async {
    return _guard(() async {
      final data = await _call(EngineMethods.providerDetect, {'url': url});
      return DetectionResult.fromMap(data);
    });
  }

  /// Fetches normalized metadata for [url].
  Future<Result<MediaMetadata>> fetchMetadata(String url) async {
    return _guard(() async {
      final data = await _call(EngineMethods.providerMetadata, {'url': url});
      return MediaMetadata.fromMap(data);
    });
  }

  /// Lists every registered provider and its capability descriptor.
  Future<Result<List<ProviderInfo>>> listProviders() async {
    return _guard(() async {
      final data = await _call(EngineMethods.providerList, const {});
      final list = (data['providers'] as List?) ?? const [];
      return list
          .map((e) => ProviderInfo.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  // ---- download.* (Phase 2) ----

  /// Enqueues a download for [url] with optional [options] and [priority].
  Future<Result<String>> enqueueDownload(
    String url, {
    Map<String, Object?>? options,
    int? priority,
    String? destDir,
  }) async {
    return _guard(() async {
      final params = <String, Object?>{
        'url': url,
        if (options != null) 'options': options,
        if (priority != null) 'priority': priority,
        if (destDir != null) 'destDir': destDir,
      };
      final data = await _call(EngineMethods.downloadEnqueue, params);
      return data['taskId'] as String? ?? '';
    });
  }

  /// Cancels a download task by id.
  Future<Result<bool>> cancelDownload(String taskId) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.downloadCancel, {'taskId': taskId});
      return data['cancelled'] as bool? ?? false;
    });
  }

  /// Pauses a download task (running or queued).
  Future<Result<bool>> pauseDownload(String taskId) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.downloadPause, {'taskId': taskId});
      return data['paused'] as bool? ?? false;
    });
  }

  /// Resumes a paused download task.
  Future<Result<bool>> resumeDownload(String taskId) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.downloadResume, {'taskId': taskId});
      return data['resumed'] as bool? ?? false;
    });
  }

  /// Manually retries a failed download task (resets retry budget).
  Future<Result<bool>> retryDownload(String taskId) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.downloadRetry, {'taskId': taskId});
      return data['retried'] as bool? ?? false;
    });
  }

  /// Clears all terminal (completed/failed/cancelled) tasks from the queue.
  Future<Result<int>> clearTerminalDownloads() async {
    return _guard(() async {
      final data = await _call(EngineMethods.downloadClear, const {});
      return data['cleared'] as int? ?? 0;
    });
  }

  /// Lists all download tasks (active + terminal).
  Future<Result<List<DownloadTaskInfo>>> listDownloads() async {
    return _guard(() async {
      final data = await _call(EngineMethods.downloadList, const {});
      final list = (data['tasks'] as List?) ?? const [];
      return list
          .map((e) =>
              DownloadTaskInfo.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  /// Returns the status of a single download task.
  Future<Result<DownloadTaskInfo>> downloadStatus(String taskId) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.downloadStatus, {'taskId': taskId});
      return DownloadTaskInfo.fromMap(data);
    });
  }

  /// Stream of typed engine events (including download progress notifications).
  Stream<BridgeEvent> get events => _channel.events;

  // ---- library.* (Phase 4) ----

  /// Lists media items with optional filtering and sorting.
  Future<Result<List<MediaItem>>> listLibrary({
    String? category,
    bool favoriteOnly = false,
    bool includeRecycled = false,
    int limit = 500,
    int offset = 0,
    String sortBy = 'added_at',
    bool sortDesc = true,
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.libraryList, {
        if (category != null) 'category': category,
        'favoriteOnly': favoriteOnly,
        'includeRecycled': includeRecycled,
        'limit': limit,
        'offset': offset,
        'sortBy': sortBy,
        'sortDesc': sortDesc,
      });
      final list = (data['items'] as List?) ?? const [];
      return list
          .map((e) => MediaItem.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  /// Searches media items by name/title/uploader/tags.
  Future<Result<List<MediaItem>>> searchLibrary(String query,
      {int limit = 100}) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.librarySearch, {'query': query, 'limit': limit});
      final list = (data['items'] as List?) ?? const [];
      return list
          .map((e) => MediaItem.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  /// Returns a single media item by id.
  Future<Result<MediaItem>> getLibraryItem(String itemId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.libraryItem, {'itemId': itemId});
      return MediaItem.fromMap(data);
    });
  }

  /// Returns the total media item count.
  Future<Result<int>> countLibrary({bool includeRecycled = false}) async {
    return _guard(() async {
      final data = await _call(EngineMethods.libraryCount, {
        'includeRecycled': includeRecycled,
      });
      return data['count'] as int? ?? 0;
    });
  }

  // ---- favorites.* (Phase 4) ----

  Future<Result<bool>> addFavorite(String itemId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.favoritesAdd, {'itemId': itemId});
      return data['favorited'] as bool? ?? false;
    });
  }

  Future<Result<bool>> removeFavorite(String itemId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.favoritesRemove, {'itemId': itemId});
      return data['unfavorited'] as bool? ?? false;
    });
  }

  Future<Result<List<MediaItem>>> listFavorites({int limit = 500}) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.favoritesList, {'limit': limit});
      final list = (data['items'] as List?) ?? const [];
      return list
          .map((e) => MediaItem.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  // ---- collections.* (Phase 4) ----

  Future<Result<MediaCollection>> createCollection({
    required String name,
    String description = '',
    String? color,
    String? icon,
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.collectionsCreate, {
        'name': name,
        'description': description,
        if (color != null) 'color': color,
        if (icon != null) 'icon': icon,
      });
      return MediaCollection.fromMap(data);
    });
  }

  Future<Result<List<MediaCollection>>> listCollections() async {
    return _guard(() async {
      final data = await _call(EngineMethods.collectionsList, const {});
      final list = (data['collections'] as List?) ?? const [];
      return list
          .map((e) =>
              MediaCollection.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  Future<Result<bool>> renameCollection(
    String collectionId,
    String name, {
    String? description,
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.collectionsRename, {
        'collectionId': collectionId,
        'name': name,
        if (description != null) 'description': description,
      });
      return data['renamed'] as bool? ?? false;
    });
  }

  Future<Result<bool>> deleteCollection(String collectionId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.collectionsDelete, {
        'collectionId': collectionId,
      });
      return data['deleted'] as bool? ?? false;
    });
  }

  Future<Result<bool>> addCollectionItem(
      String collectionId, String itemId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.collectionsAddItem, {
        'collectionId': collectionId,
        'itemId': itemId,
      });
      return data['added'] as bool? ?? false;
    });
  }

  Future<Result<bool>> removeCollectionItem(
      String collectionId, String itemId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.collectionsRemoveItem, {
        'collectionId': collectionId,
        'itemId': itemId,
      });
      return data['removed'] as bool? ?? false;
    });
  }

  Future<Result<List<MediaItem>>> collectionItems(String collectionId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.collectionsItems, {
        'collectionId': collectionId,
      });
      final list = (data['items'] as List?) ?? const [];
      return list
          .map((e) => MediaItem.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  // ---- history.* (Phase 4) ----

  Future<Result<List<HistoryEntry>>> listHistory(
      {int limit = 100, int offset = 0}) async {
    return _guard(() async {
      final data = await _call(EngineMethods.historyList, {
        'limit': limit,
        'offset': offset,
      });
      final list = (data['entries'] as List?) ?? const [];
      return list
          .map((e) =>
              HistoryEntry.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  Future<Result<DownloadStats>> historyStats() async {
    return _guard(() async {
      final data = await _call(EngineMethods.historyStats, const {});
      return DownloadStats.fromMap(data);
    });
  }

  Future<Result<int>> clearHistory() async {
    return _guard(() async {
      final data = await _call(EngineMethods.historyClear, const {});
      return data['cleared'] as int? ?? 0;
    });
  }

  // ---- file.* (Phase 4) ----

  Future<Result<MediaItem>> renameFile(String itemId, String name) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.fileRename, {'itemId': itemId, 'name': name});
      return MediaItem.fromMap(data);
    });
  }

  Future<Result<MediaItem>> moveFile(String itemId, String destDir) async {
    return _guard(() async {
      final data = await _call(EngineMethods.fileMove, {
        'itemId': itemId,
        'destDir': destDir,
      });
      return MediaItem.fromMap(data);
    });
  }

  Future<Result<MediaItem>> copyFile(String itemId, String destDir) async {
    return _guard(() async {
      final data = await _call(EngineMethods.fileCopy, {
        'itemId': itemId,
        'destDir': destDir,
      });
      return MediaItem.fromMap(data);
    });
  }

  Future<Result<bool>> recycleFile(String itemId) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.fileRecycle, {'itemId': itemId});
      return data['recycled'] as bool? ?? false;
    });
  }

  Future<Result<bool>> restoreFile(String itemId, {String? destDir}) async {
    return _guard(() async {
      final data = await _call(EngineMethods.fileRestore, {
        'itemId': itemId,
        if (destDir != null) 'destDir': destDir,
      });
      return data['restored'] as bool? ?? false;
    });
  }

  Future<Result<bool>> deleteFile(String itemId) async {
    return _guard(() async {
      final data =
          await _call(EngineMethods.fileDelete, {'itemId': itemId});
      return data['deleted'] as bool? ?? false;
    });
  }

  Future<Result<int>> emptyRecycleBin() async {
    return _guard(() async {
      final data = await _call(EngineMethods.fileEmptyRecycle, const {});
      return data['emptied'] as int? ?? 0;
    });
  }

  // ---- storage.* (Phase 4) ----

  Future<Result<StorageBreakdown>> analyzeStorage(
      {bool includeRecycled = false}) async {
    return _guard(() async {
      final data = await _call(EngineMethods.storageAnalyze, {
        'includeRecycled': includeRecycled,
      });
      return StorageBreakdown.fromMap(data);
    });
  }

  Future<Result<List<DuplicateGroup>>> findDuplicates(
      {int maxFiles = 10000}) async {
    return _guard(() async {
      final data = await _call(EngineMethods.storageDuplicates, {
        'maxFiles': maxFiles,
      });
      final list = (data['groups'] as List?) ?? const [];
      return list
          .map((e) =>
              DuplicateGroup.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  // ---- playlists.* (Phase 5) ----

  Future<Result<Playlist>> createPlaylist({
    required String name,
    String description = '',
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsCreate, {
        'name': name,
        'description': description,
      });
      return Playlist.fromMap(data);
    });
  }

  Future<Result<List<Playlist>>> listPlaylists() async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsList, const {});
      final list = (data['playlists'] as List?) ?? const [];
      return list
          .map((e) => Playlist.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  Future<Result<bool>> renamePlaylist(
    String playlistId,
    String name, {
    String? description,
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsRename, {
        'playlistId': playlistId,
        'name': name,
        if (description != null) 'description': description,
      });
      return data['renamed'] as bool? ?? false;
    });
  }

  Future<Result<bool>> deletePlaylist(String playlistId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsDelete, {
        'playlistId': playlistId,
      });
      return data['deleted'] as bool? ?? false;
    });
  }

  Future<Result<bool>> addPlaylistItem(
    String playlistId,
    String itemId, {
    int? position,
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsAddItem, {
        'playlistId': playlistId,
        'itemId': itemId,
        if (position != null) 'position': position,
      });
      return data['added'] as bool? ?? false;
    });
  }

  Future<Result<bool>> removePlaylistItem(
      String playlistId, String itemId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsRemoveItem, {
        'playlistId': playlistId,
        'itemId': itemId,
      });
      return data['removed'] as bool? ?? false;
    });
  }

  Future<Result<bool>> reorderPlaylistItem(
      String playlistId, String itemId, int newPosition) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsReorder, {
        'playlistId': playlistId,
        'itemId': itemId,
        'position': newPosition,
      });
      return data['reordered'] as bool? ?? false;
    });
  }

  Future<Result<List<MediaItem>>> playlistItems(String playlistId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsItems, {
        'playlistId': playlistId,
      });
      final list = (data['items'] as List?) ?? const [];
      return list
          .map((e) => MediaItem.fromMap(Map<String, Object?>.from(e as Map)))
          .toList(growable: false);
    });
  }

  Future<Result<bool>> setPlaylistShuffle(
      String playlistId, bool shuffle) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsSetShuffle, {
        'playlistId': playlistId,
        'shuffle': shuffle,
      });
      return data['updated'] as bool? ?? false;
    });
  }

  Future<Result<bool>> setPlaylistRepeat(
      String playlistId, RepeatMode mode) async {
    return _guard(() async {
      final data = await _call(EngineMethods.playlistsSetRepeat, {
        'playlistId': playlistId,
        'repeatMode': mode.name,
      });
      return data['updated'] as bool? ?? false;
    });
  }

  // ---- settings.* (Phase 6) ----

  Future<Result<Object?>> getSetting(String key) async {
    return _guard(() async {
      final data = await _call(EngineMethods.settingsGet, {'key': key});
      return data['value'];
    });
  }

  Future<Result<Map<String, Object?>>> getAllSettings() async {
    return _guard(() async {
      final data = await _call(EngineMethods.settingsGetAll, const {});
      return Map<String, Object?>.from(data['settings'] as Map? ?? const {});
    });
  }

  Future<Result<bool>> setSetting(String key, Object? value) async {
    return _guard(() async {
      final data = await _call(EngineMethods.settingsSet, {
        'key': key,
        'value': value,
      });
      return data['updated'] as bool? ?? false;
    });
  }

  Future<Result<int>> setManySettings(Map<String, Object?> settings) async {
    return _guard(() async {
      final data = await _call(EngineMethods.settingsSetMany, {
        'settings': settings,
      });
      return data['updated'] as int? ?? 0;
    });
  }

  Future<Result<bool>> deleteSetting(String key) async {
    return _guard(() async {
      final data = await _call(EngineMethods.settingsDelete, {'key': key});
      return data['deleted'] as bool? ?? false;
    });
  }

  Future<Result<bool>> resetSettings() async {
    return _guard(() async {
      final data = await _call(EngineMethods.settingsReset, const {});
      return data['reset'] as bool? ?? false;
    });
  }

  // ---- scheduler.* (Phase 6) ----

  Future<Result<Map<String, Object?>>> createSchedule({
    required String url,
    required String scheduleType,
    double? scheduledAt,
    int? intervalSeconds,
    int? hour,
    int? minute,
    int? dayOfWeek,
    int priority = 5,
    Map<String, Object?>? options,
    bool enabled = true,
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.schedulerCreate, {
        'url': url,
        'scheduleType': scheduleType,
        if (scheduledAt != null) 'scheduledAt': scheduledAt,
        if (intervalSeconds != null) 'intervalSeconds': intervalSeconds,
        if (hour != null) 'hour': hour,
        if (minute != null) 'minute': minute,
        if (dayOfWeek != null) 'dayOfWeek': dayOfWeek,
        'priority': priority,
        if (options != null) 'options': options,
        'enabled': enabled,
      });
      return Map<String, Object?>.from(data);
    });
  }

  Future<Result<List<Map<String, Object?>>>> listSchedules(
      {bool enabledOnly = false}) async {
    return _guard(() async {
      final data = await _call(EngineMethods.schedulerList, {
        'enabledOnly': enabledOnly,
      });
      final list = (data['schedules'] as List?) ?? const [];
      return list
          .map((e) => Map<String, Object?>.from(e as Map))
          .toList(growable: false);
    });
  }

  Future<Result<bool>> deleteSchedule(String scheduleId) async {
    return _guard(() async {
      final data = await _call(EngineMethods.schedulerDelete, {
        'scheduleId': scheduleId,
      });
      return data['deleted'] as bool? ?? false;
    });
  }

  Future<Result<bool>> setScheduleEnabled(
      String scheduleId, bool enabled) async {
    return _guard(() async {
      final data = await _call(EngineMethods.schedulerSetEnabled, {
        'scheduleId': scheduleId,
        'enabled': enabled,
      });
      return data['updated'] as bool? ?? false;
    });
  }

  // ---- credentials.* (Phase 6) ----

  Future<Result<bool>> setCredentials({
    required String provider,
    String? username,
    String? password,
    String? cookiesPath,
    String? sessionPath,
    String? token,
  }) async {
    return _guard(() async {
      final data = await _call(EngineMethods.credentialsSet, {
        'provider': provider,
        if (username != null) 'username': username,
        if (password != null) 'password': password,
        if (cookiesPath != null) 'cookiesPath': cookiesPath,
        if (sessionPath != null) 'sessionPath': sessionPath,
        if (token != null) 'token': token,
      });
      return data['updated'] as bool? ?? false;
    });
  }

  Future<Result<Map<String, Object?>>> getCredentials(
      String provider) async {
    return _guard(() async {
      final data = await _call(EngineMethods.credentialsGet, {
        'provider': provider,
      });
      return Map<String, Object?>.from(data);
    });
  }

  Future<Result<List<String>>> listCredentialProviders() async {
    return _guard(() async {
      final data = await _call(EngineMethods.credentialsList, const {});
      final list = (data['providers'] as List?) ?? const [];
      return list.cast<String>();
    });
  }

  Future<Result<bool>> deleteCredentials(String provider) async {
    return _guard(() async {
      final data = await _call(EngineMethods.credentialsDelete, {
        'provider': provider,
      });
      return data['deleted'] as bool? ?? false;
    });
  }

  Future<Result<bool>> hasCredentials(String provider) async {
    return _guard(() async {
      final data = await _call(EngineMethods.credentialsHas, {
        'provider': provider,
      });
      return data['has'] as bool? ?? false;
    });
  }

  Future<Result<T>> _guard<T>(Future<T> Function() action) async {
    try {
      final value = await action().timeout(_timeout);
      return Result.success(value);
    } on BridgeException catch (e) {
      return Result.failure(_failureMapper.fromBridge(e));
    } on TimeoutException {
      return const Result.failure(EngineTimeoutFailure());
    } catch (e) {
      return Result.failure(_failureMapper.fromObject(e));
    }
  }

  Future<Map<String, Object?>> _call(
    String method,
    Map<String, Object?> params,
  ) async {
    final request = BridgeRequest(
      callId: PlatformEngineMethodChannel.newCallId(),
      method: method,
      params: params,
    );
    return _channel.invoke(request);
  }
}

/// Version information across the three layers.
@immutable
class EngineVersionInfo {
  const EngineVersionInfo({
    required this.app,
    required this.engine,
    required this.bridgeVersion,
  });

  final String app;
  final String engine;
  final int bridgeVersion;

  @override
  String toString() =>
      'EngineVersionInfo(app: $app, engine: $engine, bridge: $bridgeVersion)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is EngineVersionInfo &&
          app == other.app &&
          engine == other.engine &&
          bridgeVersion == other.bridgeVersion;

  @override
  int get hashCode => Object.hash(app, engine, bridgeVersion);
}

/// Riverpod providers for the engine layer.
///
/// Provided here (next to the service) so feature modules import a single
/// `engine_service.dart`. The actual channel implementation is swappable for
/// tests via an override of [engineMethodChannelProvider].
final FailureMapper defaultFailureMapper = const FailureMapper();

final Provider<EngineService> engineServiceProvider =
    Provider<EngineService>((ref) {
  return EngineService(
    channel: ref.watch(engineMethodChannelProvider),
    config: ref.watch(appConfigProvider),
    failureMapper: defaultFailureMapper,
  );
});
