import 'dart:async';
import 'dart:ui' show AppExitResponse;
import 'package:flutter/material.dart';
import 'models/launcher_controller.dart';
import 'ui/shell.dart';
import 'ui/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const LauncherApp());
}

class LauncherApp extends StatefulWidget {
  const LauncherApp({super.key, this.controller});
  final LauncherController? controller;
  @override
  State<LauncherApp> createState() => _LauncherAppState();
}

class _LauncherAppState extends State<LauncherApp> {
  late final LauncherController controller =
      widget.controller ?? LauncherController();
  late final AppLifecycleListener lifecycle;
  @override
  void initState() {
    super.initState();
    lifecycle = AppLifecycleListener(
      onExitRequested: () async {
        await controller.shutdown();
        return AppExitResponse.exit;
      },
    );
    unawaited(controller.connect());
  }

  @override
  void dispose() {
    lifecycle.dispose();
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'nsp-dawrin',
    debugShowCheckedModeBanner: false,
    theme: launcherTheme(),
    home: LauncherShell(controller: controller),
  );
}
