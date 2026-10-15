"""Versioned launcher library; stores paths and preferences, never key contents."""
import copy
import json
import os
from pathlib import Path
import sys
from nsp_runtime.cache import atomic_write

DEFAULT_PREFERENCES = dict(mode='handheld', resolution=0, fullscreen=False, controller='auto',
    bindings={'0': [29, 44], '1': [27, 41], '2': [4], '3': [22], '10': [40],
              '12': [80], '13': [82], '14': [79], '15': [81]})
# USB keyboard usages -> existing macOS runtime keycodes. The UI uses USB usages.
MAC_KEYS = dict(zip(range(4, 30), [0,11,8,2,14,3,5,4,34,38,40,37,46,45,31,35,12,15,1,17,32,9,13,7,16,6]))
MAC_KEYS.update(dict(zip(range(30, 40), [18,19,20,21,23,22,26,28,25,29])))
MAC_KEYS.update({40:36,41:53,42:51,43:48,44:49,45:27,46:24,47:33,48:30,49:42,
                 51:41,52:39,53:50,54:43,55:47,56:44,57:57,79:124,80:123,81:125,82:126,
                 224:59,225:56,226:58,228:62,229:60,230:61})


def data_directory():
    if sys.platform == 'darwin': return Path.home() / 'Library/Application Support/nsp-dawrin/launcher'
    if os.name == 'nt': return Path(os.environ.get('APPDATA', Path.home())) / 'nsp-dawrin/launcher'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share')) / 'nsp-dawrin/launcher'


def preferences(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_PREFERENCES):
        raise ValueError('Unknown preference')
    result = copy.deepcopy(DEFAULT_PREFERENCES); result.update(value)
    if result['mode'] not in ('handheld','console') or result['resolution'] not in (0,720,1080):
        raise ValueError('Invalid display mode')
    if type(result['fullscreen']) is not bool or result['controller'] not in ('auto','none'):
        raise ValueError('Invalid input or fullscreen preference')
    seen = set()
    if not isinstance(result['bindings'], dict): raise ValueError('Invalid keyboard bindings')
    for action, keys in result['bindings'].items():
        if str(action) not in map(str, range(24)) or not isinstance(keys, list) or len(keys)>4:
            raise ValueError('Invalid keyboard action')
        for key in keys:
            if type(key) is not int or key not in MAC_KEYS: raise ValueError('This key cannot be mapped yet')
            if key in seen: raise ValueError('This key is already assigned to another action')
            seen.add(key)
    return result


def native_preferences(value):
    result = preferences(value)
    result['bindings'] = {action: [MAC_KEYS[key] for key in keys] for action,keys in result['bindings'].items()}
    return result


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / 'library.json'
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
            if self.data.get('schema') != 1 or not isinstance(self.data.get('library'), list):
                raise ValueError('Unsupported library file; preserve it before recovery')
        else:
            self.data = dict(schema=1, config=dict(keys='', dotnet='', cache=str(self.directory/'cache')),
                             library=[])

    def save(self):
        atomic_write(self.path, json.dumps(self.data, indent=2)+'\n')

    def entry(self, identity):
        return next((entry for entry in self.data['library'] if entry['id']==identity), None)
