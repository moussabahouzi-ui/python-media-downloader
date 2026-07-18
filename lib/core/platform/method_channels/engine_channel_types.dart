/// Typed envelope and method definitions for the MediaHub engine bridge.
///
/// This file is the Dart mirror of
/// `android/app/src/main/kotlin/com/mediahub/app/bridge/MethodChannelContract.kt`
/// and must stay in sync with `docs/BRIDGE_CONTRACT.md`.
library;

import 'package:flutter/foundation.dart';

import '../../constants/app_constants.dart';

/// Every method call is namespaced `domain.action`.
typedef BridgeMethod = String;

/// Phase 1 method set. See `docs/BRIDGE_CONTRACT.md` §1.4.
@immutable
class EngineMethods {
  const EngineMethods._();

  // engine.*
  static const BridgeMethod ping = 'engine.ping';
  static const BridgeMethod version = 'engine.version';
  static const BridgeMethod shutdown = 'engine.shutdown';

  // provider.* (Phase 2)
  static const BridgeMethod providerDetect = 'provider.detect';
  static const BridgeMethod providerMetadata = 'provider.metadata';
  static const BridgeMethod providerList = 'provider.list';

  // download.* (Phase 2 + Phase 3)
  static const BridgeMethod downloadEnqueue = 'download.enqueue';
  static const BridgeMethod downloadPause = 'download.pause';
  static const BridgeMethod downloadResume = 'download.resume';
  static const BridgeMethod downloadRetry = 'download.retry';
  static const BridgeMethod downloadCancel = 'download.cancel';
  static const BridgeMethod downloadList = 'download.list';
  static const BridgeMethod downloadStatus = 'download.status';
  static const BridgeMethod downloadClear = 'download.clear';

  // library.* (Phase 4)
  static const BridgeMethod libraryList = 'library.list';
  static const BridgeMethod librarySearch = 'library.search';
  static const BridgeMethod libraryItem = 'library.item';
  static const BridgeMethod libraryCount = 'library.count';

  // favorites.* (Phase 4)
  static const BridgeMethod favoritesAdd = 'favorites.add';
  static const BridgeMethod favoritesRemove = 'favorites.remove';
  static const BridgeMethod favoritesList = 'favorites.list';

  // collections.* (Phase 4)
  static const BridgeMethod collectionsCreate = 'collections.create';
  static const BridgeMethod collectionsList = 'collections.list';
  static const BridgeMethod collectionsRename = 'collections.rename';
  static const BridgeMethod collectionsDelete = 'collections.delete';
  static const BridgeMethod collectionsAddItem = 'collections.add_item';
  static const BridgeMethod collectionsRemoveItem = 'collections.remove_item';
  static const BridgeMethod collectionsItems = 'collections.items';

  // history.* (Phase 4)
  static const BridgeMethod historyList = 'history.list';
  static const BridgeMethod historyStats = 'history.stats';
  static const BridgeMethod historyClear = 'history.clear';

  // file.* (Phase 4)
  static const BridgeMethod fileRename = 'file.rename';
  static const BridgeMethod fileMove = 'file.move';
  static const BridgeMethod fileCopy = 'file.copy';
  static const BridgeMethod fileRecycle = 'file.recycle';
  static const BridgeMethod fileRestore = 'file.restore';
  static const BridgeMethod fileDelete = 'file.delete';
  static const BridgeMethod fileEmptyRecycle = 'file.empty_recycle';

  // storage.* (Phase 4)
  static const BridgeMethod storageAnalyze = 'storage.analyze';
  static const BridgeMethod storageDuplicates = 'storage.duplicates';

  // playlists.* (Phase 5)
  static const BridgeMethod playlistsCreate = 'playlists.create';
  static const BridgeMethod playlistsList = 'playlists.list';
  static const BridgeMethod playlistsRename = 'playlists.rename';
  static const BridgeMethod playlistsDelete = 'playlists.delete';
  static const BridgeMethod playlistsAddItem = 'playlists.add_item';
  static const BridgeMethod playlistsRemoveItem = 'playlists.remove_item';
  static const BridgeMethod playlistsReorder = 'playlists.reorder';
  static const BridgeMethod playlistsItems = 'playlists.items';
  static const BridgeMethod playlistsSetShuffle = 'playlists.set_shuffle';
  static const BridgeMethod playlistsSetRepeat = 'playlists.set_repeat';

  // settings.* (Phase 6)
  static const BridgeMethod settingsGet = 'settings.get';
  static const BridgeMethod settingsGetAll = 'settings.get_all';
  static const BridgeMethod settingsSet = 'settings.set';
  static const BridgeMethod settingsSetMany = 'settings.set_many';
  static const BridgeMethod settingsDelete = 'settings.delete';
  static const BridgeMethod settingsReset = 'settings.reset';

  // scheduler.* (Phase 6)
  static const BridgeMethod schedulerCreate = 'scheduler.create';
  static const BridgeMethod schedulerList = 'scheduler.list';
  static const BridgeMethod schedulerGet = 'scheduler.get';
  static const BridgeMethod schedulerUpdate = 'scheduler.update';
  static const BridgeMethod schedulerSetEnabled = 'scheduler.set_enabled';
  static const BridgeMethod schedulerDelete = 'scheduler.delete';
  static const BridgeMethod schedulerDue = 'scheduler.due';
  static const BridgeMethod schedulerMarkRun = 'scheduler.mark_run';

  // credentials.* (Phase 6)
  static const BridgeMethod credentialsSet = 'credentials.set';
  static const BridgeMethod credentialsGet = 'credentials.get';
  static const BridgeMethod credentialsList = 'credentials.list';
  static const BridgeMethod credentialsDelete = 'credentials.delete';
  static const BridgeMethod credentialsHas = 'credentials.has';
}

/// Event names streamed over the event channel.
@immutable
class EngineEvents {
  const EngineEvents._();

  static const String engineReady = 'engine.ready';
  static const String engineStopped = 'engine.stopped';

  // download.* notifications (Phase 2 + Phase 3)
  static const String downloadEnqueued = 'download.enqueued';
  static const String downloadStarted = 'download.started';
  static const String downloadProgress = 'download.progress';
  static const String downloadCompleted = 'download.completed';
  static const String downloadFailed = 'download.failed';
  static const String downloadCancelled = 'download.cancelled';
  static const String downloadPaused = 'download.paused';
  static const String downloadResumed = 'download.resumed';
  static const String downloadRetryScheduled = 'download.retry_scheduled';
}

/// The request envelope sent over the method channel.
@immutable
class BridgeRequest {
  const BridgeRequest({
    required this.callId,
    required this.method,
    this.params = const <String, Object?>{},
  }) : bridgeVersion = kBridgeVersion;

  final int bridgeVersion;
  final String callId;
  final String method;
  final Map<String, Object?> params;

  Map<String, Object?> toMap() => {
        'bridgeVersion': bridgeVersion,
        'callId': callId,
        'method': method,
        'params': params,
      };

  @override
  String toString() => 'BridgeRequest($method, callId=$callId)';
}

/// The success envelope returned from the method channel.
@immutable
class BridgeSuccess {
  const BridgeSuccess({required this.callId, required this.data})
      : bridgeVersion = kBridgeVersion;

  final int bridgeVersion;
  final String callId;
  final Map<String, Object?> data;

  factory BridgeSuccess.fromMap(Map<dynamic, dynamic> map) {
    return BridgeSuccess(
      callId: map['callId'] as String,
      data: Map<String, Object?>.from(map['data'] as Map? ?? const {}),
    );
  }
}

/// The error envelope returned from the method channel.
@immutable
class BridgeError {
  const BridgeError({
    required this.callId,
    required this.code,
    required this.message,
    this.details,
  }) : bridgeVersion = kBridgeVersion;

  final int bridgeVersion;
  final String callId;
  final String code;
  final String message;
  final Map<String, Object?>? details;

  factory BridgeError.fromMap(Map<dynamic, dynamic> map) {
    final error = Map<String, Object?>.from(map['error'] as Map? ?? const {});
    return BridgeError(
      callId: map['callId'] as String,
      code: error['code'] as String? ?? 'INTERNAL',
      message: error['message'] as String? ?? 'Unknown error',
      details: error['details'] is Map
          ? Map<String, Object?>.from(error['details'] as Map)
          : null,
    );
  }
}

/// A decoded engine event streamed over the event channel.
@immutable
class BridgeEvent {
  const BridgeEvent({required this.name, required this.data})
      : bridgeVersion = kBridgeVersion;

  final int bridgeVersion;
  final String name;
  final Map<String, Object?> data;

  factory BridgeEvent.fromMap(Map<dynamic, dynamic> map) {
    return BridgeEvent(
      name: map['event'] as String? ?? '',
      data: Map<String, Object?>.from(map['data'] as Map? ?? const {}),
    );
  }
}
