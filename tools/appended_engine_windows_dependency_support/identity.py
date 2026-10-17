"""Pure, strictly tagged H1/H2 identity dispatch; never native authority.

Only the two fixed reviewed pure source releases below may be loaded. No native
helper, selected executable, SDK, archive or product is imported or inspected.
The optional actual_facts argument checks consistency, not its provenance.
"""

import hashlib
import os
from pathlib import Path
import stat
import types


HERE = Path(__file__).resolve().parent
H1_KIND = 'foundation-native-engine-windows-toolchain-identity-v1'
H2_KIND = 'foundation-native-engine-windows-toolchain-identity-v2'
_RELEASES = {
    1: ('../appended_engine_windows_dependency_proof.py', 35435,
        '6d30769578be43268cf9a6226054db79d0e16956e52085fb0f1c4618505b5747'),
    2: ('proof_h2.py', 19877,
        'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9'),
}
_MODULES = {}


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _module(version):
    if version not in _MODULES:
        relative, size, expected = _RELEASES[version]
        source = HERE / relative
        with source.open('rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size != size or size > 65536:
                raise ValueError('Fixed pure identity source type/size differs')
            raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        if (_identity(before) != _identity(after) or len(raw) != size or
                hashlib.sha256(raw).hexdigest() != expected):
            raise ValueError('Fixed pure identity source identity/SHA256 differs')
        module = types.ModuleType('_private_windows_identity_v' + str(version))
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _MODULES[version] = module
    return _MODULES[version]


def _version(value):
    if type(value) is not dict or type(value.get('schema_version')) is not int:
        raise ValueError('Exact Windows identity schema/kind required')
    pair = value['schema_version'], value.get('kind')
    if pair == (1, H1_KIND):
        return 1
    if pair == (2, H2_KIND):
        return 2
    raise ValueError('Unsupported or mixed Windows identity schema/kind')


def toolchain_identity(declared_facts):
    """Construct one supported declaration without changing its kind or roles."""
    return _module(_version(declared_facts)).toolchain_identity(declared_facts)


def validate_toolchain_identity(raw, expected_pin, actual_facts=None):
    """Check exact original bytes and dispatch without H2-to-H1 projection."""
    value = _module(1).parse_document(raw)
    version = _version(value)
    if actual_facts is not None and _version(actual_facts) != version:
        raise ValueError('Declared and actual identity versions differ')
    return _module(version).validate_toolchain_identity(raw, expected_pin, actual_facts)
