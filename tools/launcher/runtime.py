"""Owned subprocess lifecycle and native runtime environment, without a shell."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from nsp_runtime.cache import atomic_write, chain_version


def environment(root, cache, title_id, settings_path, control, saves, dotnet=''):
    env = {k:v for k,v in os.environ.items() if not k.startswith(('DM_','NSP_','GAME_DIR','NATIVE_HOST'))}
    env['PATH'] = os.pathsep.join([str(Path(sys.executable).parent), '/opt/homebrew/bin', '/usr/local/bin', env.get('PATH','')])
    if dotnet: env['DOTNET'] = dotnet
    shaders = cache/'shaders'; shaders.mkdir(exist_ok=True)
    chain = chain_version(shaders)
    for name in ('shader_map.tsv','c1_full.tsv'):
        path=shaders/name; header='# chain b-'+chain+'\n'
        if not path.exists() or not path.read_text().startswith(header): atomic_write(path,header)
    env.update(GAME_DIR=str(cache), DM_PACKAGE_INDEX=str(cache/'package-index.json'),
        DM_ROMFS=str(cache/'vfs'), DM_SAVE=str(saves), DM_TEMP=str(cache/'temp'),
        DM_TITLE_ID=title_id, DM_CONTROL=str(control), NSP_SETTINGS_PATH=str(settings_path),
        DM_WINDOW='1', DM_AUDIO='1', DM_TIMEOUT='0', DM_SVC='1', DM_NVN_LOG='1',
        DM_NVN_TBDR='0', DM_PRESENT_LINK='0', DM_PRESENT_INTERVAL='game',
        DM_SHADER_DUMP=str(shaders), DM_SHADER_CHAIN=chain, DM_NVN_SHMAP=str(shaders/'shader_map.tsv'),
        DM_MSL_DIR=str(shaders/'metal'), DM_SHADER_COMPILER=str(root/'tools/compile_pending_shaders.py'),
        NSP_PYTHON=sys.executable, DM_FSLOG=str(cache/'fs-read.tsv'))
    return env


def terminate(process):
    if process is None or process.poll() is not None: return
    try:
        if os.name=='posix': os.killpg(process.pid,signal.SIGTERM)
        else: process.terminate()
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name=='posix': os.killpg(process.pid,signal.SIGKILL)
        else: process.kill()
        process.wait(timeout=3)
    except ProcessLookupError:
        pass


def spawn(command, env=None):
    return subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,start_new_session=os.name=='posix')
