#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${GAME_DIR:?Set GAME_DIR to a prepared application cache}"
GAME_DIR=$(CDPATH= cd -- "$GAME_DIR" && pwd)
export GAME_DIR
if [ -f "$GAME_DIR/package-index.json" ]; then
    export DM_PACKAGE_INDEX="$GAME_DIR/package-index.json"
    export DM_ROMFS="$GAME_DIR/vfs"
    DM_TITLE_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["title_id"])' "$DM_PACKAGE_INDEX")
    export DM_TITLE_ID
else
    : "${DM_TITLE_ID:?Set DM_TITLE_ID for an extracted application}"
    export DM_ROMFS="$GAME_DIR/RomFS"
fi
export DM_SAVE="$GAME_DIR/save" DM_TEMP="$GAME_DIR/temp"
export DM_CONTROL=${DM_CONTROL:-/tmp/nsp-dawrin-$(id -u).sock}
export DM_FSLOG="$GAME_DIR/fs-read.tsv"
export DM_SVC=${DM_SVC:-1} DM_NVN_LOG=${DM_NVN_LOG:-1}
export DM_SHADER_DUMP=${DM_SHADER_DUMP:-$GAME_DIR/shaders}
export NSP_PYTHON=${NSP_PYTHON:-$(command -v python3)}
export DM_SHADER_COMPILER=${DM_SHADER_COMPILER:-$ROOT/tools/compile_pending_shaders.py}
export DM_NVN_TBDR=0
export DM_PRESENT_LINK=${DM_PRESENT_LINK:-0}
export DM_PRESENT_INTERVAL=${DM_PRESENT_INTERVAL:-game}
mkdir -p "$DM_SHADER_DUMP"
DM_SHADER_CHAIN=$(python3 "$ROOT/tools/shader_chain.py" "$DM_SHADER_DUMP")
export DM_SHADER_CHAIN
python3 - "$DM_SHADER_DUMP" "$DM_SHADER_CHAIN" <<'PYCODE'
import pathlib,sys,os
root=pathlib.Path(sys.argv[1]);expected='# chain b-'+sys.argv[2]+'\n'
for name in ('shader_map.tsv','c1_full.tsv'):
    path=root/name
    if not path.exists() or not path.read_text().startswith(expected):
        temporary=path.with_suffix('.tmp');temporary.write_text(expected);os.replace(temporary,path)
PYCODE
export DM_NVN_SHMAP=${DM_NVN_SHMAP:-$DM_SHADER_DUMP/shader_map.tsv}
export DM_MSL_DIR=${DM_MSL_DIR:-$DM_SHADER_DUMP/metal}
exec "${NATIVE_HOST:-$ROOT/../work/bin/nsp-dawrin}" "$GAME_DIR/patched" "$@"
