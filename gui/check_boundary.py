#!/usr/bin/env python3
"""Check literal include closure and concrete GUI/domain dependencies before compiling.

This is an architectural tripwire, not a C++ parser or a security boundary. Keep
executable conformance and public-interface review alongside it.
"""
from pathlib import Path
import argparse
import posixpath
import re
import sys

PUBLIC_GUI = {'gui/contract.hpp', 'gui/layout.hpp', 'gui/runtime.hpp'}
SOURCE_SUFFIXES = {'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx',
                   '.ipp', '.tpp', '.inc', '.ixx', '.cppm'}
# Keep string contents while removing comments, so includes and widget IDs remain
# visible and an explanatory comment cannot create a false dependency.
TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*', re.S)


def uncomment(source):
    return TOKENS.sub(lambda m: ('\n' * m[0].count('\n') if m[0].startswith(('/',)) else m[0]),
                      source.replace('\\\n', ''))


def include_entries(source):
    for directive, body in re.findall(r'^\s*#\s*(include|include_next)\b\s*([^\n]+)', uncomment(source), re.M):
        match = re.fullmatch(r'\s*(?:<([^>]+)>|"([^"]+)")\s*', body)
        if directive == 'include_next' or not match:
            yield None, False
        else:
            yield match[1] or match[2], match[2] is not None


def includes(source):
    return (name for name, _ in include_entries(source))


def shared_violations(source):
    result = []
    source = uncomment(source)
    for include in includes(source):
        if include is None:
            result.append('computed include hides the application dependency boundary')
            continue
        name = posixpath.normpath(include.replace('\\', '/'))
        gui = re.search(r'(?:^|/)(gui/.*)$', name)
        if gui and gui[1] not in PUBLIC_GUI:
            result.append(include)
        if any(part.lower() in ('fl', 'sdl', 'sdl2', 'backends', 'hosts', 'host')
               for part in name.split('/')) or re.search(r'(?:^|/)(?:windows\.h|SDL[^/]*)$', name, re.I):
            result.append(include)
    code = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', source)
    if re.search(r'\b(?:import\s+Rev|Rev\s*::|Fl_\w+|Fl\s*::|SDL_\w+|'
                 r'(?:Terminal|Framebuffer|Web|Memory|Interactive|Retained)Adapter|'
                 r'gui\s*::\s*(?:fltk|rev)\b)', code):
        result.append('concrete backend dependency')
    return result


def without_includes(source):
    return re.sub(r'^\s*#\s*include\b[^\n]*', '', source, flags=re.M)


def composition_root(root, path):
    return path.parent == root / 'hosts' and path.name.endswith('_main.cpp')


def sources(directory):
    return sorted(path for path in directory.rglob('*')
                  if path.is_file() and path.suffix in SOURCE_SUFFIXES)


def resolve_include(root, path, name, quoted=True):
    if name is None:
        return None
    candidates = ([path.parent / name] if quoted else []) + [root / name, root.parent / 'include' / name]
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            if root.parent != resolved and root.parent not in resolved.parents:
                raise ValueError('local include escapes project: ' + name)
            return resolved
    return None  # External public/standard headers are checked by name/compiler.


def analyze(root):
    root = Path(root).resolve()
    failures, dependencies, visited = [], set(), set()
    shared_paths = sources(root / 'shared')
    identities = {'entries.'}
    for path in shared_paths:
        identities.update(re.findall(r'"([A-Za-z][A-Za-z0-9_]*\.[A-Za-z0-9_.-]+)"', without_includes(uncomment(path.read_text()))))

    def walk(path, layer):
        key = (path, layer)
        if key in visited:
            return
        visited.add(key); dependencies.add(path)
        text = uncomment(path.read_text())
        issues = shared_violations(text) if layer == 'shared' else []
        if layer == 'host':
            literals = re.findall(r'"((?:\\.|[^"\\])*)"', without_includes(text))
            if any(value.startswith('entries.') or value in identities for value in literals):
                issues.append('application identity in host')
            if re.search(r'\bfoundation\s*::\s*(?:Store|Record|InsertResult|InsertError)\b', text):
                issues.append('application domain dependency in host')
            app_types = re.findall(r'\bfoundation\s*::\s*ui\s*::\s*(\w+)', text)
            if any(name != 'Application' or not composition_root(root, path) for name in app_types):
                issues.append('application implementation in host')
        for name, quoted in include_entries(text):
            if name is None:
                if layer == 'host': issues.append('computed include hides host dependency boundary')
                continue
            try:
                target = resolve_include(root, path, name, quoted)
            except ValueError as error:
                issues.append(str(error)); continue
            if target is None:
                continue
            if layer == 'shared' and any(directory in target.parents for directory in (root/'host', root/'hosts')):
                issues.append('host dependency through ' + name); continue
            if layer == 'host' and root.parent / 'include/foundation' in target.parents:
                issues.append('application domain header through ' + name); continue
            if layer == 'host' and root / 'shared' in target.parents:
                # Composition roots may name the public application type. A
                # helper cannot smuggle feature code into generic host services.
                if target != root/'shared/application.hpp' or not composition_root(root, path):
                    issues.append('shared application implementation through ' + name)
                dependencies.add(target)
                continue
            walk(target, layer)
        failures.extend(str(path) + ': ' + issue for issue in issues)

    for path in shared_paths:
        walk(path.resolve(), 'shared')
    for directory in ('host', 'hosts'):
        for path in sources(root / directory):
            walk(path.resolve(), 'host')
    return sorted(set(failures)), sorted(dependencies)


def tree_violations(root):
    return analyze(root)[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependencies', action='store_true')
    args = parser.parse_args()
    failures, dependencies = analyze(Path(__file__).resolve().parent)
    if args.dependencies:
        print(';'.join(str(path) for path in dependencies), end='')
    elif failures:
        print('\n'.join(failures), file=sys.stderr)
        sys.exit(1)
