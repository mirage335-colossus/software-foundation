#!/usr/bin/env python3
"""Reject concrete GUI dependencies in shared application code before compilation."""
from pathlib import Path
import re
import sys


def shared_violations(source):
    result=[]
    for include in re.findall(r'#\s*include\s*[<"]([^>"]+)',source):
        if include.startswith('gui/') and include not in {'gui/contract.hpp','gui/layout.hpp','gui/runtime.hpp'}:
            result.append(include)
        if include.startswith(('FL/','SDL','windows.h','backends/','hosts/','host/')):
            result.append(include)
    if re.search(r'\b(?:import\s+Rev|TerminalAdapter|FramebufferAdapter|WebAdapter)\b',source):
        result.append('concrete backend dependency')
    return result


if __name__=='__main__':
    root=Path(__file__).resolve().parent
    failures=[]
    for path in (root/'shared').glob('*pp'):
        failures.extend(str(path)+': '+entry for entry in shared_violations(path.read_text()))
    for directory in ('hosts','host'):
        for path in (root/directory).glob('*pp'):
            if '"entries.' in path.read_text():failures.append(str(path)+': application identity in host')
    if failures:print('\n'.join(failures),file=sys.stderr);sys.exit(1)
