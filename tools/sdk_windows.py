#!/usr/bin/env python3
"""Produce and restore exact Windows dependency groups; never bundle MSVC."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from dependency_archive import digest, encoded, extract, file_inventory, read_json, verify_inventory, write_json
from dependency_store import names, verify_group
from sdk import export_group, materialize

TOOLS = ('sdk_windows.py', 'sdk.py', 'sdk_manifest.py', 'dependency_store.py', 'dependency_archive.py', 'verify_abi.py')


def recipe_identity(recipe):
    recipe = Path(recipe)
    inputs = {'windows-base.json': digest(recipe), 'windows-toolchain.json': digest(recipe.parent / 'windows-toolchain.json')}
    inputs.update({'tools/' + name: digest(Path(__file__).parent / name) for name in TOOLS})
    return hashlib.sha256(encoded(inputs)).hexdigest()


def check_provenance(recipe, provenance):
    for key in ('vcpkg_ref', 'triplet', 'ports', 'toolset', 'configurations', 'crt_linkage', 'library_linkage', 'lto'):
        if provenance.get(key) != recipe[key]: raise ValueError('Windows producer provenance differs: ' + key)
    if recipe['toolset'] != 'v143' or recipe['crt_linkage'] != 'static' or recipe['library_linkage'] != 'static' or recipe['lto']:
        raise ValueError('unsupported Windows dependency ABI policy')
    if not re.fullmatch(r'14\.[34]\d\.\d+(?:\.\d+)?', provenance.get('linker_version', '')):
        raise ValueError('record the exact producing v143 linker version')
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', provenance.get('windows_sdk', '')):
        raise ValueError('record the exact producing Windows SDK version')


def assemble(recipe_path, export_root, source_root, provenance_path, output):
    recipe_path, output = Path(recipe_path), Path(output).absolute()
    recipe = read_json(recipe_path)
    provenance = read_json(provenance_path)
    check_provenance(recipe, provenance)
    identity = recipe_identity(recipe_path)
    verify_inventory(export_root, provenance['files'])
    verify_inventory(source_root, provenance['source_files'])
    if output.exists(): raise ValueError('dependency group destination must be new')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work = Path(temporary)
        binary = work / 'binary'
        binary.mkdir()
        materialize(export_root, binary / 'prefix')
        sources = work / 'sources'
        materialize(source_root, sources)
        (sources / 'recipe').mkdir()
        shutil.copyfile(recipe_path, sources / 'recipe/windows-base.json')
        shutil.copyfile(recipe_path.parent / 'windows-toolchain.json', sources / 'recipe/windows-toolchain.json')
        (sources / 'tools').mkdir()
        for name in TOOLS: shutil.copyfile(Path(__file__).parent / name, sources / 'tools' / name)
        write_json(sources / 'provenance.json', provenance)
        write_json(sources / 'sources.json', {'schema_version': 1, 'recipe_id': identity, 'files': file_inventory(sources)})
        metadata = {'schema_version': 1, 'recipe_id': identity, 'kind': 'windows-dependencies',
                    'target': {'system': 'Windows', 'processor': 'x86_64', 'triple': 'x64-windows-static', 'sysroot': 'prefix'},
                    'external_toolchain': {'toolset': 'v143', 'minimum_linker': provenance['linker_version'], 'windows_sdk': provenance['windows_sdk']},
                    'sources_sha256': digest(sources / 'sources.json'), 'licenses': ['prefix'],
                    'relocation': 'relative-paths', 'provenance': provenance, 'files': file_inventory(binary)}
        write_json(binary / 'sdk.json', metadata)
        return export_group(binary, sources, output)


def empty_base(recipe_path, provenance_path, output):
    """Prepare the complete no-external-library base used by the native example."""
    recipe = read_json(recipe_path)
    if recipe['ports']: raise ValueError('nonempty dependency recipe requires reviewed export and source trees')
    provenance = read_json(provenance_path)
    check_provenance(recipe, provenance)
    output = Path(output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work = Path(temporary)
        export = work / 'export'
        source = work / 'source'
        export.mkdir(); source.mkdir()
        (export / 'README.txt').write_text('No third-party runtime libraries are required by this native core.\nMicrosoft compiler and Windows SDK are separate host prerequisites.\n')
        (source / 'README.txt').write_text('This dependency recipe selects no upstream ports.\n')
        provenance['files'] = file_inventory(export)
        provenance['source_files'] = file_inventory(source)
        write_json(work / 'provenance.json', provenance)
        return assemble(recipe_path, export, source, work / 'provenance.json', output)


def install(group, recipe, output, linker_version):
    verify_group(group, recipe)
    output = Path(output).absolute()
    if output.exists(): raise ValueError('dependency installation destination must be new')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        tree = Path(temporary) / 'base'
        extract(Path(group) / names(recipe)[0], tree)
        metadata = read_json(tree / 'sdk.json')
        if metadata.get('kind') != 'windows-dependencies': raise ValueError('not a Windows dependency base')
        def version(text):
            if not re.fullmatch(r'\d+(?:\.\d+)+', text): raise ValueError('invalid linker version')
            return tuple(map(int, text.split('.')))
        if version(linker_version) < version(metadata['external_toolchain']['minimum_linker']):
            raise ValueError('consuming linker is older than the producing linker')
        verify_inventory(tree, metadata['files'], exclude=('sdk.json',))
        tree.rename(output)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('recipe-id', 'empty-base', 'assemble', 'install'))
    parser.add_argument('--recipe-file', type=Path, default=Path(__file__).resolve().parents[1] / 'third_party/sdk/windows-base.json')
    parser.add_argument('--provenance', type=Path)
    parser.add_argument('--export-root', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--group', type=Path)
    parser.add_argument('--recipe')
    parser.add_argument('--linker-version')
    args = parser.parse_args()
    if args.action == 'recipe-id': result = {'recipe_id': recipe_identity(args.recipe_file)}
    elif args.action == 'empty-base':
        if not args.provenance or not args.output: parser.error('empty-base requires --provenance and --output')
        result = empty_base(args.recipe_file, args.provenance, args.output)
    elif args.action == 'assemble':
        if not all((args.export_root, args.source_root, args.provenance, args.output)): parser.error('assemble requires --export-root --source-root --provenance --output')
        result = assemble(args.recipe_file, args.export_root, args.source_root, args.provenance, args.output)
    else:
        if not all((args.group, args.recipe, args.output, args.linker_version)): parser.error('install requires --group --recipe --output --linker-version')
        result = install(args.group, args.recipe, args.output, args.linker_version)
    print(encoded(result).decode(), end='')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError) as error: raise SystemExit(str(error))
