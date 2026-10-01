#!/usr/bin/env python3
"""Deterministic archives and strict inventories shared by local supply tools."""
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=object_pairs)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def relative(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('invalid portable relative path')
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('invalid portable relative path: ' + name)
    for part in path.parts:
        if part.endswith(('.', ' ')) or any(ord(c) < 32 for c in part):
            raise ValueError('invalid portable path component')
    return path


def checked_file(root, name):
    path = Path(root).joinpath(*relative(name).parts)
    for parent in (path, *path.parents):
        if parent == Path(root).parent:
            break
        if parent.is_symlink():
            raise ValueError('links are not allowed in retained groups')
    if not path.is_file():
        raise ValueError('missing ordinary file: ' + name)
    return path


def file_inventory(root, exclude=()):
    root = Path(root)
    result = {}
    folded = set()
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        relative(name)
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise ValueError('unsupported retained entry: ' + name)
        if path.is_file() and name not in exclude:
            key = name.casefold()
            if key in folded:
                raise ValueError('ambiguous case-insensitive path: ' + name)
            folded.add(key)
            result[name] = digest(path)
    return result


def verify_inventory(root, files, exclude=()):
    if not isinstance(files, dict) or not files:
        raise ValueError('empty inventory')
    if any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in files.values()):
        raise ValueError('invalid checksum')
    actual = file_inventory(root, exclude)
    if actual != files:
        raise ValueError('retained file inventory or checksum mismatch')
    return actual


def archive_tree(root, output, epoch=0):
    """Ordinary files only. Stable order, metadata and gzip header."""
    root, output = Path(root).resolve(), Path(output).absolute()
    if root == output or root in output.parents or output.exists():
        raise ValueError('archive output must be new and outside input tree')
    files = file_inventory(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with temporary.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=epoch, compresslevel=1) as zipped:
            with tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for name in files:
                    path = root / name
                    info = tarfile.TarInfo(name)
                    info.size = path.stat().st_size
                    info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    info.mtime = epoch
                    with path.open('rb') as source:
                        archive.addfile(info, source)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return digest(output)


def extract(archive, destination, max_bytes=32 * 1024**3):
    """Validate the complete archive before creating any destination entry."""
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('extraction destination must not exist')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:*') as source:
        entries, names, total = [], set(), 0
        for member in source.getmembers():
            name = relative(member.name.rstrip('/') if member.isdir() else member.name)
            key = str(name).casefold()
            if key in names or not (member.isfile() or member.isdir()) or member.mode & 0o7000:
                raise ValueError('duplicate, linked, privileged or special archive entry')
            names.add(key)
            total += member.size
            if member.size < 0 or total > max_bytes:
                raise ValueError('archive exceeds extraction limit')
            entries.append((member, name))
        kinds = {str(name).casefold(): member.isdir() for member, name in entries}
        for _, name in entries:
            for parent in name.parents:
                if str(parent) != '.' and kinds.get(str(parent).casefold()) is False:
                    raise ValueError('archive file is also an entry parent')
        with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.extract-') as temporary:
            root = Path(temporary) / 'tree'
            root.mkdir()
            for member, name in entries:
                path = root.joinpath(*name.parts)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as data, path.open('xb') as output:
                        shutil.copyfileobj(data, output)
                    path.chmod(0o755 if member.mode & 0o111 else 0o644)
            root.rename(destination)
    return destination


def inspect_manifest_archive(path, manifest_name):
    """Verify complete inner file hashes without installing or running anything."""
    import io
    files, document, names, total, kinds = {}, None, set(), 0, {}
    with tarfile.open(path, 'r:*') as archive:
        for member in archive.getmembers():
            name = str(relative(member.name.rstrip('/') if member.isdir() else member.name))
            key = name.casefold()
            if key in names or not (member.isdir() or member.isfile()) or member.mode & 0o7000:
                raise ValueError('unsupported or duplicate retained archive entry')
            names.add(key)
            kinds[key] = member.isdir()
            total += member.size
            if total > 32 * 1024**3: raise ValueError('retained archive exceeds size limit')
            if member.isdir(): continue
            with archive.extractfile(member) as stream:
                value = hashlib.sha256()
                data = bytearray()
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    value.update(block)
                    if name == manifest_name:
                        data.extend(block)
                        if len(data) > 32 * 1024**2: raise ValueError('retained manifest exceeds size limit')
            if name == manifest_name:
                document = json.loads(bytes(data), object_pairs_hook=object_pairs)
                document_hash = value.hexdigest()
            else:
                files[name] = value.hexdigest()
    for name in kinds:
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.' and kinds.get(str(parent)) is False:
                raise ValueError('retained archive file is also an entry parent')
    if document is None or document.get('schema_version') != 1 or document.get('files') != files:
        raise ValueError('retained archive has a missing or incorrect complete manifest')
    return document, document_hash
