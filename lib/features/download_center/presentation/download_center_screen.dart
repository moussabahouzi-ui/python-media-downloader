import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../models/download_models.dart';
import '../../../models/provider_models.dart';
import '../providers/download_center_provider.dart';

/// Download Center: paste a URL, detect the provider, preview metadata,
/// enqueue, and watch the live queue.
class DownloadCenterScreen extends ConsumerStatefulWidget {
  const DownloadCenterScreen({super.key});

  @override
  ConsumerState<DownloadCenterScreen> createState() =>
      _DownloadCenterScreenState();
}

class _DownloadCenterScreenState extends ConsumerState<DownloadCenterScreen> {
  late final TextEditingController _urlController;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController();
    _urlController.addListener(() {
      ref.read(downloadCenterProvider.notifier).setUrl(_urlController.text);
    });
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final state = ref.watch(downloadCenterProvider);

    return Scaffold(
      body: CustomScrollView(
        slivers: <Widget>[
          SliverAppBar.large(
            title: const Text('Download Center'),
            leading: IconButton(
              tooltip: 'Back',
              icon: const Icon(Icons.arrow_back_rounded),
              onPressed: () => context.go(AppRoutes.home),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            sliver: SliverList(
              delegate: SliverChildListDelegate(<Widget>[
                _UrlInputCard(
                  theme: theme,
                  controller: _urlController,
                  state: state,
                  onDetect: () =>
                      ref.read(downloadCenterProvider.notifier).detect(),
                  onEnqueue: () =>
                      ref.read(downloadCenterProvider.notifier).enqueue(),
                ),
                const SizedBox(height: 16),
                if (state.detection != null || state.metadata != null)
                  _MetadataCard(theme: theme, state: state),
                if (state.detectingError != null) ...[
                  const SizedBox(height: 8),
                  _ErrorBanner(theme: theme, message: state.detectingError!),
                ],
                const SizedBox(height: 24),
                _QueueHeader(theme: theme, count: state.tasks.length),
                const SizedBox(height: 8),
                if (state.tasks.isEmpty)
                  _EmptyState(theme: theme)
                else
                  _TaskList(theme: theme, state: state),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

class _UrlInputCard extends StatelessWidget {
  const _UrlInputCard({
    required this.theme,
    required this.controller,
    required this.state,
    required this.onDetect,
    required this.onEnqueue,
  });

  final ThemeData theme;
  final TextEditingController controller;
  final DownloadCenterState state;
  final VoidCallback onDetect;
  final VoidCallback onEnqueue;

  @override
  Widget build(BuildContext context) {
    final canAct = state.url.trim().isNotEmpty;
    final isDetecting = state.phase == DetectionPhase.detecting;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Media URL', style: theme.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              'Paste a link from YouTube, Instagram, TikTok, X, Reddit, '
              'Vimeo, Pinterest, Twitch, SoundCloud, and more.',
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              decoration: InputDecoration(
                hintText: 'https://...',
                suffixIcon: IconButton(
                  tooltip: 'Paste',
                  icon: const Icon(Icons.content_paste_rounded),
                  onPressed: () async {
                    // Placeholder; clipboard integration in Phase 5.
                  },
                ),
              ),
              keyboardType: TextInputType.url,
              onSubmitted: (_) => canAct ? onDetect() : null,
            ),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: (canAct && !isDetecting) ? onDetect : null,
                    icon: isDetecting
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.search_rounded),
                    label: const Text('Detect'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: (canAct && !state.enqueuing) ? onEnqueue : null,
                    icon: state.enqueuing
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.download_rounded),
                    label: const Text('Download'),
                  ),
                ),
              ],
            ),
            if (state.lastEnqueuedId != null) ...[
              const SizedBox(height: 8),
              Text(
                'Queued task: ${state.lastEnqueuedId!.length > 8 ? state.lastEnqueuedId!.substring(0, 8) : state.lastEnqueuedId}…',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.primary,
                ),
              ),
            ],
            if (state.queueError != null) ...[
              const SizedBox(height: 8),
              _ErrorBanner(theme: theme, message: state.queueError!),
            ],
          ],
        ),
      ),
    );
  }
}

class _MetadataCard extends StatelessWidget {
  const _MetadataCard({required this.theme, required this.state});
  final ThemeData theme;
  final DownloadCenterState state;

  @override
  Widget build(BuildContext context) {
    final det = state.detection;
    final meta = state.metadata;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(_engineIcon(det?.engine), color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    det?.displayName ?? 'Detected',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                if (det?.authRequired ?? false)
                  _Pill(
                    theme: theme,
                    icon: Icons.lock_outline,
                    label: 'auth',
                    color: theme.colorScheme.errorContainer,
                    onColor: theme.colorScheme.onErrorContainer,
                  ),
              ],
            ),
            if (meta != null) ...[
              const SizedBox(height: 12),
              Text(
                meta.title.isEmpty ? '(no title)' : meta.title,
                style: theme.textTheme.titleSmall,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              if (meta.uploader != null) ...[
                const SizedBox(height: 2),
                Text(
                  meta.uploader!,
                  style: theme.textTheme.bodySmall,
                ),
              ],
              if (meta.durationSeconds != null) ...[
                const SizedBox(height: 4),
                Text(
                  _formatDuration(meta.durationSeconds!),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  IconData _engineIcon(String? engine) {
    switch (engine) {
      case 'yt-dlp':
        return Icons.video_library_outlined;
      case 'gallery-dl':
        return Icons.photo_library_outlined;
      case 'instaloader':
        return Icons.camera_alt_outlined;
      case 'http':
        return Icons.language_rounded;
      default:
        return Icons.memory_rounded;
    }
  }

  String _formatDuration(double seconds) {
    final m = (seconds / 60).floor();
    final s = (seconds % 60).round();
    return '${m}m ${s}s';
  }
}

class _QueueHeader extends StatelessWidget {
  const _QueueHeader({required this.theme, required this.count});
  final ThemeData theme;
  final int count;

  @override
  Widget build(BuildContext context) {
    final hasTerminal = count > 0;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(left: 4),
          child: Text(
            'Queue ($count)',
            style: theme.textTheme.titleSmall?.copyWith(
              color: theme.colorScheme.primary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        if (hasTerminal)
          TextButton.icon(
            onPressed: () => ProviderScope.containerOf(
              context,
              listen: false,
            ).read(downloadCenterProvider.notifier).clearTerminal(),
            icon: const Icon(Icons.cleaning_services_outlined, size: 18),
            label: const Text('Clear finished'),
          ),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 32),
        child: Column(
          children: <Widget>[
            Icon(Icons.inbox_rounded,
                size: 40, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: 8),
            Text(
              'No downloads yet',
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _TaskList extends StatelessWidget {
  const _TaskList({required this.theme, required this.state});
  final ThemeData theme;
  final DownloadCenterState state;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: state.tasks.map((t) => _TaskTile(theme: theme, task: t)).toList(),
    );
  }
}

class _TaskTile extends StatelessWidget {
  const _TaskTile({required this.theme, required this.task});
  final ThemeData theme;
  final DownloadTaskInfo task;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                _StateDot(state: task.state),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    task.url,
                    style: theme.textTheme.bodyMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (task.provider != null)
                  Text(
                    task.provider!,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            if (task.state == DownloadState.active ||
                task.state == DownloadState.queued) ...[
              ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: LinearProgressIndicator(
                  value: task.percent > 0 ? task.percent / 100 : null,
                  minHeight: 6,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: <Widget>[
                  Text(
                    '${task.percent.toStringAsFixed(0)}%',
                    style: theme.textTheme.bodySmall,
                  ),
                  Text(
                    _formatBytes(task.bytes),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ] else if (task.state == DownloadState.failed) ...[
              Text(
                task.error ?? 'Failed',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.error),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ] else if (task.state == DownloadState.completed) ...[
              Text(
                '${_formatBytes(task.bytes)} · ${task.outputPaths.length} file(s)',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.primary,
                ),
              ),
            ],
            _TaskActions(theme: theme, task: task),
          ],
        ),
      ),
    );
  }

  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
  }
}

class _TaskActions extends StatelessWidget {
  const _TaskActions({required this.theme, required this.task});
  final ThemeData theme;
  final DownloadTaskInfo task;

  @override
  Widget build(BuildContext context) {
    final actions = <Widget>[];

    switch (task.state) {
      case DownloadState.active:
      case DownloadState.queued:
        actions.add(_actionButton(
          context,
          icon: Icons.pause_outlined,
          label: 'Pause',
          onTap: () => _notifier(context).pauseTask(task.taskId),
        ));
        actions.add(_actionButton(
          context,
          icon: Icons.cancel_outlined,
          label: 'Cancel',
          onTap: () => _notifier(context).cancelTask(task.taskId),
        ));
      case DownloadState.paused:
        actions.add(_actionButton(
          context,
          icon: Icons.play_arrow_outlined,
          label: 'Resume',
          onTap: () => _notifier(context).resumeTask(task.taskId),
        ));
        actions.add(_actionButton(
          context,
          icon: Icons.cancel_outlined,
          label: 'Cancel',
          onTap: () => _notifier(context).cancelTask(task.taskId),
        ));
      case DownloadState.failed:
        actions.add(_actionButton(
          context,
          icon: Icons.refresh_rounded,
          label: 'Retry',
          onTap: () => _notifier(context).retryTask(task.taskId),
        ));
      case DownloadState.completed:
      case DownloadState.cancelled:
        // No actions for terminal states — clear button handles cleanup.
        break;
    }

    if (actions.isEmpty) return const SizedBox.shrink();
    return Align(
      alignment: Alignment.centerRight,
      child: Wrap(spacing: 4, children: actions),
    );
  }

  Widget _actionButton(
    BuildContext context, {
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return TextButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 18),
      label: Text(label),
    );
  }

  DownloadCenterNotifier _notifier(BuildContext context) =>
      ProviderScope.containerOf(context, listen: false)
          .read(downloadCenterProvider.notifier);
}

class _StateDot extends StatelessWidget {
  const _StateDot({required this.state});
  final DownloadState state;

  @override
  Widget build(BuildContext context) {
    final color = switch (state) {
      DownloadState.queued => Colors.amber,
      DownloadState.active => Colors.green,
      DownloadState.paused => Colors.grey,
      DownloadState.completed => Colors.teal,
      DownloadState.failed => Colors.red,
      DownloadState.cancelled => Colors.grey,
    };
    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.theme,
    required this.icon,
    required this.label,
    required this.color,
    required this.onColor,
  });
  final ThemeData theme;
  final IconData icon;
  final String label;
  final Color color;
  final Color onColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, size: 12, color: onColor),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: onColor,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.theme, required this.message});
  final ThemeData theme;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: <Widget>[
          Icon(Icons.error_outline,
              color: theme.colorScheme.onErrorContainer, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
