"""The maintained Windows dependency source family has one fixed layout.

No environment root, caller path, import search or repository discovery selects
source code. Consumers pin and compile these actual filenames without pyc.
"""

from pathlib import Path, PureWindowsPath


FAMILY = Path(__file__).resolve().parent
CHECKOUT = FAMILY.parent.parent
FAMILY_RELATIVE = 'tools/appended_engine_windows_dependency_support'
PROVIDER_RELATIVE = 'tools/appended_engine_windows_source_replay.py'
SOURCE_NAMES = frozenset((
    'tools/appended_engine_windows_source_replay.py',
    'tools/appended_engine_windows_publication.py',
    'tools/appended_engine_windows_contract.py',
    'tools/process_tree.py', 'tools/appended_engine_native_inputs.py',
    'tools/appended_engine_native_sdk.py', 'tools/appended_engine_native_consumer.py',
    'tools/appended_engine_windows_handoff.py', 'tools/dependency_archive.py',
    'tools/appended_engine_manifest.py', 'tools/appended_engine_document_contract.py',
    'tools/appended_engine_editor_contract.py', 'tools/appended_engine_native_actions_contract.py',
    'tools/appended_engine_windows_dependency_proof.py',
    'tools/appended_engine_windows_prototype.py',
    'tests/diagnostics/windows_engine_publication.py',
    'tests/diagnostics/windows_engine_source_reader.py',
))


def source(relative):
    if type(relative) is not str or relative not in SOURCE_NAMES:
        raise ValueError('Exact maintained Windows source filename required')
    return CHECKOUT.joinpath(*relative.split('/'))


def logical_family(root):
    """Pure diagnostic mapping; cannot select or load a production source root."""
    selected = PureWindowsPath(root)
    if (type(root) is not str or not selected.is_absolute() or
            selected.as_posix() != root or not root[0].isupper() or
            root[1:3] != ':/' or any(part in ('.', '..') for part in selected.parts)):
        raise ValueError('Canonical Windows checkout diagnostic root required')
    return {name: (selected / name).as_posix() for name in sorted(SOURCE_NAMES)}
