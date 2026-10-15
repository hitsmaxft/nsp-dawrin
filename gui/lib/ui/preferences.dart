import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/launcher_controller.dart';
import 'theme.dart';

const actionNames = [
  'A',
  'B',
  'X',
  'Y',
  'Left stick click',
  'Right stick click',
  'L',
  'R',
  'ZL',
  'ZR',
  'Plus',
  'Minus',
  'D-pad left',
  'D-pad up',
  'D-pad right',
  'D-pad down',
  'Left stick left',
  'Left stick up',
  'Left stick right',
  'Left stick down',
  'Right stick left',
  'Right stick up',
  'Right stick right',
  'Right stick down',
];
String keyLabel(int usage) {
  if (usage >= 4 && usage <= 29) return String.fromCharCode(usage + 61);
  if (usage >= 30 && usage <= 38) return '${usage - 29}';
  return {
        39: '0',
        40: 'Enter',
        41: 'Esc',
        42: 'Backspace',
        43: 'Tab',
        44: 'Space',
        79: '→',
        80: '←',
        81: '↓',
        82: '↑',
        224: 'Ctrl',
        225: 'Shift',
        226: 'Alt',
        228: 'Right Ctrl',
        229: 'Right Shift',
        230: 'Right Alt',
      }[usage] ??
      'Key $usage';
}

Future<void> showPreferences(
  BuildContext context,
  LauncherController controller,
  Map<String, dynamic> entry,
) => showDialog<void>(
  context: context,
  builder: (_) => PreferencesDialog(controller: controller, entry: entry),
);

class PreferencesDialog extends StatefulWidget {
  const PreferencesDialog({
    super.key,
    required this.controller,
    required this.entry,
  });
  final LauncherController controller;
  final Map<String, dynamic> entry;
  @override
  State<PreferencesDialog> createState() => _PreferencesDialogState();
}

class _PreferencesDialogState extends State<PreferencesDialog> {
  late final Map<String, dynamic> value =
      jsonDecode(jsonEncode(widget.entry['preferences']))
          as Map<String, dynamic>;
  final focus = FocusNode();
  int? capture;
  String? error;
  bool saving = false;
  @override
  void dispose() {
    focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Focus(
    focusNode: focus,
    onKeyEvent: (_, event) {
      if (capture == null || event is! KeyDownEvent) {
        return KeyEventResult.ignored;
      }
      final usage = event.physicalKey.usbHidUsage & 0xffff;
      setState(() {
        (value['bindings'] as Map)[capture.toString()] = [usage];
        capture = null;
      });
      return KeyEventResult.handled;
    },
    child: AlertDialog(
      title: const Text('Display & controls'),
      content: SizedBox(
        width: 580,
        height: 510,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.entry['name'] as String,
                style: const TextStyle(color: muted),
              ),
              const SizedBox(height: 22),
              const Text(
                'System mode · next launch',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 10),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(
                    value: 'handheld',
                    label: Text('Handheld · 720p'),
                    icon: Icon(Icons.sports_esports_outlined),
                  ),
                  ButtonSegment(
                    value: 'console',
                    label: Text('Console · 1080p'),
                    icon: Icon(Icons.desktop_windows_outlined),
                  ),
                ],
                selected: {value['mode'] as String},
                onSelectionChanged: (v) =>
                    setState(() => value['mode'] = v.first),
              ),
              const SizedBox(height: 22),
              DropdownButtonFormField<int>(
                initialValue: value['resolution'] as int,
                decoration: const InputDecoration(labelText: 'Display output'),
                items: const [
                  DropdownMenuItem(value: 0, child: Text('Automatic')),
                  DropdownMenuItem(value: 720, child: Text('1280 × 720')),
                  DropdownMenuItem(value: 1080, child: Text('1920 × 1080')),
                ],
                onChanged: (v) => setState(() => value['resolution'] = v),
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text(
                  'Full screen',
                  style: TextStyle(fontSize: 14),
                ),
                value: value['fullscreen'] as bool,
                onChanged: (v) => setState(() => value['fullscreen'] = v),
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: value['controller'] as String,
                decoration: const InputDecoration(
                  labelText: 'Input preference',
                ),
                items: const [
                  DropdownMenuItem(value: 'auto', child: Text('Automatic')),
                  DropdownMenuItem(
                    value: 'none',
                    child: Text('Keyboard & mouse only'),
                  ),
                ],
                onChanged: (v) => setState(() => value['controller'] = v),
              ),
              const SizedBox(height: 24),
              const Divider(),
              const SizedBox(height: 16),
              const Text(
                'Keyboard bindings',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 14),
              for (var i = 0; i < actionNames.length; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: 5),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          actionNames[i],
                          style: const TextStyle(fontSize: 13),
                        ),
                      ),
                      OutlinedButton(
                        onPressed: () {
                          setState(() => capture = i);
                          focus.requestFocus();
                        },
                        child: Text(
                          capture == i
                              ? 'Press a key…'
                              : ((value['bindings'] as Map)['$i'] as List? ??
                                        [])
                                    .map((v) => keyLabel(v as int))
                                    .join(' / ')
                                    .isEmpty
                              ? 'Unassigned'
                              : ((value['bindings'] as Map)['$i'] as List)
                                    .map((v) => keyLabel(v as int))
                                    .join(' / '),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Clear ${actionNames[i]}',
                        onPressed: () => setState(
                          () => (value['bindings'] as Map).remove('$i'),
                        ),
                        icon: const Icon(Icons.close, size: 16),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
      actions: [
        if (error != null)
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text(error!, style: const TextStyle(color: Colors.red)),
          ),
        TextButton(
          onPressed: saving ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: saving
              ? null
              : () async {
                  setState(() {
                    saving = true;
                    error = null;
                  });
                  final running =
                      widget.controller.session['state'] == 'running' &&
                      widget.controller.session['entry_id'] ==
                          widget.entry['id'];
                  final okay = await widget.controller.action(
                    running ? 'session.preferences' : 'library.update',
                    running
                        ? {'preferences': value}
                        : {
                            'id': widget.entry['id'],
                            'patch': {'preferences': value},
                          },
                  );
                  if (!context.mounted) return;
                  if (okay) {
                    Navigator.pop(context);
                  } else {
                    setState(() {
                      saving = false;
                      error = widget.controller.error;
                    });
                  }
                },
          child: Text(saving ? 'Saving…' : 'Save'),
        ),
      ],
    ),
  );
}
