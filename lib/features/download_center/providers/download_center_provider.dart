import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/platform/method_channels/engine_channel_types.dart';
import '../../../models/download_models.dart';
import '../../../models/provider_models.dart';
import '../../../services/engine_service.dart';

/// The discrete stages the Download Center UI moves through.
enum DetectionPhase { idle, detecting, detected, failed }

/// Immutable state for the Download Center screen.
@immutable
class DownloadCenterState {
  const DownloadCenterState({
    this.url = '',
    this.phase = DetectionPhase.idle,
    this.detection,
    this.metadata,
    this.detectingError,
    this.tasks = const [],
    this.enqueuing = false,
    this.lastEnqueuedId,
    this.queueError,
  });

  final String url;
  final DetectionPhase phase;
  final DetectionResult? detection;
  final MediaMetadata? metadata;
  final String? detectingError;
  final List<DownloadTaskInfo> tasks;
  final bool enqueuing;
  final String? lastEnqueuedId;
  final String? queueError;

  DownloadCenterState copyWith({
    String? url,
    DetectionPhase? phase,
    DetectionResult? detection,
    MediaMetadata? metadata,
    String? detectingError,
    List<DownloadTaskInfo>? tasks,
    bool? enqueuing,
    String? lastEnqueuedId,
    String? queueError,
    bool clearDetection = false,
    bool clearDetectingError = false,
    bool clearQueueError = false,
  }) {
    return DownloadCenterState(
      url: url ?? this.url,
      phase: phase ?? this.phase,
      detection: clearDetection ? null : (detection ?? this.detection),
      metadata: clearDetection ? null : (metadata ?? this.metadata),
      detectingError:
          clearDetectingError ? null : (detectingError ?? this.detectingError),
      tasks: tasks ?? this.tasks,
      enqueuing: enqueuing ?? this.enqueuing,
      lastEnqueuedId: lastEnqueuedId ?? this.lastEnqueuedId,
      queueError: clearQueueError ? null : (queueError ?? this.queueError),
    );
  }

  @override
  String toString() => 'DownloadCenterState(phase=$phase, tasks=${tasks.length})';
}

/// View-model for the Download Center.
///
/// Owns URL input, provider detection, metadata preview, enqueue, and the
/// live task list. Listens to the engine event stream to refresh progress
/// without polling.
class DownloadCenterNotifier extends StateNotifier<DownloadCenterState> {
  DownloadCenterNotifier(this._engine) : super(const DownloadCenterState()) {
    _refreshTasks();
    _eventsSub = _engine.events.listen(_onEngineEvent);
  }

  final EngineService _engine;
  StreamSubscription<BridgeEvent>? _eventsSub;

  void setUrl(String url) {
    state = state.copyWith(
      url: url,
      phase: DetectionPhase.idle,
      clearDetection: true,
      clearDetectingError: true,
      clearQueueError: true,
      lastEnqueuedId: null,
    );
  }

  /// Detects the provider and fetches metadata for the current URL.
  Future<void> detect() async {
    final url = state.url.trim();
    if (url.isEmpty) return;
    state = state.copyWith(
      phase: DetectionPhase.detecting,
      clearDetection: true,
      clearDetectingError: true,
    );

    final result = await _engine.detectProvider(url);
    result.fold(
      onSuccess: (detection) async {
        state = state.copyWith(
          phase: DetectionPhase.detected,
          detection: detection,
        );
        // Best-effort metadata; failures here don't block enqueue.
        final meta = await _engine.fetchMetadata(url);
        meta.fold(
          onSuccess: (m) => state = state.copyWith(metadata: m),
          onFailure: (_) {}, // metadata is optional preview
        );
      },
      onFailure: (f) => state = state.copyWith(
        phase: DetectionPhase.failed,
        detectingError: f.message,
      ),
    );
  }

  /// Enqueues a download for the current URL.
  Future<void> enqueue() async {
    final url = state.url.trim();
    if (url.isEmpty) return;
    state = state.copyWith(enqueuing: true, clearQueueError: true);
    final result = await _engine.enqueueDownload(url);
    result.fold(
      onSuccess: (taskId) async {
        state = state.copyWith(enqueuing: false, lastEnqueuedId: taskId);
        await _refreshTasks();
      },
      onFailure: (f) => state = state.copyWith(
        enqueuing: false,
        queueError: f.message,
      ),
    );
  }

  /// Cancels a task by id and refreshes the list.
  Future<void> cancelTask(String taskId) async {
    await _engine.cancelDownload(taskId);
    await _refreshTasks();
  }

  /// Pauses a task by id.
  Future<void> pauseTask(String taskId) async {
    await _engine.pauseDownload(taskId);
    await _refreshTasks();
  }

  /// Resumes a paused task by id.
  Future<void> resumeTask(String taskId) async {
    await _engine.resumeDownload(taskId);
    await _refreshTasks();
  }

  /// Retries a failed task by id (resets retry budget).
  Future<void> retryTask(String taskId) async {
    await _engine.retryDownload(taskId);
    await _refreshTasks();
  }

  /// Clears all terminal (completed/failed/cancelled) tasks.
  Future<void> clearTerminal() async {
    await _engine.clearTerminalDownloads();
    await _refreshTasks();
  }

  Future<void> _refreshTasks() async {
    final result = await _engine.listDownloads();
    result.fold(
      onSuccess: (tasks) => state = state.copyWith(tasks: tasks),
      onFailure: (_) {}, // keep stale list on failure
    );
  }

  void _onEngineEvent(BridgeEvent event) {
    switch (event.name) {
      case 'download.progress':
      case 'download.started':
      case 'download.completed':
      case 'download.failed':
      case 'download.enqueued':
      case 'download.paused':
      case 'download.resumed':
      case 'download.cancelled':
      case 'download.retry_scheduled':
        // Any download lifecycle event triggers a refresh. The engine emits
        // these on the worker thread; the refresh is cheap and keeps the UI
        // live without per-event state patching.
        _refreshTasks();
        break;
    }
  }

  @override
  void dispose() {
    _eventsSub?.cancel();
    super.dispose();
  }
}

final StateNotifierProvider<DownloadCenterNotifier, DownloadCenterState>
    downloadCenterProvider =
    StateNotifierProvider<DownloadCenterNotifier, DownloadCenterState>(
  (ref) => DownloadCenterNotifier(ref.watch(engineServiceProvider)),
  name: 'downloadCenterProvider',
);
