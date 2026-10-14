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
    f"exec {shlex.quote(str(root / 'run.sh'))} \"$@\"\n")
launcher.chmod(0o755)
subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
print(app)
