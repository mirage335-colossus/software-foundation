"""Fixed pure O2 joins for semantic console, builtin and resource methods.

Independent declarations remain the caller's responsibility. No ordinary result
authenticates an original, held input, native Job, runtime or issuer capability.
Only fixed checker/method source bytes are read lazily; selected inputs and
emitters are never opened or run here.
"""

from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import stat
import types


HERE = Path(__file__).resolve().parent
RESOURCE_ROLES = ('archiver', 'resource_compiler', 'manifest_tool')
BUILTIN_ROLES = ('python', 'perl', 'ruby')
_RESOURCE_NAMES = {
    'parser': 'resource/llvm_version.py',
    'codec': 'nmake_version.py',
    'emitter': 'resource/llvm_version_emitter.py',
}
_RELEASES = {
    'host': ('observation_host.py', 10856,
        '4609b6a50e0ecb73c17a8563f8b346a35a0c5ca32f471076bd7528c75558eaf0'),
    'methods': ('version_methods.py', 5431,
        '4b980a06167298130f7f8faaf2e2e3a88f25345a36b07de008db04b4c2ebb62d'),
}
_MODULES = {}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _module(name):
    if name not in _MODULES:
        relative, size, expected = _RELEASES[name]
        if type(size) is not int or not 1 <= size <= 262144:
            raise ValueError('Fixed tool method source release is not available')
        source = HERE / relative
        before = source.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                before.st_size != size):
            raise ValueError('Fixed tool method source type/size differs')
        with source.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        identity = lambda row: (row.st_dev, row.st_ino, row.st_mode,
            row.st_nlink, row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        if (identity(before) != identity(opened) or
                identity(before) != identity(after) or
                identity(before) != identity(source.lstat()) or
                len(raw) != size or _sha(raw) != expected):
            raise ValueError('Fixed tool method source identity/SHA256 differs')
        module = types.ModuleType('_private_original_observation_tools_' + name)
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _MODULES[name] = module
    return _MODULES[name]


def _resource_sources(core, proof, methods, role, emitter, collector):
    """Rebase only the three fixed source-owned resource rows, never O argv."""
    rows = methods.resource_refs(role)
    proof._fields(rows, tuple(_RESOURCE_NAMES), 'fixed resource source closure')
    for name, relative in _RESOURCE_NAMES.items():
        row = rows[name]
        proof._fields(row, ('path', 'sha256', 'bytes', 'mode'), name + ' resource source')
        if row['path'] != relative:
            raise ValueError('Fixed resource source relative path differs')
        proof._pin(row['sha256'], name + ' resource source')
        proof._integer(row['bytes'], name + ' resource source bytes', 1, 131072)
        if type(row['mode']) is not int or row['mode'] != 0o644:
            raise ValueError('Fixed resource source mode0644 required')
    suffix = '/' + rows['emitter']['path']
    if not emitter['path'].endswith(suffix):
        raise ValueError('Exact resource emitter source suffix required')
    family = emitter['path'][:-len(suffix)]
    proof.windows_path(family, 'fixed resource source family')
    expected = dict(rows['emitter'], path=emitter['path'])
    core._same(proof, emitter, expected, 'fixed resource emitter release')
    for row in rows.values():
        selected = {'path': family + '/' + row['path'], 'sha256': row['sha256']}
        core._reference(proof, selected, 'fixed resource collector source')
        if selected not in collector['sources']:
            raise ValueError('Collector sources omit fixed resource parser/codec/emitter')


def _resource_method(host, core, proof, methods, role, program, collector,
                     inputs, log_raw):
    proof._fields(inputs, ('program', 'runner', 'emitter', 'emitter_raw'),
                  'resource method inputs')
    subject = inputs['program']
    proof._fields(subject, ('path', 'sha256', 'bytes'), 'held resource subject')
    selected = {name: subject[name] for name in ('path', 'sha256')}
    core._reference(proof, selected, 'held resource subject')
    core._same(proof, selected, program, 'independent resource subject')
    proof._integer(subject['bytes'], 'held resource subject bytes', 512, 64 * 1024**2)
    runner = inputs['runner']
    core._reference(proof, runner, 'independent resource collector runner')
    core._same(proof, runner, collector['program'], 'resource collector runner')
    host._body(proof, inputs['emitter_raw'], inputs['emitter'],
               'fixed resource emitter', 131072)
    _resource_sources(core, proof, methods, role, inputs['emitter'], collector)
    argv = methods.resource_argv(role, runner['path'], inputs['emitter']['path'], subject)
    version = methods.parse_resource_version(role, methods.method_for(role), log_raw, subject)
    return runner, argv, version


def observation(raw, pin, *, role, program, inventory_subject_sha256,
                collector, command, log_raw, log_reference,
                runtime_profiles=None, method_inputs=None):
    """Return descriptive consistency facts from independently bound O inputs."""
    host = _module('host')
    runtime = host._module('runtime')
    core = runtime._core()
    original = runtime._document(raw, pin)
    expected = dict(role=role, program=program,
        inventory_subject_sha256=inventory_subject_sha256, collector=collector,
        command=command, log_raw=log_raw, log_reference=log_reference,
        runtime_profiles=runtime_profiles, method_inputs=method_inputs)
    o1 = (type(original) is dict and
          type(original.get('schema_version')) is int and
          original['schema_version'] == 1 and original.get('kind') == core.O1_KIND)
    if o1 or role in host.HOST_ROLES:
        return host.observation(raw, pin, **expected)

    methods = _module('methods')
    proof = core._module('proof')
    proof._pin(pin, 'original observation')
    proof._fields(original, set(core.O_FIELDS) | {'runtime_profiles'},
                  'original tool observation')
    if (type(original['schema_version']) is not int or
            original['schema_version'] != 2 or original['kind'] != core.O2_KIND):
        raise ValueError('Exact successor O2 tool observation schema/kind required')
    if runtime._encoded(original) != raw:
        raise ValueError('Original O2 must use the frozen canonical JSON encoding')
    if (type(role) is not str or role not in methods.ROLE_ORDER or
            role in host.HOST_ROLES or original['role'] != role):
        raise ValueError('Original observation role differs from its schema/factory')
    actual = runtime.runtime_bindings(original['runtime_profiles'])
    independent = runtime.runtime_bindings(runtime_profiles)
    core._same(proof, actual, independent, 'held runtime profiles')
    core._reference(proof, program, 'independent program')
    proof._pin(inventory_subject_sha256, 'independent inventory subject')
    core._collector(proof, collector)
    try:
        method = methods.method_for(role)
        if original['method'] != method:
            raise ValueError('Original observation method differs from its fixed source')
        if role in RESOURCE_ROLES:
            image, argv, version = _resource_method(host, core, proof, methods,
                role, program, collector, method_inputs, log_raw)
        else:
            if method_inputs is not None:
                raise ValueError('Direct tool methods accept no resource method inputs')
            emitter = None
            if role in BUILTIN_ROLES:
                candidate = command.get('argv') if type(command) is dict else None
                if type(candidate) is not list or not candidate:
                    raise ValueError('Fixed builtin emitter argv required')
                emitter = candidate[-1]
            image = program
            argv = methods.argv(role, program['path'], emitter)
            version = methods.extract(role, method, log_raw, final=True)
        host._command(core, proof, command, image, argv)
        core._log(proof, log_raw, log_reference)
        for name, value in (('target', core.TARGET), ('program', program),
                ('inventory_subject_sha256', inventory_subject_sha256),
                ('collector', collector), ('command', command), ('log', log_reference)):
            core._same(proof, original[name], value, name)
        core._job(proof, original['job'], image, command, len(log_raw))
        proof._pin(original['output_subject_sha256'], 'original output subject')
    except methods.MissingMethod as error:
        raise core.MissingMethod(str(error)) from error
    return {'observation': copy.deepcopy(original), 'version': version}
