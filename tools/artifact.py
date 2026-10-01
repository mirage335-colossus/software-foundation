#!/usr/bin/env python3
"""Inventory and verify a locally produced package, then test it after relocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile

MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000


def member_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or not path.parts:
        raise ValueError("unsafe archive path: " + name)
    return path


def inspect_archive(archive, destination=None):
    """Only regular files/directories, bounded sizes and unique normalized paths."""
    inventory = {}
    seen = set()
    total = 0

    def consume(name, size, directory, mode, stream):
        nonlocal total
        if mode & 0o7000:
            raise ValueError("unexpected privileged archive permissions")
        path = member_path(name)
        canonical = str(path).casefold()
        if canonical in seen:
            raise ValueError("duplicate archive path")
        seen.add(canonical)
        total += size
        if total > MAX_BYTES or len(seen) > MAX_FILES:
            raise ValueError("archive exceeds example limits")
        target = destination.joinpath(*path.parts) if destination else None
        if directory:
            if target:
                target.mkdir(parents=True, exist_ok=True)
            return
        data = stream.read(MAX_BYTES + 1)
        if len(data) != size:
            raise ValueError("archive member size mismatch")
        inventory[str(path)] = {"size": size, "sha256": hashlib.sha256(data).hexdigest()}
        if target:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as out:
                out.write(data)
            target.chmod(0o755 if mode & 0o111 else 0o644)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    raise ValueError("unsupported archive entry")
                with bundle.open(item) as stream:
                    consume(item.filename, item.file_size, item.is_dir(), mode, stream)
    else:
        with tarfile.open(archive, "r:*") as bundle:
            for item in bundle:
                if not (item.isfile() or item.isdir()):
                    raise ValueError("unsupported archive entry")
                stream = bundle.extractfile(item) if item.isfile() else None
                consume(item.name, item.size, item.isdir(), item.mode, stream)
                if stream:
                    stream.close()
    if not inventory:
        raise ValueError("empty archive")
    return inventory


def describe(archive):
    return {"schema_version": 1, "archive": archive.name,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "files": inspect_archive(archive)}


def verify(archive, manifest):
    expected = json.loads(manifest.read_text())
    if describe(archive) != expected:
        raise ValueError("archive identity or member inventory mismatch")
    with tempfile.TemporaryDirectory(prefix="foundation package ") as temp:
        prefix = Path(temp) / "relocated prefix"
        prefix.mkdir()
        inspect_archive(archive, prefix)
        name = "foundation-cli.exe" if os.name == "nt" else "foundation-cli"
        candidates = list(prefix.rglob(name))
        if len(candidates) != 1 or candidates[0].parent.name != "bin":
            raise ValueError("expected exactly one packaged CLI")
        executable = candidates[0]
        clean = {key: value for key, value in os.environ.items() if key not in
                 ("LD_LIBRARY_PATH", "LD_PRELOAD", "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES")}
        if os.name == "nt":
            system_root = Path(os.environ["SystemRoot"])
            clean["PATH"] = os.pathsep.join([str(executable.parent), str(system_root / "System32"), str(system_root)])
        result = subprocess.run([str(executable), "--version"], cwd=prefix, env=clean,
                                check=True, text=True, capture_output=True)
        if result.stdout != "software-foundation 0.1.0\n":
            raise ValueError("unexpected packaged version")
        subprocess.run([str(executable), "--self-check"], cwd=prefix, env=clean, check=True)
        # Use only the extracted SDK export to compile a separate consumer.
        source = Path(__file__).resolve().parents[1] / "examples/consumer"
        consumer = Path(temp) / "consumer source"
        shutil.copytree(source, consumer)
        build = Path(temp) / "consumer build"
        configs = list(prefix.rglob("FoundationConfig.cmake"))
        if len(configs) != 1:
            raise ValueError("packaged SDK export missing or ambiguous")
        subprocess.run(["cmake", "-S", str(consumer), "-B", str(build), "-G", "Ninja",
                        "-DCMAKE_BUILD_TYPE=Release", "-DFoundation_DIR=" + str(configs[0].parent),
                        "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF", "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF"], check=True)
        subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True)
        subprocess.run([str(build / ("consumer.exe" if os.name == "nt" else "consumer"))], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("archive", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.archive.resolve() == args.manifest.resolve():
        raise ValueError("manifest must not overwrite its archive")
    if args.action == "create":
        args.manifest.write_text(json.dumps(describe(args.archive), indent=2) + "\n")
    else:
        verify(args.archive, args.manifest)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as error:
        print("artifact: " + str(error), file=sys.stderr)
        sys.exit(1)
