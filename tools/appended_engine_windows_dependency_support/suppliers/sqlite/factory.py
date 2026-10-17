"""Fixed SQLite static supplier declaration; no program or native authority."""
import copy
import hashlib
from pathlib import Path

from _foundation_windows_supplier_factory_contract_v1 import (
    MissingInputs, factory_context, original_program, validate_factory_result)


SOURCE = {'version': '3.46.1', 'archive': 'sqlite.zip',
    'sha256': '77823cb110929c2bcb0f5d48e4833b5c59a8a6e40cdea3936b99e199dbbe5784',
    'bytes': 2764032, 'format': 'zip', 'strip_prefix': 'sqlite-amalgamation-3460100'}
PROJECT_SHA256 = '251324fb79752db3edf925fee4f2ad101101b6c8ade9b11ade9dcee39cb575fc'
SOURCE_MEMBERS = ('sqlite3.c', 'sqlite3.h', 'sqlite3ext.h')
MAXIMUM_JOBS = 4


def _project():
    # The fixed controller also freezes this maintained source in its catalogue.
    path = Path(__file__).with_name('CMakeLists.txt')
    with path.open('rb') as stream:
        raw = stream.read(65537)
    if not 0 < len(raw) <= 65536 or hashlib.sha256(raw).hexdigest() != PROJECT_SHA256:
        raise ValueError('Maintained SQLite static project source changed')
    value = raw.decode('ascii')
    if '\r' in value or not value.endswith('\n'):
        raise ValueError('Maintained SQLite project must have ASCII/LF source')
    return value


def reviewed_supplier_commands(supplier, *, identity, source_layout,
                               build_root, prefix_root, source_recipe_bindings):
    context = factory_context(supplier, identity=identity, source_layout=source_layout,
        build_root=build_root, prefix_root=prefix_root,
        source_recipe_bindings=source_recipe_bindings)
    if supplier != 'sqlite' or context['source_recipe_bindings']['source'] != SOURCE:
        raise ValueError('Only the exact retained SQLite3.46.1 amalgamation is selected')
    recipes = context['source_recipe_bindings']['recipes']
    if set(recipes) != {'toolchain.cmake', 'initial-cache.cmake'}:
        raise ValueError('SQLite requires the two fixed controller-rendered toolchain/cache references')
    for logical, name in (('toolchain.cmake', 'toolchain_file'),
                          ('initial-cache.cmake', 'cache_file')):
        if recipes[logical]['path'] != context[name]:
            raise ValueError('SQLite recipe reference differs from its owned project path: ' + logical)
    source_files = []
    for member in SOURCE_MEMBERS:
        if member not in context['source_layout']['files']:
            raise MissingInputs(['windows-sqlite-data-source-member-' + member.replace('.', '-')])
        item = context['source_layout']['files'][member]
        source_files.append(dict(member=member, **copy.deepcopy(item)))
    cmake = context['identity']['programs']['cmake']['path']
    binary = context['binary_root']
    arguments = (
        ('configure', [cmake, '-S', context['project_root'], '-B', binary, '-G', 'Ninja',
            '-C', context['cache_file'], '-DCMAKE_TOOLCHAIN_FILE=' + context['toolchain_file'],
            '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + context['prefix_root'],
            '-DCMAKE_MAKE_PROGRAM=' + context['identity']['programs']['ninja']['path'],
            '-DFOUNDATION_SQLITE_SOURCE=' + context['source_root']]),
        ('build', [cmake, '--build', binary, '--target', 'sqlite3',
            '--parallel', str(MAXIMUM_JOBS)]),
        ('install', [cmake, '--install', binary, '--config', 'Release',
            '--prefix', context['prefix_root']]))
    commands = []
    for stage, argv in arguments:
        commands.append({'id': 'sqlite-' + stage, 'supplier': 'sqlite', 'stage': stage,
            'program': original_program(context, 'cmake'), 'argv': argv,
            'cwd': context['project_root'] if stage == 'configure' else binary,
            'environment': copy.deepcopy(context['environment']),
            'initial_cache': copy.deepcopy(recipes['initial-cache.cmake']) if stage == 'configure' else None,
            'response_files': [], 'log_policy': 'stdout-stderr-combined'})
    result = {'commands': commands,
        'registration': {'stages': [{key: command[key] for key in ('id','supplier','stage')}
            for command in commands], 'produced_tools': {}},
        'source_files': sorted(source_files, key=lambda item: item['member']),
        'rendered_files': [{'output': 'recipes/sqlite/CMakeLists.txt', 'content': _project()}],
        'generated_inputs': [],
        'install_artifacts': {'libraries': {'SQLite3::SQLite3': 'lib/sqlite3.lib'},
            'headers': ['include/sqlite3.h', 'include/sqlite3ext.h']}}
    return validate_factory_result(context, result)
