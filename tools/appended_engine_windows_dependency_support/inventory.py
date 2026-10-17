"""Pure declarations for six generic inventories; no native admission.

The fixed frozen parser is loaded into an isolated private namespace. Only its
role set changes; no existing module or frozen source is modified. Original
references remain declarations, never files to open or authority to issue.
"""

import hashlib
from pathlib import Path
import types


ROLES = frozenset(('llvm', 'msvc_stl', 'windows_sdk', 'host_generators',
                   'native_dependencies', 'product_assets'))
PARSER_SOURCE_SHA256 = '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb'
PARSER_SOURCE_BYTES = 10077
_PARSER = None


def _parser():
    global _PARSER
    if _PARSER is None:
        source = Path(__file__).resolve().with_name('inventory_contract.py')
        with source.open('rb') as stream:
            raw = stream.read(PARSER_SOURCE_BYTES + 1)
        if len(raw) != PARSER_SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != PARSER_SOURCE_SHA256:
            raise ValueError('Frozen generic inventory parser source differs')
        module = types.ModuleType('_foundation_private_inventory_six_parser_83ff23d4356e454e')
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec', dont_inherit=True), vars(module))
        if module.ROLES != frozenset(('llvm', 'msvc_stl', 'windows_sdk', 'host_generators')):
            raise ValueError('Frozen parser role domain differs')
        module.ROLES = ROLES
        _PARSER = module
    return _PARSER


def encoded(value):
    return _parser().encoded(value)


def inventory_declaration(raw, pin, role, *, provenance_raw, provenance_pin):
    """Return owned inventory/provenance declarations, never native authority."""
    if type(role) is not str or role not in ROLES:
        raise ValueError('One of the six generic Windows inventory roles is required')
    return _parser().inventory_declaration(raw, pin, role,
        provenance_raw=provenance_raw, provenance_pin=provenance_pin)
