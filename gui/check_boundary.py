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


SOURCE_SUFFIXES = {'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx',
                   '.ipp', '.tpp', '.inc', '.ixx', '.cppm'}


def sources(directory):
    """Keep nested feature/helper files inside the same architectural boundary."""
    return sorted(path for path in directory.rglob('*')
                  if path.is_file() and path.suffix in SOURCE_SUFFIXES)


def tree_violations(root):
    root=Path(root)
    failures=[]
    for path in sources(root/'shared'):
        failures.extend(str(path)+': '+entry for entry in shared_violations(path.read_text()))
    for directory in ('hosts','host'):
        for path in sources(root/directory):
            if '"entries.' in path.read_text():failures.append(str(path)+': application identity in host')
    return failures


if __name__=='__main__':
    failures=tree_violations(Path(__file__).resolve().parent)
    if failures:print('\n'.join(failures),file=sys.stderr);sys.exit(1)
