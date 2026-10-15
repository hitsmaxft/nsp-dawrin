import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:path/path.dart' as p;

abstract class LauncherApi {
  Future<Map<String, dynamic>> call(
    String method, [
    Map<String, dynamic> params = const {},
  ]);
  Future<void> close();
}

Directory launcherDataDirectory() {
  final env = Platform.environment;
  final home = env['HOME'] ?? env['USERPROFILE'] ?? Directory.current.path;
  if (Platform.isMacOS) {
    return Directory(
      p.join(home, 'Library', 'Application Support', 'nsp-dawrin', 'launcher'),
    );
  }
  if (Platform.isWindows) {
    return Directory(p.join(env['APPDATA'] ?? home, 'nsp-dawrin', 'launcher'));
  }
  return Directory(
    p.join(
      env['XDG_DATA_HOME'] ?? p.join(home, '.local', 'share'),
      'nsp-dawrin',
      'launcher',
    ),
  );
}

class ProcessLauncherApi implements LauncherApi {
  ProcessLauncherApi._(this._process) {
    _process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
          try {
            final response = jsonDecode(line) as Map<String, dynamic>;
            final pending = _pending.remove(response['id']);
            if (pending == null) return;
            if (response['error'] != null) {
              pending.completeError(
                StateError(response['error']['message'].toString()),
              );
            } else {
              pending.complete(
                Map<String, dynamic>.from(response['result'] as Map),
              );
            }
          } catch (error) {
            _fail(StateError('Invalid launcher response: $error'));
          }
        }, onError: (Object error) => _fail(error));
    _process.stderr.transform(const Utf8Decoder(allowMalformed: true)).listen((
      text,
    ) {
      _diagnostic += text;
      if (_diagnostic.length > 2000) {
        _diagnostic = _diagnostic.substring(_diagnostic.length - 2000);
      }
    });
    _process.exitCode.then(
      (code) =>
          _fail(StateError('Launcher service exited ($code). $_diagnostic')),
    );
  }
  final Process _process;
  final Map<int, Completer<Map<String, dynamic>>> _pending = {};
  int _nextId = 0;
  bool _closed = false;
  bool _closing = false;
  String _diagnostic = '';

  static Future<ProcessLauncherApi> connect({
    String? root,
    String? python,
    Directory? dataDirectory,
  }) async {
    final data = dataDirectory ?? launcherDataDirectory();
    final connection = File(p.join(data.path, 'connection.json'));
    Map<String, dynamic> saved = {};
    if (await connection.exists()) {
      saved =
          jsonDecode(await connection.readAsString()) as Map<String, dynamic>;
    }
    if (root != null &&
        !await File(p.join(root, 'tools', 'launcher_service.py')).exists()) {
      throw StateError('Selected folder does not contain the runtime.');
    }
    final candidates = <String>[
      ?root,
      if (saved['root'] is String) saved['root'] as String,
      if (Platform.environment['NSP_RUNTIME_ROOT'] != null)
        Platform.environment['NSP_RUNTIME_ROOT']!,
      const String.fromEnvironment('NSP_RUNTIME_ROOT'),
    ];
    for (final start in [
      Directory.current.path,
      p.dirname(Platform.resolvedExecutable),
    ]) {
      var current = start;
      for (var i = 0; i < 10; i++) {
        candidates.add(current);
        final parent = p.dirname(current);
        if (parent == current) break;
        current = parent;
      }
    }
    String? selected;
    for (final candidate in candidates.where((path) => path.isNotEmpty)) {
      if (await File(
        p.join(candidate, 'tools', 'launcher_service.py'),
      ).exists()) {
        selected = candidate;
        break;
      }
    }
    if (selected == null) {
      throw StateError('Choose the runtime folder to connect your library.');
    }
    final localPython = p.join(
      selected,
      'build',
      'venv',
      Platform.isWindows ? 'Scripts' : 'bin',
      Platform.isWindows ? 'python.exe' : 'python3',
    );
    final executable =
        python ??
        Platform.environment['NSP_PYTHON'] ??
        (await File(localPython).exists()
            ? localPython
            : (Platform.isWindows ? 'python' : 'python3'));
    final process = await Process.start(
      executable,
      [
        p.join(selected, 'tools', 'launcher_service.py'),
        '--data-dir',
        data.path,
      ],
      workingDirectory: selected,
      environment: {'PYTHONUNBUFFERED': '1', 'PYTHONUTF8': '1'},
    );
    final api = ProcessLauncherApi._(process);
    try {
      await api.call('snapshot');
      await data.create(recursive: true);
      await connection.writeAsString(jsonEncode({'root': selected}));
      return api;
    } catch (_) {
      await api.close();
      rethrow;
    }
  }

  void _fail(Object error) {
    _closed = true;
    for (final pending in _pending.values) {
      if (!pending.isCompleted) pending.completeError(error);
    }
    _pending.clear();
  }

  @override
  Future<Map<String, dynamic>> call(
    String method, [
    Map<String, dynamic> params = const {},
  ]) async {
    if (_closed) {
      throw StateError('Launcher disconnected. Reconnect in Settings.');
    }
    final id = ++_nextId;
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    try {
      _process.stdin.writeln(
        jsonEncode({
          'version': 1,
          'id': id,
          'method': method,
          'params': params,
        }),
      );
      return await completer.future.timeout(const Duration(seconds: 60));
    } finally {
      _pending.remove(id);
    }
  }

  @override
  Future<void> close() async {
    if (!_closing) {
      _closing = true;
      _closed = true;
      await _process.stdin.close();
      try {
        await _process.exitCode.timeout(const Duration(seconds: 8));
      } on TimeoutException {
        _process.kill();
      }
    }
  }
}
