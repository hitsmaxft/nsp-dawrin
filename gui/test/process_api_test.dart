import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:nsp_dawrin_gui/api/launcher_api.dart';

void main() {
  test(
    'desktop transport prepares an original NSP with update and DLC',
    () async {
      var root = Directory.current;
      while (!File(
        p.join(root.path, 'tools', 'launcher_service.py'),
      ).existsSync()) {
        if (root.parent.path == root.path) {
          throw StateError('Runtime checkout not found');
        }
        root = root.parent;
      }
      final localPython = p.join(
        root.path,
        'build',
        'venv',
        Platform.isWindows ? 'Scripts' : 'bin',
        Platform.isWindows ? 'python.exe' : 'python3',
      );
      final python = File(localPython).existsSync()
          ? localPython
          : (Platform.isWindows ? 'python' : 'python3');
      final temporary = await Directory.systemTemp.createTemp(
        'nsp-desktop-test-',
      );
      ProcessLauncherApi? api;
      try {
        final packages = p.join(temporary.path, 'packages');
        final build = await Process.run(python, [
          p.join(root.path, 'tests', 'fixture_app.py'),
          '--output',
          packages,
        ]);
        expect(build.exitCode, 0, reason: build.stderr.toString());
        api = await ProcessLauncherApi.connect(
          root: root.path,
          python: python,
          dataDirectory: Directory(p.join(temporary.path, 'data')),
        );
        await api.call('config.update', {
          'patch': {'keys': p.join(packages, 'fixture.keys')},
        });
        final added = await api.call('library.add', {
          'path': p.join(packages, 'base.nsp'),
        });
        final id = (added['library'] as List).single['id'];
        await api.call('library.update', {
          'id': id,
          'patch': {
            'updates': [p.join(packages, 'update.nsp')],
            'dlc': [p.join(packages, 'addon.nsp')],
          },
        });
        await api.call('session.prepare', {'id': id});
        Map<String, dynamic> result;
        final deadline = DateTime.now().add(const Duration(seconds: 20));
        do {
          await Future<void>.delayed(const Duration(milliseconds: 100));
          result = await api.call('snapshot');
        } while (result['session']['state'] == 'preparing' &&
            DateTime.now().isBefore(deadline));
        expect(
          result['session']['state'],
          'ready',
          reason: result['session'].toString(),
        );
        expect(result['library'][0]['description']['application_version'], 2);
        await expectLater(
          ProcessLauncherApi.connect(
            root: temporary.path,
            dataDirectory: Directory(p.join(temporary.path, 'data')),
          ),
          throwsStateError,
        );
      } finally {
        await api?.close();
        await temporary.delete(recursive: true);
      }
    },
    timeout: const Timeout(Duration(seconds: 45)),
  );
}
