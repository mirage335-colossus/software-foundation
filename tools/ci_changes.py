#!/usr/bin/env python3
"""Conservative local-Git selection for development feedback, never qualification."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

# Reviewed narrative documents and the isolated optional editor may omit
# application work. Shared helpers, application runtime and unknown paths stay full.
DOCUMENTS = frozenset({
    'README.md', 'AGENTS.md', 'COMPILE', 'RELEASE',
    'docs/README.md', 'docs/architecture.md', 'docs/ci.md',
    'docs/development-speed.md', 'docs/testing.md', 'docs/validation.md',
    'docs/documentation.md', 'docs/maintenance.md',
    'docs/agent-coordination.md', 'docs/agent-recipes.md', 'docs/agent-lifecycle.md',
})
COMMIT = re.compile(r'[0-9a-f]{40}')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_capacity
# Domains cover dependencies expressed through command lines, generated recipes,
# fixtures and retained inputs, in addition to the source-reference closure below.
TOOL_DOMAINS = (
    frozenset('agent_board agent_edit agent_migrate agent_publish agent_record agent_session agent_stress check_agent_record'.split()),
    frozenset('apt_repo artifact certification distribution_release distro_channel distro_check distro_client github_release latest_release legacy_artifacts package_notices portability release release_check verify_abi verify_legacy_preservation'.split()),
    frozenset('dependencies dependency_archive prepare_dependencies sdk sdk_paths sdk_retention windows_compiler windows_graphics'.split()),
    frozenset('gui_boundary gui_source_group gui_visual gallery_browser screenshots package_wasm rev_probe host_contracts'.split()),
    frozenset('build build_capacity ci_plan ci_changes coverage qualification_tasks run_tests source_identity test_plan'.split()),
    frozenset('ci_apt ci_artifacts ci_cleanup ci_cleanup_repository ci_cleanup_previous ci_cleanup_drafts ci_cleanup_expired ci_retry ci_transport container_job workflow_storage'.split()),
    frozenset('rust_sdk rust_build rust_component rust_workflow build ci_plan source_identity test_plan release release_check offline_acceptance container_job'.split()),
    frozenset('appended appended_project appended_container appended_policy appended_compile appended_wasm appended_release appended_checkout appended_ci ci_changes'.split()),
)


def repository_path(path):
    """Only canonical relative Git paths can authorize an omission."""
    return (isinstance(path, str) and bool(path) and '\\' not in path and
            not re.match(r'[A-Za-z]:', path) and
            not any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in path) and
            all(part not in ('', '.', '..') for part in path.split('/')))


def editor_path(path):
    """Editor sources and local checks are outside the application graph."""
    return repository_path(path) and (path == 'COMPILE-editor' or path.startswith('editor/'))


def infrastructure_suites(paths, root=ROOT):
    """Select whole suites; unknown/deleted infrastructure requires every suite.

    Source references deliberately overapproximate Python imports: literal dynamic
    loader names and subprocess script names count too. Domain edges include
    non-Python coupling. Missing inventories or unreadable sources fail selection,
    never silently remove a suite from feedback.
    """
    suites = {p.stem[5:]: p for p in (root / 'tests').glob('test_*.py')}
    modules = {p.stem: p for p in (root / 'tools').glob('*.py')}
    if not suites or not modules:
        raise ValueError('complete tooling source and suite inventory required')
    all_suites = sorted(suites)
    if not paths:
        return all_suites
    changed, direct = set(), set()
    for path in paths:
        if not repository_path(path):
            return all_suites
        if path in DOCUMENTS or editor_path(path):
            continue
        if path.startswith('tools/') and Path(path).suffix == '.py' and path.count('/') == 1:
            name = Path(path).stem
            if name not in modules or not any(name in domain for domain in TOOL_DOMAINS):
                return all_suites
            changed.add(name)
        elif path.startswith('tests/test_') and Path(path).suffix == '.py' and path.count('/') == 1:
            name = Path(path).stem[5:]
            if name not in suites:
                return all_suites
            direct.add(name)
            changed.add(name)
        elif path.startswith('gui/'):
            changed.update(TOOL_DOMAINS[3])
        elif path.startswith(('rust/', 'third_party/rust/')):
            changed.update(TOOL_DOMAINS[6])
        elif path.startswith(('src/', 'include/', 'tests/')) and Path(path).suffix in ('.cpp', '.hpp', '.h', '.c', '.cc'):
            continue  # Native application contracts remain in focused/shared-gui jobs.
        else:
            return all_suites
    if not changed:
        return sorted(direct)
    def referenced(file):
        result = set()
        tree = ast.parse(file.read_text(encoding='utf-8'))
        metadata_literals = set()
        if file.parent == root / 'tools' and file.name == 'appended_policy.py':
            # These reviewed path sets classify component ownership; naming a
            # script here does not execute/import that script. Skip only pure
            # literal path elements, preserving all other references in this
            # module (including a changed/nonliteral assignment expression).
            tables = {'COMPOSITION_FILES', 'GUEST_INPUT_FILES', 'GUEST_DOCUMENT_FILES'}
            for statement in tree.body:
                targets = statement.targets if isinstance(statement, ast.Assign) else (
                    [statement.target] if isinstance(statement, ast.AnnAssign) else [])
                if len(targets) != 1 or not isinstance(targets[0], ast.Name) or targets[0].id not in tables:
                    continue
                value = statement.value
                if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and
                        value.func.id == 'frozenset' and len(value.args) == 1 and not value.keywords):
                    value = value.args[0]
                if (isinstance(value, (ast.Set, ast.List, ast.Tuple)) and
                        all(isinstance(item, ast.Constant) and repository_path(item.value) for item in value.elts)):
                    metadata_literals.update(id(item) for item in value.elts)
        for node in ast.walk(tree):
            if id(node) in metadata_literals:
                continue
            if isinstance(node, ast.Import):
                result.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result.add(node.module.split('.')[0])
                result.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Exact literal dynamic-loader names and script paths count;
                # explanatory prose and selector tables do not create edges.
                if re.fullmatch(r'[a-z][a-z0-9_]*', node.value):
                    result.add(node.value)
                result.update(re.findall(r'(?<![A-Za-z0-9_])([a-z][a-z0-9_]*)\.py(?:$|[^A-Za-z0-9_])', node.value))
        return result | {name.removeprefix('test_') for name in result if name.startswith('test_')}
    references = {name: referenced(file) for name, file in modules.items()}
    tests = {name: referenced(file) for name, file in suites.items()}
    initial = set(changed)
    for domain in TOOL_DOMAINS:
        if domain & initial:
            changed.update(domain)
    selected = direct | (changed & suites.keys())
    previous = None
    while previous != (changed, selected):
        previous = (set(changed), set(selected))
        dependencies = changed | {'test_' + name for name in selected}
        changed.update(name for name, inputs in references.items() if inputs & dependencies)
        selected.update(changed & suites.keys())
        # A selected test is not a changed production module of the same name.
        # Explicit test_ imports/paths still carry shared-fixture dependencies
        # into both real production consumers and other complete test suites.
        dependencies = changed | {'test_' + name for name in selected}
        selected.update(name for name, inputs in tests.items() if inputs & dependencies)
    return sorted(selected)


def load_supervisor():
    spec = importlib.util.spec_from_file_location('feedback_process_tree', ROOT / 'tools/process_tree.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool_jobs(value):
    if value == 'auto':
        return value
    if value == '':
        raise argparse.ArgumentTypeError('test jobs must be auto or a positive integer')
    try:
        return build_capacity.test_jobs(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def run_tool_suites(suites, output, jobs=None, root=ROOT):
    """Bounded parallel whole-suite execution with the qualification runner policy."""
    if not suites or len(set(suites)) != len(suites):
        raise ValueError('nonempty unique suites required')
    jobs = build_capacity.test_jobs(jobs if jobs is not None else os.environ.get('CTEST_PARALLEL_LEVEL'))
    known = {p.stem[5:] for p in (root / 'tests').glob('test_*.py')}
    if not set(suites) <= known:
        raise ValueError('unknown tooling suite')
    workers = min(jobs, len(suites))
    environment = build_capacity.worker_environment(os.environ, workers, capacity=jobs)
    output.mkdir(parents=True, exist_ok=False)
    processes = load_supervisor()
    def execute(name):
        receipt = output / (name + '.json')
        with (output / (name + '.log')).open('wb') as log:
            owner = processes.launch([sys.executable, '-B', str(root / 'tools/run_tests.py'),
                                      '--suite', name, '--output', str(receipt)], root, log, env=environment)
            try:
                owner.wait(timeout=900)
                code = owner.finish()
            except (subprocess.TimeoutExpired, processes.ProcessTreeError) as error:
                code = 1
                log.write(('\nSuite process ownership failed: ' + str(error) + '\n').encode())
            finally:
                owner.close()  # Join descendants before reading logs or publishing receipts.
        # run_tests rejects skips, expected failures, empty/duplicate inventories
        # and unrecorded cases. Never substitute unittest's weaker exit policy.
        passed = code == 0 and receipt.is_file()
        if passed:
            try:
                passed = json.loads(receipt.read_text())['status'] == 'passed'
            except (ValueError, KeyError):
                passed = False
        print(name + ': ' + ('passed' if passed else 'FAILED'), flush=True)
        if not passed:
            print((output / (name + '.log')).read_text(errors='replace'), flush=True)
        return {'suite': name, 'status': 'passed' if passed else 'failed'}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(execute, suites))
    summary = {'schema_version': 1, 'scope': 'development-feedback', 'suites': results,
               'status': 'passed' if all(r['status'] == 'passed' for r in results) else 'failed'}
    (output / 'summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
    return summary


def classify(paths):
    """An absent/incomplete change inventory never authorizes omitted work."""
    paths = list(paths)
    canonical = bool(paths) and all(repository_path(path) for path in paths)
    docs_only = canonical and all(path in DOCUMENTS for path in paths)
    editor_only = canonical and all(path in DOCUMENTS or editor_path(path) for path in paths)
    scope = 'documents' if docs_only else 'editor' if editor_only else 'full'
    reason = {'documents': 'Only reviewed narrative documents changed.',
              'editor': 'Only isolated optional editor paths and reviewed narrative documents changed.',
              'full': 'Source, policy, unknown paths or an empty change set require full feedback.'}
    return {'schema_version': 1, 'scope': scope,
            'build': scope == 'full', 'gui': scope == 'full', 'workflow_lint': scope == 'full',
            'changed_paths': paths, 'tool_suites': infrastructure_suites(paths),
            'reason': reason[scope]}


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20).stdout


def commit(value):
    if not isinstance(value, str) or not COMMIT.fullmatch(value) or value == '0' * 40:
        raise ValueError('an exact nonzero commit is required')
    return value


def changed_paths(root, event_name, event, expected_head):
    """Compare the tested merge/tree with its exact event baseline, without APIs.

    Depth-two checkouts contain a PR merge's first parent. A multi-commit push
    may lack its previous tip; that condition deliberately selects full work.
    --no-renames makes moves include both deleted and added paths.
    """
    head = commit(expected_head)
    if git(root, 'rev-parse', 'HEAD').decode().strip() != head:
        raise ValueError('checked-out source differs from the event commit')
    if event_name == 'pull_request':
        base = commit(event['pull_request']['base']['sha'])
        if git(root, 'rev-parse', 'HEAD^1').decode().strip() != base:
            raise ValueError('the tested PR merge does not have the event base parent')
        commit(event['pull_request']['head']['sha'])
        if git(root, 'rev-parse', 'HEAD^2').decode().strip() != event['pull_request']['head']['sha']:
            raise ValueError('the tested PR merge does not have the event head parent')
    elif event_name == 'push':
        base = commit(event['before'])
        if commit(event['after']) != head or event.get('deleted'):
            raise ValueError('push event does not identify the checked-out live tip')
    else:
        raise ValueError('unsupported feedback event')
    raw = git(root, 'diff', '--name-only', '--no-renames', '-z', base, head, '--')
    if raw and not raw.endswith(b'\0'):
        raise ValueError('incomplete changed-path output')
    if not raw:
        return []
    items = raw[:-1].split(b'\0')
    if not all(items):
        raise ValueError('empty changed-path record')
    return [item.decode('utf-8', errors='strict') for item in items]


APPENDED_FEEDBACK_SUITES = frozenset({'appended_project', 'appended_policy', 'appended_container',
                                     'appended_wasm', 'appended_compile', 'appended_release', 'appended_entry',
                                     'appended_checkout', 'appended_ci'})
REVIEWED_FEEDBACK_TEST_SUITES = APPENDED_FEEDBACK_SUITES | {'source_identity', 'ci_changes'}


def appended_suites(paths=()):
    suites = set(APPENDED_FEEDBACK_SUITES)
    suites.update(Path(path).stem[5:] for path in paths if repository_path(path) and
                  path.startswith('tests/test_') and path.count('/') == 1 and path.endswith('.py') and
                  Path(path).stem[5:] in REVIEWED_FEEDBACK_TEST_SUITES)
    if any(not (ROOT / 'tests' / ('test_' + name + '.py')).is_file() for name in suites):
        raise ValueError('complete appended tooling suite inventory required')
    return sorted(suites)


def unselected_test_paths(paths):
    from appended_policy import test_only_path
    return sorted(path for path in paths if test_only_path(path) and not (
        path.startswith('tests/test_') and path.count('/') == 1 and path.endswith('.py') and
        Path(path).stem[5:] in REVIEWED_FEEDBACK_TEST_SUITES))


def inactive_payload_feedback(paths, *, root=ROOT):
    """Disabled payload edits need tooling feedback, with no reuse assertion."""
    result = {'schema_version': 1, 'scope': 'appended-inactive',
            'build': False, 'gui': False, 'workflow_lint': False,
            'changed_paths': paths, 'tool_suites': [],
            'retained_eligible': False, 'maintenance_required': False,
            'composition_requested': False, 'actions': ['composition-tooling'],
            'qualification': 'development-feedback-only', 'payload_execution': 'not-run',
            'reason': 'only inactive payload or guest tooling/documentation inputs changed; no guest compile or kernel reuse requested'}
    try:
        from appended_policy import (COMPOSITION_FILES, audit, classify_paths, guest_input_path,
                                     guest_tooling_path, non_kernel_metadata_path)
        metadata = [path for path in paths if non_kernel_metadata_path(path) or
                    guest_tooling_path(path) or path in COMPOSITION_FILES]
        result['actions'] = sorted((set(result['actions']) | set(classify_paths(metadata)['actions'])) -
                                   {'guest-compile', 'module-check', 'module-source-identity-check', 'pack', 'compose'})
        if any(guest_input_path(path) for path in paths):
            result['insulation'] = audit(root, binary_roots=('sdk/appended',), web_roots=())
            if not result['insulation']['ok']:
                result.update(scope='appended-maintenance', maintenance_required=True,
                              reason='guest SDK source insulation failed; explicit source correction required')
                return result
        result['test_tooling_required'] = unselected_test_paths(paths)
        result['tool_suites'] = appended_suites(paths)
    except (KeyError, TypeError, ValueError, OSError) as error:
        result.update(scope='appended-maintenance', maintenance_required=True, reason=str(error))
    return result


def selected_kernel_contract(project, descriptor, payload_requirements=None):
    """Check selected capabilities without pretending a package was inspected."""
    from appended_container import _compatible, _requirements
    if project.kernel_profile != 'auto' and descriptor['profile'] != project.selected_profile:
        raise ValueError('retained kernel profile differs from explicitly selected kernel.profile; '
                         'select a compatible retained kernel or explicit kernel maintenance')
    components = {name: {'present': getattr(project, name).enabled} for name in ('web', 'binary')}
    baseline = {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []}
    _compatible(SimpleNamespace(index={'components': components, 'requires': baseline}), descriptor)
    if payload_requirements is not None:
        _requirements(payload_requirements)
        _compatible(SimpleNamespace(index={'components': components, 'requires': payload_requirements}), descriptor)
    return {'requirement_checks': ('project-profile-and-baseline-abi-only' if payload_requirements is None
                                   else 'project-profile-and-explicit-package-requirements'),
            'package_requirements_checked': payload_requirements is not None}


def appended_feedback(root, paths, project, kernel_inputs, *, kernel_descriptor=None,
                      payload_requirements=None, error=None, history_error=None):
    """Retained-only feedback cannot fall through to a native/kernel build."""
    from appended_policy import audit, classify_paths, retained_eligibility
    result = {'schema_version': 1, 'scope': 'appended-maintenance',
              'build': False, 'gui': False,
              'workflow_lint': any(repository_path(path) and path.startswith('.github/') for path in paths),
              'changed_paths': paths, 'tool_suites': [],
              'retained_eligible': False, 'maintenance_required': True,
              'requirement_checks': 'unverified', 'package_requirements_checked': False,
              'qualification': 'development-feedback-only',
              'payload_execution': 'not-run'}
    selection = classify_paths(paths)
    result['actions'] = selection['actions']
    if project is not None:
        applicable = [path for path in paths
                      if not (repository_path(path) and
                              ((not project.web.enabled and path.startswith(project.web.source + '/')) or
                               (not project.binary.enabled and path.startswith(project.binary.source + '/'))))]
        result['actions'] = classify_paths(applicable)['actions']
        if not project.binary.enabled:
            result['actions'] = sorted(set(result['actions']) -
                                       {'guest-compile', 'module-check', 'module-source-identity-check'})
        result['mode'] = project.mode
        # When comparison history is absent, component presence supplies the
        # feedback actions. It never substitutes for content compatibility.
        if history_error:
            result['actions'] = sorted({'composition-tooling', 'pack', 'compose'} |
                                      ({'web-check'} if project.web.enabled else set()) |
                                      ({'guest-tooling-check', 'sdk-insulation', 'binding-conformance',
                                        'module-source-identity-check', 'module-check'}
                                       if project.binary.enabled else set()))
    if error:
        result['reason'] = error
        return result
    if kernel_descriptor is not None:
        try:
            from appended_container import validate_descriptor
            validate_descriptor(kernel_descriptor)
            descriptor_inputs = kernel_descriptor.get('kernel_inputs')
            if kernel_inputs is not None and kernel_inputs != descriptor_inputs:
                raise ValueError('kernel input inventory differs from the authenticated kernel descriptor')
            kernel_inputs = descriptor_inputs
        except (KeyError, TypeError, ValueError, OSError) as failure:
            result['reason'] = 'retained kernel contract unavailable: ' + str(failure)
            return result
    compatibility = retained_eligibility(root, kernel_inputs)
    result['kernel_inputs'] = compatibility
    result['reason'] = compatibility['reason']
    if history_error:
        result['comparison_history'] = 'unavailable; complete pinned kernel content comparison used'
    # Only the selected application components impose source prerequisites. The
    # SDK is an independently shipped binary contract and is audited if present.
    try:
        from appended_project import load_project
        project = load_project(root, check_sources=True)
        binary = (project.binary.source, 'sdk/appended') if project.binary.enabled else ('sdk/appended',)
        web = (project.web.source,) if project.web.enabled else ()
        insulation = audit(root, binary_roots=binary, web_roots=web)
        result['insulation'] = insulation
        result['tool_suites'] = appended_suites(paths)
        result['test_tooling_required'] = unselected_test_paths(paths)
        if not insulation['ok']:
            result['reason'] = 'appended source insulation failed; explicit source correction required'
            return result
    except (KeyError, TypeError, ValueError, OSError) as failure:
        result['reason'] = 'appended source checks unavailable: ' + str(failure)
        return result
    if compatibility['eligible']:
        if kernel_descriptor is None:
            result['reason'] = ('kernel input inventory matches, but capabilities are unverified: '
                                'a complete independently authenticated kernel descriptor is required '
                                'before retained reuse; no kernel build was selected')
            return result
        try:
            result.update(selected_kernel_contract(project, kernel_descriptor, payload_requirements))
        except (KeyError, TypeError, ValueError, OSError) as failure:
            result['reason'] = 'retained kernel contract is incompatible: ' + str(failure)
            return result
        result.update(scope='appended', retained_eligible=True, maintenance_required=False)
    return result


def select(root, event_name, event, expected_head, *, kernel_inputs=None, kernel_descriptor=None,
           payload_requirements=None, appended=False, appended_error=None):
    """Use Git for conventional feedback and pinned contents for appended reuse.

    API callers own independent authentication of kernel_descriptor. The CLI
    authenticates it with an explicit SHA-256; a project never supplies its own
    trusted pin. Legacy kernel_inputs-only callers retain source diagnostics but
    cannot establish capability compatibility or retained eligibility. Optional
    payload_requirements use the existing package requires format; absent actual
    requirements, eligibility covers project profiles and baseline ABI only.
    """
    from appended_project import load_project
    root = Path(root).resolve()
    project, project_error = None, None
    try:
        project = load_project(root, check_sources=False)
    except (KeyError, TypeError, ValueError, OSError) as error:
        project_error = 'invalid appended project configuration: ' + str(error)
    retained_route = (appended or kernel_inputs is not None or kernel_descriptor is not None or
                      payload_requirements is not None or project_error or
                      project is not None and project.selected_profile != 'minimal')
    if retained_route:
        history_error = None
        try:
            paths = changed_paths(root, event_name, event, expected_head)
        except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
            paths, history_error = [], type(error).__name__
        return appended_feedback(root, paths, project, kernel_inputs,
                                 kernel_descriptor=kernel_descriptor, payload_requirements=payload_requirements,
                                 error=project_error or appended_error, history_error=history_error)
    try:
        paths = changed_paths(root, event_name, event, expected_head)
        from appended_policy import COMPOSITION_FILES, guest_input_path, non_kernel_metadata_path, payload_path
        if (paths and any(payload_path(path) or guest_input_path(path) for path in paths) and
                all(payload_path(path) or guest_input_path(path) or non_kernel_metadata_path(path) or
                    path in COMPOSITION_FILES for path in paths)):
            return inactive_payload_feedback(paths, root=root)
        return classify(paths)
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        result = classify([])
        result['reason'] = 'Complete change inventory unavailable; full feedback selected (' + type(error).__name__ + ').'
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--event', type=Path, default=os.environ.get('GITHUB_EVENT_PATH'))
    parser.add_argument('--event-name', default=os.environ.get('GITHUB_EVENT_NAME', ''))
    parser.add_argument('--head', default=os.environ.get('GITHUB_SHA', ''))
    parser.add_argument('--kernel-descriptor', type=Path,
                        default=os.environ.get('FOUNDATION_APPENDED_KERNEL_DESCRIPTOR'),
                        help='retained-only feedback with an independently pinned kernel descriptor')
    parser.add_argument('--kernel-descriptor-sha256',
                        default=os.environ.get('FOUNDATION_APPENDED_KERNEL_DESCRIPTOR_SHA256'))
    parser.add_argument('--github-output', type=Path, default=os.environ.get('GITHUB_OUTPUT'))
    parser.add_argument('--summary', type=Path, default=os.environ.get('GITHUB_STEP_SUMMARY'))
    parser.add_argument('--run-tool-suites', action='store_true')
    parser.add_argument('--tool-output', type=Path, default=Path('build/changed-tools'))
    parser.add_argument('--tool-jobs', type=tool_jobs,
                        help='auto or a positive worker count; default is resource-aware')
    args = parser.parse_args(argv)
    try:
        event = json.loads(args.event.read_text(encoding='utf-8')) if args.event else {}
    except (OSError, ValueError):
        event = {}
    kernel_descriptor, appended_error = None, None
    explicit_appended = args.kernel_descriptor is not None or args.kernel_descriptor_sha256 is not None
    if explicit_appended:
        try:
            from appended_container import load_kernel_descriptor
            if args.kernel_descriptor is None or args.kernel_descriptor_sha256 is None:
                raise ValueError('retained feedback requires both a kernel descriptor and independent SHA-256')
            kernel_descriptor = load_kernel_descriptor(args.kernel_descriptor, args.kernel_descriptor_sha256)
            if kernel_descriptor.get('kernel_inputs') is None:
                raise ValueError('pinned kernel descriptor has no kernel input inventory')
        except (KeyError, TypeError, ValueError, OSError) as error:
            appended_error = str(error)
    result = select(args.root, args.event_name, event, args.head, kernel_descriptor=kernel_descriptor,
                    appended=explicit_appended, appended_error=appended_error)
    if args.github_output:
        with args.github_output.open('a', encoding='utf-8') as stream:
            for key in ('build', 'gui', 'workflow_lint'):
                stream.write(f'{key}={str(result[key]).lower()}\n')
            stream.write('tools=' + str(bool(result['tool_suites'])).lower() + '\n')
            stream.write('scope=' + result['scope'] + '\n')
            if result['scope'].startswith('appended'):
                stream.write('retained_eligible=' + str(result['retained_eligible']).lower() + '\n')
                stream.write('maintenance_required=' + str(result['maintenance_required']).lower() + '\n')
    if args.summary:
        with args.summary.open('a', encoding='utf-8') as stream:
            stream.write('Development feedback: ' + result['scope'] + '. ' + result['reason'] + '\n')
            if result['scope'] == 'documents':
                stream.write('Documentation checks run; compile, GUI and workflow syntax work omitted.\n')
            elif result['scope'] == 'editor':
                stream.write('Documentation checks run; application compile, GUI, workflow syntax and tooling suites omitted. Editor checks remain explicit and local.\n')
            elif result['scope'] == 'appended-inactive':
                stream.write('Inactive payload feedback runs tooling only; no guest compilation, '
                             'composition or retained-kernel eligibility is claimed.\n')
            elif result['scope'].startswith('appended'):
                stream.write('Retained-only feedback: no native or shared-GUI fallback build is permitted. '
                             'Payload execution and release qualification remain separate.\n')
            if result.get('test_tooling_required'):
                stream.write('Changed test harnesses require separate tooling or prebuilt-runtime checks; '
                             'see test_tooling_required in the selector JSON. These checks have not passed.\n')
            stream.write('This selection does not qualify a candidate or release.\n')
    print(json.dumps(result, sort_keys=True))
    if result.get('maintenance_required'):
        return 1
    if args.run_tool_suites and result['tool_suites']:
        return 0 if run_tool_suites(result['tool_suites'], args.tool_output.resolve(), args.tool_jobs)['status'] == 'passed' else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
