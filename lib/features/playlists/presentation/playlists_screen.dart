import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../models/media_library_models.dart';
import '../../../services/engine_service.dart';
import 'providers/playlists_provider.dart';

/// Playlists screen: create, browse, rename, and delete playlists.
class PlaylistsScreen extends ConsumerStatefulWidget {
  const PlaylistsScreen({super.key});

  @override
  ConsumerState<PlaylistsScreen> createState() => _PlaylistsScreenState();
}

class _PlaylistsScreenState extends ConsumerState<PlaylistsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(playlistsProvider.notifier).refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final state = ref.watch(playlistsProvider);

    return Scaffold(
      body: CustomScrollView(
        slivers: <Widget>[
          SliverAppBar.large(
            title: const Text('Playlists'),
            leading: IconButton(
              tooltip: 'Back',
              icon: const Icon(Icons.arrow_back_rounded),
              onPressed: () => context.go(AppRoutes.home),
            ),
            actions: <Widget>[
              IconButton(
                tooltip: 'New playlist',
                icon: const Icon(Icons.playlist_add_rounded),
                onPressed: () => _showCreateDialog(context),
              ),
            ],
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
            sliver: state.isLoading
                ? const SliverFillRemaining(
                    child: Center(child: CircularProgressIndicator()),
                  )
                : state.playlists.isEmpty
                    ? SliverFillRemaining(
                        child: _EmptyState(theme: theme),
                      )
                    : SliverList(
                        delegate: SliverChildBuilderDelegate(
                          (context, index) {
                            final pl = state.playlists[index];
                            return _PlaylistTile(
                              theme: theme,
                              playlist: pl,
                              onTap: () => ref
                                  .read(playlistsProvider.notifier)
                                  .openPlaylist(context, pl),
                              onDelete: () => ref
                                  .read(playlistsProvider.notifier)
                                  .deletePlaylist(pl.playlistId),
                            );
                          },
                          childCount: state.playlists.length,
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  void _showCreateDialog(BuildContext context) {
    final controller = TextEditingController();
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Playlist'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'Playlist name'),
          onSubmitted: (_) {
            if (controller.text.trim().isNotEmpty) {
              ref.read(playlistsProvider.notifier).createPlaylist(controller.text.trim());
            }
            Navigator.pop(ctx);
          },
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              if (controller.text.trim().isNotEmpty) {
                ref
                    .read(playlistsProvider.notifier)
                    .createPlaylist(controller.text.trim());
              }
              Navigator.pop(ctx);
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          Icon(Icons.queue_music_rounded,
              size: 48, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(height: 12),
          Text('No playlists yet', style: theme.textTheme.titleMedium),
          const SizedBox(height: 4),
          Text('Tap + to create one.', style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _PlaylistTile extends StatelessWidget {
  const _PlaylistTile({
    required this.theme,
    required this.playlist,
    required this.onTap,
    required this.onDelete,
  });
  final ThemeData theme;
  final Playlist playlist;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: theme.colorScheme.primaryContainer,
          child: Icon(Icons.queue_music_rounded,
              color: theme.colorScheme.onPrimaryContainer),
        ),
        title: Text(playlist.name),
        subtitle: Text(
          '${playlist.itemCount} item(s)'
          '${playlist.shuffle ? ' · shuffle' : ''}'
          '${playlist.repeatMode != RepeatMode.off ? ' · repeat ${playlist.repeatMode.name}' : ''}',
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline, size: 20),
          onPressed: onDelete,
        ),
        onTap: onTap,
      ),
    );
  }
}
