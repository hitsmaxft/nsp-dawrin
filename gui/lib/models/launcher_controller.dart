import 'dart:async';
import 'package:flutter/foundation.dart';
import '../api/launcher_api.dart';

class LauncherController extends ChangeNotifier {
  LauncherController({this._api});
  LauncherApi? _api;
  Timer? _timer;
  bool _polling = false;
  bool _disposed = false;
  bool busy = false;
  bool connected = false;
  String? error;
  String? selectedId;
  Map<String, dynamic> data = {};
  List<Map<String, dynamic>> get library => (data['library'] as List? ?? [])
      .map((e) => Map<String, dynamic>.from(e as Map))
      .toList();
  Map<String, dynamic> get session =>
      Map<String, dynamic>.from(data['session'] as Map? ?? {});
  Map<String, dynamic> get config =>
      Map<String, dynamic>.from(data['config'] as Map? ?? {});
  Map<String, dynamic> get capabilities =>
      Map<String, dynamic>.from(data['capabilities'] as Map? ?? {});
  bool get active => [
    'preparing',
    'launching',
    'running',
    'stopping',
  ].contains(session['state']);
  Map<String, dynamic>? get selected {
    for (final entry in library) {
      if (entry['id'] == selectedId) return entry;
    }
    return null;
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _accept(Map<String, dynamic> value) {
    data = value;
    if (!library.any((e) => e['id'] == selectedId)) {
      selectedId = library.isEmpty ? null : library.first['id'] as String;
    }
  }

  Future<void> connect({String? root}) async {
    busy = true;
    error = null;
    _notify();
    try {
      if (root != null) {
        await _api?.close();
        _api = null;
      }
      _api ??= await ProcessLauncherApi.connect(root: root);
      _accept(await _api!.call('snapshot'));
      connected = true;
      _timer?.cancel();
      _timer = Timer.periodic(const Duration(seconds: 2), (_) => refresh());
    } catch (exception) {
      error = exception.toString();
      connected = false;
      await _api?.close();
      _api = null;
    } finally {
      busy = false;
      _notify();
    }
  }

  Future<void> refresh() async {
    if (_polling || busy || !connected || _disposed) return;
    _polling = true;
    try {
      _accept(await _api!.call('snapshot'));
      _notify();
    } catch (exception) {
      error = exception.toString();
      connected = false;
      await _api?.close();
      _api = null;
      _notify();
    } finally {
      _polling = false;
    }
  }

  Future<bool> action(
    String method, [
    Map<String, dynamic> params = const {},
  ]) async {
    if (busy || _api == null) return false;
    busy = true;
    error = null;
    _notify();
    try {
      _accept(await _api!.call(method, params));
      return true;
    } catch (exception) {
      error = exception.toString();
      return false;
    } finally {
      busy = false;
      _notify();
    }
  }

  Future<Map<String, dynamic>> devices() async {
    try {
      return _api == null ? {} : await _api!.call('session.devices');
    } catch (exception) {
      error = exception.toString();
      _notify();
      return {};
    }
  }

  Future<void> chooseController(String id) async {
    try {
      await _api?.call('session.settings', {'controller': id});
      error = null;
    } catch (exception) {
      error = exception.toString();
    }
    _notify();
  }

  void select(String id) {
    selectedId = id;
    _notify();
  }

  void dismissError() {
    error = null;
    _notify();
  }

  Future<void> shutdown() async {
    _timer?.cancel();
    await _api?.close();
  }

  @override
  void dispose() {
    _disposed = true;
    _timer?.cancel();
    unawaited(_api?.close());
    super.dispose();
  }
}
