import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../models/media_library_models.dart';
import '../providers/library_provider.dart';

/// Media Library: browse, search, filter, and manage downloaded media.
class LibraryScreen extends ConsumerStatefulWidget {
  const LibraryScreen({super.key});

  @override
  ConsumerState<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends ConsumerState<LibraryScreen> {
  late final TextEditingController _searchController;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
    _searchController.addListener(() {
      ref.read(libraryProvider.notifier).setSearchQuery(_searchController.text);
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final state = ref.watch(libraryProvider);

    return Scaffold(
      body: CustomScrollView(
        slivers: <Widget>[
          SliverAppBar.large(
            title: const Text('Library'),
            leading: IconButton(
              tooltip: 'Back',
              icon: const Icon(Icons.arrow_back_rounded),
              onPressed: () => context.go(AppRoutes.home),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
            sliver: SliverList(
              delegate: SliverChildListDelegate(<Widget>[
                _SearchBar(theme: theme, controller: _searchController),
                const SizedBox(height: 12),
                _CategoryChips(
                  theme: theme,
                  selected: state.selectedCategory,
                  favoritesOnly: state.favoritesOnly,
                  onCategory: (c) =>
                      ref.read(libraryProvider.notifier).setCategory(c),
                  onFavoritesOnly: (v) =>
                      ref.read(libraryProvider.notifier).setFavoritesOnly(v),
                ),
                const SizedBox(height: 16),
                if (state.error != null)
                  _ErrorBanner(theme: theme, message: state.error!)
                else if (state.isLoading)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 48),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (state.items.isEmpty)
                  _EmptyState(theme: theme)
                else
                  _MediaGrid(theme: theme, items: state.items),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

class _SearchBar extends StatelessWidget {
  const _SearchBar({required this.theme, required this.controller});
  final ThemeData theme;
  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      decoration: InputDecoration(
        hintText: 'Search media...',
        prefixIcon: const Icon(Icons.search_rounded),
        suffixIcon: controller.text.isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.clear_rounded),
                onPressed: () {
                  controller.clear();
                },
              )
            : null,
      ),
    );
  }
}

class _CategoryChips extends StatelessWidget {
  const _CategoryChips({
    required this.theme,
    required this.selected,
    required this.favoritesOnly,
    required this.onCategory,
    required this.onFavoritesOnly,
  });
  final ThemeData theme;
  final MediaCategory? selected;
  final bool favoritesOnly;
  final void Function(MediaCategory?) onCategory;
  final void Function(bool) onFavoritesOnly;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 4,
      children: <Widget>[
        ChoiceChip(
          label: const Text('All'),
          selected: selected == null,
          onSelected: (_) => onCategory(null),
        ),
        for (final cat in MediaCategory.values)
          ChoiceChip(
            label: Text(cat.displayName),
            avatar: Icon(cat.icon, size: 18),
            selected: selected == cat,
            onSelected: (_) => onCategory(cat),
          ),
        ChoiceChip(
          label: const Text('Favorites'),
          avatar: const Icon(Icons.favorite, size: 18),
          selected: favoritesOnly,
          onSelected: onFavoritesOnly,
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
        padding: const EdgeInsets.symmetric(vertical: 48),
        child: Column(
          children: <Widget>[
            Icon(Icons.video_library_outlined,
                size: 48, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: 12),
            Text('No media yet', style: theme.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              'Download media to see it here.',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _MediaGrid extends StatelessWidget {
  const _MediaGrid({required this.theme, required this.items});
  final ThemeData theme;
  final List<MediaItem> items;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.85,
      ),
      itemBuilder: (context, index) {
        final item = items[index];
        return _MediaCard(theme: theme, item: item);
      },
    );
  }
}

class _MediaCard extends ConsumerWidget {
  const _MediaCard({required this.theme, required this.item});
  final ThemeData theme;
  final MediaItem item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: InkWell(
        onTap: () {}, // Phase 5: open player
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(item.category.icon, color: theme.colorScheme.primary, size: 28),
                  const Spacer(),
                  IconButton(
                    icon: Icon(
                      item.favorite
                          ? Icons.favorite
                          : Icons.favorite_border,
                      size: 20,
                      color: item.favorite
                          ? Colors.red
                          : theme.colorScheme.onSurfaceVariant,
                    ),
                    onPressed: () => ref
                        .read(libraryProvider.notifier)
                        .toggleFavorite(item),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                item.displayTitle,
                style: theme.textTheme.titleSmall,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              if (item.uploader != null)
                Text(
                  item.uploader!,
                  style: theme.textTheme.bodySmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              const Spacer(),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: <Widget>[
                  Text(
                    _formatBytes(item.sizeBytes),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  if (item.provider != null)
                    Text(
                      item.provider!,
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                ],
              ),
            ],
          ),
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
