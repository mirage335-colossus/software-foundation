"""Fixed maintained static OpenSSL source factory; declarations have no authority.

Supplier executable inputs require reviewed immutable source, independently of
the ordinary C/header data projection. No tool, source patch or native command
is executed while constructing this result.
"""
import hashlib
import json
from pathlib import Path

import _foundation_windows_supplier_factory_contract_v1 as contract


CONSUMER_FACTS = {
    'OpenSSL::Crypto': {
        'includes': ['include'], 'definitions': [],
        'links': ['ws2_32', 'gdi32', 'advapi32', 'crypt32', 'user32'],
    },
    'OpenSSL::SSL': {
        'includes': ['include'], 'definitions': [], 'links': ['OpenSSL::Crypto'],
    },
}
_TARGET = 'VC-FOUNDATION-AMD64-STATIC-NOASM-V1'
_FLAGS = ('no-shared', 'no-asm', 'no-uplink', 'no-apps', 'no-docs',
          'no-tests', 'no-module', 'no-makedepend', '--release')
_RESOURCES = {
    'bootstrap-patches.json': 'b7f04dcfbdf90790b1008ad10401fe75b2c264479a005abda72b1eef417cfb01',
    'foundation-amd64-static-noasm.conf': 'c8a8ad5567ef549c3b1af7f9deededbd2223f48f1727ef159ada19a0b2d27380',
    'graph-patches.json': 'caadc8d571d62bcfd7ddb33caf277a3bf393715b3e0427200dbfe4df3c6d27ed',
    'install.py.in': 'd39b96e4276af1e346ac52f208a27b6df41545a89de80347539ef6d827a24937',
    'prepare.py.in': 'f17e55f9d1498e3a38da74528e2b6c55479d76b7d2bfd700ff2b4135d338a80e',
    'reviewed-sources.json': '77a2e253e8c9c22b4c39f72c088d2de6688dbcb66db89e6c25b50af48ddaf8e1',
}
_BOOTSTRAP = (
    'Configure', 'configdata.pm.in', 'build.info', 'crypto/build.info',
    'Configurations/00-base-templates.conf', 'Configurations/10-main.conf',
    'Configurations/common0.tmpl', 'Configurations/gentemplate.pm',
    'Configurations/windows-makefile.tmpl', 'Configurations/windows-checker.pm',
    'Configurations/platform.pm', 'Configurations/platform/BASE.pm',
    'Configurations/platform/Windows.pm', 'Configurations/platform/Windows/MSVC.pm',
    'util/dofile.pl', 'util/perl/OpenSSL/Glob.pm', 'util/perl/OpenSSL/Template.pm',
    'util/perl/OpenSSL/Util.pm', 'util/perl/OpenSSL/config.pm',
    'util/perl/OpenSSL/fallback.pm', 'external/perl/MODULES.txt',
    'external/perl/Text-Template-1.56/lib/Text/Template.pm',
    'include/openssl/configuration.h.in',
)
# The finite mandatory helpers add no external child tools. Ordinary compiled
# sources, manifests and mandatory template fragments retain the admitted
# pinned archive's normal build-input authority; they are not a second audit
# gate. The private generator guard rejects additional script/native children.
_GENERATORS = ('util/perl/OpenSSL/paramnames.pm', 'util/mkbuildinf.pl')


def _resource(name):
    expected = _RESOURCES.get(name)
    if expected is None:
        raise ValueError('Unsealed maintained OpenSSL resource: ' + name)
    path = Path(__file__).with_name(name)
    with path.open('rb') as stream:
        data = stream.read(65537)
    if (not data or len(data) > 65536 or hashlib.sha256(data).hexdigest() != expected
            or not data.isascii() or b'\r' in data or b'\0' in data):
        raise ValueError('Maintained OpenSSL resource changed: ' + name)
    return data.decode('ascii')


def _reviewed():
    return json.loads(_resource('reviewed-sources.json'))


def missing_executable_sources(source_layout):
    """Pure exact missing-source report; never an alternative admission seam."""
    metadata = _reviewed()
    files = source_layout['files']
    required = set(_BOOTSTRAP) | set(_GENERATORS)
    missing = []
    for member in sorted(required):
        expected = metadata['reviewed_original_files'].get(member)
        if expected is None or member not in files:
            missing.append(member)
        elif files.get(member) != expected:
            raise ValueError('Exact reviewed OpenSSL source projection differs: ' + member)
    return missing


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n'


def _source_chunks(context):
    chunks, chunk = [], {'files': [], 'directories': []}
    items = [('directories', name) for name in context['source_layout']['directories']]
    items += [('files', [name, row['bytes'], row['sha256']])
              for name, row in sorted(context['source_layout']['files'].items())]
    for key, item in items:
        chunk[key].append(item)
        if len(_json(chunk)) > 60000:
            chunk[key].pop()
            if not any(chunk.values()):
                raise ValueError('Original source index item exceeds bound')
            chunks.append(chunk)
            chunk = {'files': [], 'directories': []}
            chunk[key].append(item)
    if any(chunk.values()):
        chunks.append(chunk)
    if len(chunks) > 24:
        raise ValueError('Fixed OpenSSL source index exceeds render count')
    return chunks


def _patches():
    files = []
    for name in ('bootstrap-patches.json', 'graph-patches.json'):
        value = json.loads(_resource(name))
        files.extend(value['files'])
    names = [row['member'] for row in files]
    if len(names) != len(set(names)):
        raise ValueError('Maintained OpenSSL patch resources overlap')
    return {'files': sorted(files, key=lambda row: row['member'])}


def _command(context, identifier, stage, role, arguments, cwd):
    program = contract.original_program(context, role)
    environment = dict(context['environment'])
    if role == 'nmake':
        environment['COMSPEC'] = context['identity']['system_root'] + '/System32/cmd.exe'
    return {'id': identifier, 'supplier': 'openssl', 'stage': stage, 'program': program,
        'argv': [program['declaration']['path'], *arguments], 'cwd': cwd,
        'environment': environment, 'initial_cache': None,
        'response_files': [], 'log_policy': 'stdout-stderr-combined'}


def _declarations(context):
    """Complete staged declarations, also exercised by isolated pure fixtures.

    Public construction checks executable-source review first. Calling this
    pure internal builder cannot admit source, a tool, a job, or native work.
    """
    rendered, references = [], {}
    prefix = 'recipes/openssl/'

    def render(name, content):
        output = prefix + name
        ref = contract.rendered_reference(context, output, content)
        rendered.append({'output': output, 'content': content})
        references[name] = ref
        return ref

    prepare = render('prepare.py', _resource('prepare.py.in'))
    install = render('install.py', _resource('install.py.in'))
    private = render('foundation-amd64-static-noasm.conf',
                     _resource('foundation-amd64-static-noasm.conf'))
    patches = render('patches.json', _json(_patches()))
    indexes = [render('source-index-%03d.json' % number, _json(value))
               for number, value in enumerate(_source_chunks(context))]
    metadata = _reviewed()
    generated_headers = sorted(metadata['generated_public_headers'])
    original_headers = sorted(name.rsplit('/', 1)[-1]
        for name in context['source_layout']['files']
        if name.startswith('include/openssl/') and name.count('/') == 2 and name.endswith('.h'))
    header_index = render('install-headers.json', _json({
        'original': original_headers, 'generated': generated_headers}))
    if len(rendered) > 32 or sum(len(row['content']) for row in rendered) > 1024**2:
        raise ValueError('Fixed OpenSSL renders exceed closed bounds')
    binary = context['binary_root']
    tree = binary + '/source'
    configuration = binary + '/configdata.pm'
    template = binary + '/makefile.in'
    makefile = binary + '/makefile'
    prepare_arguments = [prepare['path'], '--source-root', context['source_root'],
        '--tree-root', tree, '--build-root', binary, '--patch-spec', patches['path']]
    for index in indexes:
        prepare_arguments += ['--source-index', index['path']]
    commands = [_command(context, 'openssl-prepare', 'generate', 'python', prepare_arguments,
        context['workspace_root'])]
    roles = {'CC': 'compiler', 'LD': 'linker', 'AR': 'archiver',
        'RC': 'resource_compiler', 'MT': 'manifest_tool', 'PERL': 'perl', 'HASHBANGPERL': 'perl'}
    bindings = [key + '=' + contract.original_program(context, role)['declaration']['path']
                for key, role in roles.items()]
    commands.append(_command(context, 'openssl-configure', 'configure', 'perl',
        [tree + '/Configure', '--config=' + private['path'], _TARGET, *_FLAGS,
         '--prefix=' + context['prefix_root'], '--openssldir=' + context['prefix_root'] + '/ssl',
         '--libdir=lib', *bindings], binary))
    commands.append(_command(context, 'openssl-emit-template', 'generate', 'perl',
        [configuration, '--foundation-stage=emit-template'], binary))
    commands.append(_command(context, 'openssl-render-template', 'generate', 'perl',
        [configuration, '--foundation-stage=render-template', template], binary))
    commands.append(_command(context, 'openssl-build-libraries', 'build', 'nmake',
        ['/F', makefile, 'build_libs'], binary))
    library_paths = [binary + '/libcrypto.lib', binary + '/libssl.lib']
    install_arguments = [install['path'], '--source-root', context['source_root'],
        '--prefix', context['prefix_root'], '--header-index', header_index['path']]
    for path in library_paths:
        install_arguments += ['--library', path]
    for name in generated_headers:
        install_arguments += ['--generated-header', binary + '/include/openssl/' + name]
    commands.append(_command(context, 'openssl-install', 'install', 'python', install_arguments,
        binary))
    generated = []

    def produced(consumer, producer, output):
        generated.append({'consumer_command_id': consumer,
            'producing_command_id': producer, 'output': output})

    produced('openssl-configure', 'openssl-prepare', 'build/openssl/source/Configure')
    produced('openssl-emit-template', 'openssl-configure', 'build/openssl/configdata.pm')
    produced('openssl-render-template', 'openssl-configure', 'build/openssl/configdata.pm')
    produced('openssl-render-template', 'openssl-emit-template', 'build/openssl/makefile.in')
    produced('openssl-build-libraries', 'openssl-render-template', 'build/openssl/makefile')
    for name in ('libcrypto.lib', 'libssl.lib'):
        produced('openssl-install', 'openssl-build-libraries', 'build/openssl/' + name)
    for name in generated_headers:
        producer = 'openssl-render-template' if name == 'configuration.h' else 'openssl-build-libraries'
        produced('openssl-install', producer, 'build/openssl/include/openssl/' + name)
    artifacts = {'libraries': {'OpenSSL::Crypto': 'lib/libcrypto.lib',
        'OpenSSL::SSL': 'lib/libssl.lib'}, 'headers': sorted({
            'include/openssl/' + name for name in [*original_headers, *generated_headers]})}
    result = {'commands': commands, 'registration': {
        'stages': [{key: row[key] for key in ('id', 'supplier', 'stage')} for row in commands],
        'produced_tools': {}},
        'source_files': [{'member': name, 'sha256': row['sha256'], 'bytes': row['bytes']}
            for name, row in sorted(context['source_layout']['files'].items())],
        'rendered_files': sorted(rendered, key=lambda row: row['output']),
        'generated_inputs': generated, 'install_artifacts': artifacts}
    return contract.validate_factory_result(context, result)


def reviewed_supplier_commands(supplier, *, identity, source_layout, build_root,
                               prefix_root, source_recipe_bindings):
    if supplier != 'openssl':
        raise ValueError('Exact fixed OpenSSL supplier required')
    context = contract.factory_context(supplier, identity=identity,
        source_layout=source_layout, build_root=build_root, prefix_root=prefix_root,
        source_recipe_bindings=source_recipe_bindings)
    missing = missing_executable_sources(context['source_layout'])
    if missing:
        gaps = ['openssl-executable-source-review-' + name.lower().replace('/', '-').replace('.', '-').replace('_', '-')
                for name in missing]
        raise contract.MissingInputs(gaps)
    return _declarations(context)
