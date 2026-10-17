"""Additive pure original-O consistency joins for two fixed Windows host methods.

Expected declarations and method inputs must be independently reconstructed by
the calling factory. No returned ordinary dictionary authenticates an original
origin, held input, native owner, runtime observation or issuer capability.
Selected programs, runtimes, projects and emitters are never opened or run here.
Only the finite pinned checker/parser source closure is read lazily.
"""

from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import stat
import types


HERE = Path(__file__).resolve().parent
HOST_ROLES = ('nmake', 'msbuild')
NMAKE_METHOD = 'nmake-pe-version-resource-v1'
_RELEASES = {
    'runtime': ('observation_runtime.py', 6100,
        '061a0535dda535c31ecf340d645af773bdc52ccc9b8aa88fc9a190eddfc6e756'),
    'msbuild': ('host_methods.py', 4780,
        '017230b1026703e027d007f17a82ac00eb6df2729f0169f989343a224d092e3d'),
    'nmake': ('nmake_version.py', 22934,
        '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc'),
}
_NMAKE_EMITTER_BYTES = 5294
_NMAKE_EMITTER_SHA256 = '82ae5d7e673450505435af68bd1c1aa04718dac86fe454bde267b6547d35adb0'
_MODULES = {}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _module(name):
    if name not in _MODULES:
        relative, size, expected = _RELEASES[name]
        if type(size) is not int or not 1 <= size <= 131072:
            raise ValueError('Fixed host method source release is not available')
        path = HERE / relative
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                before.st_size != size):
            raise ValueError('Fixed host method source type/size differs')
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        identity = lambda item: (item.st_dev, item.st_ino, item.st_mode,
            item.st_nlink, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
        if (identity(before) != identity(opened) or
                identity(before) != identity(after) or
                identity(before) != identity(path.lstat()) or
                len(raw) != size or _sha(raw) != expected):
            raise ValueError('Fixed host method source identity/SHA256 differs')
        module = types.ModuleType('_private_original_observation_host_' + name)
        module.__file__ = str(path)
        exec(compile(raw, str(path), 'exec'), vars(module))
        _MODULES[name] = module
    return _MODULES[name]


def _body(proof, raw, reference, label, maximum):
    proof._fields(reference, ('path', 'sha256', 'bytes', 'mode'), label)
    proof.windows_path(reference['path'], label)
    proof._pin(reference['sha256'], label)
    proof._integer(reference['bytes'], label + ' bytes', 1, maximum)
    if type(reference['mode']) is not int or reference['mode'] != 0o644:
        raise ValueError(label + ' logical mode0644 required')
    if (type(raw) is not bytes or len(raw) != reference['bytes'] or
            _sha(raw) != reference['sha256']):
        raise ValueError(label + ' supplied bytes/SHA256 differ')
    return {name: reference[name] for name in ('path', 'sha256')}


def _environment(proof, value):
    # Preserve the frozen command environment contract for both new methods.
    proof._fields(value, ('SystemRoot', 'PATH', 'TEMP', 'TMP'),
                  'closed version environment')
    for name in ('SystemRoot', 'TEMP', 'TMP'):
        proof.windows_path(value[name], 'version environment ' + name)
    if value['TEMP'] != value['TMP']:
        raise ValueError('Version TEMP/TMP declarations differ')
    proof._text(value['PATH'], 'version PATH')
    directories = value['PATH'].split(';')
    if (not 1 <= len(directories) <= 64 or
            len({item.casefold() for item in directories}) != len(directories)):
        raise ValueError('Finite unique version PATH declarations required')
    for item in directories:
        proof.windows_path(item, 'version PATH directory')


def _command(core, proof, value, image, argv):
    proof._fields(value, ('program', 'argv', 'cwd', 'environment'),
                  'version command')
    core._reference(proof, value['program'], 'command program')
    core._same(proof, value['program'], image, 'command program')
    proof.windows_path(value['cwd'], 'version command cwd')
    actual = value['argv']
    if type(actual) is not list or not 1 <= len(actual) <= 32:
        raise ValueError('Finite literal version argv required')
    for item in actual:
        proof._text(item, 'version argv')
    core._same(proof, actual, argv, 'fixed host method argv')
    _environment(proof, value['environment'])


def _method(core, proof, role, program, collector, runtime_profile, inputs,
            log_raw):
    if role == 'msbuild':
        proof._fields(inputs, ('runtime_profile', 'project', 'project_raw'),
                      'MSBuild method inputs')
        core._same(proof, inputs['runtime_profile'], runtime_profile,
                   'MSBuild selected runtime profile')
        selected = _module('msbuild')
        project = _body(proof, inputs['project_raw'], inputs['project'],
                        'MSBuild source project', 16384)
        selected.verify_project(inputs['project_raw'])
        argv = selected.msbuild_argv(program['path'], project['path'])
        version = selected.extract_msbuild(log_raw)['version']
        return selected.METHOD, program, argv, version

    proof._fields(inputs, ('runtime_profile', 'program', 'runner', 'emitter',
                          'emitter_raw'), 'NMake method inputs')
    core._same(proof, inputs['runtime_profile'], runtime_profile,
               'NMake selected runtime profile')
    subject = inputs['program']
    proof._fields(subject, ('path', 'sha256', 'bytes'), 'NMake held program')
    held = {name: subject[name] for name in ('path', 'sha256')}
    core._reference(proof, held, 'NMake held program')
    core._same(proof, held, program, 'NMake held program')
    proof._integer(subject['bytes'], 'NMake held program bytes', 512, 64 * 1024**2)
    runner = inputs['runner']
    core._reference(proof, runner, 'independent NMake collector runner')
    core._same(proof, runner, collector['program'], 'NMake collector runner')
    emitter = _body(proof, inputs['emitter_raw'], inputs['emitter'],
                    'NMake fixed collector emitter', 131072)
    if (len(inputs['emitter_raw']) != _NMAKE_EMITTER_BYTES or
            _sha(inputs['emitter_raw']) != _NMAKE_EMITTER_SHA256):
        raise ValueError('NMake emitter differs from its fixed source release')
    if emitter['path'].rsplit('/', 1)[-1] != 'nmake_version_emitter.py':
        raise ValueError('Exact selected NMake emitter basename required')
    parser = {'path': emitter['path'].rsplit('/', 1)[0] + '/nmake_version.py',
              'sha256': _RELEASES['nmake'][2]}
    for source in (emitter, parser):
        core._reference(proof, source, 'NMake fixed collector source')
        if source not in collector['sources']:
            raise ValueError('NMake collector sources omit its fixed emitter/parser')
    selected = _module('nmake')
    facts = selected.parse_output(log_raw, program=subject)
    argv = [runner['path'], '-I', '-S', emitter['path'], '--program',
            program['path'], '--sha256', program['sha256'], '--bytes',
            str(subject['bytes'])]
    return NMAKE_METHOD, runner, argv, '.'.join(map(str, facts['version4']))


def observation(raw, pin, *, role, program, inventory_subject_sha256,
                collector, command, log_raw, log_reference,
                runtime_profiles=None, method_inputs=None):
    """Validate independent declarations and derive consistency facts only.

    O1 and other O2 methods delegate unchanged. New host methods accept only the
    fixed per-role input shapes; no expected version or command callback exists.
    For NMake alone the independently selected collector Python is the command
    and Job image, while the observed program remains the selected NMake image.
    """
    runtime = _module('runtime')
    core = runtime._core()
    original = runtime._document(raw, pin)
    expected = dict(role=role, program=program,
        inventory_subject_sha256=inventory_subject_sha256, collector=collector,
        command=command, log_raw=log_raw, log_reference=log_reference,
        runtime_profiles=runtime_profiles)
    o1 = (type(original) is dict and
          type(original.get('schema_version')) is int and
          original['schema_version'] == 1 and
          original.get('kind') == core.O1_KIND)
    if o1 or role not in HOST_ROLES:
        if method_inputs is not None:
            raise ValueError('Frozen original method has no host-method inputs')
        return runtime.observation(raw, pin, **expected)

    proof = core._module('proof')
    proof._pin(pin, 'original observation')
    proof._fields(original, set(core.O_FIELDS) | {'runtime_profiles'},
                  'original host observation')
    if (type(original['schema_version']) is not int or
            original['schema_version'] != 2 or original['kind'] != core.O2_KIND):
        raise ValueError('Exact successor O2 host observation schema/kind required')
    if runtime._encoded(original) != raw:
        raise ValueError('Original O2 must use the frozen canonical JSON encoding')
    if type(role) is not str or original['role'] != role:
        raise ValueError('Original observation role differs from its schema/factory')
    actual = runtime.runtime_bindings(original['runtime_profiles'])
    independent = runtime.runtime_bindings(runtime_profiles)
    core._same(proof, actual, independent, 'held runtime profiles')
    core._reference(proof, program, 'independent program')
    proof._pin(inventory_subject_sha256, 'independent inventory subject')
    core._collector(proof, collector)
    method, image, argv, version = _method(core, proof, role, program,
        collector, independent[role], method_inputs, log_raw)
    if original['method'] != method:
        raise ValueError('Original observation method differs from its fixed source')
    _command(core, proof, command, image, argv)
    core._log(proof, log_raw, log_reference)
    for name, value in (('target', core.TARGET), ('program', program),
            ('inventory_subject_sha256', inventory_subject_sha256),
            ('collector', collector), ('command', command), ('log', log_reference)):
        core._same(proof, original[name], value, name)
    core._job(proof, original['job'], image, command, len(log_raw))
    proof._pin(original['output_subject_sha256'], 'original output subject')
    return {'observation': copy.deepcopy(original), 'version': version}
