#!/usr/bin/env python3
"""Content-based retained-kernel eligibility and appended-source tripwires.

Path selection is development feedback only. Eligibility always compares a
complete, versioned content projection to an independently pinned inventory.
These source checks are architectural tripwires, not language parsers or a
security boundary; runtime and module validation remain separate checks.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys

from dependency_archive import digest, encoded, object_pairs, read_json
from source_identity import snapshot_paths, portable_executables

PROJECTION = 'foundation-appended-kernel-v2'
SELECTION_COMPARISON = 'foundation-appended-kernel-v2-acquisition-selection-v1'
CONFIGURATION = 'foundation-project.json'
PAYLOAD_ROOTS = ('src-web-appended', 'src-bin-appended')
PRODUCT_METADATA_FILES = frozenset({'README.md', 'LICENSE', 'AGENTS.md'})
TEST_ONLY_ROOTS = ('tests', 'gui/tests')
NARRATIVE_ROOTS = ('docs', '.agent-pending')
# These exact sources compile into the replaceable guest only. They are not
# inputs to the native/browser kernel targets. New SDK files remain conservative
# until reviewed; authoritative root ABI headers/schemas and validators stay in
# the kernel projection. Complete source/SDK inventories retain every file.
GUEST_INPUT_FILES = frozenset({
    'tools/appended_compile.py', 'sdk/appended/guest.c',
    'sdk/appended/include/stdint.h', 'sdk/appended/include/stddef.h',
    'sdk/appended/include/foundation/appended/guest.h',
    'sdk/appended/include/foundation/appended/guest.hpp',
    'sdk/appended/include/foundation/appended/view.h',
    'sdk/appended/include/foundation/appended/providers.h',
    'sdk/appended/include/foundation/appended/providers.hpp',
    'sdk/appended/rust/Cargo.toml', 'sdk/appended/rust/src/abi.rs',
    'sdk/appended/rust/src/bootstrap.rs', 'sdk/appended/rust/src/lib.rs',
    'sdk/appended/rust/src/record.rs', 'sdk/appended/rust/src/providers.rs',
})
GUEST_DOCUMENT_FILES = frozenset({'sdk/appended/README.md'})
# Reviewed pure configuration/container/policy tools. Do not generalize this to
# an appended_* glob: compilation and ABI validation can affect kernel contracts.
COMPOSITION_FILES = frozenset({
    'tools/appended_project.py', 'tools/appended_container.py',
    'tools/appended_policy.py', 'tests/test_appended_project.py',
    'tests/test_appended_container.py', 'tests/test_appended_policy.py',
    'tools/appended_release.py', 'tests/test_appended_release.py',
    'tools/appended_checkout.py', 'tests/test_appended_checkout.py',
    'tools/appended_ci.py', 'tests/test_appended_ci.py',
    'tools/appended_qualification.py', 'tests/test_appended_qualification.py',
    'tools/appended_release_check.py', 'tests/test_appended_release_check.py',
    'tools/appended_delivery.py', 'tests/test_appended_delivery.py',
    'tools/appended_guest_check.py', 'tests/test_appended_guest_check.py',
    'tools/appended_install_check.py', 'tests/test_appended_install_check.py',
    'tools/appended_browser_check.py', 'tests/test_appended_browser_check.py',
    'docs/appended-release-policy.json',
    'tools/ci_changes.py',
    '.github/workflows/appended-compose.yml',
    '.github/appended-retained.json',
})
KERNEL_ROOTS = frozenset({
    'src', 'include', 'gui', 'rust', 'third_party', 'cmake', 'abi', 'sdk',
    'tools', 'tests', '.github',
})
KERNEL_FILES = frozenset({'CMakeLists.txt', 'CMakePresets.json', 'build.sh'})
SHA256 = re.compile(r'[0-9a-f]{64}')


def repository_path(value):
    return (isinstance(value, str) and bool(value) and '\\' not in value and
            not value.startswith('/') and not re.match(r'[A-Za-z]:', value) and
            not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value) and
            all(part not in ('', '.', '..') for part in value.split('/')))


def payload_path(name):
    return repository_path(name) and any(name.startswith(root + '/') for root in PAYLOAD_ROOTS)


def test_only_path(name):
    return repository_path(name) and any(name == root or name.startswith(root + '/') for root in TEST_ONLY_ROOTS)


def narrative_path(name):
    # Only Markdown is reviewed as narrative. Machine policies, screenshots,
    # resources and unknown files below docs/ remain conservative kernel inputs.
    return (repository_path(name) and name.endswith('.md') and
            any(name.startswith(root + '/') for root in NARRATIVE_ROOTS))


def non_kernel_metadata_path(name):
    return repository_path(name) and (name in PRODUCT_METADATA_FILES or name in GUEST_DOCUMENT_FILES or
                                     narrative_path(name) or test_only_path(name))


def guest_tooling_path(name):
    return repository_path(name) and name in GUEST_INPUT_FILES


def guest_input_path(name):
    return guest_tooling_path(name) or repository_path(name) and name in GUEST_DOCUMENT_FILES


def excluded_kernel_input(name):
    return repository_path(name) and (name in PAYLOAD_ROOTS or payload_path(name) or
                                     non_kernel_metadata_path(name) or guest_tooling_path(name))


def pruned_kernel_namespace(name):
    return repository_path(name) and (name in PAYLOAD_ROOTS or payload_path(name) or test_only_path(name))


def classify_paths(paths):
    """Aggregate known payload changes, without making a compatibility claim."""
    if not isinstance(paths, (list, tuple)) or not paths:
        return {'known_changes': False, 'kernel_paths': [], 'unknown_paths': [],
                'actions': [], 'reason': 'complete nonempty changed-path evidence required'}
    kernel, unknown, actions = set(), set(), set()
    for name in paths:
        if not repository_path(name):
            unknown.add(str(name))
        elif name.startswith(PAYLOAD_ROOTS[0] + '/'):
            actions.update(('web-check', 'pack', 'compose'))
        elif name.startswith(PAYLOAD_ROOTS[1] + '/'):
            actions.update(('guest-compile', 'module-check', 'pack', 'compose'))
        elif guest_tooling_path(name):
            # Existing verified modules retain their original compile inputs.
            # Changed SDK/helper bytes require fresh tooling/conformance checks;
            # compare the module's pinned compile inputs before recompiling it.
            actions.update(('guest-tooling-check', 'sdk-insulation', 'binding-conformance',
                            'module-source-identity-check', 'module-check'))
        elif name == CONFIGURATION or name in COMPOSITION_FILES:
            actions.update(('composition-tooling', 'pack', 'compose'))
        elif test_only_path(name):
            actions.update(('test-tooling', 'prebuilt-runtime-check'))
        elif non_kernel_metadata_path(name):
            actions.add('composition-tooling' if name == 'LICENSE' else 'documentation-check')
        elif name in KERNEL_FILES or name.split('/')[0] in KERNEL_ROOTS:
            kernel.add(name)
        else:
            unknown.add(name)
    return {'known_changes': not kernel and not unknown,
            'kernel_paths': sorted(kernel), 'unknown_paths': sorted(unknown),
            'actions': sorted(actions),
            'reason': ('compare pinned kernel input bytes and modes before reuse' if not kernel and not unknown
                       else 'kernel or unclassified changes require explicit kernel maintenance')}


def configuration_projection(root):
    # The shared project validator is authoritative for fields, duplicate keys
    # and combinations. Source existence belongs to payload preparation, not to
    # this kernel inventory; disabled payloads impose no source prerequisite.
    from appended_project import load_project
    project = load_project(root, check_sources=False)
    roots = {name: project.data['appended'][name]['source'] for name in ('web', 'binary')}
    if tuple(roots[name] for name in ('web', 'binary')) != PAYLOAD_ROOTS:
        raise ValueError('kernel projection v2 requires the standard appended source roots')
    return {'schema_version': 1, 'kernel': project.data['kernel'], 'payload_roots': roots}


def kernel_source_tree(root, supplement=None):
    """Describe all current kernel inputs, including unknown files and modes.

    The full source archive remains unchanged. The reviewed omission domains are
    fixed payload roots, test-only trees, Markdown under docs/ and .agent-pending/,
    exact root product metadata, exact composition/guest tools and guest-only
    bindings, and application-only configuration fields. The current kernel
    production graph consumes none as code. Guest compilation/conformance and
    complete SDK identities remain separate prerequisites.
    LICENSE and installed documentation describe the downstream application;
    retained original kernel notices/documentation remain pinned in their source
    and artifact inventories and are never replaced by these downstream inputs.
    Kernel implementations, authoritative ABI inputs, unknown SDK files and
    supplier notices remain conservative inputs.
    A synthetic configuration also represents missing config so adding ordinary
    product identity/presence does not change kernel inputs.
    """
    return _kernel_source_tree(root, supplement, configuration_projection(root))


def _kernel_source_tree(root, supplement, configuration):
    # Keep the v2 source identity unchanged. The comparison caller captures the
    # validated configuration once, so its raw identity and finite alternative
    # below always describe the same configuration observation.
    root = Path(root).resolve(strict=True)
    paths = snapshot_paths(root, supplement, exclude=excluded_kernel_input, prune=pruned_kernel_namespace)
    paths = {name: path for name, path in paths.items()
             if not payload_path(name) and name not in COMPOSITION_FILES}
    executables = portable_executables(root, paths, exclude=excluded_kernel_input)
    if supplement:
        # Preserve the same supplemental portable-mode rules as source_identity.
        from source_identity import selected_files, SUPPLEMENT_PREFIX
        extra = selected_files(supplement)
        executables.difference_update({name for name in executables if name.startswith(SUPPLEMENT_PREFIX)})
        executables.update(SUPPLEMENT_PREFIX + name for name in portable_executables(supplement, extra))
    files = {name: digest(path) for name, path in sorted(paths.items()) if name != CONFIGURATION}
    files[CONFIGURATION] = hashlib.sha256(encoded(configuration)).hexdigest()
    files = dict(sorted(files.items()))
    executables = sorted(executables)
    identity = hashlib.sha256(encoded({'files': files, 'executables': executables})).hexdigest()
    return {'schema_version': 1, 'projection': PROJECTION, 'tree_sha256': identity,
            'files': files, 'executables': executables}


def validate_kernel_inputs(data):
    if isinstance(data, dict) and data.get('projection') == 'foundation-appended-kernel-v1':
        raise ValueError('kernel input projection v1 is unsupported; independently issue a v2 descriptor '
                         'from retained original kernel source; no automatic rebuild or descriptor migration')
    if (not isinstance(data, dict) or set(data) !=
            {'schema_version', 'projection', 'tree_sha256', 'files', 'executables'} or
            type(data['schema_version']) is not int or data['schema_version'] != 1 or
            data['projection'] != PROJECTION):
        raise ValueError('unsupported pinned kernel input projection')
    files, executable = data['files'], data['executables']
    if (not isinstance(files, dict) or not files or CONFIGURATION not in files or
            any(not repository_path(name) or not isinstance(value, str) or not SHA256.fullmatch(value)
                for name, value in files.items()) or
            any(excluded_kernel_input(name) or name in COMPOSITION_FILES for name in files)):
        raise ValueError('invalid pinned kernel file inventory')
    if (not isinstance(executable, list) or any(not isinstance(name, str) for name in executable) or
            executable != sorted(set(executable)) or not set(executable) <= set(files)):
        raise ValueError('invalid pinned kernel executable inventory')
    actual = hashlib.sha256(encoded({'files': files, 'executables': executable})).hexdigest()
    if data['tree_sha256'] != actual:
        raise ValueError('pinned kernel input identity mismatch')
    return data


def retained_eligibility(root, expected, supplement=None):
    """Compare actual bytes/inventory/modes; never invoke a compiler or Git diff."""
    result = {'eligible': False, 'differences': [], 'expected_sha256': None,
              'actual_sha256': None, 'reason': ''}
    try:
        if not expected:
            raise ValueError('missing independently pinned kernel input inventory')
        expected = validate_kernel_inputs(expected)
        result['expected_sha256'] = expected['tree_sha256']
        configuration = configuration_projection(root)
        actual = _kernel_source_tree(root, supplement, configuration)
        result['actual_sha256'] = actual['tree_sha256']
        before_modes, after_modes = set(expected['executables']), set(actual['executables'])
        for name in sorted(set(expected['files']) | set(actual['files'])):
            changes = []
            if name not in expected['files']:
                changes.append('added')
            elif name not in actual['files']:
                changes.append('deleted')
            else:
                if expected['files'][name] != actual['files'][name]: changes.append('content')
                if (name in before_modes) != (name in after_modes): changes.append('executable')
            if changes: result['differences'].append({'path': name, 'changes': changes})
        result['eligible'] = not result['differences']
        result['reason'] = ('complete pinned kernel input inventory matches current bytes and modes'
                            if result['eligible'] else 'kernel inputs changed; explicit kernel maintenance required')
        if result['differences'] == [{'path': CONFIGURATION, 'changes': ['content']}]:
            # Selection chooses where an already built kernel is acquired. It
            # does not alter its implementation. Accept only the other exact
            # canonical enum value, with profile, roots, file inventory, bytes
            # and modes held fixed. This is a comparison policy, never a v2
            # descriptor migration or a replacement for the raw source hash.
            current = configuration['kernel']['selection']
            previous = {'project': 'foundation', 'foundation': 'project'}[current]
            alternative = dict(configuration, kernel=dict(configuration['kernel'], selection=previous))
            alternative_sha = hashlib.sha256(encoded(alternative)).hexdigest()
            if expected['files'][CONFIGURATION] == alternative_sha:
                result.update(eligible=True, comparison_policy=SELECTION_COMPARISON,
                              comparison_sha256=expected['tree_sha256'],
                              selection_metadata_difference={
                                  'path': CONFIGURATION,
                                  'expected_selection': previous, 'actual_selection': current,
                                  'expected_configuration_sha256': alternative_sha,
                                  'actual_configuration_sha256': actual['files'][CONFIGURATION]},
                              reason='complete pinned kernel inputs match under explicit acquisition-selection comparison policy; raw source identities remain distinct')
    except (KeyError, TypeError, ValueError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        result['reason'] = str(error)
    return result


JS_SUFFIXES = frozenset({'.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'})
WEB_SUFFIXES = frozenset({'.html', '.htm', '.svg', '.xhtml', *JS_SUFFIXES})
WEB_METADATA = frozenset({'package.json', 'package-lock.json', 'npm-shrinkwrap.json',
                          'yarn.lock', 'pnpm-lock.yaml', 'bun.lock', 'bun.lockb', '.npmrc'})
LITERAL_OR_COMMENT = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|/\*.*?\*/|//[^\n]*', re.S)
JS_REGEX = re.compile(r'/(?![/*])(?:\\.|[^/\\\n\[]|\[(?:\\.|[^\\\]\n])*\])+/[a-z]*')
JS_IDENTIFIER = re.compile(r'[A-Za-z_$][\w$]*')
BACKEND_IDENTIFIERS = re.compile(
    r'\b(?:SDL_[A-Za-z0-9_]+|Fl_[A-Za-z0-9_]+|(?:Terminal|Framebuffer|Web|Memory|Interactive|Retained)Adapter)\b')
BACKEND_NAMES = frozenset({'fltk', 'sdl', 'sdl2', 'rev', 'terminal', 'framebuffer',
                           'hosted-web', 'wasm', 'windows', 'win32', 'linux', 'darwin',
                           'firefox', 'chrome', 'chromium', 'edge'})
BACKEND_FIELD = r'\b(?:backend|guiBackend|rendererBackend|adapter|platform|userAgent)\b'


def binary_violations(source, name=''):
    """Reject concrete script/toolchain artifacts without banning ordinary words."""
    failures = set()
    path = Path(name)
    if path.suffix.lower() in WEB_SUFFIXES | {'.css'} or path.name in WEB_METADATA or 'node_modules' in path.parts:
        failures.add('script or web-toolchain file in binary application/SDK')
    patterns = (
        (r'(?i)\b[\w@./-]+\.(?:mjs|cjs|jsx|js)(?:\b|[?#])', 'JavaScript file reference'),
        (r'(?i)<\s*script\b|```\s*(?:javascript|js|typescript|ts)\b', 'JavaScript snippet'),
        (r'\b(?:EM_JS|EM_ASM(?:_INT|_DOUBLE)?|emscripten_run_script(?:_int|_string)?)\b', 'embedded JavaScript glue'),
        (r'\b(?:wasm[_-]bindgen|js[_-]sys|web[_-]sys)\b', 'web binding dependency'),
        (r'\bem(?:cc|\+\+)(?=$|[\s\"\x27;)])|[<\"\x27/]emscripten[/\\]|\bfind_package\s*\(\s*Emscripten\b', 'web compiler dependency'),
        (r'(?im)(?:^|[\s\"\x27=;(])(?:npm|npx|pnpm|yarn|bun)\s+(?:install|add|run|exec|ci|build)\b', 'web package-manager dependency'),
        (r'(?im)(?:^|[;\n]|\bCOMMAND)\s*node(?:js)?\s+(?:-[ep]\b|--eval\b|[^\s]+\.(?:mjs|cjs|js)\b)', 'web runtime tool dependency'),
        (r'--(?:js-library|pre-js|post-js)\b|\b(?:node_modules|package-lock\.json)\b', 'web toolchain dependency'),
        (r'\bfunction\s*(?:[A-Za-z_$][\w$]*\s*)?\([^;{}]*\)\s*\{|\b(?:console|document)\s*\.\s*(?:log|getElementById|querySelector)\s*\(', 'JavaScript snippet'),
    )
    for pattern, rule in patterns:
        if re.search(pattern, source): failures.add(rule)
    return sorted(failures)


def template_expressions(value):
    position = 0
    while True:
        opening = value.find('${', position)
        if opening < 0: return
        begin, end, depth = opening + 2, opening + 2, 1
        while end < len(value) and depth:
            token = LITERAL_OR_COMMENT.match(value, end)
            if token:
                end = token.end()
                continue
            depth += (value[end] == '{') - (value[end] == '}')
            end += 1
        if depth: return
        yield value[begin:end - 1]
        position = end


def javascript_tokens(source):
    literals = {}
    def replace(match):
        value = match[0]
        if value.startswith(('//', '/*')):
            return '\n' * value.count('\n')
        key = 'APPENDED_STRING_' + str(len(literals))
        literals[key] = value[1:-1]
        # Template interpolations are executable code, so keep their expressions.
        expressions = []
        if value.startswith('`'):
            for expression in template_expressions(value):
                nested_code, nested_literals = javascript_tokens(expression)
                aliases = {}
                for previous, contents in nested_literals.items():
                    current = 'APPENDED_STRING_' + str(len(literals))
                    literals[current] = contents
                    aliases[previous] = current
                expressions.append(re.sub(r'APPENDED_STRING_\d+', lambda m: aliases.get(m[0], m[0]), nested_code))
        return key + (' ' + ' '.join(expressions) if expressions else '')
    pieces, position, expression = [], 0, True
    while position < len(source):
        token = LITERAL_OR_COMMENT.match(source, position)
        if token:
            pieces.append(replace(token))
            if not token[0].startswith(('//', '/*')): expression = False
            position = token.end()
            continue
        if source[position] == '/' and expression:
            token = JS_REGEX.match(source, position)
            if token:
                pieces.append(replace(token))
                expression, position = False, token.end()
                continue
        token = JS_IDENTIFIER.match(source, position)
        if token:
            pieces.append(token[0])
            expression = token[0] in {'return', 'throw', 'case', 'delete', 'void', 'typeof',
                                      'yield', 'await', 'new', 'in', 'of'}
            position = token.end()
            continue
        character = source[position]
        pieces.append(character)
        if source[position:position + 2] in ('++', '--'):
            pieces.append(character)
            position += 2
            continue
        if not character.isspace():
            expression = character in '([{=,:;!?~+-*/%&|^<>'
        position += 1
    return ''.join(pieces), literals


def concrete_module(name):
    normalized = posixpath.normpath(name.replace('\\', '/')).lower()
    parts = normalized.split('/')
    return ((any(part in ('backends', 'adapters', 'hosts') for part in parts) and
             any(Path(part).stem in BACKEND_NAMES for part in parts)) or
            re.search(r'(?:^|/)(?:gui|platform)/(?:hosts?|devices?|drivers?|backends?|adapters?)(?:/|$)', normalized) is not None or
            ('gui' in parts and any(Path(part).stem in BACKEND_NAMES for part in parts)) or
            normalized in ('fltk', 'sdl', 'sdl2', 'rev', 'serialport', 'usb', 'node:serialport') or
            normalized.startswith(('node:', '@serialport/', '@sdl/', 'wasm-bindgen', 'web-sys', 'js-sys')))


def web_violations(source, name=''):
    if name and Path(name).suffix.lower() not in WEB_SUFFIXES and Path(name).name != 'package.json':
        return []  # Passive resources and documentation are not executable scripts.
    failures = set()
    code, literals = javascript_tokens(source)
    # Bracket notation and optional access express the same concrete dependency
    # as a dotted field. Keep unrelated application string contents opaque.
    code = re.sub(r'\[\s*(APPENDED_STRING_\d+)\s*\]',
                  lambda m: '.' + literals[m[1]] if literals.get(m[1]) in
                  {'backend', 'guiBackend', 'rendererBackend', 'adapter', 'platform', 'userAgent',
                   'serial', 'usb', 'hid', 'ccall', 'cwrap', 'instantiate', 'instantiateStreaming',
                   'compile', 'compileStreaming', 'Module', 'Instance'} else m[0], code)
    imports = re.findall(r'\b(?:from|import|require)\s*(?:\(\s*)?(APPENDED_STRING_\d+)', code)
    for key in imports:
        if concrete_module(literals[key]): failures.add('concrete backend/device/web-runtime import: ' + literals[key])
    if BACKEND_IDENTIFIERS.search(code): failures.add('concrete GUI backend identifier')
    if re.search(r'\b(?:WebAssembly\s*(?:\?\.|\.)\s*(?:instantiate(?:Streaming)?|compile(?:Streaming)?|Module|Instance)|'
                 r'Module\s*(?:\?\.|\.)\s*(?:ccall|cwrap|HEAP\w+|_\w+)|'
                 r'navigator\s*(?:\?\.|\.)\s*(?:serial|usb|hid)|wasm_bindgen)\b', code):
        failures.add('concrete browser runtime/device implementation')
    # A backend switch is identified by its own case values. Product labels in
    # the body and unrelated literals in compound conditions remain harmless.
    for match in re.finditer(r'\bswitch\s*\(', code):
        begin, depth, end = match.end(), 1, match.end()
        while end < len(code) and depth:
            depth += (code[end] == '(') - (code[end] == ')')
            end += 1
        condition = code[begin:end - 1]
        if not re.search(BACKEND_FIELD, condition, re.I):
            continue
        opening = code.find('{', end)
        if opening < 0: continue
        closing, depth = opening + 1, 1
        while closing < len(code) and depth:
            depth += (code[closing] == '{') - (code[closing] == '}')
            closing += 1
        values = {literals[key].lower() for key in
                  re.findall(r'\bcase\s+(APPENDED_STRING_\d+)\s*:', code[opening:closing]) if key in literals}
        if values & BACKEND_NAMES:
            failures.add('application branches on concrete GUI/platform backend')
    # Comparisons used in ternaries and short-circuit expressions are branches
    # too. Requiring a concrete backend value preserves ordinary product text.
    for condition in re.findall(BACKEND_FIELD + r'\s*(?:===?|!==?)\s*APPENDED_STRING_\d+|'
                                r'APPENDED_STRING_\d+\s*(?:===?|!==?)\s*' + BACKEND_FIELD, code, re.I):
        if any(literals[key].lower() in BACKEND_NAMES for key in re.findall(r'APPENDED_STRING_\d+', condition)):
            failures.add('application branches on concrete GUI/platform backend')
    for key in re.findall(BACKEND_FIELD + r'\s*\.\s*(?:includes|startsWith|endsWith|match)\s*\(\s*(APPENDED_STRING_\d+)', code):
        if literals.get(key, '').lower() in BACKEND_NAMES:
            failures.add('application branches on concrete GUI/platform backend')
    if Path(name).suffix.lower() in ('.html', '.htm', '.svg', '.xhtml'):
        # HTML outside scripts is application text. Inspect script elements and
        # event handlers separately, not the prose/attribute names themselves.
        failures = set()
        for attributes, script in re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', source, re.I | re.S):
            failures.update(web_violations(script, 'inline.js'))
            for quoted, single, plain in re.findall(r'\bsrc\s*=\s*(?:\"([^\"]*)\"|\x27([^\x27]*)\x27|([^\s\"\x27>]+))', attributes, re.I):
                module = html.unescape(quoted or single or plain)
                if concrete_module(module): failures.add('concrete backend/device/web-runtime import: ' + module)
        for handler in re.findall(r'\bon[a-z]+\s*=\s*(?:\"([^\"]*)\"|\x27([^\x27]*)\x27|([^\s\"\x27>]+))', source, re.I):
            failures.update(web_violations(html.unescape(handler[0] or handler[1] or handler[2]), 'inline.js'))
    if Path(name).name == 'package.json':
        try:
            document = json.loads(source, object_pairs_hook=object_pairs)
            for field in ('dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'):
                dependencies = document.get(field, {})
                if isinstance(dependencies, dict):
                    for module in dependencies:
                        if concrete_module(module): failures.add('concrete backend/device/web-runtime import: ' + module)
        except (ValueError, AttributeError):
            failures.add('invalid web dependency manifest')
    return sorted(failures)


def audit(root, binary_roots=('src-bin-appended', 'sdk/appended'), web_roots=('src-web-appended',)):
    """Inspect explicitly selected source/SDK scopes; missing scopes are optional."""
    root = Path(root).resolve(strict=True)
    failures, count, visited = [], 0, set()
    for scopes, checker in ((binary_roots, binary_violations), (web_roots, web_violations)):
        for scope in scopes:
            if not repository_path(scope): raise ValueError('audit scope must be a canonical relative path')
            directory = root / scope
            current = root
            for part in scope.split('/'):
                current = current / part
                if current.is_symlink(): raise ValueError('linked appended audit scope: ' + scope)
            if not directory.exists(): continue
            if not directory.is_dir(): raise ValueError('appended audit scope is not a directory: ' + scope)
            for path in sorted(directory.rglob('*')):
                if path.is_symlink(): raise ValueError('linked appended source: ' + path.relative_to(root).as_posix())
                if not path.is_file(): continue
                identity = (path, checker)
                if identity in visited: continue
                visited.add(identity)
                count += 1
                name = path.relative_to(root).as_posix()
                raw = path.read_bytes()
                try: source = raw.decode('utf-8') if b'\0' not in raw else ''
                except UnicodeDecodeError: source = ''
                for rule in checker(source, name): failures.append({'path': name, 'rule': rule})
    return {'schema_version': 1, 'ok': not failures, 'files_scanned': count,
            'violations': sorted(failures, key=lambda item: (item['path'], item['rule']))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('identity', 'eligibility', 'audit'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--supplement', type=Path)
    parser.add_argument('--kernel', type=Path, help='independently pinned kernel descriptor containing kernel_inputs')
    args = parser.parse_args(argv)
    if args.action == 'identity': result = kernel_source_tree(args.root, args.supplement)
    elif args.action == 'audit': result = audit(args.root)
    else:
        if not args.kernel: parser.error('eligibility requires --kernel')
        result = retained_eligibility(args.root, read_json(args.kernel).get('kernel_inputs'), args.supplement)
    print(encoded(result).decode(), end='')
    return 0 if result.get('eligible', result.get('ok', True)) else 1


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error: raise SystemExit(str(error))
