#!/usr/bin/env python3
"""Bind a build to a complete portable source snapshot, including retained inputs."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from dependency_archive import archive_tree, digest, encoded, file_inventory, inspect_manifest_archive, read_json, relative, write_json

SUPPLEMENT_PREFIX = 'third_party/retained/gui/'


def selected_files(root):
    root = Path(root).resolve(strict=True)
    if (root / '.git').exists():
        result = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
        names = set(item.decode('utf-8') for item in result.split(b'\0') if item)
    elif (root / 'source.json').is_file():
        names = set(read_json(root / 'source.json')['files'])
        # Extra source files cannot silently disappear from a restored snapshot.
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
        ignored = lambda name: name == 'source.json' or name.split('/')[0] in ('build', '.agent-work', '.git') or '__pycache__' in Path(name).parts or name.endswith('.pyc')
        if names != {name for name in actual if not ignored(name)}:
            raise ValueError('restored source inventory changed')
    else:
        names = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    result = {}
    for name in sorted(names):
        if name == 'source.json' or name.split('/')[0] in ('build', '.git', '.agent-work') or '__pycache__' in Path(name).parts or name.endswith('.pyc'):
            continue
        path = root.joinpath(*relative(name).parts)
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('source snapshot contains an escaping or linked file')
        if not path.exists(): continue  # An intentional tracked deletion changes the identity.
        if not path.is_file(): raise ValueError('source snapshot needs an explicitly retained submodule tree')
        result[name] = path
    if not result: raise ValueError('source snapshot is empty')
    return result


def snapshot_paths(root, supplement=None):
    files = selected_files(root)
    if supplement:
        extra = selected_files(supplement)
        retained = {name: path for name, path in files.items() if name.startswith(SUPPLEMENT_PREFIX)}
        expected = {SUPPLEMENT_PREFIX + name: path for name, path in extra.items()}
        if retained and ({name: digest(path) for name, path in retained.items()} != {name: digest(path) for name, path in expected.items()}):
            raise ValueError('retained GUI source differs from explicit supplement')
        files.update(expected)
    return files


def describe_paths(paths):
    files = {name: digest(path) for name, path in sorted(paths.items())}
    executables = sorted(name for name, path in paths.items() if path.stat().st_mode & 0o111)
    identity = hashlib.sha256(encoded({'files': files, 'executables': executables})).hexdigest()
    return {'schema_version': 1, 'tree_sha256': identity, 'files': files, 'executables': executables}


def source_tree(root, supplement=None):
    return describe_paths(snapshot_paths(root, supplement))


def archive_source(root, output, supplement=None, epoch=0):
    output = Path(output).absolute()
    source_root = Path(root).resolve(strict=True)
    if source_root in output.parents and source_root / 'build' not in output.parents:
        raise ValueError('source archive output must be outside source inputs or under ignored build/')
    if output.exists(): raise ValueError('source archive destination must be new')
    paths = snapshot_paths(root, supplement)
    before = describe_paths(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.source-') as temporary:
        staged = Path(temporary) / 'source'
        staged.mkdir()
        for name, path in paths.items():
            destination = staged / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            destination.chmod(0o755 if name in before['executables'] else 0o644)
        copied = source_tree(staged)
        if copied != before or source_tree(root, supplement) != before:
            raise ValueError('source inputs changed while snapshotting')
        write_json(staged / 'source.json', before)
        archive_tree(staged, output, epoch)
    verify_source_archive(output)
    return before


def verify_source_archive(archive):
    data, _ = inspect_manifest_archive(archive, 'source.json')
    executables = []
    with tarfile.open(archive) as source:
        for member in source:
            if member.isfile() and member.name != 'source.json' and member.mode & 0o111:
                executables.append(member.name)
    if sorted(executables) != data.get('executables'):
        raise ValueError('source executable mode inventory mismatch')
    actual = hashlib.sha256(encoded({'files': data['files'], 'executables': sorted(executables)})).hexdigest()
    if actual != data.get('tree_sha256'):
        raise ValueError('source tree identity mismatch')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('digest', 'archive', 'verify'))
    parser.add_argument('--root', type=Path)
    parser.add_argument('--supplement', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--epoch', type=int, default=0)
    args = parser.parse_args()
    if args.action == 'verify':
        if not args.archive: parser.error('verify requires --archive')
        result = verify_source_archive(args.archive)
    else:
        if not args.root: parser.error('--root is required')
        if args.action == 'digest':
            print(source_tree(args.root, args.supplement)['tree_sha256'])
            return
        if not args.output: parser.error('archive requires --output')
        result = archive_source(args.root, args.output, args.supplement, args.epoch)
    print(encoded(result).decode(), end='')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error: raise SystemExit(str(error))
