"""Pure D3 supplier declarations composed with the frozen D2 source validator.

The internal validation projection removes only independently checked COMSPEC
and finite CMake generated-operand syntax. It emits no rewritten command or
proof artifact. The return value is an owned copy of the original checked D3
declarations. Neither this helper nor its private pure base has native authority.
"""
import copy
import hashlib
from pathlib import Path
import re
import types
import sys


# The fixed registry pins this successor's source before installing it under the
# existing supplier-facing name, in its own isolated source/runtime instance.
MODULE_NAME = '_foundation_windows_supplier_factory_contract_v1'
BASE_SHA256 = 'd0afcc6c1e4ae8c64dd2e37d4b363b754ea2e821b8ddf8c8e9047a8a749b25a3'
_BASE = None


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _base():
    return _owner()._support_module('supplier_factory_contract_base')


# Source authors share this exact exception class with this private pure base;
# no old global module, fixture, validator callback or native registry is used.
MissingInputs = _base().MissingInputs


def factory_context(supplier, *, identity, source_layout, build_root, prefix_root,
                    source_recipe_bindings):
    return _base().factory_context(supplier, identity=identity, source_layout=source_layout,
        build_root=build_root, prefix_root=prefix_root, source_recipe_bindings=source_recipe_bindings)


def original_program(context, role):
    return _base().original_program(context, role)


def render_cmake_inputs(context):
    return _base().render_cmake_inputs(context)


def rendered_reference(context, output, content):
    return _base().rendered_reference(context, output, content)


def _literal_argv(commands):
    aggregate = 0
    for command in commands:
        argv = command['argv']
        if (type(argv) is not list or not 1 <= len(argv) <= 512
                or any(type(arg) is not str or not arg or len(arg) > 8192
                    or any(ord(char) < 32 or ord(char) > 126 for char in arg) for arg in argv)):
            raise ValueError('Finite original D3 literal argv required before projection')
        aggregate += sum(map(len, argv))
        if aggregate > 1024**2:
            raise ValueError('Original D3 argv bytes exceed bound before projection')


def _response_operands(command):
    """Response records describe actual @ operands, never ordinary scripts."""
    responses = command['response_files']
    if type(responses) is not list or len(responses) > 128:
        raise ValueError('Finite Source-owned response-file records required')
    paths = []
    for reference in responses:
        _base()._fields(reference, ('path', 'sha256'), 'D3 response file')
        _base()._path(reference['path'])
        if (type(reference['sha256']) is not str
                or re.fullmatch(r'[0-9a-f]{64}', reference['sha256']) is None):
            raise ValueError('Exact response-file source pin required')
        paths.append(reference['path'])
    if (len({path.casefold() for path in paths}) != len(paths)
            or paths != [argument[1:] for argument in command['argv'][1:] if argument.startswith('@')]):
        raise ValueError('Response records must match the actual ordered @ operands')


def _operand(command, path):
    # Paths are ordinary exact literal operands. Quotes, lists and expansion
    # syntax cannot acquire meaning by being hidden inside a CMake definition.
    _base()._path(path)
    if any(char in path for char in "'\";$%`"):
        raise ValueError('Generated path contains quote/list/expansion syntax')
    program = command['program']
    cmake = (type(program) is dict and program.get('kind') == 'original'
        and program.get('role') == 'cmake')
    matches = []
    for index, argument in enumerate(command['argv'][1:], 1):
        match = (re.fullmatch(r'-D[A-Za-z_][A-Za-z0-9_]*(?::(?:FILEPATH|PATH))?=(.*)', argument)
            if cmake else None)
        if argument == path or match is not None and match.group(1) == path:
            matches.append(index)
        elif path.casefold() in argument.casefold():
            raise ValueError('Generated path occurs in an unsupported literal operand')
    if len(matches) != 1:
        raise ValueError('Exactly one finite generated operand required')
    return matches[0]


def validate_factory_result(context, result):
    base = _base()
    context = base._check_context(context)
    base._source_preflight(result)
    base._fields(result, ('commands', 'registration', 'source_files', 'rendered_files',
        'generated_inputs', 'install_artifacts'), 'D3 supplier result')
    commands = result['commands']
    if type(commands) is not list or not 1 <= len(commands) <= 128:
        raise ValueError('Finite D3 supplier command sequence required')
    indices = {}
    for index, command in enumerate(commands):
        base._fields(command, base._COMMAND, 'D3 supplier command')
        identifier = command['id']
        if (type(identifier) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', identifier) is None
                or identifier in indices):
            raise ValueError('Unique exact D3 command identifiers required')
        indices[identifier] = index
    _literal_argv(commands)
    for command in commands:
        _response_operands(command)
    projected = copy.deepcopy(result)
    for original, checked in zip(commands, projected['commands']):
        environment, program = original['environment'], original['program']
        if type(environment) is not dict:
            raise ValueError('Closed original D3 environment required')
        # deepcopy preserves aliases. Isolate both projected mutable fields so
        # checking one command never rewrites a different command's projection.
        checked['environment'] = dict(environment)
        checked['argv'] = list(original['argv'])
        aliases = [name for name in environment if name.casefold() == 'comspec']
        nmake = (type(program) is dict and program.get('kind') == 'original'
            and program.get('role') == 'nmake')
        if nmake:
            command_processor = context['identity']['system_root'] + '/System32/cmd.exe'
            base._path(command_processor)
            if aliases != ['COMSPEC'] or environment['COMSPEC'] != command_processor:
                raise ValueError('Original NMake requires exact derived COMSPEC')
            checked['environment'].pop('COMSPEC')
        elif aliases:
            raise ValueError('COMSPEC is restricted to the original NMake role')
        # Every remaining environment field/value is still checked by the real
        # base validator against the unchanged six-field context environment.
    generated = result['generated_inputs']
    if type(generated) is not list or len(generated) > 4096:
        raise ValueError('Finite D3 generated input declarations required')
    for row in generated:
        base._fields(row, ('consumer_command_id', 'producing_command_id', 'output'), 'D3 generated input')
        output = base._relative(row['output'])
        consumer, producer = row['consumer_command_id'], row['producing_command_id']
        if (type(consumer) is not str or type(producer) is not str
                or consumer not in indices or producer not in indices):
            raise ValueError('Exact fixed D3 generated consumer/producer required')
        index = indices[consumer]
        path = context['workspace_root'] + '/' + output
        operand_index = _operand(commands[index], path)
        projected['commands'][index]['argv'][operand_index] = path
    # The real base checks all original stages, registration, programs, refs,
    # sources, render bytes, generated producer order/aliases and artifacts.
    # Only the two extensions independently checked above differ internally.
    base.validate_factory_result(context, projected)
    base._source_encoded(result)
    return copy.deepcopy(result)
