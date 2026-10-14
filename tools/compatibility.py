"""Classify shared compatibility gaps without exporting raw runtime logs."""
from collections import defaultdict
import re


def classify(result,log):
    if result.get('outcome')=='rendering_started':return dict(category='passed',key='rendering_started')
    patterns=[
        ('ipc-command',r'Unsupported IPC command: ([A-Za-z0-9_:-]{1,8}:\d+)'),
        ('ipc-service',r'Unsupported IPC service: ([A-Za-z0-9_:-]{1,8})'),
        ('service',r'unsupported import ([A-Za-z_][A-Za-z0-9_.$]{0,250})'),
        ('service',r'UNIMPL ([A-Za-z_][A-Za-z0-9_.$]{0,250})'),
        ('syscall',r'(?:unimplemented|unsupported|unknown) (?:SVC|svc)[^\n]*?(0x[0-9a-fA-F]+)'),
        ('prerequisite',r'Missing local key: ([a-z_0-9]+)'),
        ('shader-stage',r'Unsupported (?:runtime )?shader stage: (\d+)'),
        ('shader-metadata',r'(Missing (?:or invalid )?compute (?:workgroup|shared-memory|code offset) metadata)'),
        ('shader-binding',r'(?:unmapped NVN texture handle|Unsupported storage buffer address table|resource category) ([A-Za-z0-9_]+)'),
        ('cpu-rewrite',r'(?:unsupported|Unsupported) instruction[^\n]*?(0x[0-9a-fA-F]+)'),
        ('native-fault',r'native fault signal=\d+ address=\S+ pc=((?:main|sdk|subsdk\d|host)\+(?:0x[0-9a-fA-F]+|0))'),
        ('guest-abort',r'Break#\d+ reason=\S+ Result=(0x[0-9a-fA-F]+)'),
    ]
    for category,pattern in patterns:
        match=re.search(pattern,log)
        if match:return dict(category=category,key=match[1])
    if result.get('last_status',{}).get('shader_failures',0) or 'shader compilation failed' in log.lower():
        return dict(category='shader-translation',key='translation_failed')
    return dict(category='startup',key=result.get('outcome','unknown'))


def group(results):
    groups=defaultdict(list)
    for result in results:
        gap=result['classification']
        if gap['category']!='passed':groups[(gap['category'],gap['key'])].append(result['id'])
    return [dict(category=c,key=k,cases=ids) for (c,k),ids in sorted(groups.items(),key=lambda item:(-len(item[1]),item[0]))]
