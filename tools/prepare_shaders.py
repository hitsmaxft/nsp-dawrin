"""Prepare offline translation jobs from DM_SHADER_DUMP output (no game edits)."""
import argparse
import json
import struct
from pathlib import Path
from nsp_runtime.facts import JsonFactsProvider
from nsp_runtime.cache import atomic_write, chain_version

p = argparse.ArgumentParser()
p.add_argument("directory", type=Path)
p.add_argument('--chain')
args = p.parse_args()
root = args.directory.resolve()
out = root / "translated" / (args.chain or chain_version(root))
out.mkdir(parents=True, exist_ok=True)
facts = JsonFactsProvider(root / "shader-facts.json")
fact_report = {}
jobs = []
for control in sorted(root.glob("*.control")):
    ctl = control.read_bytes()
    code = control.with_suffix(".code").read_bytes()
    assert len(ctl) == 0x880 and code[:4] == bytes.fromhex("78563412")
    stage = (struct.unpack_from("<I", code, 0x30)[0] >> 10) & 15
    if stage not in (1, 5):
        raise ValueError(f"{control.name}: unimplemented shader stage {stage}")
    c1off, size = struct.unpack_from("<II", ctl, 0x700)
    assert 0x80 <= c1off <= size == len(code)
    dst = out / (control.stem + ".maxwell")
    dst.write_bytes(code[0x30:c1off])
    stage_name = "vs" if stage == 1 else "ps"
    metadata = facts.facts_for(control.stem, stage_name)
    jobs.append(dict(key=control.stem, stage=stage_name, code=str(dst),
                     c1=code[c1off:size].hex(), debug=False, **metadata.values))
    fact_report[control.stem] = dict(source=metadata.source, complete=metadata.complete)
atomic_write(root / "jobs.json", json.dumps(jobs, indent=2) + "\n")
atomic_write(root / "facts-report.json", json.dumps(fact_report, indent=2))
print(f"Prepared {len(jobs)} graphics shader jobs")
