"""One pure original-O/Job/whole-log contract for fresh and retained factories.

Expected facts must come from the caller's fixed independent source factory.
Matching serialized facts never establish a native owner, origin, hard Job cap,
input admission or producer authority. No expected version is accepted.
"""

import copy
import hashlib
import os
from pathlib import Path
import stat
import types


HERE = Path(__file__).resolve().parent
O1_KIND = 'foundation-native-engine-windows-tool-version-observation-v1'
O2_KIND = 'foundation-native-engine-windows-tool-version-observation-v2'
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
O_FIELDS = ('schema_version', 'kind', 'target', 'role', 'method', 'program',
            'inventory_subject_sha256', 'collector', 'command', 'log', 'job',
            'output_subject_sha256')
JOB_FIELDS = ('owner', 'launch_intent_sha256', 'image', 'launch_suspended',
    'assigned_before_resume', 'breakaway_allowed', 'kill_on_close', 'exit_code',
    'elapsed_milliseconds', 'wall_limit_milliseconds', 'process_count',
    'process_limit', 'peak_output_bytes', 'output_limit_bytes',
    'active_processes_at_join', 'streams_closed', 'join_completed', 'owner_closed')
TRUE_FLAGS = ('launch_suspended', 'assigned_before_resume', 'kill_on_close',
              'streams_closed', 'join_completed', 'owner_closed')
MAX_LOG = 65536
_SOURCE_RELEASES = {
    'methods': ('methods.py', 9983,
        'ab6fad7a14c7d08e5980c8c4a61eda3a3e76a2e85d5ff7006a36fd296e54eefc'),
    'proof': ('../appended_engine_windows_dependency_proof.py', 35435,
        '6d30769578be43268cf9a6226054db79d0e16956e52085fb0f1c4618505b5747'),
}
_MODULES = {}


class MissingMethod(ValueError):
    """A named missing final-version method, never an observed native fact."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _module(name):
    if name not in _MODULES:
        relative, size, expected = _SOURCE_RELEASES[name]
        source = HERE / relative
        with source.open('rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size != size or size > 65536:
                raise ValueError('Fixed observation data-helper source type/size differs')
            raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_size,
                                  value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(after) or len(raw) != size or _sha(raw) != expected:
            raise ValueError('Fixed observation data-helper source identity/SHA256 differs')
        module = types.ModuleType('_private_observation_' + name)
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _MODULES[name] = module
    return _MODULES[name]


def _methods():
    return _module('methods')


def _same(proof, value, expected, label):
    if proof.encoded(value) != proof.encoded(expected):
        raise ValueError('Original observation differs from independent ' + label)


def _reference(proof, value, label):
    return proof._reference(value, label)


def _collector(proof, value):
    proof._fields(value, ('program', 'runtime_subject_sha256', 'sources', 'qualification'), 'collector')
    _reference(proof, value['program'], 'collector program')
    proof._pin(value['runtime_subject_sha256'], 'collector runtime subject')
    _reference(proof, value['qualification'], 'collector qualification')
    sources = value['sources']
    if type(sources) is not list or not 1 <= len(sources) <= 128:
        raise ValueError('Finite exact collector source references required')
    seen = set()
    for item in sources:
        item = _reference(proof, item, 'collector source')
        if item['path'].casefold() in seen:
            raise ValueError('Collector source references alias or repeat')
        seen.add(item['path'].casefold())


def _command(proof, methods, role, value, program):
    proof._fields(value, ('program', 'argv', 'cwd', 'environment'), 'version command')
    _reference(proof, value['program'], 'command program')
    _same(proof, value['program'], program, 'command program')
    proof.windows_path(value['cwd'], 'version command cwd')
    argv = value['argv']
    if type(argv) is not list or not 1 <= len(argv) <= 32:
        raise ValueError('Finite literal version argv required')
    for item in argv:
        proof._text(item, 'version argv')
    emitter = None if role == 'cmake' else argv[-1]
    _same(proof, argv, methods.argv(role, program['path'], emitter), 'fixed method argv')
    environment = value['environment']
    proof._fields(environment, ('SystemRoot', 'PATH', 'TEMP', 'TMP'), 'closed version environment')
    for name in ('SystemRoot', 'TEMP', 'TMP'):
        proof.windows_path(environment[name], 'version environment ' + name)
    if environment['TEMP'] != environment['TMP']:
        raise ValueError('Version TEMP/TMP declarations differ')
    proof._text(environment['PATH'], 'version PATH')
    directories = environment['PATH'].split(';')
    if not 1 <= len(directories) <= 64 or len({item.casefold() for item in directories}) != len(directories):
        raise ValueError('Finite unique version PATH declarations required')
    for item in directories:
        proof.windows_path(item, 'version PATH directory')


def _log(proof, raw, reference):
    proof._fields(reference, ('path', 'sha256', 'bytes', 'mode'), 'whole original log reference')
    proof.windows_path(reference['path'], 'whole original log')
    proof._pin(reference['sha256'], 'whole original log')
    proof._integer(reference['bytes'], 'whole original log bytes', 1, MAX_LOG)
    if type(reference['mode']) is not int or reference['mode'] != 0o644:
        raise ValueError('Whole original log mode0644 required')
    if type(raw) is not bytes or len(raw) != reference['bytes'] or _sha(raw) != reference['sha256']:
        raise ValueError('Whole original log bytes/SHA256 differ')


def _job(proof, value, program, command, log_bytes):
    proof._fields(value, JOB_FIELDS, 'original Job')
    if value['owner'] != 'windows-job-v1':
        raise ValueError('Original Job owner kind differs')
    for name in TRUE_FLAGS:
        if value[name] is not True:
            raise ValueError('Original Job requires exact true flag: ' + name)
    if value['breakaway_allowed'] is not False:
        raise ValueError('Original Job forbids breakaway')
    for name in ('exit_code', 'active_processes_at_join'):
        proof._integer(value[name], 'original Job ' + name, 0, 0)
    _reference(proof, value['image'], 'Job image')
    _same(proof, value['image'], program, 'Job image')
    proof._pin(value['launch_intent_sha256'], 'Job launch intent')
    if value['launch_intent_sha256'] != _sha(proof.encoded(command)):
        raise ValueError('Original Job canonical launch intent SHA256 differs')
    wall = proof._integer(value['wall_limit_milliseconds'], 'Job wall limit', 1, 60000)
    elapsed = proof._integer(value['elapsed_milliseconds'], 'Job elapsed', 0, 60000)
    if elapsed >= wall:
        raise ValueError('Original Job elapsed must be strictly below its wall limit')
    count = proof._integer(value['process_count'], 'Job process count', 1, 64)
    limit = proof._integer(value['process_limit'], 'Job process limit', 1, 64)
    if count > limit:
        raise ValueError('Original Job process count exceeds its limit')
    peak = proof._integer(value['peak_output_bytes'], 'Job peak output bytes', log_bytes, 16 * 1024**2)
    output_limit = proof._integer(value['output_limit_bytes'], 'Job output limit', 1, 16 * 1024**2)
    if peak > output_limit:
        raise ValueError('Original Job peak output exceeds its limit')


def observation(raw, pin, *, role, program, inventory_subject_sha256, collector,
                command, log_raw, log_reference):
    """Check O1/O2 against independent factory declarations and derive final facts.

    The returned ordinary dict cannot replace either factory's live native/origin
    authority. Output-subject and Job facts remain serialized consistency claims.
    """
    proof, methods = _module('proof'), _methods()
    proof._pin(pin, 'original observation')
    value = proof.parse_document(raw)
    if _sha(raw) != pin:
        raise ValueError('Original observation raw SHA256 differs')
    proof._fields(value, O_FIELDS, 'original observation')
    schema, kind = value['schema_version'], value['kind']
    if type(schema) is not int or (schema, kind) not in ((1, O1_KIND), (2, O2_KIND)):
        raise ValueError('Unsupported or mixed original observation schema/kind')
    roles = methods.ROLE_ORDER[:11] if schema == 1 else methods.ROLE_ORDER
    if type(role) is not str or role not in roles or value['role'] != role:
        raise ValueError('Original observation role differs from its schema/factory')
    try:
        method = methods.method_for(role)
        if value['method'] != method:
            raise ValueError('Original observation method differs from its fixed source')
        _reference(proof, program, 'independent program')
        proof._pin(inventory_subject_sha256, 'independent inventory subject')
        _collector(proof, collector)
        _command(proof, methods, role, command, program)
        _log(proof, log_raw, log_reference)
        for name, expected in (('target', TARGET), ('program', program),
                ('inventory_subject_sha256', inventory_subject_sha256), ('collector', collector),
                ('command', command), ('log', log_reference)):
            _same(proof, value[name], expected, name)
        _job(proof, value['job'], program, command, len(log_raw))
        proof._pin(value['output_subject_sha256'], 'original output subject')
        version = methods.extract(role, method, log_raw, final=True)
    except methods.MissingMethod as error:
        raise MissingMethod(str(error)) from error
    return {'observation': copy.deepcopy(value), 'version': version}
