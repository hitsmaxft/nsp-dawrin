import 'dart:async';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import '../models/launcher_controller.dart';
import 'preferences.dart';
import 'theme.dart';

const packageType = XTypeGroup(
  label: 'Application packages',
  extensions: ['nsp', 'xci'],
);

class LauncherShell extends StatefulWidget {
  const LauncherShell({super.key, required this.controller});
  final LauncherController controller;
  @override
  State<LauncherShell> createState() => _LauncherShellState();
}

class _LauncherShellState extends State<LauncherShell> {
  int page = 0;
  String search = '';
  bool alphabetical = false;
  LauncherController get c => widget.controller;

  Future<void> add() async {
    final files = await openFiles(acceptedTypeGroups: [packageType]);
    for (final file in files) {
      if (!await c.action('library.add', {'path': file.path})) break;
    }
  }

  Future<void> contentDialog(Map<String, dynamic> entry) async {
    var updates = List<String>.from(entry['updates'] as List);
    var dlc = List<String>.from(entry['dlc'] as List);
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) {
          Widget group(String title, List<String> paths) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleMedium),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: () async {
                      final files = await openFiles(
                        acceptedTypeGroups: [packageType],
                      );
                      update(() {
                        for (final file in files) {
                          if (!paths.contains(file.path)) paths.add(file.path);
                        }
                      });
                    },
                    icon: const Icon(Icons.add, size: 16),
                    label: const Text('Add files'),
                  ),
                ],
              ),
              if (paths.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(bottom: 20),
                  child: Text(
                    'No additional content',
                    style: TextStyle(color: muted),
                  ),
                ),
              for (final path in paths)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.insert_drive_file_outlined),
                  title: Text(p.basename(path), maxLines: 2),
                  trailing: IconButton(
                    tooltip: 'Remove association',
                    icon: const Icon(Icons.close, size: 18),
                    onPressed: () => update(() => paths.remove(path)),
                  ),
                ),
            ],
          );
          return AlertDialog(
            title: const Text('Manage content'),
            content: SizedBox(
              width: 520,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry['name'] as String,
                      style: const TextStyle(color: muted),
                    ),
                    const SizedBox(height: 18),
                    group('Updates', updates),
                    const Divider(),
                    group('Add-on content', dlc),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () async {
                  Navigator.pop(context);
                  await c.action('library.update', {
                    'id': entry['id'],
                    'patch': {'updates': updates, 'dlc': dlc},
                  });
                },
                child: const Text('Apply content'),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> rename(Map<String, dynamic> entry) async {
    final input = TextEditingController(text: entry['name'] as String);
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Rename in library'),
        content: TextField(
          controller: input,
          autofocus: true,
          onSubmitted: (v) => Navigator.pop(context, v),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    input.dispose();
    if (value != null) {
      await c.action('library.update', {
        'id': entry['id'],
        'patch': {'name': value},
      });
    }
  }

  Future<void> remove(Map<String, dynamic> entry) async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove from library?'),
        content: const Text(
          'Your package files, prepared content and saves will stay on disk.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (accepted == true) await c.action('library.remove', {'id': entry['id']});
  }

  Future<void> stop() async {
    final preparing = c.session['state'] == 'preparing';
    final accepted =
        preparing ||
        await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('End this session?'),
                content: const Text(
                  'Save your progress in the application before stopping.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Keep playing'),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('End session'),
                  ),
                ],
              ),
            ) ==
            true;
    if (accepted) await c.action('session.stop');
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: c,
    builder: (context, _) {
      final width = MediaQuery.sizeOf(context).width;
      return Scaffold(
        body: SafeArea(
          child: Row(
            children: [
              navigation(width >= 1000),
              Expanded(
                child: Column(
                  children: [
                    if (c.busy) const LinearProgressIndicator(minHeight: 2),
                    if (c.error != null)
                      MaterialBanner(
                        backgroundColor: const Color(0xffffeee6),
                        leading: const Icon(Icons.info_outline),
                        content: Text(c.error!.replaceFirst('Bad state: ', '')),
                        actions: [
                          TextButton(
                            onPressed: () => setState(() => page = 2),
                            child: const Text('Settings'),
                          ),
                          IconButton(
                            tooltip: 'Dismiss',
                            onPressed: c.dismissError,
                            icon: const Icon(Icons.close),
                          ),
                        ],
                      ),
                    Expanded(
                      child: switch (page) {
                        1 => sessionPage(),
                        2 => settingsPage(),
                        _ => libraryPage(width),
                      },
                    ),
                    statusBar(),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    },
  );

  Widget navigation(bool wide) => Container(
    width: wide ? 194 : 76,
    padding: EdgeInsets.symmetric(horizontal: wide ? 18 : 10, vertical: 30),
    decoration: const BoxDecoration(color: ink),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: accent,
                borderRadius: BorderRadius.circular(13),
              ),
              child: const Icon(Icons.sports_esports_outlined, color: ink),
            ),
            if (wide) ...[
              const SizedBox(width: 10),
              const Expanded(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'nsp-dawrin',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                      letterSpacing: -.4,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 50),
        for (final item in [
          (0, Icons.grid_view_rounded, 'Library'),
          (1, Icons.play_circle_outline, 'Session'),
          (2, Icons.tune_rounded, 'Settings'),
        ])
          Padding(
            padding: const EdgeInsets.only(bottom: 7),
            child: Tooltip(
              message: item.$3,
              child: Material(
                color: page == item.$1
                    ? const Color(0xff304238)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(12),
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: () => setState(() => page = item.$1),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 15,
                      vertical: 16,
                    ),
                    child: Row(
                      children: [
                        Icon(
                          item.$2,
                          size: 20,
                          color: page == item.$1
                              ? accent
                              : const Color(0xff9cafa3),
                        ),
                        if (wide) ...[
                          const SizedBox(width: 13),
                          Expanded(
                            child: Text(
                              item.$3,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                color: page == item.$1
                                    ? Colors.white
                                    : const Color(0xffbdc9c1),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        const Spacer(),
        TextButton(
          onPressed: () => showLicensePage(
            context: context,
            applicationName: 'nsp-dawrin',
            applicationVersion: '0.1.0',
          ),
          child: wide
              ? const Text(
                  'About',
                  style: TextStyle(color: Color(0xff9cafa3), fontSize: 10),
                )
              : const Icon(Icons.info_outline, color: muted),
        ),
      ],
    ),
  );

  Widget statusBar() => Container(
    height: 42,
    padding: const EdgeInsets.symmetric(horizontal: 28),
    decoration: const BoxDecoration(
      color: Colors.white,
      border: Border(top: BorderSide(color: border)),
    ),
    child: Row(
      children: [
        Icon(
          Icons.circle,
          size: 7,
          color: c.connected ? const Color(0xff6d9e46) : Colors.orange,
        ),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            c.connected
                ? (c.session['state'] as String? ?? 'Connected')
                : 'Disconnected',
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: muted, fontSize: 11),
          ),
        ),
        if (c.active)
          TextButton(
            onPressed: stop,
            child: const Text('Stop', style: TextStyle(fontSize: 11)),
          ),
        const SizedBox(width: 16),
        Text(
          c.capabilities['platform'] as String? ?? 'Desktop',
          style: const TextStyle(color: muted, fontSize: 11),
        ),
      ],
    ),
  );

  Widget libraryPage(double width) {
    var entries = c.library
        .where(
          (e) => (e['name'] as String).toLowerCase().contains(
            search.toLowerCase(),
          ),
        )
        .toList();
    entries.sort(
      (a, b) => alphabetical
          ? (a['name'] as String).compareTo(b['name'] as String)
          : ((b['last_played'] as num?) ?? 0).compareTo(
              (a['last_played'] as num?) ?? 0,
            ),
    );
    final detail = width >= 1250 && c.selected != null;
    return Row(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(32, 32, 32, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Library',
                            style: Theme.of(context).textTheme.headlineLarge,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '${c.library.length} ${c.library.length == 1 ? 'application' : 'applications'}',
                            style: const TextStyle(color: muted),
                          ),
                        ],
                      ),
                    ),
                    FilledButton.icon(
                      key: const Key('add-package'),
                      onPressed: c.busy || !c.connected ? null : add,
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('Add package'),
                    ),
                  ],
                ),
                const SizedBox(height: 26),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        key: const Key('library-search'),
                        onChanged: (value) => setState(() => search = value),
                        decoration: const InputDecoration(
                          hintText: 'Search library',
                          prefixIcon: Icon(Icons.search, size: 20),
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    DropdownButtonHideUnderline(
                      child: DropdownButton<bool>(
                        value: alphabetical,
                        style: const TextStyle(fontSize: 12, color: muted),
                        borderRadius: BorderRadius.circular(12),
                        items: const [
                          DropdownMenuItem(
                            value: false,
                            child: Text('Recent first'),
                          ),
                          DropdownMenuItem(
                            value: true,
                            child: Text('Name A–Z'),
                          ),
                        ],
                        onChanged: (value) =>
                            setState(() => alphabetical = value!),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 22),
                if (entries.isEmpty)
                  emptyLibrary()
                else
                  LayoutBuilder(
                    builder: (context, box) {
                      final columns = box.maxWidth > 760
                          ? 3
                          : box.maxWidth > 420
                          ? 2
                          : 1;
                      return GridView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: entries.length,
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: columns,
                          crossAxisSpacing: 18,
                          mainAxisSpacing: 18,
                          mainAxisExtent: 222,
                        ),
                        itemBuilder: (context, i) =>
                            gameCard(entries[i], detail),
                      );
                    },
                  ),
              ],
            ),
          ),
        ),
        if (detail)
          Container(
            width: 296,
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(left: BorderSide(color: border)),
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Material(color: Colors.white, child: details(c.selected!)),
            ),
          ),
      ],
    );
  }

  Widget emptyLibrary() => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(vertical: 38, horizontal: 20),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: border),
    ),
    child: Column(
      children: [
        const Icon(Icons.folder_open_rounded, size: 36, color: muted),
        const SizedBox(height: 15),
        Text(
          search.isEmpty ? 'No applications' : 'No matches',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        if (search.isEmpty) ...[
          const SizedBox(height: 18),
          OutlinedButton(
            onPressed: c.connected && !c.busy
                ? add
                : () => setState(() => page = 2),
            child: Text(c.connected ? 'Browse files' : 'Set up launcher'),
          ),
        ],
      ],
    ),
  );

  Widget gameCard(Map<String, dynamic> entry, bool detail) {
    final selected = entry['id'] == c.selectedId;
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(17),
        side: BorderSide(
          color: selected ? const Color(0xff829c67) : border,
          width: selected ? 1.5 : 1,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          c.select(entry['id'] as String);
          if (!detail) {
            showDialog<void>(
              context: context,
              builder: (context) => Dialog(
                child: SizedBox(
                  width: 360,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(26),
                    child: details(entry),
                  ),
                ),
              ),
            );
          }
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: artwork(entry)),
            Padding(
              padding: const EdgeInsets.fromLTRB(15, 13, 13, 13),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          entry['name'] as String,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          (entry['dlc'] as List).isNotEmpty
                              ? '${(entry['dlc'] as List).length} add-ons attached'
                              : p
                                    .extension(entry['path'] as String)
                                    .substring(1)
                                    .toUpperCase(),
                          style: const TextStyle(color: muted, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  const Icon(
                    Icons.arrow_outward_rounded,
                    size: 18,
                    color: muted,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget artwork(Map<String, dynamic> entry, {double? height}) {
    final hash = (entry['id'] as String).codeUnits.fold<int>(
      0,
      (a, b) => a + b,
    );
    final colors = [
      const Color(0xffcddabc),
      const Color(0xffd6c9b3),
      const Color(0xffbfd3d5),
      const Color(0xffd6c5cc),
    ];
    return Container(
      height: height,
      width: double.infinity,
      color: colors[hash % colors.length],
      child: Stack(
        children: [
          Positioned(
            right: -25,
            top: -25,
            child: SizedBox(
              width: 190,
              height: 190,
              child: CustomPaint(painter: OrbitPainter(light: true)),
            ),
          ),
          Positioned(
            left: 20,
            bottom: 14,
            child: Text(
              (entry['name'] as String).substring(0, 1).toUpperCase(),
              style: TextStyle(
                fontSize: 72,
                fontWeight: FontWeight.w300,
                color: ink.withValues(alpha: .72),
                height: 1,
              ),
            ),
          ),
          Positioned(
            top: 14,
            left: 15,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: .6),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                p
                    .extension(entry['path'] as String)
                    .replaceFirst('.', '')
                    .toUpperCase(),
                style: const TextStyle(
                  fontSize: 9,
                  letterSpacing: 1,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget details(Map<String, dynamic> entry) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          const Spacer(),
          PopupMenuButton<String>(
            enabled: !c.active,
            tooltip: 'Library actions',
            onSelected: (value) =>
                value == 'rename' ? rename(entry) : remove(entry),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'rename', child: Text('Rename')),
              PopupMenuItem(
                value: 'remove',
                child: Text('Remove from library'),
              ),
            ],
          ),
        ],
      ),
      const SizedBox(height: 12),
      ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: artwork(entry, height: 170),
      ),
      const SizedBox(height: 22),
      Text(
        entry['name'] as String,
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 24),
      SizedBox(
        width: double.infinity,
        child: FilledButton.icon(
          key: const Key('play-selected'),
          onPressed: c.busy || c.active || c.capabilities['ready'] != true
              ? null
              : () {
                  if (Navigator.of(context).canPop()) Navigator.pop(context);
                  c.action('session.start', {'id': entry['id']});
                  setState(() => page = 1);
                },
          icon: const Icon(Icons.play_arrow_rounded),
          label: const Text('Play'),
        ),
      ),
      const SizedBox(height: 9),
      SizedBox(
        width: double.infinity,
        child: OutlinedButton.icon(
          onPressed: c.busy || c.active
              ? null
              : () {
                  if (Navigator.of(context).canPop()) Navigator.pop(context);
                  c.action('session.prepare', {'id': entry['id']});
                  setState(() => page = 1);
                },
          icon: const Icon(Icons.download_done, size: 17),
          label: const Text('Prepare content'),
        ),
      ),
      if (c.capabilities['ready'] != true)
        TextButton(
          onPressed: () {
            if (Navigator.of(context).canPop()) Navigator.pop(context);
            setState(() => page = 2);
          },
          child: const Text('Runtime setup', style: TextStyle(fontSize: 12)),
        ),
      const SizedBox(height: 24),
      ListTile(
        contentPadding: EdgeInsets.zero,
        leading: const Icon(Icons.layers_outlined, size: 21),
        title: const Text('Updates & add-ons', style: TextStyle(fontSize: 13)),
        subtitle: Text(
          '${(entry['updates'] as List).length} updates · ${(entry['dlc'] as List).length} add-ons',
          style: const TextStyle(fontSize: 11),
        ),
        trailing: const Icon(Icons.chevron_right, size: 18),
        onTap: c.active ? null : () => contentDialog(entry),
      ),
      ListTile(
        contentPadding: EdgeInsets.zero,
        leading: const Icon(Icons.tune, size: 21),
        title: const Text('Display & controls', style: TextStyle(fontSize: 13)),
        subtitle: Text(
          entry['preferences']['mode'] == 'console'
              ? 'Console · 1080p mode'
              : 'Handheld · 720p mode',
          style: const TextStyle(fontSize: 11),
        ),
        trailing: const Icon(Icons.chevron_right, size: 18),
        onTap: () => showPreferences(context, c, entry),
      ),
      const SizedBox(height: 20),
      ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Information', style: TextStyle(fontSize: 13)),
        children: [
          ListTile(
            title: const Text('Version'),
            trailing: Text('${entry['description']['application_version']}'),
          ),
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: SelectableText(
              entry['path'] as String,
              style: const TextStyle(fontSize: 11, color: muted),
            ),
          ),
        ],
      ),
    ],
  );

  Widget sessionPage() {
    final session = c.session;
    final metrics = session['metrics'] as Map? ?? {};
    final state = session['state'] as String? ?? 'idle';
    final entry = c.library
        .where((e) => e['id'] == session['entry_id'])
        .firstOrNull;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(36),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Session', style: Theme.of(context).textTheme.headlineLarge),
          const SizedBox(height: 28),
          panel(
            child: Row(
              children: [
                const Icon(Icons.play_circle_outline, size: 36),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        entry?['name'] as String? ?? 'No active session',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 6),
                      Text(state, style: const TextStyle(color: muted)),
                    ],
                  ),
                ),
                if (c.active)
                  OutlinedButton.icon(
                    onPressed: stop,
                    icon: const Icon(Icons.stop_rounded),
                    label: const Text('Stop'),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          if (state == 'running')
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                OutlinedButton.icon(
                  onPressed: entry == null
                      ? null
                      : () => showPreferences(context, c, entry),
                  icon: const Icon(Icons.tune, size: 18),
                  label: const Text('Display & controls'),
                ),
                OutlinedButton.icon(
                  onPressed: controllers,
                  icon: const Icon(Icons.sports_esports_outlined, size: 18),
                  label: const Text('Controller'),
                ),
              ],
            ),
          if (session['report'] != null)
            FilledButton.icon(
              onPressed: () => reportDialog(
                Map<String, dynamic>.from(session['report'] as Map),
              ),
              icon: const Icon(Icons.bug_report_outlined),
              label: const Text('Repair prompt'),
            ),
          if (state == 'failed')
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Text(
                session['message'] as String? ?? '',
                style: const TextStyle(color: Colors.red),
              ),
            ),
          const SizedBox(height: 20),
          panel(
            child: ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Diagnostics'),
              children: [
                Wrap(
                  spacing: 24,
                  runSpacing: 12,
                  children: [
                    for (final item in [
                      ('frames', 'Frames'),
                      ('shader_loads', 'Shaders'),
                      ('shader_failures', 'Errors'),
                      ('save_commits', 'Saves'),
                    ])
                      Text(
                        '${item.$2}  ${metrics[item.$1] ?? '—'}',
                        style: const TextStyle(color: muted),
                      ),
                  ],
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: SelectableText(
                    (session['logs'] as List? ?? []).join('\n'),
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      height: 1.6,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> controllers() async {
    final devices = await c.devices();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Choose controller'),
        children: [
          for (final device in [
            {'id': 'auto', 'name': 'Automatic selection'},
            {'id': 'none', 'name': 'Keyboard & mouse only'},
            ...List<Map<String, dynamic>>.from(
              devices['devices'] as List? ?? [],
            ),
          ])
            SimpleDialogOption(
              onPressed: () {
                Navigator.pop(context);
                c.chooseController(device['id'] as String);
              },
              child: Text(device['name'] as String),
            ),
        ],
      ),
    );
  }

  Future<void> reportDialog(Map<String, dynamic> report) => showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Repair prompt'),
      content: SizedBox(
        width: 660,
        height: 400,
        child: SingleChildScrollView(
          child: SelectableText(
            report['agent_prompt'] as String? ?? 'No report available.',
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton.icon(
          onPressed: () async {
            await Clipboard.setData(
              ClipboardData(text: report['agent_prompt'] as String),
            );
            if (context.mounted) Navigator.pop(context);
          },
          icon: const Icon(Icons.copy, size: 16),
          label: const Text('Copy prompt'),
        ),
      ],
    ),
  );

  Widget settingsPage() {
    final checks = c.capabilities['checks'] as Map? ?? {};
    Widget location(String title, String field, {bool directory = false}) {
      final value = c.config[field] as String? ?? '';
      return ListTile(
        contentPadding: EdgeInsets.zero,
        title: Text(title, style: const TextStyle(fontSize: 14)),
        subtitle: value.isEmpty
            ? null
            : Tooltip(
                message: value,
                child: Text(
                  p.basename(value),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
        trailing: OutlinedButton(
          onPressed: c.active || c.busy || !c.connected
              ? null
              : () async {
                  final path = directory
                      ? await getDirectoryPath()
                      : (await openFile())?.path;
                  if (path != null) {
                    await c.action('config.update', {
                      'patch': {field: path},
                    });
                  }
                },
          child: const Text('Choose'),
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(36),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Settings', style: Theme.of(context).textTheme.headlineLarge),
          const SizedBox(height: 28),
          panel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                sectionTitle(Icons.link, 'Runtime connection'),
                const SizedBox(height: 20),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    FilledButton(
                      onPressed: c.busy || c.active
                          ? null
                          : () async {
                              final root = await getDirectoryPath();
                              if (root != null) await c.connect(root: root);
                            },
                      child: const Text('Choose runtime folder'),
                    ),
                    OutlinedButton(
                      onPressed: c.busy || c.active ? null : () => c.connect(),
                      child: const Text('Reconnect'),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                location('Key file', 'keys'),
                location('Cache folder', 'cache', directory: true),
                if (c.connected && c.capabilities['execution'] != true)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      'Playback requires macOS 26+ / ARM64.',
                      style: TextStyle(color: muted),
                    ),
                  ),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Advanced', style: TextStyle(fontSize: 14)),
                  children: [
                    location('.NET executable', 'dotnet'),
                    for (final item in [
                      ('packages', 'Package tools'),
                      ('native', 'Native runner'),
                      ('shaders', 'Shader translator'),
                      ('dotnet', '.NET'),
                      ('spirv_cross', 'SPIRV-Cross'),
                    ])
                      ListTile(
                        dense: true,
                        title: Text(item.$2),
                        trailing: Icon(
                          checks[item.$1] == true
                              ? Icons.check_circle_outline
                              : Icons.remove_circle_outline,
                          size: 18,
                          color: muted,
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          if (c.selected != null)
            panel(
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.tune),
                title: Text(c.selected!['name'] as String),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => showPreferences(context, c, c.selected!),
              ),
            ),
        ],
      ),
    );
  }
}

Widget panel({required Widget child}) => Container(
  padding: const EdgeInsets.all(23),
  decoration: BoxDecoration(
    color: Colors.white,
    borderRadius: BorderRadius.circular(18),
    border: Border.all(color: border),
  ),
  child: Material(color: Colors.transparent, child: child),
);
Widget sectionTitle(IconData icon, String title) => Row(
  children: [
    Icon(icon, size: 21),
    const SizedBox(width: 12),
    Text(
      title,
      style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
    ),
  ],
);

class OrbitPainter extends CustomPainter {
  OrbitPainter({this.light = false});
  final bool light;
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.3
      ..color = (light ? ink : accent).withValues(alpha: light ? .13 : .28);
    final center = Offset(size.width / 2, size.height / 2);
    for (var i = 0; i < 8; i++) {
      canvas.drawOval(
        Rect.fromCenter(
          center: center.translate(i * 6, i * 2),
          width: size.width * .3 + i * 24,
          height: size.height * .65 + i * 14,
        ),
        paint,
      );
    }
    canvas.drawCircle(
      center.translate(-30, 22),
      size.width * .12,
      Paint()
        ..color = (light ? Colors.white : accent).withValues(
          alpha: light ? .38 : .9,
        ),
    );
  }

  @override
  bool shouldRepaint(covariant OrbitPainter oldDelegate) =>
      light != oldDelegate.light;
}
