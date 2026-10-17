"""Private pure D3 consistency; runtime declarations never create authority.

H2 and all D2 helpers are loaded from one fixed frozen source into a private
module. This module validates D3 directly; it never relabels a D3 document D2.
No selected program, OS image, runtime, SDK, supplier or product body is read.
"""

import copy
import hashlib
from pathlib import Path
import types


RECEIPT_KIND = 'foundation-native-engine-windows-dependencies-build-v3'
MAX_PROFILE_BYTES = 2 * 1024**2
MAX_COMMAND_PROCESSOR_BYTES = 64 * 1024**2
EXPECTED_FIELDS = ('bindings', 'commands', 'prefix', 'libraries', 'probe',
                   'registration', 'original_program_evidence', 'nmake_runtime')
_H1_SYSTEM_LINKS = frozenset(('advapi32', 'bcrypt', 'crypt32', 'iphlpapi', 'normaliz',
    'ole32', 'secur32', 'shell32', 'shlwapi', 'user32', 'version', 'winmm', 'ws2_32'))
SYSTEM_LINKS = _H1_SYSTEM_LINKS | frozenset(('gdi32',))
_D2 = None


def _d2():
    global _D2
    if _D2 is None:
        source = Path(__file__).resolve().parent / 'proof_h2.py'
        with source.open('rb') as stream:
            raw = stream.read(19878)
        if (len(raw) != 19877 or hashlib.sha256(raw).hexdigest() !=
                'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9'):
            raise ValueError('Frozen D2 pure helper source differs')
        module = types.ModuleType('_private_d3_frozen_h2d2')
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _D2 = module
    return _D2


def encoded(value):
    return _d2().encoded(value)


def validate_libraries(value, bindings, prefix, paths=None, observations=False):
    """Check the unchanged twenty-library shape with the closed D3 system policy.

    The frozen function gets one private globals dictionary. Neither the shared
    H1 module nor the D2 helper instance is changed. Inspection values remain
    declarations here; this pure check performs no body or native admission.
    """
    h1 = _d2().legacy()
    if h1.SYSTEM_LINKS != _H1_SYSTEM_LINKS:
        raise ValueError('Frozen H1 system library policy differs')
    namespace = dict(h1._libraries.__globals__)
    namespace['SYSTEM_LINKS'] = SYSTEM_LINKS
    check = types.FunctionType(h1._libraries.__code__, namespace,
                               '_private_d3_libraries')
    return check(value, bindings, prefix, h1._Paths() if paths is None else paths,
                 observations)


def _runtime(value, expected, identity, paths):
    h1 = _d2().legacy()
    h1._fields(value, ('profile', 'subject_sha256', 'system_root', 'windows_version',
                       'command_processor'), 'D3 independently admitted NMake runtime')
    profile = h1._fields(value['profile'], ('path', 'sha256', 'bytes', 'mode'), 'NMake runtime profile')
    h1._reference({key: profile[key] for key in ('path', 'sha256')}, 'NMake runtime profile', paths)
    h1._integer(profile['bytes'], 'NMake runtime profile bytes', 1, MAX_PROFILE_BYTES)
    h1._equal(profile['mode'], 0o644, 'NMake runtime profile mode')
    h1._pin(value['subject_sha256'], 'NMake runtime subject')
    h1._equal(value['subject_sha256'], expected['original_program_evidence']['nmake']['runtime_subject_sha256'],
              'independent NMake original/runtime subject')
    h1.windows_path(value['system_root'], 'NMake runtime SystemRoot')
    h1._equal(value['system_root'], identity['system_root'], 'NMake runtime/H2 SystemRoot')
    version = h1._array(value['windows_version'], 'NMake runtime Windows version', 3, 3)
    for number in version:
        h1._integer(number, 'NMake runtime Windows version component', 0, 2**31 - 1)
    processor = h1._fields(value['command_processor'], ('path', 'sha256', 'bytes'), 'NMake command processor')
    h1._reference({key: processor[key] for key in ('path', 'sha256')}, 'NMake command processor', paths)
    h1._integer(processor['bytes'], 'NMake command processor bytes', 1, MAX_COMMAND_PROCESSOR_BYTES)
    h1._equal(processor['path'], identity['system_root'] + '/System32/cmd.exe',
              'exact derived NMake command processor')
    return processor['path']


def _environment(command, command_processor):
    """Extend exactly the original NMake role; retain every frozen D2 rule."""
    environment = command['environment']
    aliases = [name for name in environment if name.casefold() == 'comspec']
    original_nmake = command['program']['kind'] == 'original' and command['program']['role'] == 'nmake'
    if original_nmake:
        if aliases != ['COMSPEC'] or environment['COMSPEC'] != command_processor:
            raise ValueError('D3 original NMake requires exact derived COMSPEC')
    elif aliases:
        raise ValueError('D3 COMSPEC is restricted to the original NMake role')


def validate_receipt(value, expected, identity):
    """Check D3 source declarations only, with independently supplied expectations.

    This direct D3 orchestration retains the frozen D2 helpers and their joins.
    Neither a caller's expected dictionary nor its runtime profile is admitted.
    """
    d2 = _d2()
    h1 = d2.legacy()
    h1.encoded(value); h1.encoded(expected)
    identity = d2.toolchain_identity(identity)
    h1._fields(expected, EXPECTED_FIELDS, 'D3 independent expectations')
    h1._fields(value, ('schema_version', 'kind', 'target', 'scope', 'bindings', 'commands',
                     'prefix', 'libraries', 'postflight', 'probe', 'facts'), 'D3 receipt')
    for key, wanted in (('schema_version', 3), ('kind', RECEIPT_KIND), ('target', d2.TARGET), ('scope', h1.SCOPE)):
        h1._equal(value[key], wanted, 'D3 ' + key)
    paths = d2._identity_paths(identity)
    h1._bindings(expected['bindings'], paths)
    h1._equal(expected['bindings']['toolchain_identity_sha256'],
              hashlib.sha256(encoded(identity)).hexdigest(), 'independent H2 digest')
    h1._prefix(expected['prefix'], paths)
    d2._original_evidence(expected['original_program_evidence'], identity, paths)
    processor = _runtime(expected['nmake_runtime'], expected, identity, paths)
    h1._array(expected['commands'], 'expected D3 commands', h1.MAX_COMMANDS, 1)
    for command in expected['commands']: h1._fields(command, h1.COMMAND_FIELDS, 'D3 expected command')
    d2._registration(expected['registration'], expected['commands'], identity, paths)
    indices = {item['id']: index for index, item in enumerate(expected['commands'])}
    for index, command in enumerate(expected['commands']):
        d2._command(command, expected['registration'], identity, paths, indices, index)
        _environment(command, processor)
    validate_libraries(expected['libraries'], expected['bindings'], expected['prefix'], paths, False)
    h1._probe(expected['probe'], expected['commands'], expected['libraries'], paths)
    for key in ('bindings', 'prefix', 'probe'): h1._equal(value[key], expected[key], 'original D3 ' + key)
    h1._array(value['commands'], 'actual D3 commands', h1.MAX_COMMANDS, 1)
    if len(value['commands']) != len(expected['commands']): raise ValueError('Incomplete D3 stages')
    closed = {}
    for actual, declaration in zip(value['commands'], expected['commands']):
        h1._fields(actual, h1.COMMAND_FIELDS + ('logs', 'output_subject_sha256', 'job',
                       'resolved_program', 'produced_outputs'), 'D3 command observations')
        h1._equal({key: actual[key] for key in h1.COMMAND_FIELDS}, declaration, 'registered D3 literal command')
        h1._fields(actual['logs'], ('combined',), 'original D3 combined log')
        h1._reference(actual['logs']['combined'], 'original D3 log')
        if actual['logs']['combined']['path'].casefold() in paths.entries:
            raise ValueError('D3 log aliases another original input/output')
        h1._reference(actual['logs']['combined'], 'original D3 log', paths)
        h1._pin(actual['output_subject_sha256'], 'closed D3 output subject')
        program = d2._resolved(actual['resolved_program'], declaration, expected, identity, closed)
        h1._equal(program['path'], declaration['argv'][0], 'resolved D3 execution path')
        execution = {**declaration, 'program': program}
        h1._job(actual['job'], execution)
        d2._produced_outputs(actual['produced_outputs'], declaration['id'], expected['registration'])
        closed[declaration['id']] = actual
    validate_libraries(value['libraries'], value['bindings'], value['prefix'], paths, True)
    h1._equal({target: {key: item for key, item in record.items() if key != 'inspection'}
               for target, record in value['libraries'].items()}, expected['libraries'], 'D3 library map')
    h1._fields(value['postflight'], ('toolchain_identity_sha256', 'sources'), 'D3 frozen postflight')
    h1._equal(value['postflight']['toolchain_identity_sha256'],
              expected['bindings']['toolchain_identity_sha256'], 'unchanged H2 postflight')
    h1._equal(value['postflight']['sources'], {name: expected['bindings']['sources'][name]['source_subject_sha256']
                                             for name in h1.SOURCES}, 'unchanged D3 sources')
    h1._fields(value['facts'], h1.FALSE_FACTS, 'unqualified D3 facts')
    for key in h1.FALSE_FACTS: h1._equal(value['facts'][key], False, 'unqualified D3 ' + key)
    return copy.deepcopy(value)


def dependency_receipt(declared_facts, expected, identity):
    return validate_receipt(declared_facts, expected, identity)


def validate_dependency_receipt(raw, expected_pin, expected, identity):
    h1 = _d2().legacy()
    h1._pin(expected_pin, 'D3 receipt')
    value = h1.parse_document(raw)
    if hashlib.sha256(raw).hexdigest() != expected_pin: raise ValueError('D3 receipt SHA256 mismatch')
    return validate_receipt(value, expected, identity)
