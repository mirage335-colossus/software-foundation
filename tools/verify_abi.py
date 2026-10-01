#!/usr/bin/env python3
"""Inspect ELF files without executing them; enforce the declared runtime floor."""
import argparse
from pathlib import Path
import re
import subprocess
from dependency_archive import digest, encoded, write_json

BOOKWORM = {'GLIBC': '2.36', 'GLIBCXX': '3.4.30', 'CXXABI': '1.3.13', 'GCC': '12.0.0'}
MACHINES = {'x86_64': 'Advanced Micro Devices X86-64', 'aarch64': 'AArch64'}
HOST_LIBRARIES = {'libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libdl.so.2', 'librt.so.1',
                  'libresolv.so.2', 'libutil.so.1', 'ld-linux-x86-64.so.2', 'ld-linux-aarch64.so.1'}


def version(value):
    if not re.fullmatch(r'\d+(?:\.\d+)*', value):
        raise ValueError('unsupported named ABI requirement: ' + value)
    return tuple(int(x) for x in value.split('.'))


def elf(path):
    with Path(path).open('rb') as stream:
        return stream.read(4) == b'\x7fELF'


def run(readelf, *args):
    return subprocess.check_output([str(readelf), '--wide', *map(str, args)], text=True,
                                   env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, stderr=subprocess.STDOUT)


def inspect(path, readelf='readelf'):
    path = Path(path)
    header = run(readelf, '--file-header', path)
    machine = re.search(r'^\s*Machine:\s*(.+)$', header, re.M)
    if not machine or not re.search(r'^\s*Class:\s*ELF64$', header, re.M):
        raise ValueError('expected a supported 64-bit ELF file')
    dynamic = run(readelf, '--dynamic', path)
    needed = re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', dynamic)
    rpath = re.findall(r'\(RPATH\).*?\[([^\]]*)\]', dynamic)
    runpath = re.findall(r'\(RUNPATH\).*?\[([^\]]*)\]', dynamic)
    headers = run(readelf, '--program-headers', path)
    loader = re.findall(r'Requesting program interpreter:\s*([^\]]+)', headers)
    info = run(readelf, '--version-info', path)
    requirements = {}
    # Only dependency imports matter; version definitions in an exported library
    # describe its capabilities rather than its own runtime requirements.
    needs = info.split('Version needs section', 1)
    if len(needs) == 2:
        for family, value in re.findall(r'Name:\s*(GLIBCXX|GLIBC|CXXABI|GCC)_([^\s]+)', needs[1]):
            parsed = version(value)
            if parsed > version(requirements.get(family, '0')):
                requirements[family] = value
    return {'sha256': digest(path), 'machine': machine.group(1).strip(), 'needed': sorted(needed),
            'rpaths': rpath + runpath, 'rpath': rpath, 'runpath': runpath,
            'loader': loader, 'requirements': requirements}


def resolve_closure(root, results):
    """Prove private edges using contained loader paths, without environment help."""
    base = root if root.is_dir() else root.parent
    paths = {name: base / name for name in results}
    by_path = {path.resolve(): name for name, path in paths.items()}
    for name in results:
        if Path(name).name in HOST_LIBRARIES:
            raise ValueError('package must not bundle the target libc or loader: ' + name)
    reached = set()
    resolutions = {}

    def directories(name, key):
        return tuple(dict.fromkeys((paths[name].parent / item.removeprefix('$ORIGIN').lstrip('/')).resolve()
                                   for value in results[name][key] for item in value.split(':')))

    def visit(name, inherited, active):
        context = (name, inherited)
        if context in active:
            return
        active = active | {context}
        reached.add(name)
        entry = results[name]
        own = directories(name, 'rpath') if not entry['runpath'] else ()
        chain = tuple(dict.fromkeys(own + inherited))
        # RUNPATH applies to direct edges only. RPATH may be inherited by
        # descendants; a requesting object's RUNPATH overrides that search.
        search = directories(name, 'runpath') if entry['runpath'] else chain
        for needed in entry['needed']:
            if not needed or '/' in needed or '\\' in needed:
                raise ValueError('target dependency must use a bare library name')
            if needed in HOST_LIBRARIES:
                continue
            candidates = set()
            for directory in search:
                provider = directory / needed
                if provider.exists():
                    resolved = provider.resolve(strict=True)
                    if resolved not in by_path:
                        raise ValueError('runtime provider is outside the inspected ELF inventory: ' + needed)
                    candidates.add(by_path[resolved])
            if not candidates:
                raise ValueError('package runtime closure is incomplete: loader cannot resolve ' + needed + ' from ' + name)
            if len(candidates) != 1:
                raise ValueError('ambiguous runtime loader providers: ' + needed + ' from ' + name)
            provider = next(iter(candidates))
            previous = resolutions.setdefault((name, needed), provider)
            if previous != provider:
                raise ValueError('runtime provider changes between executable contexts: ' + needed)
            visit(provider, chain, active)

    for name, entry in results.items():
        if entry['loader']:
            visit(name, (), set())
    # A library outside an executable's closure needs its own usable paths;
    # dynamically selected modules cannot silently borrow an unknown context.
    for name in results:
        if name not in reached:
            visit(name, (), set())
    return [{'from': name, 'needed': needed, 'provider': provider}
            for (name, needed), provider in sorted(resolutions.items())]


def audit(root, processor='x86_64', ceilings=None, readelf='readelf', host=False, runtime_resolution=True):
    root = Path(root).resolve(strict=True)
    ceilings = BOOKWORM if ceilings is None else ceilings
    if processor not in MACHINES:
        raise ValueError('unsupported processor')
    results = {}
    for path in sorted(root.rglob('*')) if root.is_dir() else [root]:
        if path.is_symlink():
            if root.is_dir() and root not in path.resolve(strict=True).parents:
                raise ValueError('runtime path escapes the inspected tree')
            continue
        if not path.is_file() or not elf(path):
            continue
        entry = inspect(path, readelf)
        notes = run(readelf, '--notes', path)
        if not host and re.search(r'x86 ISA needed:.*x86-64-v[234]', notes):
            raise ValueError('ELF requires instructions above the generic x86_64 baseline')
        if entry['machine'] != MACHINES[processor]:
            raise ValueError('wrong ELF architecture: ' + str(path))
        for family, required in entry['requirements'].items():
            if family not in ceilings or version(required) > version(ceilings[family]):
                raise ValueError('runtime requirement above ceiling: ' + family + '_' + required + ': ' + str(path))
        if not host:
            allowed_loader = '/lib64/ld-linux-x86-64.so.2' if processor == 'x86_64' else '/lib/ld-linux-aarch64.so.1'
            if any(item != allowed_loader for item in entry['loader']):
                raise ValueError('unexpected target loader path')
            for rpath in entry['rpaths']:
                for item in rpath.split(':'):
                    if not item or not (item == '$ORIGIN' or item.startswith('$ORIGIN/')):
                        raise ValueError('target runtime search path must be relative to its executable')
                    resolved = (path.parent / item.removeprefix('$ORIGIN').lstrip('/')).resolve()
                    if root.is_dir() and resolved != root and root not in resolved.parents:
                        raise ValueError('target runtime search path escapes package')
        name = path.relative_to(root).as_posix() if root.is_dir() else path.name
        results[name] = entry
    if not results:
        raise ValueError('no ELF files inspected')
    resolution = []
    if not host:
        provided = {Path(name).name for name in results}
        for entry in results.values():
            absent = set(entry['needed']) - provided - HOST_LIBRARIES
            if absent:
                raise ValueError('package runtime closure is incomplete: ' + ', '.join(sorted(absent)))
        if runtime_resolution:
            resolution = resolve_closure(root, results)
    return {'schema_version': 1, 'processor': processor, 'ceilings': ceilings,
            'scope': 'host' if host else ('target' if runtime_resolution else 'staged-requirements'),
            'runtime_resolution': 'passed' if not host and runtime_resolution else 'not_checked',
            'resolution': resolution, 'files': results, 'status': 'passed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--processor', choices=tuple(MACHINES), default='x86_64')
    parser.add_argument('--readelf', default='readelf')
    parser.add_argument('--host', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): args.output.unlink()
    write_json(args.output, audit(args.root, args.processor, readelf=args.readelf, host=args.host))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error: raise SystemExit(str(error))
