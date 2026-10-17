"""Explicit D2/D3 dependency dispatch on an isolated frozen pure W2 module.

Only the private module copy's H2 dependency provider changes. Every W2 function,
plan, witness field, COFF inspector and complete link check stays source-exact.
The supplied original dependency bytes/hash are never rewritten or downgraded.
"""

import hashlib
from pathlib import Path
import types


KIND = 'foundation-native-engine-windows-static-probe-object-witness-v2'
PLAN_KIND = 'foundation-native-engine-windows-static-probe-object-plan-v2'
MISSING_CONSTRUCTOR = 'windows-static-probe-v2-original-compile-owned-witness-constructor'
SOURCE_SHA256 = 'd71938060a67c63c3557d1c45c98fe9039462a31e122d47cc0a4dc859e95b4ca'
MAX_SOURCE_BYTES = 65536
MAX_OBJECT_BYTES = 4 * 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024
MAX_DOCUMENT = 4 * 1024 * 1024
_D3 = None
_W2 = None


class MissingSource(ValueError):
    pass


def _d3():
    global _D3
    if _D3 is None:
        source = Path(__file__).resolve().with_name('proof_d3.py')
        spec = types.ModuleType('_private_w2_d3_receipt')
        spec.__file__ = str(source)
        with source.open('rb') as stream:
            raw = stream.read(9777)
        if (len(raw) != 9776 or hashlib.sha256(raw).hexdigest() !=
                'a032b4f632e3770bd6b1daeef28a95759717483aabe8a549f27b8710ea21d55a'):
            raise ValueError('Frozen D3 pure source differs')
        exec(compile(raw, str(source), 'exec'), vars(spec))
        _D3 = spec
    return _D3


def _dependency(raw, pin, expected, identity):
    d3 = _d3()
    d2 = d3._d2()
    value = d2.legacy().parse_document(raw)
    if type(value) is not dict:
        raise ValueError('Explicit original D2 or D3 dependency object required')
    pair = (value.get('schema_version'), value.get('kind'))
    if pair == (2, d2.RECEIPT_KIND):
        return d2.validate_dependency_receipt(raw, pin, expected, identity)
    if pair == (3, d3.RECEIPT_KIND):
        return d3.validate_dependency_receipt(raw, pin, expected, identity)
    raise ValueError('Explicit original D2 or D3 dependency schema/kind required')


def _w2():
    global _W2
    if _W2 is None:
        source = Path(__file__).resolve().parent / 'probe_w2.py'
        with source.open('rb') as stream:
            raw = stream.read(12737)
        if (len(raw) != 12736 or hashlib.sha256(raw).hexdigest() !=
                'e11c3734ea8ba7a1e9bc52fdf4c19822ecf06f2c46579d456b3ad568476d06b3'):
            raise ValueError('Frozen W2 pure source differs')
        module = types.ModuleType('_private_w2_d3_frozen_w2')
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        d2 = _d3()._d2()
        module._H2 = types.SimpleNamespace(
            validate_toolchain_identity=d2.validate_toolchain_identity,
            legacy=d2.legacy, _identity_paths=d2._identity_paths,
            validate_dependency_receipt=_dependency)
        _W2 = module
    return _W2


def encoded(value):
    return _w2().encoded(value)


def plan(identity_raw, identity_pin, maintained_source_path, workspace_root, limits):
    return _w2().plan(identity_raw, identity_pin, maintained_source_path, workspace_root, limits)


def inspect_object(raw):
    return _w2().inspect_object(raw)


def output_subject(selected_plan, object_raw, log_raw):
    return _w2().output_subject(selected_plan, object_raw, log_raw)


def validate_witness(raw_witness, witness_pin, *, identity_raw, identity_pin, dependency_raw,
        dependency_pin, dependency_path, expected, maintained_source_raw, compiled_source_raw,
        object_raw, log_raw, maintained_source_path, workspace_root, limits):
    return _w2().validate_witness(raw_witness, witness_pin, identity_raw=identity_raw,
        identity_pin=identity_pin, dependency_raw=dependency_raw, dependency_pin=dependency_pin,
        dependency_path=dependency_path, expected=expected, maintained_source_raw=maintained_source_raw,
        compiled_source_raw=compiled_source_raw, object_raw=object_raw, log_raw=log_raw,
        maintained_source_path=maintained_source_path, workspace_root=workspace_root, limits=limits)


def require_native_constructor():
    raise MissingSource(MISSING_CONSTRUCTOR)
