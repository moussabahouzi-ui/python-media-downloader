import 'package:flutter/foundation.dart';

/// The lifecycle state of a download task, mirrored from the Python engine.
enum DownloadState {
  queued,
  active,
  paused,
  completed,
  failed,
  cancelled;

  static DownloadState fromString(String value) {
    return DownloadState.values.firstWhere(
      (s) => s.name == value,
      orElse: () => DownloadState.queued,
    );
  }

  bool get isTerminal =>
      this == DownloadState.completed ||
      this == DownloadState.failed ||
      this == DownloadState.cancelled;

  bool get isActive => this == DownloadState.active;
}

/// A snapshot of a download task.
@immutable
class DownloadTaskInfo {
  const DownloadTaskInfo({
    required this.taskId,
    required this.url,
    required this.state,
    required this.priority,
    required this.percent,
    required this.bytes,
    required this.total,
    required this.outputPaths,
    required this.elapsed,
    this.provider,
    this.engine,
    this.metadata,
    this.error,
    this.lastError,
    this.retries = 0,
    this.retryAfter,
  });

  factory DownloadTaskInfo.fromMap(Map<String, Object?> map) {
    return DownloadTaskInfo(
      taskId: map['taskId'] as String? ?? '',
      url: map['url'] as String? ?? '',
      state: DownloadState.fromString(map['state'] as String? ?? 'queued'),
      priority: map['priority'] as int? ?? 5,
      percent: (map['percent'] as num?)?.toDouble() ?? 0.0,
      bytes: map['bytes'] as int? ?? 0,
      total: map['total'] as int?,
      outputPaths: List<String>.from(map['outputPaths'] as List? ?? const []),
      provider: map['provider'] as String?,
      engine: map['engine'] as String?,
      metadata: map['metadata'] is Map
          ? Map<String, Object?>.from(map['metadata'] as Map)
          : null,
      error: map['error'] as String?,
      lastError: map['lastError'] as String?,
      retries: map['retries'] as int? ?? 0,
      retryAfter: (map['retryAfter'] as num?)?.toDouble(),
      elapsed: (map['elapsed'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final String taskId;
  final String url;
  final DownloadState state;
  final int priority;
  final double percent;
  final int bytes;
  final int? total;
  final List<String> outputPaths;
  final String? provider;
  final String? engine;
  final Map<String, Object?>? metadata;
  final String? error;
  final String? lastError;
  final int retries;
  final double? retryAfter;
  final double elapsed;

  /// Primary output path (first file), for single-file downloads.
  String? get outputPath =>
      outputPaths.isNotEmpty ? outputPaths.first : null;

  DownloadTaskInfo copyWith({
    String? taskId,
    String? url,
    DownloadState? state,
    int? priority,
    double? percent,
    int? bytes,
    int? total,
    List<String>? outputPaths,
    String? provider,
    String? engine,
    Map<String, Object?>? metadata,
    String? error,
    String? lastError,
    int? retries,
    double? retryAfter,
    double? elapsed,
  }) {
    return DownloadTaskInfo(
      taskId: taskId ?? this.taskId,
      url: url ?? this.url,
      state: state ?? this.state,
      priority: priority ?? this.priority,
      percent: percent ?? this.percent,
      bytes: bytes ?? this.bytes,
      total: total ?? this.total,
      outputPaths: outputPaths ?? this.outputPaths,
      elapsed: elapsed ?? this.elapsed,
      provider: provider ?? this.provider,
      engine: engine ?? this.engine,
      metadata: metadata ?? this.metadata,
      error: error ?? this.error,
      lastError: lastError ?? this.lastError,
      retries: retries ?? this.retries,
      retryAfter: retryAfter ?? this.retryAfter,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DownloadTaskInfo &&
          taskId == other.taskId &&
          state == other.state &&
          percent == other.percent &&
          bytes == other.bytes;

  @override
  int get hashCode => Object.hash(taskId, state, percent, bytes);

  @override
  String toString() =>
      'DownloadTaskInfo($taskId, $state, ${percent.toStringAsFixed(1)}%)';
}
