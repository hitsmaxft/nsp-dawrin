"""Package the native runner without application data or local secrets."""
from pathlib import Path
import plistlib
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
app = root / "build/nsp-dawrin.app"
contents = app / "Contents"
macos = contents / "MacOS"
macos.mkdir(parents=True, exist_ok=True)
shutil.copy2(root / "build/bin/nsp-dawrin", macos / "nsp-dawrin")
shutil.copy2(root / "build/bin/crash-report", macos / "crash-report")
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
launcher.write_text("""#!/bin/sh
set -eu
MACOS=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$MACOS/../../../.." && pwd)
export DM_WINDOW=1 DM_TIMEOUT=${DM_TIMEOUT:-0} DM_AUDIO=${DM_AUDIO:-1}
export NATIVE_HOST="$MACOS/nsp-dawrin"
export NSP_CRASH_REPORTER="$MACOS/crash-report"
if [ -z "${NSP_PYTHON:-}" ]; then
    if [ -x "$ROOT/build/venv/bin/python3" ]; then
        NSP_PYTHON="$ROOT/build/venv/bin/python3"
    else
        NSP_PYTHON=python3
    fi
fi
export NSP_PYTHON
exec "$NSP_PYTHON" "$ROOT/tools/run_with_report.py" -- "$ROOT/run.sh" "$@"
""")
launcher.chmod(0o755)
subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
print(app)
