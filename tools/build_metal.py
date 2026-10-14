"""Convert translated SPIR-V into macOS MSL and explicit NVN binding metadata."""
import argparse
import concurrent.futures
import hashlib
import threading
import json
import re
import subprocess
from pathlib import Path
from nsp_runtime.cache import atomic_write, chain_version
from nsp_runtime.bindings import storage_binding, resource_writable

p = argparse.ArgumentParser()
p.add_argument("directory", type=Path)
p.add_argument("--spirv-cross", default="spirv-cross")
p.add_argument('--chain')
p.add_argument('--key')
args = p.parse_args()
root = args.directory.resolve()
chain = args.chain or chain_version(root, args.spirv_cross)
translated = root / "translated" / chain
out = root / "metal" / ("b-" + chain)
out.mkdir(parents=True, exist_ok=True)
jobs = json.loads((root / "jobs.json").read_text())
cross_lock = threading.Lock()
cross_results = {}

def cross_compile(path):
    fingerprint = hashlib.sha256(path.read_bytes()).digest()
    with cross_lock:
        owner = fingerprint not in cross_results
        if owner: cross_results[fingerprint] = concurrent.futures.Future()
        future = cross_results[fingerprint]
    if owner:
        try:
            msl = subprocess.check_output([args.spirv_cross, str(path), '--msl',
                '--msl-version', '23000', '--msl-argument-buffers'], text=True, timeout=15)
            reflection = json.loads(subprocess.check_output([args.spirv_cross, str(path), '--reflect'], text=True, timeout=15))
            future.set_result((msl, reflection))
        except Exception as error: future.set_exception(error)
    return future.result()

def texture_slot(resource, sampler=False):
    handle = resource["handle"] & 0xffffffff
    kind = handle >> 28
    if kind not in (0,1):raise ValueError(f'Unsupported texture handle kind: {kind}')
    off = ((handle >> 14) & 0x3fff) if sampler and kind else handle & 0x3fff
    byte = off * 4
    if kind:
        base = 0x568 if sampler else 0x168
    else:
        base = 0x20  # Combined texture/sampler handles in NVN driver constant buffer 2.
    if byte < base or (byte - base) % 8:
        raise ValueError(f"unmapped NVN texture handle {handle:#x}, sampler={sampler}")
    slot = (byte - base) // 8
    if slot >= 128:
        raise ValueError(f"texture slot out of range: {slot}")
    return slot, bool(kind)

def convert(job):
    key = job["key"]
    row = f"native\t{key}\t{dict(vs='vertex',ps='fragment',cs='compute')[job['stage']]}\t{key}\n"
    spv = translated / (key + ".spv")
    resource_bytes = (translated / (key + ".res.json")).read_bytes()
    fingerprint = hashlib.sha256(spv.read_bytes() + resource_bytes + job["c1"].encode()).hexdigest()
    metadata = out / (key + "_b.json")
    if (out / (key + "_b.metal")).exists() and metadata.exists():
        cached = json.loads(metadata.read_text())
        if cached.get("input_digest") == fingerprint and cached.get("chain") == chain:
            return row
    resources = json.loads(resource_bytes)
    msl, reflection = cross_compile(spv)
    names = {}
    for category in ("ubos", "ssbos", "textures", "separate_images", "separate_samplers", "images"):
        for entry in reflection.get(category, []):
            names[entry["name"]] = category, entry
    bindings = []
    driver = {}
    for typ, name, aid in re.findall(r"^\s*(\S[^;\n]*?)\s+(\w+)\s+\[\[id\((\d+)\)\]\];", msl, re.M):
        sampler = typ == "sampler"
        lookup = name[:-5] if sampler and name.endswith("Smplr") else name
        category, entry = names[lookup]
        bind = dict(arg_id=int(aid), msl_name=name, msl_type=typ)
        if category == "ubos":
            if lookup == "support_buffer":
                bind["kind"] = "support"
            else:
                cb = next(r for r in resources["cbufs"] if r["binding"] == entry["binding"])["slot"]
                if cb >= 3:
                    bind.update(kind="cbuf", reg=cb-3)
                elif cb == 1:
                    bind["kind"] = "c1"
                else:
                    bind.update(kind="drvcb", bank=cb)
                    driver[str(cb)] = True
        elif category == "ssbos":
            storage = next(r for r in resources["sbufs"] if r["binding"] == entry["binding"])
            bind.update(storage_binding(storage, job["stage"]))
        elif category in ("textures", "separate_images", "separate_samplers", "images"):
            tex = next(r for r in resources["images" if category=="images" else "textures"] if r["binding"] == entry["binding"])
            if tex["array"] != 1:
                raise ValueError(f"{key}: descriptor arrays require explicit mapping")
            slot, separate = texture_slot(tex, sampler)
            bind.update(kind=("samp" if separate else "samp_tex") if sampler else "img" if category=="images" else "tbuf" if "texture_buffer" in typ else "tex", reg=slot)
            if category=="images": bind["rw"]=resource_writable(tex, 'image')
        else:
            raise ValueError(f"{key}: resource category {category} requires implementation")
        bindings.append(bind)
    vin = [dict(location=int(loc), msl_type=typ) for typ, loc in
           re.findall(r"(\w+)\s+\w+\s+\[\[attribute\((\d+)\)\]\]", msl)]
    function = re.search(r"(?:vertex|fragment|kernel)\s+\w+\s+(\w+)\(", msl)
    if not function:
        raise ValueError(f"{key}: no supported entry point")
    data = dict(input_digest=fingerprint, route="B", chain=chain, entry=function[1], bindings=bindings,
                vertex_inputs=vin, c1=job["c1"], drv_reads=driver, drv_unfillable=[],
                raster=dict(discard=1, sample_mask=1,
                            colors=[v["location"] for v in reflection.get("outputs", [])]
                            if job["stage"] == "ps" else []),
                translation_notes=resources["notes"],threadgroup_size=job.get("local",[]))
    atomic_write(out / (key + "_b.metal"), msl)
    atomic_write(out / (key + "_b.json"), json.dumps(data, indent=2) + "\n")
    return row

failures = []
def checked(job):
    try: return convert(job)
    except Exception as error:
        failures.append(dict(key=job['key'], error=str(error)))
        return None

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    rows = [row for row in executor.map(checked, [j for j in jobs if not args.key or j['key']==args.key]) if row]
if args.key and (root/'shader_map.tsv').exists():
    previous=(root/'shader_map.tsv').read_text().splitlines()
    if previous and previous[0]==f'# chain b-{chain}':
        rows=[line+'\n' for line in previous if line and not line.startswith('#') and line.split('\t')[1]!=args.key]+rows
atomic_write(root / "shader_map.tsv", f"# chain b-{chain}\n" + "".join(rows))
atomic_write(root / "c1_full.tsv", f"# chain b-{chain}\n" + "".join(row.split('\t')[1] + "_b\n" for row in rows))
atomic_write(root / "binding-failures.json", json.dumps(failures, indent=2))
print(f"Generated {len(rows)} MSL shaders and binding manifests")
print(f"Unresolved shader bindings: {len(failures)}")
