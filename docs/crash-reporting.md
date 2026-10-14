# Crash reporting

`tools/run_with_report.py` supervises the native runner in its own process group.
It captures a bounded 512 KiB log tail and polls the local control API for runtime
counters and active settings. An abnormal exit produces a report; normal exits,
user termination, and the runner's alarm timeout do not. The independent AppKit
report window survives the failed runtime.

Reports live under `~/Library/Application Support/nsp-dawrin/CrashReports`.
Set `NSP_REPORT_ROOT` or use `--output-root` to select another external directory.
Each report directory has mode 0700 and its files have mode 0600:

| File | Contents |
| --- | --- |
| `report.json` | Structured diagnostics, issue draft, agent prompt and draft URL |
| `issue.md` | Reproduction questions and bounded diagnostic summary |
| `agent-prompt.md` | Module-oriented repair instructions and diagnostics |
| `runtime.log` | Raw local log tail for further investigation |

Shareable diagnostics use an allowlist: build revision, OS and architecture,
exit classification, module offsets and ABI symbols, numeric runtime counters,
active mode and resolution. Arbitrary log lines, package paths, keys, register
dumps and controller identities are excluded. The raw log remains local and is
not part of the issue draft or prompt. The fingerprint groups failures by
revision, location and first symbol; host ASLR addresses do not affect it.

The report window previews the issue and agent prompt. Opening the GitHub draft
requires a user click, and submission happens in the browser. Long issue bodies
are copied for pasting instead of being embedded in the URL. No report is
uploaded automatically. The draft uses GitHub's documented
[issue URL query parameters](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue).

```sh
# Capture an existing prepared session without a report window.
GAME_DIR=/path/cache DM_WINDOW=1 DM_TIMEOUT=90 \
  python tools/run_with_report.py --no-ui

# Generate a report from a previously captured local log.
python tools/crash_report.py /path/runtime.log --exit-code 139 --show
```

`--echo` also streams the raw runner output to the terminal. Direct `run.sh`
and bounded `tools/smoke.py` launches retain their existing process ownership
and do not open a crash window. Preparation errors before runtime launch remain
CLI errors. A supervisor or whole-system failure cannot produce this report.

## Extension and verification

Keep collection and rendering separate. Extend `collect()` with validated
structured fields, not arbitrary log copying. Keep report data outside the
checkout. The native signal handler must not invoke AppKit, Python, networking,
or report serialization; the supervising process handles those after exit.

`tests/test_crash_report.py` checks disclosure boundaries, file permissions,
bounded capture, fingerprints, and child process termination. The native helper
supports `--validate` and `--check-ui` after a report path; the latter constructs
the AppKit previews and actions without opening a browser or using the clipboard.
