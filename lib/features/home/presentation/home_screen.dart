import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../app/theme/app_theme.dart';
import '../../../core/constants/app_constants.dart';
import '../../../services/engine_service.dart';

/// Home dashboard. Phase 1 shows the brand, an engine health card, and entry
/// points to the rest of the app. Subsequent phases replace the placeholders
/// with the real dashboard (active downloads, recents, stats).
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  @override
  void initState() {
    super.initState();
    // Fire-and-forget health check once on first build.
    WidgetsBinding.instance.addPostFrameCallback((_) => _pingEngine());
  }

  Future<void> _pingEngine() async {
    final engine = ref.read(engineServiceProvider);
    await engine.ping();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final engineVersionAsync = ref.watch(_engineVersionProvider);

    return Scaffold(
      body: CustomScrollView(
        slivers: <Widget>[
          SliverAppBar.large(
            title: const Text('MediaHub'),
            actions: <Widget>[
              IconButton(
                tooltip: 'Settings',
                icon: const Icon(Icons.settings_outlined),
                onPressed: () => context.push(AppRoutes.settings),
              ),
            ],
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            sliver: SliverList(
              delegate: SliverChildListDelegate(<Widget>[
                _HeroCard(theme: theme),
                const SizedBox(height: 16),
                _EngineHealthCard(
                  theme: theme,
                  version: engineVersionAsync,
                  onRetry: _pingEngine,
                ),
                const SizedBox(height: 16),
                _FeatureGrid(theme: theme),
                const SizedBox(height: 16),
                Text(
                  'MediaHub v$kAppVersion · bridge v$kBridgeVersion',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.center,
                ),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Your media, your device.',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Download, organize, and play media from a dozen platforms — '
              'all processed locally on your device. No servers, no tracking.',
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _EngineHealthCard extends StatelessWidget {
  const _EngineHealthCard({
    required this.theme,
    required this.version,
    required this.onRetry,
  });
  final ThemeData theme;
  final AsyncValue<EngineVersionInfo> version;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                const Icon(Icons.memory_rounded),
                const SizedBox(width: 12),
                Expanded(
                  child: Text('Media engine', style: theme.textTheme.titleMedium),
                ),
                version.when(
                  data: (info) => _StatusChip(
                    label: 'online',
                    color: theme.colorScheme.primaryContainer,
                    onColor: theme.colorScheme.onPrimaryContainer,
                  ),
                  loading: () => _StatusChip(
                    label: 'starting…',
                    color: theme.colorScheme.surfaceContainerHighest,
                    onColor: theme.colorScheme.onSurfaceVariant,
                  ),
                  error: (e, _) => _StatusChip(
                    label: 'offline',
                    color: theme.colorScheme.errorContainer,
                    onColor: theme.colorScheme.onErrorContainer,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            version.when(
              data: (info) => Text(
                'engine ${info.engine} · bridge v${info.bridgeVersion}',
                style: theme.textTheme.bodyMedium,
              ),
              loading: () => Text(
                'Waking the embedded engine…',
                style: theme.textTheme.bodyMedium,
              ),
              error: (e, _) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Engine unreachable.',
                    style: theme.textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(
                      onPressed: onRetry,
                      icon: const Icon(Icons.refresh_rounded, size: 18),
                      label: const Text('Retry'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.label,
    required this.color,
    required this.onColor,
  });
  final String label;
  final Color color;
  final Color onColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: onColor,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _FeatureGrid extends StatelessWidget {
  const _FeatureGrid({required this.theme});
  final ThemeData theme;

  static const List<_FeatureTile> _tiles = <_FeatureTile>[
    _FeatureTile(
      icon: Icons.download_rounded,
      title: 'Download Center',
      subtitle: 'Add URLs, pick quality, queue downloads',
      route: AppRoutes.downloadCenter,
    ),
    _FeatureTile(
      icon: Icons.queue_rounded,
      title: 'Queue',
      subtitle: 'Active & pending downloads',
      route: AppRoutes.downloadCenter,
    ),
    _FeatureTile(
      icon: Icons.video_library_outlined,
      title: 'Library',
      subtitle: 'Browse your saved media',
      route: AppRoutes.library,
    ),
    _FeatureTile(
      icon: Icons.history_rounded,
      title: 'History',
      subtitle: 'Past downloads & stats',
      route: AppRoutes.history,
    ),
    _FeatureTile(
      icon: Icons.favorite_outline,
      title: 'Favorites',
      subtitle: 'Pinned media & collections',
      route: AppRoutes.library,
    ),
    _FeatureTile(
      icon: Icons.queue_music_rounded,
      title: 'Playlists',
      subtitle: 'Ordered playback queues',
      route: AppRoutes.playlists,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _tiles.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 1.35,
      ),
      itemBuilder: (context, index) {
        final tile = _tiles[index];
        return Card(
          child: InkWell(
            onTap: () => tile.onTap(context),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Icon(tile.icon, color: theme.colorScheme.primary),
                  const Spacer(),
                  Text(tile.title, style: theme.textTheme.titleSmall),
                  const SizedBox(height: 2),
                  Text(
                    tile.subtitle,
                    style: theme.textTheme.bodySmall,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _FeatureTile {
  const _FeatureTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.route,
  });
  final IconData icon;
  final String title;
  final String subtitle;
  final String? route;

  void onTap(BuildContext context) {
    if (route != null) {
      context.push(route!);
    }
  }
}

/// One-shot engine version probe for the home dashboard.
final FutureProvider<EngineVersionInfo> _engineVersionProvider =
    FutureProvider<EngineVersionInfo>(
  (ref) => ref.watch(engineServiceProvider).version().then(
        (result) => result.fold(
          (failure) => throw failure,
          (data) => data,
        ),
      ),
  name: '_engineVersionProvider',
);
