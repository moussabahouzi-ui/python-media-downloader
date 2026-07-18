import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../app/theme/app_theme.dart';
import '../../../core/constants/app_constants.dart';
import '../../../services/engine_service.dart';
import 'providers/settings_providers.dart';

/// The full Settings screen — appearance, downloads, security, scheduler,
/// credentials, and about sections.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(settingsStoreProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final settings = ref.watch(settingsStoreProvider);

    return Scaffold(
      body: CustomScrollView(
        slivers: <Widget>[
          SliverAppBar.large(
            title: const Text('Settings'),
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
                _SectionHeader(theme: theme, title: 'Appearance'),
                const SizedBox(height: 8),
                _AppearanceCard(theme: theme, settings: settings, ref: ref),
                const SizedBox(height: 24),
                _SectionHeader(theme: theme, title: 'Downloads'),
                const SizedBox(height: 8),
                _DownloadsCard(theme: theme, settings: settings, ref: ref),
                const SizedBox(height: 24),
                _SectionHeader(theme: theme, title: 'Security'),
                const SizedBox(height: 8),
                _SecurityCard(theme: theme, settings: settings, ref: ref),
                const SizedBox(height: 24),
                _SectionHeader(theme: theme, title: 'Scheduler'),
                const SizedBox(height: 8),
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.schedule_rounded),
                    title: const Text('Scheduled Downloads'),
                    subtitle: const Text('Manage recurring and one-time schedules'),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => context.push(AppRoutes.scheduler),
                  ),
                ),
                const SizedBox(height: 24),
                _SectionHeader(theme: theme, title: 'About'),
                const SizedBox(height: 8),
                _AboutCard(theme: theme),
                const SizedBox(height: 32),
                FilledButton.tonalIcon(
                  onPressed: () => ref.read(settingsStoreProvider.notifier).reset(),
                  icon: const Icon(Icons.restart_alt_rounded),
                  label: const Text('Reset all settings'),
                ),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.theme, required this.title});
  final ThemeData theme;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(
        title,
        style: theme.textTheme.titleSmall?.copyWith(
          color: theme.colorScheme.primary,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _AppearanceCard extends StatelessWidget {
  const _AppearanceCard({required this.theme, required this.settings, required this.ref});
  final ThemeData theme;
  final SettingsState settings;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Theme mode', style: theme.textTheme.titleSmall),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: ThemeModePreference.values.map((mode) {
                final selected = settings.themeMode == mode;
                return ChoiceChip(
                  label: Text(_labelFor(mode)),
                  selected: selected,
                  onSelected: (_) => ref.read(settingsStoreProvider.notifier)
                      .setThemeMode(mode),
                );
              }).toList(),
            ),
            const SizedBox(height: 16),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('Dynamic color', style: theme.textTheme.titleSmall),
              subtitle: Text(
                'Material You from wallpaper (Android 12+)',
                style: theme.textTheme.bodySmall,
              ),
              value: settings.useDynamicColor,
              onChanged: (v) => ref.read(settingsStoreProvider.notifier)
                  .setDynamicColor(v),
            ),
            const SizedBox(height: 8),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.language_rounded),
              title: const Text('Language'),
              trailing: DropdownButton<String>(
                value: settings.language,
                items: const <DropdownMenuItem<String>>[
                  DropdownMenuItem(value: 'en', child: Text('English')),
                  DropdownMenuItem(value: 'fr', child: Text('Français')),
                  DropdownMenuItem(value: 'es', child: Text('Español')),
                  DropdownMenuItem(value: 'de', child: Text('Deutsch')),
                  DropdownMenuItem(value: 'ar', child: Text('العربية')),
                ],
                onChanged: (v) {
                  if (v != null) {
                    ref.read(settingsStoreProvider.notifier).setLanguage(v);
                  }
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _labelFor(ThemeModePreference mode) {
    switch (mode) {
      case ThemeModePreference.system:
        return 'System';
      case ThemeModePreference.light:
        return 'Light';
      case ThemeModePreference.dark:
        return 'Dark';
      case ThemeModePreference.amoled:
        return 'AMOLED';
    }
  }
}

class _DownloadsCard extends StatelessWidget {
  const _DownloadsCard({required this.theme, required this.settings, required this.ref});
  final ThemeData theme;
  final SettingsState settings;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Max concurrent downloads', style: theme.textTheme.titleSmall),
            const SizedBox(height: 4),
            Text(
              '${settings.maxConcurrent} simultaneous downloads',
              style: theme.textTheme.bodySmall,
            ),
            Slider(
              value: settings.maxConcurrent.toDouble(),
              min: 1,
              max: 8,
              divisions: 7,
              label: '${settings.maxConcurrent}',
              onChanged: (v) => ref.read(settingsStoreProvider.notifier)
                  .setMaxConcurrent(v.round()),
            ),
            const Divider(),
            Text('Max retries', style: theme.textTheme.titleSmall),
            const SizedBox(height: 4),
            Text(
              '${settings.maxRetries} retry attempts on failure',
              style: theme.textTheme.bodySmall,
            ),
            Slider(
              value: settings.maxRetries.toDouble(),
              min: 0,
              max: 10,
              divisions: 10,
              label: '${settings.maxRetries}',
              onChanged: (v) => ref.read(settingsStoreProvider.notifier)
                  .setMaxRetries(v.round()),
            ),
            const Divider(),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.folder_outlined),
              title: const Text('Default download folder'),
              subtitle: Text(
                settings.defaultDestDir.isEmpty
                    ? 'App default'
                    : settings.defaultDestDir,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {}, // Phase 6+: folder picker
            ),
          ],
        ),
      ),
    );
  }
}

class _SecurityCard extends StatelessWidget {
  const _SecurityCard({required this.theme, required this.settings, required this.ref});
  final ThemeData theme;
  final SettingsState settings;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('Encrypt local storage', style: theme.textTheme.titleSmall),
              subtitle: Text(
                'Credentials encrypted via Android Keystore',
                style: theme.textTheme.bodySmall,
              ),
              value: settings.encryptStorage,
              onChanged: (v) => ref.read(settingsStoreProvider.notifier)
                  .setEncryptStorage(v),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('Auto-lock', style: theme.textTheme.titleSmall),
              subtitle: Text(
                'Require biometric unlock when returning to the app',
                style: theme.textTheme.bodySmall,
              ),
              value: settings.autoLock,
              onChanged: (v) => ref.read(settingsStoreProvider.notifier)
                  .setAutoLock(v),
            ),
          ],
        ),
      ),
    );
  }
}

class _AboutCard extends StatelessWidget {
  const _AboutCard({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: <Widget>[
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('Version'),
            subtitle: Text('MediaHub v$kAppVersion · bridge v$kBridgeVersion'),
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.code_rounded),
            title: const Text('Build'),
            subtitle: const Text('Phase 6 — complete'),
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.security_outlined),
            title: const Text('Security'),
            subtitle: const Text('Encrypted storage · R8 obfuscation · scoped storage'),
          ),
        ],
      ),
    );
  }
}
