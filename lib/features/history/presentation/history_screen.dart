import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../models/media_library_models.dart';
import '../../../services/engine_service.dart';

/// History screen: download history log + aggregate stats.
class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  Future<List<HistoryEntry>>? _historyFuture;
  Future<DownloadStats>? _statsFuture;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    final engine = ref.read(engineServiceProvider);
    _historyFuture = engine.listHistory().then((result) => result.fold(
      (failure) => throw Exception('Failed to load history: $failure'),
      (data) => data,
    ));
    _statsFuture = engine.historyStats().then((result) => result.fold(
      (failure) => throw Exception('Failed to load stats: $failure'),
      (data) => data,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: CustomScrollView(
        slivers: <Widget>[
          SliverAppBar.large(
            title: const Text('History'),
            leading: IconButton(
              tooltip: 'Back',
              icon: const Icon(Icons.arrow_back_rounded),
              onPressed: () => context.go(AppRoutes.home),
            ),
            actions: <Widget>[
              IconButton(
                tooltip: 'Clear history',
                icon: const Icon(Icons.delete_sweep_outlined),
                onPressed: () async {
                  await ref.read(engineServiceProvider).clearHistory();
                  _load();
                  setState(() {});
                },
              ),
            ],
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
            sliver: SliverList(
              delegate: SliverChildListDelegate(<Widget>[
                _StatsCard(
                  theme: theme,
                  statsFuture: _statsFuture,
                ),
                const SizedBox(height: 16),
                Text(
                  'Recent downloads',
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: theme.colorScheme.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                FutureBuilder<List<HistoryEntry>>(
                  future: _historyFuture,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 32),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }
                    if (snapshot.hasError || !snapshot.hasData) {
                      return _ErrorCard(
                        theme: theme,
                        message: 'Could not load history.',
                      );
                    }
                    final entries = snapshot.data!;
                    if (entries.isEmpty) {
                      return Card(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 32),
                          child: Column(
                            children: <Widget>[
                              Icon(Icons.history,
                                  size: 40,
                                  color: theme.colorScheme.onSurfaceVariant),
                              const SizedBox(height: 8),
                              Text('No history yet',
                                  style: theme.textTheme.bodyMedium),
                            ],
                          ),
                        ),
                      );
                    }
                    return Column(
                      children: entries
                          .map((e) => _HistoryTile(theme: theme, entry: e))
                          .toList(),
                    );
                  },
                ),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatsCard extends StatelessWidget {
  const _StatsCard({required this.theme, required this.statsFuture});
  final ThemeData theme;
  final Future<DownloadStats>? statsFuture;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<DownloadStats>(
      future: statsFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Center(
                child: snapshot.connectionState == ConnectionState.waiting
                    ? const CircularProgressIndicator(strokeWidth: 2)
                    : Text('Stats unavailable',
                        style: theme.textTheme.bodyMedium),
              ),
            ),
          );
        }
        final stats = snapshot.data!;
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text('Statistics', style: theme.textTheme.titleMedium),
                const SizedBox(height: 12),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: _Stat(
                        theme: theme,
                        label: 'Total',
                        value: '${stats.totalDownloads}',
                      ),
                    ),
                    Expanded(
                      child: _Stat(
                        theme: theme,
                        label: 'Completed',
                        value: '${stats.completed}',
                        color: Colors.green,
                      ),
                    ),
                    Expanded(
                      child: _Stat(
                        theme: theme,
                        label: 'Failed',
                        value: '${stats.failed}',
                        color: Colors.red,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  'Total downloaded: ${_formatBytes(stats.totalBytes)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({
    required this.theme,
    required this.label,
    required this.value,
    this.color,
  });
  final ThemeData theme;
  final String label;
  final String value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        Text(
          value,
          style: theme.textTheme.headlineSmall?.copyWith(color: color),
        ),
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.theme, required this.entry});
  final ThemeData theme;
  final HistoryEntry entry;

  @override
  Widget build(BuildContext context) {
    final isSuccess = entry.state == 'completed';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  isSuccess ? Icons.check_circle : Icons.error_outline,
                  size: 18,
                  color: isSuccess ? Colors.green : Colors.red,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    entry.url,
                    style: theme.textTheme.bodyMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (entry.provider != null)
                  Text(
                    entry.provider!,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              children: <Widget>[
                Text(
                  _formatBytes(entry.bytesDone),
                  style: theme.textTheme.bodySmall,
                ),
                const SizedBox(width: 12),
                Text(
                  entry.state,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: isSuccess
                        ? Colors.green
                        : theme.colorScheme.error,
                  ),
                ),
              ],
            ),
            if (entry.error != null) ...[
              const SizedBox(height: 4),
              Text(
                entry.error!,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.error),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.theme, required this.message});
  final ThemeData theme;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: <Widget>[
            Icon(Icons.error_outline, color: theme.colorScheme.error, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Text(message, style: theme.textTheme.bodyMedium),
            ),
          ],
        ),
      ),
    );
  }
}

String _formatBytes(int bytes) {
  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  if (bytes < 1024 * 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
}
