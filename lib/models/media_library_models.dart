import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// High-level media category, mirrored from the Python engine.
enum MediaCategory {
  video,
  audio,
  image,
  other;

  static MediaCategory fromString(String value) {
    return MediaCategory.values.firstWhere(
      (c) => c.name == value,
      orElse: () => MediaCategory.other,
    );
  }

  String get displayName {
    switch (this) {
      case MediaCategory.video:
        return 'Videos';
      case MediaCategory.audio:
        return 'Audio';
      case MediaCategory.image:
        return 'Images';
      case MediaCategory.other:
        return 'Other';
    }
  }

  IconData get icon {
    switch (this) {
      case MediaCategory.video:
        return Icons.video_library_outlined;
      case MediaCategory.audio:
        return Icons.music_note_outlined;
      case MediaCategory.image:
        return Icons.photo_outlined;
      case MediaCategory.other:
        return Icons.insert_drive_file_outlined;
    }
  }
}

/// A single indexed media file in the library.
@immutable
class MediaItem {
  const MediaItem({
    required this.itemId,
    required this.path,
    required this.name,
    required this.category,
    required this.sizeBytes,
    required this.tags,
    required this.favorite,
    required this.recycled,
    required this.createdAt,
    required this.addedAt,
    this.mimeType,
    this.durationMs,
    this.width,
    this.height,
    this.provider,
    this.url,
    this.taskId,
    this.title,
    this.uploader,
    this.thumbnailPath,
  });

  factory MediaItem.fromMap(Map<String, Object?> map) {
    return MediaItem(
      itemId: map['itemId'] as String? ?? '',
      path: map['path'] as String? ?? '',
      name: map['name'] as String? ?? '',
      category: MediaCategory.fromString(map['category'] as String? ?? 'other'),
      sizeBytes: map['sizeBytes'] as int? ?? 0,
      mimeType: map['mimeType'] as String?,
      durationMs: map['durationMs'] as int?,
      width: map['width'] as int?,
      height: map['height'] as int?,
      provider: map['provider'] as String?,
      url: map['url'] as String?,
      taskId: map['taskId'] as String?,
      title: map['title'] as String?,
      uploader: map['uploader'] as String?,
      thumbnailPath: map['thumbnailPath'] as String?,
      tags: List<String>.from(map['tags'] as List? ?? const []),
      favorite: map['favorite'] as bool? ?? false,
      recycled: map['recycled'] as bool? ?? false,
      createdAt: (map['createdAt'] as num?)?.toDouble() ?? 0.0,
      addedAt: (map['addedAt'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final String itemId;
  final String path;
  final String name;
  final MediaCategory category;
  final int sizeBytes;
  final String? mimeType;
  final int? durationMs;
  final int? width;
  final int? height;
  final String? provider;
  final String? url;
  final String? taskId;
  final String? title;
  final String? uploader;
  final String? thumbnailPath;
  final List<String> tags;
  final bool favorite;
  final bool recycled;
  final double createdAt;
  final double addedAt;

  String get displayTitle => title?.isNotEmpty == true ? title! : name;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is MediaItem && itemId == other.itemId && favorite == other.favorite;

  @override
  int get hashCode => Object.hash(itemId, favorite);
}

/// A user-defined collection of media items.
@immutable
class MediaCollection {
  const MediaCollection({
    required this.collectionId,
    required this.name,
    required this.description,
    required this.itemCount,
    required this.createdAt,
    required this.updatedAt,
    this.color,
    this.icon,
  });

  factory MediaCollection.fromMap(Map<String, Object?> map) {
    return MediaCollection(
      collectionId: map['collectionId'] as String? ?? '',
      name: map['name'] as String? ?? '',
      description: map['description'] as String? ?? '',
      color: map['color'] as String?,
      icon: map['icon'] as String?,
      itemCount: map['itemCount'] as int? ?? 0,
      createdAt: (map['createdAt'] as num?)?.toDouble() ?? 0.0,
      updatedAt: (map['updatedAt'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final String collectionId;
  final String name;
  final String description;
  final String? color;
  final String? icon;
  final int itemCount;
  final double createdAt;
  final double updatedAt;
}

/// An append-only download history entry.
@immutable
class HistoryEntry {
  const HistoryEntry({
    required this.taskId,
    required this.url,
    required this.state,
    required this.bytesDone,
    required this.outputPaths,
    required this.recordedAt,
    this.historyId,
    this.provider,
    this.engine,
    this.error,
    this.metadata,
    this.startedAt,
    this.finishedAt,
  });

  factory HistoryEntry.fromMap(Map<String, Object?> map) {
    return HistoryEntry(
      historyId: map['historyId'] as int?,
      taskId: map['taskId'] as String? ?? '',
      url: map['url'] as String? ?? '',
      provider: map['provider'] as String?,
      engine: map['engine'] as String?,
      state: map['state'] as String? ?? '',
      bytesDone: map['bytesDone'] as int? ?? 0,
      outputPaths: List<String>.from(map['outputPaths'] as List? ?? const []),
      error: map['error'] as String?,
      metadata: map['metadata'] is Map
          ? Map<String, Object?>.from(map['metadata'] as Map)
          : null,
      startedAt: (map['startedAt'] as num?)?.toDouble(),
      finishedAt: (map['finishedAt'] as num?)?.toDouble(),
      recordedAt: (map['recordedAt'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final int? historyId;
  final String taskId;
  final String url;
  final String? provider;
  final String? engine;
  final String state;
  final int bytesDone;
  final List<String> outputPaths;
  final String? error;
  final Map<String, Object?>? metadata;
  final double? startedAt;
  final double? finishedAt;
  final double recordedAt;
}

/// Aggregate download statistics.
@immutable
class DownloadStats {
  const DownloadStats({
    required this.totalDownloads,
    required this.completed,
    required this.failed,
    required this.cancelled,
    required this.totalBytes,
    required this.byProvider,
    required this.byCategory,
  });

  factory DownloadStats.fromMap(Map<String, Object?> map) {
    return DownloadStats(
      totalDownloads: map['totalDownloads'] as int? ?? 0,
      completed: map['completed'] as int? ?? 0,
      failed: map['failed'] as int? ?? 0,
      cancelled: map['cancelled'] as int? ?? 0,
      totalBytes: map['totalBytes'] as int? ?? 0,
      byProvider: Map<String, int>.from(
        (map['byProvider'] as Map? ?? const {}).map(
          (k, v) => MapEntry(k as String, v as int),
        ),
      ),
      byCategory: Map<String, int>.from(
        (map['byCategory'] as Map? ?? const {}).map(
          (k, v) => MapEntry(k as String, v as int),
        ),
      ),
    );
  }

  final int totalDownloads;
  final int completed;
  final int failed;
  final int cancelled;
  final int totalBytes;
  final Map<String, int> byProvider;
  final Map<String, int> byCategory;
}

/// Storage usage breakdown.
@immutable
class StorageBreakdown {
  const StorageBreakdown({
    required this.totalBytes,
    required this.byCategory,
    required this.fileCount,
    required this.fileCountByCategory,
  });

  factory StorageBreakdown.fromMap(Map<String, Object?> map) {
    return StorageBreakdown(
      totalBytes: map['totalBytes'] as int? ?? 0,
      byCategory: Map<String, int>.from(
        (map['byCategory'] as Map? ?? const {}).map(
          (k, v) => MapEntry(k as String, v as int),
        ),
      ),
      fileCount: map['fileCount'] as int? ?? 0,
      fileCountByCategory: Map<String, int>.from(
        (map['fileCountByCategory'] as Map? ?? const {}).map(
          (k, v) => MapEntry(k as String, v as int),
        ),
      ),
    );
  }

  final int totalBytes;
  final Map<String, int> byCategory;
  final int fileCount;
  final Map<String, int> fileCountByCategory;
}

/// A group of duplicate files.
@immutable
class DuplicateGroup {
  const DuplicateGroup({
    required this.key,
    required this.sizeBytes,
    required this.paths,
  });

  factory DuplicateGroup.fromMap(Map<String, Object?> map) {
    return DuplicateGroup(
      key: map['key'] as String? ?? '',
      sizeBytes: map['sizeBytes'] as int? ?? 0,
      paths: List<String>.from(map['paths'] as List? ?? const []),
    );
  }

  final String key;
  final int sizeBytes;
  final List<String> paths;
}

/// Playback repeat modes.
enum RepeatMode {
  off,
  all,
  one;

  static RepeatMode fromString(String value) {
    return RepeatMode.values.firstWhere(
      (m) => m.name == value,
      orElse: () => RepeatMode.off,
    );
  }
}

/// An ordered playback queue of media items.
@immutable
class Playlist {
  const Playlist({
    required this.playlistId,
    required this.name,
    required this.description,
    required this.itemCount,
    required this.shuffle,
    required this.repeatMode,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Playlist.fromMap(Map<String, Object?> map) {
    return Playlist(
      playlistId: map['playlistId'] as String? ?? '',
      name: map['name'] as String? ?? '',
      description: map['description'] as String? ?? '',
      itemCount: map['itemCount'] as int? ?? 0,
      shuffle: map['shuffle'] as bool? ?? false,
      repeatMode: RepeatMode.fromString(map['repeatMode'] as String? ?? 'off'),
      createdAt: (map['createdAt'] as num?)?.toDouble() ?? 0.0,
      updatedAt: (map['updatedAt'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final String playlistId;
  final String name;
  final String description;
  final int itemCount;
  final bool shuffle;
  final RepeatMode repeatMode;
  final double createdAt;
  final double updatedAt;
}
