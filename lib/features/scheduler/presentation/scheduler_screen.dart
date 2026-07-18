import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../services/engine_service.dart';

/// Scheduled Downloads screen: create, list, enable/disable, delete schedules.
class SchedulerScreen extends ConsumerStatefulWidget {
  const SchedulerScreen({super.key});

  @override
  ConsumerState<SchedulerScreen> createState() => _SchedulerScreenState();
}

class _SchedulerScreenState extends ConsumerState<SchedulerScreen> {
  Future<List<Map<String, Object?>>>? _schedulesFuture;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    final engine = ref.read(engineServiceProvider);
    _schedulesFuture = engine
        .listSchedules()
        .then((r) => r.fold((s) => s, (_) => throw Exception('failed')));
  }

  void _refresh() {
    setState(_load);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: CustomScrollView(
        slivers: <Widget>[
          SliverAppBar.large(
            title: const Text('Scheduled Downloads'),
            leading: IconButton(
              tooltip: 'Back',
              icon: const Icon(Icons.arrow_back_rounded),
              onPressed: () => context.go(AppRoutes.settings),
            ),
            actions: <Widget>[
              IconButton(
                tooltip: 'Add schedule',
                icon: const Icon(Icons.add_rounded),
                onPressed: () => _showCreateDialog(context),
              ),
            ],
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
            sliver: FutureBuilder<List<Map<String, Object?>>>(
              future: _schedulesFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const SliverFillRemaining(
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (snapshot.hasError || !snapshot.hasData) {
                  return SliverFillRemaining(
                    child: Center(
                      child: Text('Could not load schedules',
                          style: theme.textTheme.bodyMedium),
                    ),
                  );
                }
                final schedules = snapshot.data!;
                if (schedules.isEmpty) {
                  return SliverFillRemaining(
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: <Widget>[
                          Icon(Icons.schedule_rounded,
                              size: 48,
                              color: theme.colorScheme.onSurfaceVariant),
                          const SizedBox(height: 12),
                          Text('No schedules yet',
                              style: theme.textTheme.titleMedium),
                          const SizedBox(height: 4),
                          Text('Tap + to create one.',
                              style: theme.textTheme.bodySmall),
                        ],
                      ),
                    ),
                  );
                }
                return SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (context, index) {
                      final s = schedules[index];
                      return _ScheduleTile(
                        theme: theme,
                        schedule: s,
                        onToggle: (enabled) async {
                          await ref
                              .read(engineServiceProvider)
                              .setScheduleEnabled(
                                s['scheduleId'] as String,
                                enabled,
                              );
                          _refresh();
                        },
                        onDelete: () async {
                          await ref
                              .read(engineServiceProvider)
                              .deleteSchedule(s['scheduleId'] as String);
                          _refresh();
                        },
                      );
                    },
                    childCount: schedules.length,
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _showCreateDialog(BuildContext context) {
    final urlController = TextEditingController();
    String scheduleType = 'interval';
    final intervalController = TextEditingController(text: '300');

    showDialog<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('New Schedule'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                TextField(
                  controller: urlController,
                  decoration: const InputDecoration(labelText: 'URL'),
                  autofocus: true,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: scheduleType,
                  decoration: const InputDecoration(labelText: 'Type'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'interval', child: Text('Interval (every N seconds)')),
                    DropdownMenuItem(value: 'daily', child: Text('Daily')),
                    DropdownMenuItem(value: 'weekly', child: Text('Weekly')),
                    DropdownMenuItem(value: 'one_time', child: Text('One-time')),
                  ],
                  onChanged: (v) {
                    if (v != null) setDialogState(() => scheduleType = v);
                  },
                ),
                const SizedBox(height: 12),
                if (scheduleType == 'interval')
                  TextField(
                    controller: intervalController,
                    decoration: const InputDecoration(
                      labelText: 'Interval (seconds)',
                      hintText: '300',
                    ),
                    keyboardType: TextInputType.number,
                  ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () async {
                final url = urlController.text.trim();
                if (url.isEmpty) return;
                await ref.read(engineServiceProvider).createSchedule(
                      url: url,
                      scheduleType: scheduleType,
                      intervalSeconds: scheduleType == 'interval'
                          ? int.tryParse(intervalController.text) ?? 300
                          : null,
                    );
                if (ctx.mounted) Navigator.pop(ctx);
                _refresh();
              },
              child: const Text('Create'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScheduleTile extends StatelessWidget {
  const _ScheduleTile({
    required this.theme,
    required this.schedule,
    required this.onToggle,
    required this.onDelete,
  });
  final ThemeData theme;
  final Map<String, Object?> schedule;
  final void Function(bool) onToggle;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final enabled = schedule['enabled'] as bool? ?? false;
    final url = schedule['url'] as String? ?? '';
    final type = schedule['scheduleType'] as String? ?? '';
    final runCount = schedule['runCount'] as int? ?? 0;
    final nextRun = schedule['nextRunAt'] as double?;

    return Card(
      child: ListTile(
        leading: Icon(
          enabled ? Icons.schedule_rounded : Icons.schedule_outlined,
          color: enabled ? theme.colorScheme.primary : null,
        ),
        title: Text(url, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(
          '$type · ran $runCount time(s)'
          '${nextRun != null ? ' · next: ${_formatTime(nextRun)}' : ''}',
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Switch(
              value: enabled,
              onChanged: onToggle,
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline, size: 20),
              onPressed: onDelete,
            ),
          ],
        ),
      ),
    );
  }

  String _formatTime(double epochSeconds) {
    final dt = DateTime.fromMillisecondsSinceEpoch(
      (epochSeconds * 1000).round(),
    );
    return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}
