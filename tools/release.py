#!/usr/bin/env python3
"""Assemble and recover complete local releases. Never publishes remotely."""
import argparse
from pathlib import Path
import re
import shutil
import tempfile
import artifact
from dependency_archive import digest, encoded, file_inventory, read_json, relative, verify_inventory, write_json
from dependency_store import copy_group, verify_group
from source_identity import verify_source_archive


def safe_name(name):
    if len(relative(name).parts) != 1:
        raise ValueError('release asset names must be simple filenames')
    return name


def dependency_recipes(entry):
    recipes = entry.get('dependency_recipes', [entry['sdk_recipe']])
    if not recipes or len(recipes) != len(set(recipes)) or entry['sdk_recipe'] not in recipes:
        raise ValueError('artifact dependency recipes must be complete, unique and include its primary SDK')
    if any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in recipes):
        raise ValueError('invalid dependency recipe identity')
    return sorted(recipes)


def validate_package(archive, entry, source_identity):
    with tempfile.TemporaryDirectory(prefix='release-inspect-') as temporary:
        root = Path(temporary)
        artifact.inspect_archive(archive, root)
        records = list(root.rglob('build-info.txt'))
        if len(records) != 1:
            raise ValueError('application archive requires one build information record')
        info = {}
        for line in records[0].read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                if key in info: raise ValueError('duplicate packaged build information field')
                info[key] = value
        if info.get('sdk_recipe_id') != entry['sdk_recipe']:
            raise ValueError('packaged SDK recipe differs from release specification')
        if info.get('source_tree_sha256') != source_identity:
            raise ValueError('packaged source tree differs from retained source archive')
        if info.get('target') != entry['target']:
            raise ValueError('packaged target differs from release specification')
        backends = [value for value in info.get('gui_backends', '').split(',') if value]
        if len(backends) != len(set(backends)) or sorted(backends) != sorted(entry.get('backends', [])):
            raise ValueError('packaged backends differ from release specification')
        declared = info.get('dependency_recipes', '').split(',')
        if sorted(declared) != dependency_recipes(entry):
            raise ValueError('packaged dependency list differs from release specification')


def verify_release(directory):
    directory = Path(directory).resolve(strict=True)
    metadata = read_json(directory / 'release.json')
    if metadata.get('schema_version') != 1 or metadata.get('qualification') != 'candidate':
        raise ValueError('unsupported local release manifest')
    verify_inventory(directory, metadata['files'], exclude=('release.json',))
    source = metadata['source']
    safe_name(source['archive'])
    if digest(directory / source['archive']) != source['sha256']:
        raise ValueError('release source identity mismatch')
    source_manifest = verify_source_archive(directory / source['archive'])
    if source.get('tree_sha256') != source_manifest['tree_sha256']:
        raise ValueError('release source tree binding mismatch')
    wanted = set()
    for entry in metadata['artifacts']:
        for name in ('archive', 'manifest'):
            safe_name(entry[name])
        if digest(directory / entry['archive']) != entry['sha256'] or digest(directory / entry['manifest']) != entry['manifest_sha256']:
            raise ValueError('release application identity mismatch')
        if artifact.describe(directory / entry['archive']) != read_json(directory / entry['manifest']):
            raise ValueError('release application archive inventory mismatch')
        validate_package(directory / entry['archive'], entry, source_manifest['tree_sha256'])
        wanted.update(dependency_recipes(entry))
    observed = set()
    for entry in metadata['dependencies']:
        recipe = entry['recipe_id']
        if recipe in observed: raise ValueError('duplicate dependency recipe')
        observed.add(recipe)
        if verify_group(directory / 'dependencies' / recipe, recipe) != entry['files']:
            raise ValueError('release dependency identity mismatch')
    if not wanted or wanted != observed:
        raise ValueError('release must retain exactly every required SDK group')
    if not metadata['required_scopes'] or len(metadata['required_scopes']) != len(set(metadata['required_scopes'])):
        raise ValueError('release scopes must be nonempty and unique')
    referenced = {source['archive']}
    for entry in metadata['artifacts']:
        referenced.update((entry['archive'], entry['manifest']))
    for entry in metadata['dependencies']:
        referenced.update('dependencies/' + entry['recipe_id'] + '/' + name for name in entry['files'])
    if set(metadata['files']) != referenced:
        raise ValueError('unexpected or omitted release asset')
    return metadata


def assemble(spec_path, base, output):
    spec_path, output = Path(spec_path).resolve(), Path(output).absolute()
    spec = read_json(spec_path)
    if spec.get('schema_version') != 1 or not spec.get('artifacts'):
        raise ValueError('release spec must list application archives')
    if output.exists() or output.is_symlink():
        raise ValueError('release output must be new')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.release-') as temporary:
        staged = Path(temporary) / 'release'
        staged.mkdir()
        seen = {'release.json', 'dependencies'}
        def retain(name):
            path = Path(name)
            if not path.is_absolute(): path = spec_path.parent / path
            path = path.resolve(strict=True)
            filename = safe_name(path.name)
            if filename in seen: raise ValueError('duplicate release asset filename')
            seen.add(filename)
            shutil.copyfile(path, staged / filename)
            if digest(path) != digest(staged / filename): raise ValueError('input changed during release assembly')
            return filename
        source = retain(spec['source']['path'])
        source_hash = digest(staged / source)
        if source_hash != spec['source']['sha256']:
            raise ValueError('source archive differs from frozen specification')
        source_manifest = verify_source_archive(staged / source)
        metadata = {'schema_version': 1, 'qualification': 'candidate',
                    'source': {'archive': source, 'sha256': source_hash, 'tree_sha256': source_manifest['tree_sha256']}, 'artifacts': [],
                    'dependencies': [], 'required_scopes': spec['required_scopes']}
        recipes = set()
        for entry in spec['artifacts']:
            archive = retain(entry['path'])
            manifest = retain(entry['manifest_path'])
            if artifact.describe(staged / archive) != read_json(staged / manifest):
                raise ValueError('application archive does not match its manifest')
            if digest(staged / archive) != entry['sha256']:
                raise ValueError('application archive differs from frozen specification')
            recipe = entry['sdk_recipe']
            validate_package(staged / archive, entry, source_manifest['tree_sha256'])
            recipes.update(dependency_recipes(entry))
            metadata['artifacts'].append({'archive': archive, 'sha256': digest(staged / archive),
                'manifest': manifest, 'manifest_sha256': digest(staged / manifest),
                'target': entry['target'], 'backends': entry.get('backends', []), 'sdk_recipe': recipe,
                'dependency_recipes': dependency_recipes(entry)})
        for recipe in sorted(recipes):
            files = copy_group(Path(base) / recipe, staged / 'dependencies' / recipe, recipe)
            metadata['dependencies'].append({'recipe_id': recipe, 'files': files})
        metadata['files'] = file_inventory(staged)
        write_json(staged / 'release.json', metadata)
        verify_release(staged)
        staged.rename(output)
    return metadata


def recover(directory, output):
    directory, output = Path(directory).resolve(strict=True), Path(output).absolute()
    data = verify_release(directory)
    if output.exists() or output.is_symlink(): raise ValueError('recovery output must be new')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.recover-') as temporary:
        staged = Path(temporary) / 'recovered'
        staged.mkdir()
        shutil.copyfile(directory / data['source']['archive'], staged / data['source']['archive'])
        for entry in data['dependencies']:
            recipe = entry['recipe_id']
            copy_group(directory / 'dependencies' / recipe, staged / 'dependencies' / recipe, recipe)
        write_json(staged / 'recovery.json', {'release_sha256': digest(directory / 'release.json'),
                   'source': data['source'], 'dependencies': data['dependencies']})
        staged.rename(output)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    create = sub.add_parser('assemble')
    create.add_argument('--spec', type=Path, required=True)
    create.add_argument('--base', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    for action in ('verify', 'recover'):
        command = sub.add_parser(action)
        command.add_argument('directory', type=Path)
        if action == 'recover': command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'assemble': result = assemble(args.spec, args.base, args.output)
    elif args.action == 'verify': result = verify_release(args.directory)
    else: result = recover(args.directory, args.output)
    print(encoded(result).decode(), end='')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError) as error: raise SystemExit(str(error))
