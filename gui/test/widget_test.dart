import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nsp_dawrin_gui/api/launcher_api.dart';
import 'package:nsp_dawrin_gui/main.dart';
import 'package:nsp_dawrin_gui/models/launcher_controller.dart';

class FakeApi implements LauncherApi {
  final calls = <String>[];
  Map<String, dynamic>? lastParams;
  final data = <String, dynamic>{
    'library': <Map<String, dynamic>>[],
    'config': {'keys': '', 'cache': '', 'dotnet': ''},
    'capabilities': {
      'platform': 'Test desktop',
      'ready': true,
      'execution': true,
      'checks': <String, bool>{},
    },
    'session': {
      'state': 'idle',
      'message': 'Ready when you are',
      'metrics': <String, dynamic>{},
      'logs': <String>[],
    },
  };
  void populate() {
    data['library'] = [
      for (final name in ['Orbit Garden', 'Paper Horizons', 'Quiet Circuit'])
        {
          'id': name,
          'name': name,
          'path': '/example/$name.nsp',
          'updates': <String>[],
          'dlc': <String>[],
          'description': {
            'application_version': 1,
            'title_id': '0100f00000001000',
          },
          'preferences': {
            'mode': 'handheld',
            'resolution': 0,
            'fullscreen': false,
            'controller': 'auto',
            'bindings': <String, dynamic>{},
          },
        },
    ];
  }

  @override
  Future<Map<String, dynamic>> call(
    String method, [
    Map<String, dynamic> params = const {},
  ]) async {
    calls.add(method);
    lastParams = params;
    if (method == 'session.start') {
      data['session'] = {
        'state': 'running',
        'entry_id': params['id'],
        'message': 'Session running',
        'logs': <String>[],
      };
    }
    return data;
  }

  @override
  Future<void> close() async {}
}

void main() {
  Future<LauncherController> mount(
    WidgetTester tester,
    FakeApi api, {
    Size size = const Size(1440, 900),
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    if (Platform.environment['NSP_GUI_PREVIEW'] != null) {
      await tester.runAsync(() async {
        final font = FontLoader('Arial')
          ..addFont(
            File(
              '/System/Library/Fonts/Supplemental/Arial.ttf',
            ).readAsBytes().then((b) => ByteData.sublistView(b)),
          );
        await font.load();
      });
    }
    final controller = LauncherController(api: api);
    await tester.pumpWidget(
      RepaintBoundary(
        key: const Key('preview'),
        child: LauncherApp(controller: controller),
      ),
    );
    await tester.pumpAndSettle();
    return controller;
  }

  testWidgets('empty library connects and settings are reachable', (
    tester,
  ) async {
    await mount(tester, FakeApi());
    expect(find.text('Your library'), findsOneWidget);
    expect(find.byKey(const Key('add-package')), findsOneWidget);
    await tester.tap(find.byTooltip('Settings'));
    await tester.pumpAndSettle();
    expect(find.text('Runtime connection'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('library searches and starts the selected application', (
    tester,
  ) async {
    final api = FakeApi()..populate();
    await mount(tester, api);
    final output = Platform.environment['NSP_GUI_PREVIEW'];
    if (output != null) {
      final boundary = tester.renderObject<RenderRepaintBoundary>(
        find.byKey(const Key('preview')),
      );
      await tester.runAsync(() async {
        final image = await boundary.toImage();
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        await File(output).writeAsBytes(bytes!.buffer.asUint8List());
        image.dispose();
      });
    }
    await tester.enterText(find.byKey(const Key('library-search')), 'Quiet');
    await tester.pumpAndSettle();
    expect(find.text('Paper Horizons'), findsNothing);
    await tester.tap(find.text('Quiet Circuit').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Play'));
    await tester.pumpAndSettle();
    expect(api.calls, contains('session.start'));
    expect(api.lastParams?['id'], 'Quiet Circuit');
    expect(tester.takeException(), isNull);
  });
  testWidgets('preferences persist through the API and narrow layout fits', (
    tester,
  ) async {
    final api = FakeApi()..populate();
    await mount(tester, api, size: const Size(900, 720));
    await tester.tap(find.text('Orbit Garden').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Display & controls'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Console · 1080p'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save preferences'));
    await tester.pumpAndSettle();
    expect(api.calls, contains('library.update'));
    expect(api.lastParams?['patch']['preferences']['mode'], 'console');
    expect(tester.takeException(), isNull);
  });
  testWidgets('unsupported execution disables Play but permits preparation', (
    tester,
  ) async {
    final api = FakeApi()..populate();
    (api.data['capabilities'] as Map)['ready'] = false;
    await mount(tester, api);
    final play = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Play'),
    );
    expect(play.onPressed, isNull);
    await tester.tap(find.text('Prepare content'));
    await tester.pumpAndSettle();
    expect(api.calls, contains('session.prepare'));
  });
}
