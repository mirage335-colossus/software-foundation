#!/usr/bin/env python3
"""Verify the retained optional interpreter inputs without fetching or writing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

COMMIT = "28ecb9af6d2040e474a70f7cb7f43666740141fb"
ARCHIVE_SHA256 = "5ecbb8851bd9acb54a83be10f0536167cb0da13b007406578761672b0bd94b18"
XXHASH_LICENSE_SHA256 = "6ffedbc0f7878612d2b23589f1ff2ab15633e1df7963a5d9fc750ec5500c7e7a"
PATCH_FILE = "patches/0001-widen-slot-usage.patch"
PATCH_SHA256 = "865ddbe08d1c01cd9907fa3b60d8c68f75d2366f9eaba7282e5d2d128c6b9b90"
# Deliberately not a general patch interpreter: this reviewed recipe requires
# one exact complete upstream line per replacement, with no fuzz or fallback.
PATCH_REPLACEMENTS = {
    "source/m3_compile.c": (b"    if (M3_LIKELY(o->m3Slots[i_slot] < 0xFF)) {\n",
                            b"    if (M3_LIKELY(o->m3Slots[i_slot] < 0xFFFF)) {\n"),
    "source/m3_compile.h": (b"    u8         m3Slots[d_m3MaxFunctionSlots];\n",
                            b"    u16        m3Slots[d_m3MaxFunctionSlots];\n"),
}
METADATA = {"manifest.json", "SHA256SUMS", "README.md"}
SOURCE = Path(__file__).resolve().parents[1] / "third_party" / "wasm3"


def verify_source(directory: Path = SOURCE) -> dict:
    directory = Path(directory).absolute()
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("wasm3 source root must be a real directory")
    manifest_file = directory / "manifest.json"
    if manifest_file.is_symlink():
        raise ValueError("wasm3 manifest must be a regular file")
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    if (data.get("schema_version") != 1 or data.get("name") != "wasm3" or
            data.get("commit") != COMMIT or data.get("archive_sha256") != ARCHIVE_SHA256 or
            data.get("archive_url") != "https://codeload.github.com/wasm3/wasm3/tar.gz/" + COMMIT or
            data.get("patches") != [{"file": PATCH_FILE, "sha256": PATCH_SHA256}]):
        raise ValueError("unexpected wasm3 supplier identity")
    files = data.get("files")
    if not isinstance(files, dict) or not {"LICENSE", "XXHASH-LICENSE", "upstream.tar.gz"} <= files.keys():
        raise ValueError("incomplete wasm3 source and notice inventory")
    found = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in retained wasm3 inputs")
        if path.is_file():
            found.add(path.relative_to(directory).as_posix())
        elif not path.is_dir():
            raise ValueError("nonregular wasm3 input")
    if found != set(files) | METADATA:
        raise ValueError("unlisted or missing wasm3 supplier input")
    for name, expected in files.items():
        parsed = PurePosixPath(name)
        if parsed.is_absolute() or ".." in parsed.parts or str(parsed) != name or name in METADATA:
            raise ValueError("invalid wasm3 inventory path")
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("invalid wasm3 input digest")
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("changed wasm3 input: " + name)
    if files["upstream.tar.gz"] != ARCHIVE_SHA256:
        raise ValueError("changed wasm3 source recovery archive")
    if files["XXHASH-LICENSE"] != XXHASH_LICENSE_SHA256:
        raise ValueError("changed xxHash supplier notice")
    if files.get(PATCH_FILE) != PATCH_SHA256:
        raise ValueError("changed retained wasm3 patch")
    # Hashing a mutable manifest alone cannot establish an unchanged upstream
    # subset. Compare every compiled input to the independently pinned recovery
    # archive without extracting, following links or executing supplier code.
    expected_sources = set()
    prefix = "wasm3-" + COMMIT + "/"
    with tarfile.open(directory / "upstream.tar.gz", "r:gz") as archive:
        for member in archive:
            if member.name == prefix[:-1] and member.isdir():
                continue
            if not member.name.startswith(prefix):
                raise ValueError("unexpected wasm3 archive root")
            relative = member.name[len(prefix):]
            parsed = PurePosixPath(relative)
            include = (relative == "LICENSE" or
                       (len(parsed.parts) == 2 and parsed.parts[0] == "source" and
                        parsed.suffix in {".c", ".h"} and not parsed.name.startswith("m3_api_")))
            if not include:
                continue
            if not member.isfile() or relative in expected_sources:
                raise ValueError("invalid or duplicate supplier archive input")
            expected_sources.add(relative)
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("unreadable wasm3 archive input")
            expected = stream.read()
            if relative in PATCH_REPLACEMENTS:
                before, after = PATCH_REPLACEMENTS[relative]
                if expected.count(before) != 1:
                    raise ValueError("changed exact wasm3 patch context")
                expected = expected.replace(before, after, 1)
            if hashlib.sha256(expected).hexdigest() != files.get(relative):
                raise ValueError("source subset differs from pinned wasm3 archive: " + relative)
    if expected_sources | {"upstream.tar.gz", "XXHASH-LICENSE", PATCH_FILE} != set(files):
        raise ValueError("source subset is not the complete declared wasm3 core")
    checksums = "".join(value + "  " + name + "\n" for name, value in sorted(files.items()))
    if (directory / "SHA256SUMS").read_text(encoding="ascii") != checksums:
        raise ValueError("wasm3 checksum list differs from complete inventory")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args(argv)
    try:
        data = verify_source(args.source)
    except (OSError, ValueError, TypeError, tarfile.TarError) as error:
        parser.exit(1, "wasm3 source verification failed: " + str(error) + "\n")
    print("wasm3 source verified: " + data["commit"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
