"""Library, preparation and session API shared by desktop clients."""
import copy
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import threading
import time
import uuid
from content import ContentSet
from nsp_runtime.cache import atomic_write
from smoke import query
from .store import Store, preferences, native_preferences
from . import runtime

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ('preparing','launching','running','stopping')


class ChildFailure(RuntimeError):
    def __init__(self, returncode):
        self.returncode = returncode
        super().__init__(f'Operation exited with code {returncode}. See session details.')


class Launcher:
    def __init__(self, directory, root=ROOT):
        self.root=Path(root).resolve(); self.store=Store(directory)
        if self.store.directory.is_relative_to(self.root): raise ValueError('Launcher data must be outside the checkout')
        self.lock=threading.RLock(); self.process=None; self.worker=None; self.cancel=threading.Event()
        self.logs=deque(maxlen=100); self.control=None
        self.session=dict(state='idle',entry_id=None,message='Ready when you are',metrics={},report=None)

    def capabilities(self):
        native=self.root/'build/bin/nsp-dawrin'
        translator=self.root/'build/dotnet/bin/dmsh_xlate/release/dmsh_xlate.dll'
        dotnet=self.store.data['config'].get('dotnet') or shutil.which('dotnet')
        cross=shutil.which('spirv-cross') or ('/opt/homebrew/bin/spirv-cross' if Path('/opt/homebrew/bin/spirv-cross').is_file() else '')
        checks=dict(packages=all(importlib.util.find_spec(x) is not None for x in ('cryptography','capstone','lz4')),
                    native=native.is_file(),shaders=translator.is_file(),dotnet=bool(dotnet and Path(dotnet).is_file()),spirv_cross=bool(cross))
        supported=sys.platform=='darwin' and platform.machine()=='arm64' and int(platform.mac_ver()[0].split('.')[0] or 0)>=26
        return dict(platform=platform.system(),execution=supported,checks=checks,
                    ready=supported and all(checks.values()), protocol=1)

    def snapshot(self):
        with self.lock:
            if self.session['state']=='running' and self.process and self.control:
                try:
                    status=query(self.control,'status')
                    if status.get('pid')==self.process.pid: self.session['metrics']=status
                except (OSError,ValueError,RuntimeError): pass
            return copy.deepcopy(dict(library=self.store.data['library'],config=self.store.data['config'],
                session={**self.session,'logs':list(self.logs)},capabilities=self.capabilities()))

    def _idle(self):
        if self.worker and self.worker.is_alive(): raise ValueError('Stop the current operation first')

    def _entry(self, identity):
        entry=self.store.entry(identity)
        if not entry: raise ValueError('Library entry no longer exists')
        return entry

    def _describe(self, path, updates, dlc):
        keys=self.store.data['config']['keys']
        if not keys or not Path(keys).is_file(): raise ValueError('Choose your local key file in Settings first')
        paths=[Path(p).expanduser().resolve() for p in [path,*updates,*dlc]]
        if any(p.suffix.lower() not in ('.nsp','.xci') or not p.is_file() for p in paths):
            raise ValueError('Choose an existing NSP or XCI file')
        content=ContentSet(paths,keys)
        try: return content.describe()
        finally: content.close()

    def dispatch(self, method, params):
        with self.lock:
            if method=='snapshot': return self.snapshot()
            if method=='config.update':
                self._idle(); patch=params.get('patch',{})
                if set(patch)-{'keys','dotnet','cache'} or not all(isinstance(v,str) for v in patch.values()):
                    raise ValueError('Invalid launcher configuration')
                for name,value in patch.items():
                    if value and name in ('keys','dotnet') and not Path(value).is_file(): raise ValueError('Selected file is unavailable')
                    if name=='cache' and (not value or Path(value).resolve().is_relative_to(self.root)):
                        raise ValueError('Choose a cache folder outside the source checkout')
                self.store.data['config'].update(patch); self.store.save()
            elif method=='library.add':
                path=str(Path(params['path']).expanduser().resolve())
                if any(e['path']==path for e in self.store.data['library']): raise ValueError('This package is already in your library')
                description=self._describe(path,[],[])
                self.store.data['library'].append(dict(id=uuid.uuid4().hex,path=path,name=Path(path).stem,
                    updates=[],dlc=[],description=description,preferences=preferences({}),last_played=None))
                self.store.save()
            elif method=='library.update':
                self._idle(); entry=self._entry(params['id']); candidate=copy.deepcopy(entry)
                patch=params.get('patch',{})
                if set(patch)-{'name','updates','dlc','preferences'}: raise ValueError('Unknown library field')
                if 'name' in patch and (not isinstance(patch['name'],str) or not patch['name'].strip()): raise ValueError('Enter a name')
                if 'preferences' in patch: patch={**patch,'preferences':preferences(patch['preferences'])}
                for field in ('updates','dlc'):
                    if field in patch and (not isinstance(patch[field],list) or not all(isinstance(p,str) for p in patch[field])): raise ValueError('Invalid content list')
                candidate.update(patch)
                if 'updates' in patch or 'dlc' in patch:
                    candidate['description']=self._describe(candidate['path'],candidate['updates'],candidate['dlc'])
                entry.update(candidate); self.store.save()
            elif method=='library.remove':
                self._idle(); entry=self._entry(params['id']); self.store.data['library'].remove(entry); self.store.save()
            elif method in ('session.prepare','session.start'):
                self._idle(); entry=copy.deepcopy(self._entry(params['id']))
                if method=='session.start' and not self.capabilities()['ready']: raise ValueError('Complete the runtime setup in Settings before playing')
                self.cancel.clear(); self.logs.clear()
                self.session=dict(state='preparing',entry_id=entry['id'],message='Reading content',metrics={},report=None)
                self.worker=threading.Thread(target=self._run,args=(entry,method=='session.start'),daemon=True); self.worker.start()
            elif method=='session.stop':
                self.cancel.set()
                if self.session['state'] in ACTIVE: self.session.update(state='stopping',message='Stopping session')
                runtime.terminate(self.process)
            elif method=='session.settings':
                if self.session['state']!='running': raise ValueError('Start a session to select a connected controller')
                choice=params.get('controller')
                if not isinstance(choice,str) or '\n' in choice or '\r' in choice or len(choice)>128: raise ValueError('Invalid controller')
                return query(self.control,'settings controller '+choice)
            elif method=='session.devices':
                if self.session['state']!='running': return dict(devices=[],selected_controller='auto')
                return query(self.control,'settings')
            elif method=='session.preferences':
                if self.session['state']!='running': raise ValueError('No running session')
                value=preferences(params['preferences']); query(self.control,'settings '+json.dumps(native_preferences(value),separators=(',',':')))
                entry=self._entry(self.session['entry_id']); entry['preferences']=value; self.store.save()
            else: raise ValueError('Unknown launcher method')
            return self.snapshot()

    def _child(self, command, env=None, log_path=None):
        with self.lock:
            if self.cancel.is_set(): raise InterruptedError('Cancelled')
            self.process=runtime.spawn(command,env); process=self.process
        stream=Path(log_path).open('wb') if log_path else None
        try:
            while True:
                line=process.stdout.readline(65536)
                if not line: break
                if stream: stream.write(line)
                text=line.decode('utf-8','replace').strip()
                with self.lock:
                    if text: self.logs.append(text[-500:])
            code=process.wait()
        finally:
            if stream: stream.close()
            process.stdout.close()
            with self.lock:
                if self.process is process: self.process=None
        if self.cancel.is_set(): raise InterruptedError('Cancelled')
        if code: raise ChildFailure(code)

    def _run(self, entry, play):
        native_started = False
        try:
            config=copy.deepcopy(self.store.data['config'])
            paths=[entry['path'],*entry['updates'],*entry['dlc']]
            fingerprint=hashlib.sha256(json.dumps([(p,Path(p).stat().st_size,Path(p).stat().st_mtime_ns) for p in paths]).encode()+
                (self.root/'tools/patch_nso.py').read_bytes()).hexdigest()[:16]
            cache_root=Path(config['cache'])/fingerprint; title_id=entry['description']['title_id']; cache=cache_root/title_id
            command=[sys.executable,str(self.root/'tools/launch.py'),entry['path'],'--keys',config['keys'],
                '--cache-root',str(cache_root),'--prepare-only']
            for field,flag in (('updates','--update'),('dlc','--dlc')):
                for path in entry[field]: command.extend([flag,path])
            self._child(command)
            with self.lock:
                if self.cancel.is_set(): raise InterruptedError('Cancelled')
                self.session.update(state='ready',message='Ready to play')
            if not play: return
            with tempfile.TemporaryDirectory(prefix='nsp-gui-',dir='/tmp') as temporary:
                control=Path(temporary)/'control.sock'; settings=Path(temporary)/'settings.json'
                atomic_write(settings,json.dumps(native_preferences(entry['preferences'])))
                env=runtime.environment(self.root,cache,title_id,settings,control,self.store.directory/'saves'/title_id,config['dotnet'])
                with self.lock:
                    self.control=control; self.session.update(state='running',message='Session running')
                    self._entry(entry['id'])['last_played']=time.time(); self.store.save()
                native_started = True
                self._child([str(self.root/'build/bin/nsp-dawrin'),str(cache/'patched')],env,cache/'gui-runtime.log')
            with self.lock: self.session.update(state='exited',message='Session ended')
        except InterruptedError:
            with self.lock: self.session.update(state='stopped',message='Stopped')
        except Exception as error:
            with self.lock:
                self.session.update(state='failed',message=str(error))
                if native_started and (cache/'gui-runtime.log').exists():
                    from crash_report import create_report
                    with (cache/'gui-runtime.log').open('rb') as log:
                        log.seek(0,2); log.seek(max(0,log.tell()-262144)); text=log.read().decode('utf-8','replace')
                    try:
                        report=create_report(text,getattr(error,'returncode',1),self.store.directory/'reports',status=self.session['metrics'])
                        self.session['report']=json.loads(report.read_text())
                    except Exception: pass
        finally:
            with self.lock: self.control=None

    def close(self):
        with self.lock: self.cancel.set(); process=self.process
        runtime.terminate(process)
        if self.worker: self.worker.join(timeout=5)
