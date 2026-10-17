#!/usr/bin/env python3
"""Verify/export/restore retained engine inputs; never fetch, build or run them."""
import argparse
import ctypes
import errno
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile

import appended_engine_manifest as engine_manifest
from appended_engine_manifest import (MAX_MANIFEST, binary_contract,
    integrity_result, json_bytes, ordinary_root, path_name, read_document,
    plain_state, recipe_identity, sha256, source_contract, tree_inventory, verify_binding,
    verify_engine, verify_inputs, verify_sources)
from dependency_archive import archive_entries, digest, encoded

MAX_ARCHIVE_BYTES = 32 * 1024**3


class _OwnedTree:
    """Cleanup belongs to the original directory identity, never a reused name."""
    def __init__(self, parent, prefix):
        self.path = Path(tempfile.mkdtemp(dir=parent, prefix=prefix))
        state = plain_state(self.path.lstat(), directory=True)
        self.identity = state.st_dev, state.st_ino
        if engine_manifest.WINDOWS and not all(self.identity):
            raise ValueError('Windows staging identity unavailable; preserve tree: ' + str(self.path))
        self.published = False

    def __enter__(self):
        try:
            self.path.chmod(0o755)
        except OSError:
            self.__exit__(None, None, None)
            raise
        return self

    def publish(self, output):
        publish_fresh(self.path, output)
        self.published = True

    def __exit__(self, *_):
        if self.published:
            return False
        try:
            state = self.path.lstat()
        except FileNotFoundError:
            return False
        if (state.st_dev, state.st_ino) != self.identity:
            raise ValueError('engine staging identity changed; preserve it for inspection')
        ordinary_root(self.path)
        shutil.rmtree(self.path)
        return False


def group_names(recipe):
    sha256(recipe, 'engine recipe')
    prefix = 'engine-' + recipe
    return prefix + '-binary.tar.gz', prefix + '-sources.tar.gz', prefix + '-SHA256SUMS'


def group_snapshot(group, recipe):
    root = ordinary_root(group)
    names = group_names(recipe)
    if {path.name for path in root.iterdir()} != set(names):
        raise ValueError('engine group must contain exactly binary, source and checksum files')
    for name in names:
        path = root / name
        state = plain_state(path.lstat(), directory=False)
        if not engine_manifest.WINDOWS and stat.S_IMODE(state.st_mode) != 0o644:
            raise ValueError('engine group entries must be ordinary 0644 files')
    checksums = root / names[2]
    if checksums.stat().st_size > 1024:
        raise ValueError('engine checksum inventory exceeds size limit')
    values = {name: digest(root / name) for name in names}
    expected = ''.join(values[name] + '  ' + name + '\n' for name in names[:2]).encode('ascii')
    if checksums.read_bytes() != expected:
        raise ValueError('engine group checksum inventory differs from complete matched pair')
    return values


def inspect_archive(path, manifest):
    """Validate safe members, all bytes, explicit directories and normalized modes."""
    with tarfile.open(path, 'r:*') as archive:
        entries = archive_entries(archive, MAX_ARCHIVE_BYTES, 'portable')
        files, modes, directories, documents = {}, {}, [], {}
        for member, member_name in entries:
            name = path_name(str(member_name))
            mode = stat.S_IMODE(member.mode)
            if member.isdir():
                if mode != 0o755:
                    raise ValueError('engine archive directory mode must be 0755')
                directories.append(name)
                modes[name] = mode
                continue
            if mode not in (0o644, 0o755):
                raise ValueError('engine archive file mode must be 0644 or 0755')
            if name == manifest or (manifest == 'sources.json' and name == 'recipe.json'):
                if member.size > MAX_MANIFEST:
                    raise ValueError('engine archive manifest exceeds size limit')
                with archive.extractfile(member) as stream:
                    content = stream.read(MAX_MANIFEST + 1)
                documents[name] = (json_bytes(content), hashlib.sha256(content).hexdigest())
                value = documents[name][1]
            else:
                value_hash = hashlib.sha256()
                with archive.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        value_hash.update(block)
                value = value_hash.hexdigest()
            if name == manifest:
                if mode != 0o644:
                    raise ValueError('engine root manifest mode must be 0644')
            else:
                files[name] = value
                modes[name] = mode
    if manifest not in documents:
        raise ValueError('engine archive has no exact root manifest')
    data, manifest_hash = documents[manifest]
    if manifest == 'engine-sdk.json':
        binary_contract(data)
        recipe = None
    else:
        if 'recipe.json' not in documents:
            raise ValueError('engine source archive has no retained recipe')
        recipe, recipe_hash = documents['recipe.json']
        source_contract(data, recipe, recipe_hash)
    if (files != data['files'] or sorted(directories) != data['directories']
            or modes != data['modes']):
        raise ValueError('engine archive complete inventory or mode mismatch')
    return data, manifest_hash, recipe


def verify_group(group, recipe):
    root = ordinary_root(group)
    initial = group_snapshot(root, recipe)
    binary_name, source_name, _ = group_names(recipe)
    binary, binary_hash, _ = inspect_archive(root / binary_name, 'engine-sdk.json')
    source, source_hash, source_recipe = inspect_archive(root / source_name, 'sources.json')
    if binary['recipe_id'] != recipe:
        raise ValueError('engine group differs from selected recipe')
    verify_binding(binary, source, source_hash, source_recipe)
    if group_snapshot(root, recipe) != initial:
        raise ValueError('engine group changed during verification')
    return integrity_result(recipe_id=recipe, files=initial,
        binary_manifest_sha256=binary_hash, source_manifest_sha256=source_hash)


def new_destination(output, inputs=()):
    output = Path(output).absolute()
    parent = ordinary_root(output.parent)
    try:
        output.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError('engine output destination already exists')
    for root in inputs:
        root = ordinary_root(root)
        if output == root or root in output.parents:
            raise ValueError('engine output must be outside retained input trees')
    return parent / output.name


def publish_fresh(staged, output):
    """No-replace same-volume publication; unsupported hosts fail closed."""
    staged = ordinary_root(staged)
    output = new_destination(output)
    parent = ordinary_root(output.parent)
    before = plain_state(parent.lstat(), directory=True)
    identity = before.st_dev, before.st_ino
    if (staged.parent != parent or plain_state(staged.lstat(), directory=True).st_dev != before.st_dev
            or (engine_manifest.WINDOWS and not all(identity))):
        raise ValueError('engine publication requires an identified same-volume staging parent')
    ordinary_root(parent)
    after = plain_state(parent.lstat(), directory=True)
    if (after.st_dev, after.st_ino) != identity:
        raise ValueError('engine output parent changed before publication')
    if engine_manifest.WINDOWS:
        # Python's Windows rename uses no replacement/cross-volume-copy flags.
        # In particular an existing empty destination directory must survive.
        os.rename(staged, output)
        return
    if sys.platform.startswith('linux'):
        library = ctypes.CDLL(None, use_errno=True)
        rename = getattr(library, 'renameat2', None)
        if rename is None:
            raise ValueError('atomic no-replace engine publication is unavailable')
        rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint)
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(staged), -100, os.fsencode(output), 1) == 0:
            return
        error = ctypes.get_errno()
        if error in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP):
            raise ValueError('filesystem lacks atomic no-replace engine publication')
        raise OSError(error, os.strerror(error), str(output))
    raise ValueError('atomic no-replace engine publication is unsupported on this host')


def archive_tree(root, output, manifest):
    manifest_data, manifest_hash = read_document(root, manifest)
    if manifest == 'engine-sdk.json':
        binary_contract(manifest_data)
    elif manifest == 'sources.json':
        recipe, recipe_hash = read_document(root, 'recipe.json')
        source_contract(manifest_data, recipe, recipe_hash)
    else:
        raise ValueError('unknown engine archive manifest')
    initial = tree_inventory(root, manifest, logical_modes=manifest_data['modes'])
    # Include empty directories and their modes; the generic SDK archiver omits
    # them. Every supplied mode was checked before creating any archive bytes.
    with Path(output).open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=1) as zipped:
            with tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for name in sorted(set(initial['files']) | set(initial['directories']) | {manifest}):
                    info = tarfile.TarInfo(name)
                    info.mtime = 0
                    info.mode = initial['modes'].get(name, 0o644)
                    if name in initial['directories']:
                        info.type = tarfile.DIRTYPE
                        archive.addfile(info)
                    else:
                        path = Path(root) / name
                        info.size = path.stat().st_size
                        with path.open('rb') as source:
                            archive.addfile(info, source)
    Path(output).chmod(0o644)
    if (tree_inventory(root, manifest, logical_modes=manifest_data['modes']) != initial
            or read_document(root, manifest)[1] != manifest_hash):
        raise ValueError('retained engine input changed during archive creation')
    return manifest_data


def extract_owned(archive_path, destination):
    """Extract only into an exclusively owned, ordinary empty staging root."""
    destination = ordinary_root(destination)
    if any(destination.iterdir()):
        raise ValueError('engine extraction staging root must be empty')
    with tarfile.open(archive_path, 'r:*') as archive:
        entries = archive_entries(archive, MAX_ARCHIVE_BYTES, 'portable')
        for member, name in entries:
            path_name(str(name))
            if stat.S_IMODE(member.mode) not in ((0o755,) if member.isdir() else (0o644, 0o755)):
                raise ValueError('engine extraction mode is not normalized')
        for member, name in entries:
            if member.isdir():
                path = destination.joinpath(*name.parts)
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(0o755)
        for member, name in entries:
            if member.isfile():
                path = destination.joinpath(*name.parts)
                # Complete archive inspection already required explicit parents.
                ordinary_root(path.parent)
                with archive.extractfile(member) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output)
                path.chmod(stat.S_IMODE(member.mode))


def export_group(binary_root, source_root, output):
    binary_root, source_root = ordinary_root(binary_root), ordinary_root(source_root)
    if binary_root == source_root or binary_root in source_root.parents or source_root in binary_root.parents:
        raise ValueError('engine binary and source roots must be disjoint')
    output = new_destination(output, (binary_root, source_root))
    binary, binary_hash = verify_engine(binary_root)
    sources, source_hash, recipe = verify_sources(source_root)
    verify_binding(binary, sources, source_hash, recipe)
    identity = binary['recipe_id']
    names = group_names(identity)
    with _OwnedTree(output.parent, '.engine-export-') as staged:
        group = staged.path
        archive_tree(binary_root, group / names[0], 'engine-sdk.json')
        archive_tree(source_root, group / names[1], 'sources.json')
        with (group / names[2]).open('xb') as stream:
            stream.write(''.join(digest(group / name) + '  ' + name + '\n' for name in names[:2]).encode('ascii'))
        (group / names[2]).chmod(0o644)
        result = verify_group(group, identity)
        if verify_engine(binary_root)[1] != binary_hash or verify_sources(source_root)[1] != source_hash:
            raise ValueError('engine manifests changed before export publication')
        staged.publish(output)
    return result


def restore(group, recipe, output, *, sources=False):
    group = ordinary_root(group)
    output = new_destination(output, (group,))
    initial = verify_group(group, recipe)
    names = group_names(recipe)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.engine-restore-') as work:
        owned = Path(work) / 'group'
        owned.mkdir(mode=0o755)
        for name in names:
            with (group / name).open('rb') as source, (owned / name).open('xb') as destination:
                shutil.copyfileobj(source, destination)
            (owned / name).chmod(0o644)
        if verify_group(owned, recipe) != initial or group_snapshot(group, recipe) != initial['files']:
            raise ValueError('engine retained group changed during private snapshot')
        with _OwnedTree(output.parent, '.engine-restored-') as staged:
            tree = staged.path
            extract_owned(owned / names[1 if sources else 0], tree)
            if sources:
                _, actual_hash, _ = verify_sources(tree)
            else:
                _, actual_hash = verify_engine(tree, expected_recipe=recipe)
            if actual_hash != initial['source_manifest_sha256' if sources else 'binary_manifest_sha256']:
                raise ValueError('restored engine manifest differs from retained group')
            staged.publish(output)
    return integrity_result(recipe_id=recipe, manifest_sha256=actual_hash,
                            kind='sources' if sources else 'binary')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('recipe-id', 'verify-inputs', 'verify',
        'verify-sources', 'verify-group', 'export-group', 'restore', 'restore-sources'))
    parser.add_argument('--root', type=Path)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--group', type=Path)
    parser.add_argument('--recipe')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    allowed = {
        'recipe-id': ('root',), 'verify-inputs': ('root',),
        'verify': ('root', 'recipe', 'manifest_sha256'),
        'verify-sources': ('root', 'recipe', 'manifest_sha256'),
        'verify-group': ('group', 'recipe'),
        'export-group': ('binary', 'sources', 'output'),
        'restore': ('group', 'recipe', 'output'),
        'restore-sources': ('group', 'recipe', 'output'),
    }[args.action]
    if any(value is not None and name not in allowed for name, value in vars(args).items() if name != 'action'):
        parser.error('option does not apply to ' + args.action)
    def need(*names):
        if any(getattr(args, name) is None for name in names):
            parser.error(args.action + ' requires ' + ', '.join('--' + name for name in names))
    if args.action == 'recipe-id':
        need('root')
        result = integrity_result(recipe_id=recipe_identity(args.root))
    elif args.action == 'verify-inputs':
        need('root')
        _, identity, _ = verify_inputs(args.root)
        result = integrity_result(recipe_id=identity)
    elif args.action == 'verify':
        need('root')
        data, identity = verify_engine(args.root, expected_recipe=args.recipe,
                                       expected_manifest=args.manifest_sha256)
        result = integrity_result(recipe_id=data['recipe_id'], manifest_sha256=identity)
    elif args.action == 'verify-sources':
        need('root')
        data, identity, _ = verify_sources(args.root)
        if args.recipe is not None and sha256(args.recipe, 'recipe pin') != data['recipe_id']:
            raise ValueError('engine source recipe pin mismatch')
        if args.manifest_sha256 is not None and sha256(args.manifest_sha256, 'source manifest pin') != identity:
            raise ValueError('engine source manifest pin mismatch')
        result = integrity_result(recipe_id=data['recipe_id'], manifest_sha256=identity)
    elif args.action == 'verify-group':
        need('group', 'recipe')
        result = verify_group(args.group, args.recipe)
    elif args.action == 'export-group':
        need('binary', 'sources', 'output')
        result = export_group(args.binary, args.sources, args.output)
    else:
        need('group', 'recipe', 'output')
        result = restore(args.group, args.recipe, args.output, sources=args.action == 'restore-sources')
    print(encoded(result).decode(), end='')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, tarfile.TarError) as error:
        raise SystemExit(str(error))
