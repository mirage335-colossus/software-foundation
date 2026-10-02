#!/usr/bin/env python3
"""Thin hosted adapters; substantive byte and lifecycle checks live in tools/."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_plan as ci
import github_release as delivery
import dependency_store
import coverage as evidence


def retained_graphics(url, archive):
    """Read an exact private own-repository asset or an explicit HTTPS mirror."""
    from urllib.parse import urlsplit
    import windows_graphics
    parsed = urlsplit(url)
    if parsed.hostname != 'api.github.com':
        return windows_graphics.fetch_retained(url, archive)
    repository = delivery.location(value('GITHUB_REPOSITORY'))
    prefix = '/repos/'+repository+'/releases/assets/'
    if (parsed.scheme != 'https' or parsed.netloc != 'api.github.com' or parsed.query or parsed.fragment or
            not parsed.path.startswith(prefix) or not parsed.path[len(prefix):].isdigit() or
            int(parsed.path[len(prefix):]) < 1):
        raise ValueError('private graphics asset must belong to this repository')
    remote = delivery.Remote(repository)
    row = remote.transport.json(parsed.path.lstrip('/'))
    expected = windows_graphics.lock()['archive']
    if (row.get('id') != int(parsed.path[len(prefix):]) or row.get('name') != expected['name'] or
            row.get('state') != 'uploaded' or row.get('size') != expected['size'] or
            row.get('digest') != 'sha256:'+expected['sha256']):
        raise ValueError('private graphics asset differs from locked archive')
    if archive.exists() or archive.is_symlink():
        receipt = windows_graphics.verify_archive(archive)
    else:
        # A failed transfer remains an invalid input, never a supplier fallback.
        remote.download(row, archive, expected['sha256'])
        receipt = windows_graphics.verify_archive(archive)
    receipt['acquisition'] = 'private-repository-retention'
    receipt['asset_id'] = row['id']
    return receipt


def value(name):
    text = os.environ.get(name, '')
    if not text: raise ValueError('missing workflow input: ' + name)
    return text


def boolean(name):
    item = value(name)
    if item not in ('true', 'false'): raise ValueError('invalid boolean: ' + name)
    return item == 'true'


def write(path, item):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_new(path, item)


def output(name, item):
    with Path(value('GITHUB_OUTPUT')).open('a', encoding='utf-8') as stream:
        stream.write(name + '=' + json.dumps(item, separators=(',', ':')) + '\n')


def scalar_output(name, item):
    text = str(item).lower() if isinstance(item, bool) else str(item)
    if any(c in text for c in '\r\n'): raise ValueError('workflow output must occupy one line')
    with Path(value('GITHUB_OUTPUT')).open('a', encoding='utf-8') as stream:
        stream.write(name + '=' + text + '\n')


def storage_context():
    # Reusable jobs belong to their caller's exact run, not a new callee run.
    reference = value('GITHUB_WORKFLOW_REF')
    prefix = value('GITHUB_REPOSITORY') + '/.github/workflows/'
    if not reference.startswith(prefix) or '@' not in reference[len(prefix):]:
        raise ValueError('workflow reference does not belong to this repository')
    filename = reference[len(prefix):].split('@', 1)[0]
    if not ci.re.fullmatch(r'[a-zA-Z0-9_-]+\.ya?ml', filename):
        raise ValueError('invalid workflow identity')
    return dict(repository=value('GITHUB_REPOSITORY'), run_id=int(value('GITHUB_RUN_ID')),
        attempt=int(value('GITHUB_RUN_ATTEMPT')), source_commit=value('GITHUB_SHA'), workflow=filename)


def bundle_inputs(specification):
    """Preserve the selected common-root layout, with no implicit entire-tree upload."""
    import glob
    declarations = [line.strip() for line in specification.splitlines() if line.strip()]
    if not declarations or len(declarations) > 100 or len(specification) > 65536:
        raise ValueError('bounded explicit bundle paths required')
    bases, matches = [], set()
    for text in declarations:
        path = Path(text)
        if path.is_absolute() or '..' in path.parts or '\\' in text or ':' in text:
            raise ValueError('bundle path must be relative to the checkout')
        prefix = []
        for part in path.parts:
            if glob.has_magic(part): break
            prefix.append(part)
        base = Path(*prefix)
        if len(prefix) == len(path.parts) and not (ROOT/base).is_dir(): base=base.parent
        bases.append(ROOT/base)
        matches.update(Path(item).absolute() for item in glob.glob(str(ROOT/path), recursive=True))
    base = Path(os.path.commonpath(bases))
    if base != ROOT and ROOT not in base.parents: raise ValueError('bundle root escaped checkout')
    if base in matches:
        matches.remove(base); matches.update(base.iterdir())
    return base, sorted(str(path.relative_to(base)).replace('\\','/') for path in matches)


def store_bundle():
    import ci_transport
    base, paths = bundle_inputs(value('BUNDLE_PATHS'))
    if not paths: raise ValueError('bundle selection contains no files')
    name=value('BUNDLE_NAME')
    pointer=ci_transport.publish_bundle(**storage_context(), name=name, root=base, paths=paths,
        runner_name=value('RUNNER_NAME'))
    write(ROOT/'build/transport-pointers'/ (name+'.json'), pointer)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(value('GITHUB_STEP_SUMMARY')).open('a',encoding='utf-8') as stream:
            stream.write('Verified CI bundle pointer: `'+json.dumps(pointer,sort_keys=True)+'`\n')
    if os.environ.get('GITHUB_OUTPUT'): output('bundle_pointer',pointer)


def fetch_bundle(name, output, *, allow_failed=False):
    result=ci.restore_run_bundle(**storage_context(), name=name, output=Path(output), allow_failed=allow_failed)
    write(ROOT/'build/transport-receipts'/(name+'.json'),result)
    return result


def sdk_recipe(target, profile):
    if profile not in ('core', 'all-gui'): raise ValueError('unknown SDK capability profile')
    if profile == 'all-gui' and target.startswith('linux-'):
        return ROOT / ('third_party/sdk/gui-aarch64/recipe.json' if target.endswith('aarch64') else 'third_party/sdk/gui-x86_64/recipe.json')
    if profile == 'all-gui' and target == 'windows-x86_64':
        return ROOT / 'third_party/sdk/windows-gui/windows-base.json'
    if target.startswith('linux-'):
        return ROOT / ('third_party/sdk/aarch64/recipe.json' if target.endswith('aarch64') else 'third_party/sdk/recipe.json')
    return ROOT / ('third_party/sdk/windows-base.json' if target.startswith('windows-') else 'third_party/sdk/wasm.json')


def sdk_identity(target, profile):
    if target not in (*ci.STANDARD, 'browser-wasm32'):
        raise ValueError('unknown SDK target')
    recipe = sdk_recipe(target, profile)
    if target.startswith('linux-'):
        import distro_sdk
        return distro_sdk.recipe_id(recipe)
    if target == 'windows-x86_64':
        import sdk_windows
        return sdk_windows.recipe_identity(recipe)
    import sdk_wasm
    return sdk_wasm.recipe_identity(recipe)


def ordinary_directory(path):
    """Do not follow links or Windows reparse points in an owned directory."""
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or
            getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
        raise ValueError('SDK isolation requires ordinary directories: ' + str(path))
    return info.st_dev, info.st_ino


def absent(path):
    try: path.lstat()
    except FileNotFoundError: return True
    return False


@contextmanager
def isolated_sdk_producer(target, profile, recipe, origin, files):
    """Exclude original producer paths during all synchronous consumer work.

    The caller owns this build tree exclusively and must stop producer writers
    first. This is relocation qualification, not a hostile-process sandbox.
    Never delete or overwrite an unexpected entry during recovery.
    """
    parent = ROOT / 'build'; original = parent / 'sdk-inputs'
    receipt_path = parent / 'sdk-isolation.json'
    if not absent(receipt_path): raise FileExistsError('SDK isolation receipt must be new')
    parent_id = ordinary_directory(parent)
    receipt = dict(schema_version=1, status='started', target=target, profile=profile,
        recipe_id=recipe, group_files=files, origin=origin,
        source_commit=value('GITHUB_SHA'), run_id=value('GITHUB_RUN_ID'),
        attempt=int(value('GITHUB_RUN_ATTEMPT')), original=str(original),
        initial_state='unchecked', quarantine=None, disposition='unchanged',
        checkpoints=[], consumers='not-completed')
    holder = moved = original_id = holder_id = failure = None

    def check_absent(label):
        if ordinary_directory(parent) != parent_id:
            raise ValueError('SDK isolation parent identity changed; preserve trees')
        if not absent(original):
            raise ValueError('SDK producer path was recreated; preserve both trees')
        if moved is not None and (ordinary_directory(holder) != holder_id or
                                  ordinary_directory(moved) != original_id):
            raise ValueError('SDK quarantine identity changed; preserve trees')
        receipt['checkpoints'].append(label)

    try:
        if absent(original):
            receipt['initial_state'] = 'absent'
        else:
            original_id = ordinary_directory(original)
            receipt['initial_state'] = 'present'
            holder = Path(tempfile.mkdtemp(prefix='sdk-producer-quarantine-', dir=parent))
            holder_id = ordinary_directory(holder); moved = holder / 'sdk-inputs'
            receipt['quarantine'] = str(moved)
            receipt['disposition'] = 'preserved'
            # The private holder is new. Any rename error has an unknown outcome;
            # retain both spellings for explicit inspection instead of retrying.
            original.rename(moved)
        check_absent('before-install-and-core')
        yield check_absent
        check_absent('after-all-consumers')
        receipt['consumers'] = 'completed'
        if moved is not None:
            moved.rename(original)
            if (ordinary_directory(parent) != parent_id or ordinary_directory(original) != original_id or
                    not absent(moved) or ordinary_directory(holder) != holder_id):
                raise ValueError('SDK restoration identity differs; preserve trees')
            holder.rmdir()  # Only the exact now-empty owned holder may be removed.
            receipt['disposition'] = 'restored'
        else:
            receipt['disposition'] = 'remained-absent'
        receipt['status'] = 'passed'
    except BaseException as error:
        failure = error
        receipt['status'] = 'failed'
        receipt['error_type'] = type(error).__name__
        # Incomplete consumers or uncertain filesystem operations never trigger
        # restoration, recursive deletion, success receipts or publication.
        raise
    finally:
        try:
            if ordinary_directory(parent) != parent_id:
                raise ValueError('SDK isolation parent changed; preserve trees and receipt destination')
            write(receipt_path, receipt)
        except BaseException as publication_error:
            if failure is not None: raise publication_error from failure
            raise


def retain_sdk_group(target, profile):
    """Retain checked bytes for diagnosis/retry, without consumer approval."""
    identity = sdk_identity(target, profile)
    origin = evidence.load(ROOT / 'build/sdk-origin.json')
    if origin.get('recipe') != identity:
        raise ValueError('retained SDK identity differs from the selected current recipe')
    files = dependency_store.verify_group(ROOT / 'build/sdk-group', identity)
    receipt = dict(schema_version=1, status='verified', qualification='unqualified',
        publication_approved=False, target=target, profile=profile, recipe_id=identity,
        source_commit=value('GITHUB_SHA'), run_id=value('GITHUB_RUN_ID'),
        attempt=int(value('GITHUB_RUN_ATTEMPT')), files=files)
    write(ROOT / 'build/sdk-retention.json', receipt)
    return receipt


def retained_request(target, profile, *, producer_host=False):
    raw = os.environ.get('SDK_RETAINED_INPUT', '')
    if value('SDK_SOURCE') != 'retained':
        if raw.strip(): raise ValueError('retained SDK input requires explicit source=retained')
        return None
    if len(raw.encode('utf-8')) > 16384: raise ValueError('retained SDK input exceeds supported size')
    request = delivery.parse(raw)
    # Planning runs on Linux for every target; enforce recipe bytes on the selected producer host.
    identity = sdk_identity(target, profile) if producer_host else request.get('recipe_id') if isinstance(request, dict) else None
    return ci.retained_sdk_request(request, value('GITHUB_REPOSITORY'), target, profile, identity)


def main(command):
    os.chdir(ROOT)
    (ROOT / 'build').mkdir(exist_ok=True)
    if command == 'bundle-store':
        store_bundle()
    elif command == 'bundle-fetch':
        fetch_bundle(value('BUNDLE_NAME'),value('BUNDLE_OUTPUT'),
                     allow_failed=os.environ.get('BUNDLE_ALLOW_FAILED')=='true')
    elif command == 'fetch-sdk-bundles':
        targets=[*ci.STANDARD,'browser-wasm32'] if value('SDK_TARGET')=='all' else [value('SDK_TARGET')]
        if any(target not in (*ci.STANDARD,'browser-wasm32') for target in targets): raise ValueError('unknown SDK target')
        for target in targets:
            fetch_bundle('sdk-group-'+target+'-'+value('GITHUB_RUN_ATTEMPT'),'build/sdk-groups/'+target)
    elif command == 'fetch-application-bundles':
        for target in evidence.load(Path('build/source/recipes.json')):
            fetch_bundle('application-'+target+'-'+value('GITHUB_RUN_ATTEMPT'),'build/packages/'+target)
    elif command == 'fetch-evidence-bundles':
        for item in evidence.executions(evidence.load(Path('build/check-plan.json'))):
            fetch_bundle('evidence-'+item['id']+'-'+value('GITHUB_RUN_ATTEMPT'),
                         'build/evidence/'+item['id'],allow_failed=True)
    elif command == 'candidate-aggregate':
        import test_plan
        selected = delivery.parse(value('CANDIDATE_TARGETS'))
        if not isinstance(selected, dict) or set(selected) != {'include'} or not isinstance(selected['include'], list):
            raise ValueError('complete candidate target matrix required')
        rows = selected['include']
        if any(not isinstance(row, dict) or set(row) != {'target', 'runner'} or row['target'] not in ci.STANDARD for row in rows):
            raise ValueError('unknown candidate target')
        targets = [row['target'] for row in rows]
        if not targets or len(set(targets)) != len(targets):
            raise ValueError('missing or duplicate candidate targets')
        diagnostic = boolean('DEVFAST')
        scopes = ['core'] if diagnostic else ['core', 'tools', 'integration']
        for target in targets:
            reports = []
            for scope in scopes:
                destination = Path('build/candidate-results') / target / scope
                fetch_bundle('source-' + target + '-' + scope + '-' + value('GITHUB_RUN_ATTEMPT'), destination)
                reports.append(destination / ('candidate-' + scope + '.json'))
            write(Path('build/candidate-results') / target / 'coverage.json',
                  test_plan.candidate_merge(reports, diagnostic=diagnostic))
    elif command == 'sdk-import-legacy':
        raw=value('LEGACY_INPUT')
        if len(raw.encode('utf-8'))>16384: raise ValueError('legacy import request exceeds supported size')
        target,profile=value('TARGET'),value('SDK_PROFILE')
        identity=sdk_identity(target,profile)
        request=delivery.parse(raw)
        imported=ci.import_legacy_sdk(value('GITHUB_REPOSITORY'),request,target,profile,identity,
            ROOT/'build/sdk-group',proof_output=ROOT/'build/legacy-proof')
        write(ROOT/'build/sdk-import.json',imported)
        write(ROOT/'build/sdk-origin.json',dict(origin='retained',recipe=identity,
            qualification='unqualified',publication_approved=False,legacy_import=imported))
        retain_sdk_group(target,profile)
    elif command == 'sdk-import-request':
        context=storage_context();target,profile=value('TARGET'),value('SDK_PROFILE')
        if context['workflow']!='sdk-import.yml': raise ValueError('import request requires explicit import workflow')
        pointers={kind:evidence.load(ROOT/'build/transport-pointers'/
            (f'sdk-{kind}-{target}-{context["attempt"]}.json')) for kind in ('group','proof')}
        for kind,pointer in pointers.items():
            if (any(pointer.get(key)!=item for key,item in context.items()) or
                pointer.get('name')!=f'sdk-{kind}-{target}-{context["attempt"]}' or
                pointer.get('job_id')!=pointers['group'].get('job_id')):
                raise ValueError('import bundle pointers do not identify one exact producer')
        request=dict(schema_version=2,**context,target=target,profile=profile,
            recipe_id=sdk_identity(target,profile),job_id=pointers['group']['job_id'],
            **{kind:dict(manifest_id=pointer['manifest']['id'],manifest_sha256=pointer['manifest']['sha256'])
               for kind,pointer in pointers.items()})
        ci.retained_sdk_request(request,context['repository'],target,profile,request['recipe_id'])
        write(ROOT/'build/import-retained-input.json',request)
        output('retained_input',request)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with Path(value('GITHUB_STEP_SUMMARY')).open('a',encoding='utf-8') as stream:
                stream.write('Exact unqualified retained SDK request (no publication approval):\n```json\n'+
                    json.dumps(request,indent=2,sort_keys=True)+'\n```\n')
    elif command == 'sdk-plan':
        if value('SDK_SOURCE') == 'retained' and value('TARGET') == 'all':
            raise ValueError('retained SDK reuse selects one exact target per dispatch')
        retained_request(value('TARGET'), value('SDK_PROFILE'))
        if value('SDK_PROFILE') == 'all-gui':
            import screenshots
            screenshots.gui_input_selection(value('GITHUB_REPOSITORY'), delivery.parse(value('GUI_INPUT')))
        targets = [*ci.STANDARD, 'browser-wasm32']
        if value('TARGET') != 'all': targets = [value('TARGET')]
        if any(t not in (*ci.STANDARD, 'browser-wasm32') for t in targets): raise ValueError('unknown SDK target')
        output('matrix', {'include': [{'target': t, 'runner': ci.STANDARD.get(t, 'ubuntu-24.04')} for t in targets]})
    elif command == 'sdk-inputs':
        identity = sdk_identity(value('TARGET'), value('SDK_PROFILE'))
        request = retained_request(value('TARGET'), value('SDK_PROFILE'), producer_host=True)
        origin = (ci.retained_sdk(value('GITHUB_REPOSITORY'), request, value('TARGET'), value('SDK_PROFILE'),
                  identity, Path('build/sdk-group')) if request is not None else
                  ci.maintenance_base(value('GITHUB_REPOSITORY'), identity, Path('build/sdk-group'), source=value('SDK_SOURCE')))
        write('build/sdk-origin.json', origin)
    elif command == 'sdk-retain':
        retain_sdk_group(value('TARGET'), value('SDK_PROFILE'))
        output('retained', True)
    elif command in ('graphics-maintain', 'graphics-input'):
        ci.assert_host('windows-x86_64')
        import windows_graphics
        archive = ROOT / 'build/host-graphics/mesa-windows.7z'
        archive.parent.mkdir(parents=True, exist_ok=True)
        receipt = (windows_graphics.fetch(archive, network=True) if command == 'graphics-maintain' else
                   retained_graphics(value('GRAPHICS_ARCHIVE_URL'), archive))
        write('build/host-graphics/acquisition.json', receipt)
    elif command == 'sdk-produce':
        target = value('TARGET'); recipe = sdk_recipe(target, value('SDK_PROFILE'));  jobs = int(value('JOBS'))
        if target != 'browser-wasm32': ci.assert_host(target)
        origin = evidence.load(Path('build/sdk-origin.json'))
        if origin['origin'] in ('base', 'retained'):
            result = {'recipe_id': origin['recipe']}
        elif target.startswith('linux-'):
            import distro_sdk
            distro_sdk.fetch(recipe, ROOT / 'build/sdk-inputs', jobs)
            result = distro_sdk.build(recipe, ROOT / 'build/sdk-inputs', ROOT / 'build/sdk-group', jobs)
        elif target == 'windows-x86_64':
            import sdk_windows
            provenance = evidence.load(recipe)
            selected = evidence.load(ROOT / 'build/windows-toolchain.json')
            provenance.update(linker_version=selected['LinkerVersion'], windows_sdk=selected['WindowsSdk'],
                              tools_version=selected['ToolsVersion'], installation_path=selected['InstallationPath'])
            write('build/windows-provenance.json', provenance)
            for action in ('fetch', 'build'):
                argv = [sys.executable, 'tools/sdk_windows.py', action, '--recipe-file', str(recipe),
                        '--provenance', 'build/windows-provenance.json', '--cache', 'build/sdk-inputs', '--jobs', str(jobs)]
                if action == 'build': argv += ['--output', 'build/sdk-group']
                subprocess.run(argv, check=True)
            result = {'recipe_id': sdk_windows.recipe_identity(recipe)}
        else:
            import sdk_wasm
            sdk_wasm.fetch(recipe, ROOT / 'build/sdk-inputs', network=True)
            result = sdk_wasm.prepare(recipe, ROOT / 'build/sdk-inputs', ROOT / 'build/sdk-group')
        checksums = list(Path('build/sdk-group').glob('sdk-*-SHA256SUMS'))
        if len(checksums) != 1: raise ValueError('producer did not return one complete SDK group')
        recipe_id = checksums[0].name[4:-len('-SHA256SUMS')]
        files = dependency_store.verify_group(Path('build/sdk-group'), recipe_id)
        if recipe_id != origin['recipe']: raise ValueError('produced SDK identity differs from selected recipe')
        pending = []
        with isolated_sdk_producer(target, value('SDK_PROFILE'), recipe_id, origin['origin'], files) as isolated:
            consumer = ROOT / 'build/sdk-consumer'
            pending.append((consumer, ci.prepared_check(target, recipe_id, Path('build/sdk-group'), consumer,
                                                       jobs, defer_qualification=True)))
            isolated('after-core')
            if value('SDK_PROFILE') == 'all-gui':
                ci.gui_group_module().verify(ROOT / 'build/gui-group')
                isolated('before-gui-install')
                consumer = ROOT / 'build/sdk-gui-consumer'
                pending.append((consumer, ci.prepared_check(target, recipe_id, Path('build/sdk-group'), consumer,
                    jobs, ROOT / 'build/gui-group', defer_qualification=True,
                    graphics_archive=ROOT / 'build/host-graphics/mesa-windows.7z' if target == 'windows-x86_64' else None)))
        isolation = evidence.sha(ROOT / 'build/sdk-isolation.json')
        for consumer, receipt in pending:
            receipt['producer_isolation'] = {'file': '../sdk-isolation.json', 'sha256': isolation}
            write(consumer / 'qualification.json', receipt)
        request = dict(repository=value('GITHUB_REPOSITORY'), recipe=recipe_id, group='build/sdk-group', source_commit=value('GITHUB_SHA'))
        write('build/sdk-publication-plan.json', delivery.publish_base(**request))
    elif command == 'publish-bases':
        for group in sorted(Path('build/sdk-groups').iterdir()):
            if not group.is_dir(): raise ValueError('unexpected SDK transport entry')
            files = list(group.glob('sdk-*-SHA256SUMS'))
            if len(files) != 1: raise ValueError('missing complete SDK output')
            recipe = files[0].name[4:-len('-SHA256SUMS')]
            result = delivery.publish_base(value('GITHUB_REPOSITORY'), recipe, group, value('GITHUB_SHA'), execute=True)
            write('build/receipts/base-' + recipe + '.json', result)
    elif command == 'apt-native-smoke':
        import artifact, release_check
        release_check.apt_preflight('linux-x86_64')
        write('build/apt-evidence/started.json', dict(operation=command, target='linux-x86_64',
              backend='core', status='started', source_commit=os.environ.get('GITHUB_SHA')))
        subprocess.run([sys.executable, 'tools/build.py', 'package', 'release', '--portable', '--jobs', '2',
                        '--build-dir', 'build/apt-smoke'], check=True)
        packages = ROOT / 'build/apt-smoke/packages'
        archives = list(packages.glob('*.tar.gz'))
        if len(archives) != 1: raise ValueError('one native archive required for APT mechanism check')
        archive = archives[0]; manifest = archive.with_name(archive.name + '.json')
        write(manifest, artifact.describe(archive))
        entry = dict(archive=archive.name, manifest=manifest.name, sha256=evidence.sha(archive), target='linux-x86_64')
        result = release_check.run_apt(packages, entry, 'core', ROOT / 'build/apt-smoke/work', ROOT / 'build/apt-evidence')
        write('build/apt-evidence/result.json', result)
    elif command == 'gui-input':
        import screenshots
        raw = value('GUI_INPUT')
        if len(raw.encode('utf-8')) > 16384:
            raise ValueError('GUI input selector exceeds supported size')
        result = screenshots.fetch_gui_input(value('GITHUB_REPOSITORY'),
            delivery.parse(raw), ROOT / 'build/gui-group')
        write(ROOT / 'build/gui-origin.json', result)
    elif command == 'gui-maintain':
        lock = evidence.load(ROOT / 'third_party/gui-boundary.lock.json')
        source = ROOT / 'build/gui-upstream'
        subprocess.run(['git', 'clone', '--config', 'core.autocrlf=false', '--config', 'core.eol=lf', '--no-checkout', lock['upstream'], str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', lock['revision']], check=True)
        ci.gui_group_module().export(source, Path('build/gui-group'))
        plan = ci.publish_gui_group(value('GITHUB_REPOSITORY'), Path('build/gui-group'), value('GITHUB_SHA'))
        write('build/gui-publication-plan.json', plan)
        if os.environ.get('GITHUB_OUTPUT'): output('redistributable', plan['redistributable'])
    elif command == 'native-gui-check':
        ci.prepared_check(value('TARGET'), value('RECIPE'), ROOT / 'build/base' / value('RECIPE'),
                          ROOT / 'build/native-gui', int(value('JOBS')), ROOT / 'build/gui-group',
                          graphics_archive=ROOT / 'build/host-graphics/mesa-windows.7z' if value('TARGET') == 'windows-x86_64' else None)
    elif command == 'publish-gui':
        write('build/receipts/gui-publication.json', ci.publish_gui_group(value('GITHUB_REPOSITORY'), Path('build/gui-group'), value('GITHUB_SHA'), execute=True))
    elif command == 'application-plan':
        recipes = delivery.parse(value('RECIPES').encode())
        matrix = ci.release_matrix(recipes, value('PROFILE'))
        write('build/recipes.json', recipes)
        output('matrix', matrix)
        gui = None
        if value('PROFILE') == 'all-gui':
            ci.fetch_gui_group(value('GITHUB_REPOSITORY'), value('GUI_GROUP'), Path('build/gui-group'))
            restored = ci.gui_group_module().restore(Path('build/gui-group'), Path('build/gui-restored'))
            gui = Path(restored['source'])
        ci.source_archive(ROOT / 'build/source.tar.gz', gui)
    elif command == 'fetch-sdk':
        delivery.fetch_base(value('GITHUB_REPOSITORY'), value('RECIPE'), Path('build/base') / value('RECIPE'))
    elif command == 'application-build':
        ci.prepared_package(value('TARGET'), value('RECIPE'), (ROOT / 'build/base' / value('RECIPE')),
                            ROOT / 'build/source/source.tar.gz', ROOT / 'build/produced', int(value('JOBS')),
                            graphics_archive=ROOT / 'build/host-graphics/mesa-windows.7z'
                            if value('TARGET') == 'windows-x86_64' and value('PROFILE') == 'all-gui' else None)
    elif command == 'assemble':
        recipes = evidence.load(Path('build/source/recipes.json'))
        for recipe in sorted(set(recipes.values())):
            delivery.fetch_base(value('GITHUB_REPOSITORY'), recipe, Path('build/base') / recipe)
        ci.assemble_release(Path('build/source/source.tar.gz'), Path('build/packages'), Path('build/base'), Path('build/candidate'), value('PROFILE'))
        tag = os.environ.get('TAG') or 'candidate-' + value('GITHUB_RUN_ID') + '-attempt-' + value('GITHUB_RUN_ATTEMPT')
        request = dict(repository=value('GITHUB_REPOSITORY'), tag=tag, directory='build/candidate',
                       source_commit=value('GITHUB_SHA'), packager_commit=value('GITHUB_SHA'),
                       publication_id='run-' + value('GITHUB_RUN_ID') + '-attempt-' + value('GITHUB_RUN_ATTEMPT'),
                       experiment=boolean('EXPERIMENT'))
        write('build/publication-request.json', request)
        plan = delivery.publish_candidate(**request)
        write('build/publication-plan.json', plan)
        write('build/delivery.json', plan['delivery'])
        for name,item in dict(tag=tag,inventory_sha256=plan['delivery']['inventory_sha256'],
                              source_commit=value('GITHUB_SHA'),delivery_sha256=evidence.sha(Path('build/delivery.json'))).items():
            scalar_output(name,item)
    elif command == 'publish-candidate':
        request = evidence.load(Path('build/publication-request.json'))
        if request['source_commit'] != value('GITHUB_SHA') or request['packager_commit'] != value('GITHUB_SHA'):
            raise ValueError('publication input differs from checked-out workflow revision')
        write('build/receipts/publication.json', delivery.publish_candidate(**request, execute=True))
        scalar_output('published',True)
    elif command == 'certification-plan':
        ci.fetch_candidate(value('GITHUB_REPOSITORY'), value('TAG'), value('INVENTORY'), Path('build/fetched'))
        shutil.move('build/fetched/candidate', 'build/candidate')
        shutil.move('build/fetched/delivery.json', 'build/delivery.json')
        matrix = ci.qualification_plan(ROOT / 'build/candidate', value('PROFILE'), ROOT / 'build/check-plan.json')
        output('matrix', matrix)
    elif command in ('check-prerequisites', 'check'):
        plan = evidence.load(Path('build/check-plan.json'))
        evidence.validate(plan); evidence.check_inputs(plan, ROOT)
        matches = [item for item in plan['checks'] if item['id'] == value('CHECK')]
        if len(matches) != 1: raise ValueError('check not in frozen inventory')
        item = matches[0]
        if ci.platform.system() == 'Linux' and ci.needs_browser_prerequisite(item['backend'], item['scope']):
            directory = ROOT / 'build/prerequisites' / value('CHECK')
            if command == 'check-prerequisites':
                receipt = ci.install_browser_prerequisite(item['target'], item['environment'], item['backend'], directory)
                receipt.update(plan=plan['id'], check=item['id'], run_id=value('GITHUB_RUN_ID'),
                               attempt=int(value('GITHUB_RUN_ATTEMPT')))
                write(directory / 'browser.json', receipt)
            elif not (directory / 'browser.json').is_file():
                raise ValueError('run privileged browser prerequisite setup before unprivileged qualification')
        if command == 'check':
            # The invoked release check independently binds this receipt to the
            # frozen plan, actual host, package/browser bytes and evidence.
            result = evidence.run_execution(plan, value('CHECK'), ROOT, ROOT / 'build/evidence' / value('CHECK'),
                                       value('GITHUB_RUN_ID'), int(value('GITHUB_RUN_ATTEMPT')))
            if result['status'] != 'passed': raise ValueError('required qualification did not pass')
    elif command in ('certificate', 'attach-certificate'):
        identity = evidence.load(Path('build/delivery.json'))
        plan = evidence.load(Path('build/check-plan.json'))
        reports = [evidence.result_path(plan, x['id'], Path('build/evidence')) for x in plan['checks']]
        policy = ROOT / 'docs/release-policy.json'; directory = ROOT / 'build/candidate'
        if command == 'certificate':
            import certify_release
            result = certify_release.certify(directory, ci.module('release').verify_release(directory), plan, reports,
                       evidence.load(policy), value('PROFILE'), identity['experiment'])
            write('build/certificate.json', result)
            for name,item in dict(certificate_sha256=evidence.sha(Path('build/certificate.json')),
                certification_run=value('GITHUB_RUN_ID'),certification_attempt=value('GITHUB_RUN_ATTEMPT'),
                inventory_sha256=identity['inventory_sha256'],eligible_for_promotion=result['eligible_for_promotion']).items():
                scalar_output(name,item)
            write('build/attachment-plan.json', delivery.attach_certificate(value('GITHUB_REPOSITORY'), value('TAG'), directory,
                    identity, Path('build/certificate.json'), Path('build/check-plan.json'), policy, value('PROFILE'),
                    reports, int(value('GITHUB_RUN_ATTEMPT'))))
        else:
            write('build/receipts/attachment.json', delivery.attach_certificate(value('GITHUB_REPOSITORY'), value('TAG'), directory,
                    identity, Path('build/certificate.json'), Path('build/check-plan.json'), policy, value('PROFILE'),
                    reports, int(value('GITHUB_RUN_ATTEMPT')), execute=True))
            scalar_output('attached',True)
    elif command in ('promotion-plan', 'promote'):
        if command == 'promotion-plan':
            ci.fetch_candidate(value('GITHUB_REPOSITORY'), value('TAG'), value('INVENTORY'), Path('build/fetched'))
            shutil.move('build/fetched/candidate', 'build/candidate')
            shutil.move('build/fetched/delivery.json', 'build/delivery.json')
        request = dict(repository=value('GITHUB_REPOSITORY'), tag=value('TAG'), directory=Path('build/candidate'),
                       delivery=evidence.load(Path('build/delivery.json')), policy=Path('docs/release-policy.json'), profile=value('PROFILE'),
                       run_id=value('CERTIFICATION_RUN'), attempt=int(value('CERTIFICATION_ATTEMPT')), certificate_sha256=value('CERTIFICATE'))
        write('build/receipts/' + command + '.json', delivery.promote(**request, execute=command == 'promote'))
        if command=='promote': scalar_output('promoted',True)
    else: raise ValueError('unknown workflow operation')


if __name__ == '__main__':
    try: main(sys.argv[1])
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        uncertain = sys.argv[1] in ('bundle-store', 'publish-bases', 'publish-gui', 'publish-candidate', 'attach-certificate', 'promote')
        receipt = {'ok': False, 'uncertain': uncertain or bool(getattr(error, 'uncertain', False)),
                   'operation': sys.argv[1], 'error': str(error),
                   'action': 'reconcile remote state before retry' if uncertain else 'repair prerequisites and inspect retained evidence'}
        try: write('build/receipts/failure.json', receipt)
        except OSError: pass
        raise SystemExit(json.dumps(receipt))
