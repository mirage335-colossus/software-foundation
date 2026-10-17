#!/usr/bin/env python3
"""Finite Windows dependency entry point with one lazy source owner.

Importing this facade loads only standard-library code. Legacy metadata callers
remain available lazily; native production uses the fixed maintained controller
and its single source cache. No caller path, module or status grants authority.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import threading
import types


_FAMILY = Path(__file__).resolve().with_name('appended_engine_windows_dependency_support')
_CONTROLLER_NAME = '_foundation_windows_h2d3_controller_core_v1'
_CONTROLLER_SHA256 = '88702300048da4fcdcc67dd42929f3369e86430b9b371b7e846db744b1937983'  # Joined only after the actual controller source release.
_CONTROLLER_BYTES = 61631
_LEGACY_NAME = '_foundation_windows_dependencies_legacy_v1'
_LEGACY_SHA256 = 'a604aff8c735afdd50394200ee6e2045d924c46ce7c4792307569bccff27d139'
_LEGACY_BYTES = 63097
_ROLES = frozenset(('controller', 'selection', 'current_inputs', 'generated_inputs',
    'supplier_factory_contract', 'supplier_factory_contract_base', 'supplier_registry',
    'producer', 'retained_dependency', 'source_inputs', 'library_interfaces',
    'dependency_publication'))
_SOURCE_LOCK = threading.RLock()
_SOURCE_CACHE = {}
_FAILED_RESERVATIONS = []
_LEGACY_EXPORTS = frozenset(('ARCHIVE_HELPER_SOURCES', 'DependencyInputs', 'FALSE_FACTS', 'IDENTITY_FIELDS', 'JOB_PROCESS_LIMIT_GAP', 'LIMIT_BOUNDS', 'MAX_METADATA', 'MAX_SOURCE_ARCHIVE_BYTES', 'MAX_SOURCE_BYTES', 'MAX_SOURCE_FILES', 'MAX_SOURCE_MEMBER_BYTES', 'MissingInputs', 'PLAN_KIND', 'PROBE_OBJECT_BINDING_GAP', 'PROFILE', 'PROFILE_PIN', 'PUBLICATION_SOURCES', 'RECIPE', 'RECIPE_FILES', 'ROOT', 'SCOPE', 'SELECTION_KIND', 'SOURCE_METADATA', 'SOURCE_METADATA_PIN', 'SOURCE_REVIEW', 'SOURCE_REVIEW_PIN', '_CANDIDATE_TOKEN', '_CandidateReceipt', '_absolute_row', '_activation_gaps', '_archive_projection', '_assemble_receipt', '_command_toolchain_join', '_equal', '_execute_commands', '_fields', '_hash', '_host_read', '_inspect_prefix', '_integer', '_inventory_encoded', '_inventory_equal', '_local_metadata', '_native_sources', '_native_toolchain', '_open_workspace', '_probe_link_inputs', '_publish_candidate', '_recipe_metadata', '_reference', '_relative', '_require_reviewed_recipe', '_review_gaps', '_run_stage', '_source_projection', '_source_receipt_envelope', '_subject', '_validate_prefix_metadata', '_verify_probe', 'admit_dependency_producer', 'build', 'inspect_selection', 'plan', 'require_native_host', 'validate_limits', 'validate_selection', 'validate_source_declarations'))


class SourceBindingError(ValueError):
    pass


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
        value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _source_bytes(path, pin, size):
    """Capture one fixed source file; no input tree or cached bytecode is opened."""
    if (type(pin) is not str or len(pin) != 64 or
            any(character not in '0123456789abcdef' for character in pin) or
            type(size) is not int or not 1 <= size <= 1024 * 1024):
        raise SourceBindingError('The maintained controller source binding is unfinished')
    path = Path(path)
    before = path.lstat()
    for current in (path, *path.parents):
        state = current.lstat()
        if (stat.S_ISLNK(state.st_mode) or getattr(state, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISREG(state.st_mode) if current == path else stat.S_ISDIR(state.st_mode))):
            raise SourceBindingError('Maintained source paths must be ordinary and unaliased')
    if before.st_nlink != 1 or before.st_size != size:
        raise SourceBindingError('Maintained source byte count or link identity changed')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(size + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) != size or _identity(before) != _identity(opened) or
            _identity(before) != _identity(after) or
            _identity(before) != _identity(path.lstat()) or
            hashlib.sha256(raw).hexdigest() != pin):
        raise SourceBindingError('Maintained source bytes or physical identity changed')
    return raw


def _fixed_source(filename, pin, size, name):
    """Reserve exact captured code atomically; failures retain their blockers."""
    with _SOURCE_LOCK:
        path = _FAMILY / filename
        raw = _source_bytes(path, pin, size)
        cached = _SOURCE_CACHE.get(name)
        if cached is not None:
            if (cached['path'] != str(path) or cached['pin'] != pin or
                    sys.modules.get(name) is not cached['module'] or
                    getattr(cached['module'], '__file__', None) != str(path)):
                raise SourceBindingError('Owned source module registration changed')
            return cached['module']
        if name in sys.modules:
            raise SourceBindingError('Unknown preloaded maintained source module')
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module.__package__ = ''
        if sys.modules.setdefault(name, module) is not module:
            raise SourceBindingError('Maintained source reservation lost its module slot')
        try:
            if name == _CONTROLLER_NAME:
                entry = sys.modules.get(__name__)
                if (type(entry) is not types.ModuleType or vars(entry) is not globals() or
                        vars(entry).get('__file__') != str(Path(__file__).resolve())):
                    raise SourceBindingError('The controller requires its actual dependency entry owner')
                module.__dict__['_dependency_entry_owner'] = entry
            exec(compile(raw, str(path), 'exec', dont_inherit=True), vars(module))
            if (sys.modules.get(name) is not module or
                    getattr(module, '__file__', None) != str(path)):
                raise SourceBindingError('Maintained source registration changed during loading')
            _SOURCE_CACHE[name] = {'path': str(path), 'pin': pin, 'module': module}
            return module
        except BaseException:
            _FAILED_RESERVATIONS.append(module)
            # An uncertain reservation remains a blocker. Never delete or
            # restore a foreign slot after a failed source execution.
            raise


def _module(role):
    """Resolve only a fixed role through the controller's sole verified cache."""
    if type(role) is not str or role not in _ROLES:
        raise SourceBindingError('An exact maintained Windows dependency role is required')
    controller = _fixed_source('controller.py', _CONTROLLER_SHA256,
        _CONTROLLER_BYTES, _CONTROLLER_NAME)
    resolver = getattr(controller, '_support_module', None)
    if not callable(resolver) or resolver('controller') is not controller:
        raise SourceBindingError('The maintained controller has no matching source owner')
    return resolver(role)


def _legacy():
    return _fixed_source('legacy.py', _LEGACY_SHA256, _LEGACY_BYTES, _LEGACY_NAME)


def __getattr__(name):
    if name not in _LEGACY_EXPORTS:
        raise AttributeError(name)
    return getattr(_legacy(), name)


def inventory_declaration(raw, pin, role, *, provenance_raw, provenance_pin):
    return _module('current_inputs').inventory_declaration(raw, pin, role,
        provenance_raw=provenance_raw, provenance_pin=provenance_pin)


def validate_toolchain_identity(raw, pin, actual_facts=None):
    return _module('current_inputs').validate_toolchain_identity(raw, pin, actual_facts)


def engine_admission_declaration(value, handoff):
    return _module('current_inputs').engine_admission_declaration(value, handoff)


def admit_retained_dependency_with_probe(request_ref, *, overall_deadline):
    return _module('retained_dependency').admit_retained_dependency_with_probe(
        request_ref, overall_deadline=overall_deadline)


def require_retained_dependency_with_probe(token):
    return _module('retained_dependency').require_retained_dependency_with_probe(token)


def require_dependency_with_probe(token):
    return _module('producer').require_dependency_with_probe(token)


def admit_retained_originals(request_ref, *, deadline, limits):
    return _module('current_inputs').admit_retained_originals(request_ref,
        deadline=deadline, limits=limits)


def require_original_membership(token, references):
    return _module('current_inputs').require_original_membership(token, references)


def _arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action, old_name in (('plan', 'selection'), ('build', 'plan')):
        child = sub.add_parser(action)
        group = child.add_mutually_exclusive_group(required=True)
        group.add_argument('--request')
        group.add_argument('--' + old_name)
        child.add_argument('--request-sha256')
        child.add_argument('--' + old_name + '-sha256')
    args = parser.parse_args(argv)
    old_name = 'selection' if args.action == 'plan' else 'plan'
    if args.request is not None:
        if args.request_sha256 is None or getattr(args, old_name + '_sha256') is not None:
            parser.error('--request requires only its matching --request-sha256')
        return ['--request', args.request, '--request-sha256', args.request_sha256], args.action
    if getattr(args, old_name + '_sha256') is None or args.request_sha256 is not None:
        parser.error('--' + old_name + ' requires only its matching SHA256')
    return ['--' + old_name, getattr(args, old_name), '--' + old_name + '-sha256',
        getattr(args, old_name + '_sha256')], args.action


def main(argv=None):
    arguments, action = _arguments(argv)
    if arguments[0] == '--request':
        return _module('producer').cli([action, *arguments])
    return _legacy().main([action, *arguments])


def cli(argv=None):
    try:
        arguments, action = _arguments(argv)
        if arguments[0] == '--request':
            return _module('producer').cli([action, *arguments])
        return _legacy().cli([action, *arguments])
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
