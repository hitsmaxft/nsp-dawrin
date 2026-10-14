"""Package the native runner without application data or local secrets."""
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
app = root.parent / "nsp-dawrin.app"
contents = app / "Contents"
macos = contents / "MacOS"
macos.mkdir(parents=True, exist_ok=True)
shutil.copy2(root.parent / "work/bin/nsp-dawrin", macos / "nsp-dawrin")
shutil.copy2(root.parent / "work/bin/crash-report", macos / "crash-report")
notices = contents / "Resources" / "Licenses"
notices.mkdir(parents=True, exist_ok=True)
for name in ("LICENSE", "COPYING"):
    shutil.copy2(root / name, notices / name)
for source in (root / "LICENSES").iterdir():
    if source.is_file():
        shutil.copy2(source, notices / source.name)
shutil.copy2(root / "src/third_party/bcdec/LICENSE", notices / "bcdec-LICENSE")
shutil.copy2(root / "src/third_party/h264-interface/NOTICE", notices / "AOSP-AVC-NOTICE")
shutil.copy2(root / "src/third_party/openmax-interface/NOTICE", notices / "OpenMAX-NOTICE")
for source in (root / "src/third_party/openmax-interface").glob("*.h"):
    shutil.copy2(source, notices / source.name)
header = (root / "src/gfx/nvn/include/nvn.h").read_text()
(notices / "nvn-header-MIT.txt").write_text(header.split("*/", 1)[0] + "*/\n")
(contents / "Info.plist").write_bytes(plistlib.dumps(dict(
    CFBundleIdentifier="local.nsp-dawrin.runner",
    CFBundleName="nsp-dawrin",
    CFBundleExecutable="launcher",
    CFBundlePackageType="APPL",
    CFBundleVersion="1",
    CFBundleShortVersionString="0.1",
    LSMinimumSystemVersion="26.0",
    NSHighResolutionCapable=True,
)))
launcher = macos / "launcher"
launcher.write_text("#!/bin/sh\nset -eu\n"
    "export DM_WINDOW=1 DM_TIMEOUT=${DM_TIMEOUT:-0} DM_AUDIO=${DM_AUDIO:-1}\n"
    f"export NATIVE_HOST={shlex.quote(str(macos / 'nsp-dawrin'))}\n"
    f"export NSP_CRASH_REPORTER={shlex.quote(str(macos / 'crash-report'))}\n"
    f"exec python3 {shlex.quote(str(root / 'tools/run_with_report.py'))} -- {shlex.quote(str(root / 'run.sh'))} \"$@\"\n")
launcher.chmod(0o755)
subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
print(app)
