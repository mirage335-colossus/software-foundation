#!/usr/bin/env python3
"""Thin hosted adapters; substantive byte and lifecycle checks live in tools/."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_plan as ci
import github_release as delivery
import dependency_store
import coverage as evidence


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


def sdk_recipe(target, profile):
    if profile not in ('core', 'all-gui'): raise ValueError('unknown SDK capability profile')
    if profile == 'all-gui' and target.startswith('linux-'):
        return ROOT / ('third_party/sdk/gui-aarch64/recipe.json' if target.endswith('aarch64') else 'third_party/sdk/gui-x86_64/recipe.json')
    if profile == 'all-gui' and target == 'windows-x86_64':
        return ROOT / 'third_party/sdk/windows-gui/windows-base.json'
    if target.startswith('linux-'):
        return ROOT / ('third_party/sdk/aarch64/recipe.json' if target.endswith('aarch64') else 'third_party/sdk/recipe.json')
    return ROOT / ('third_party/sdk/windows-base.json' if target.startswith('windows-') else 'third_party/sdk/wasm.json')


def main(command):
    os.chdir(ROOT)
    (ROOT / 'build').mkdir(exist_ok=True)
    if command == 'sdk-plan':
        targets = [*ci.STANDARD, 'browser-wasm32']
        if value('TARGET') != 'all': targets = [value('TARGET')]
        if any(t not in (*ci.STANDARD, 'browser-wasm32') for t in targets): raise ValueError('unknown SDK target')
        output('matrix', {'include': [{'target': t, 'runner': ci.STANDARD.get(t, 'ubuntu-24.04')} for t in targets]})
    elif command == 'sdk-inputs':
        target = value('TARGET'); recipe = sdk_recipe(target, value('SDK_PROFILE'))
        if target.startswith('linux-'):
            import distro_sdk
            identity = distro_sdk.recipe_id(recipe)
        elif target == 'windows-x86_64':
            import sdk_windows
            identity = sdk_windows.recipe_identity(recipe)
        else:
            import sdk_wasm
            identity = sdk_wasm.recipe_identity(recipe)
        write('build/sdk-origin.json', ci.maintenance_base(value('GITHUB_REPOSITORY'), identity,
              Path('build/sdk-group'), source=value('SDK_SOURCE')))
    elif command in ('graphics-maintain', 'graphics-input'):
        ci.assert_host('windows-x86_64')
        import windows_graphics
        archive = ROOT / 'build/host-graphics/mesa-windows.7z'
        archive.parent.mkdir(parents=True, exist_ok=True)
        receipt = (windows_graphics.fetch(archive, network=True) if command == 'graphics-maintain' else
                   windows_graphics.fetch_retained(value('GRAPHICS_ARCHIVE_URL'), archive))
        write('build/host-graphics/acquisition.json', receipt)
    elif command == 'sdk-produce':
        target = value('TARGET'); recipe = sdk_recipe(target, value('SDK_PROFILE'));  jobs = int(value('JOBS'))
        if target != 'browser-wasm32': ci.assert_host(target)
        origin = evidence.load(Path('build/sdk-origin.json'))
        if origin['origin'] == 'base':
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
        dependency_store.verify_group(Path('build/sdk-group'), recipe_id)
        if recipe_id != origin['recipe']: raise ValueError('produced SDK identity differs from selected recipe')
        ci.prepared_check(target, recipe_id, Path('build/sdk-group'), ROOT / 'build/sdk-consumer', jobs)
        if value('SDK_PROFILE') == 'all-gui':
            main('gui-maintain')
            ci.prepared_check(target, recipe_id, Path('build/sdk-group'), ROOT / 'build/sdk-gui-consumer', jobs, ROOT / 'build/gui-group',
                              graphics_archive=ROOT / 'build/host-graphics/mesa-windows.7z' if target == 'windows-x86_64' else None)
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
                            ROOT / 'build/source/source.tar.gz', ROOT / 'build/produced', int(value('JOBS')))
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
    elif command == 'publish-candidate':
        request = evidence.load(Path('build/publication-request.json'))
        if request['source_commit'] != value('GITHUB_SHA') or request['packager_commit'] != value('GITHUB_SHA'):
            raise ValueError('publication input differs from checked-out workflow revision')
        write('build/receipts/publication.json', delivery.publish_candidate(**request, execute=True))
    elif command == 'certification-plan':
        ci.fetch_candidate(value('GITHUB_REPOSITORY'), value('TAG'), value('INVENTORY'), Path('build/fetched'))
        shutil.move('build/fetched/candidate', 'build/candidate')
        shutil.move('build/fetched/delivery.json', 'build/delivery.json')
        matrix = ci.qualification_plan(ROOT / 'build/candidate', value('PROFILE'), ROOT / 'build/check-plan.json')
        output('matrix', matrix)
    elif command == 'check':
        plan = evidence.load(Path('build/check-plan.json'))
        evidence.validate(plan); evidence.check_inputs(plan, ROOT)
        matches = [item for item in plan['checks'] if item['id'] == value('CHECK')]
        if len(matches) != 1: raise ValueError('check not in frozen inventory')
        item = matches[0]
        if ci.platform.system() == 'Linux' and ci.needs_browser_prerequisite(item['backend'], item['scope']):
            directory = ROOT / 'build/prerequisites' / value('CHECK')
            receipt = ci.install_browser_prerequisite(item['target'], item['environment'], item['backend'], directory)
            receipt.update(plan=plan['id'], check=item['id'], run_id=value('GITHUB_RUN_ID'),
                           attempt=int(value('GITHUB_RUN_ATTEMPT')))
            write(directory / 'browser.json', receipt)
        result = evidence.run_case(plan, value('CHECK'), ROOT, ROOT / 'build/evidence' / value('CHECK'),
                                   value('GITHUB_RUN_ID'), int(value('GITHUB_RUN_ATTEMPT')))
        if result['status'] != 'passed': raise ValueError('required qualification did not pass')
    elif command in ('certificate', 'attach-certificate'):
        identity = evidence.load(Path('build/delivery.json'))
        plan = evidence.load(Path('build/check-plan.json'))
        reports = [Path('build/evidence') / x['id'] / 'result.json' for x in plan['checks']]
        policy = ROOT / 'docs/release-policy.json'; directory = ROOT / 'build/candidate'
        if command == 'certificate':
            import certify_release
            result = certify_release.certify(directory, ci.module('release').verify_release(directory), plan, reports,
                       evidence.load(policy), value('PROFILE'), identity['experiment'])
            write('build/certificate.json', result)
            write('build/attachment-plan.json', delivery.attach_certificate(value('GITHUB_REPOSITORY'), value('TAG'), directory,
                    identity, Path('build/certificate.json'), Path('build/check-plan.json'), policy, value('PROFILE'),
                    reports, int(value('GITHUB_RUN_ATTEMPT'))))
        else:
            write('build/receipts/attachment.json', delivery.attach_certificate(value('GITHUB_REPOSITORY'), value('TAG'), directory,
                    identity, Path('build/certificate.json'), Path('build/check-plan.json'), policy, value('PROFILE'),
                    reports, int(value('GITHUB_RUN_ATTEMPT')), execute=True))
    elif command in ('promotion-plan', 'promote'):
        if command == 'promotion-plan':
            ci.fetch_candidate(value('GITHUB_REPOSITORY'), value('TAG'), value('INVENTORY'), Path('build/fetched'))
            shutil.move('build/fetched/candidate', 'build/candidate')
            shutil.move('build/fetched/delivery.json', 'build/delivery.json')
        request = dict(repository=value('GITHUB_REPOSITORY'), tag=value('TAG'), directory=Path('build/candidate'),
                       delivery=evidence.load(Path('build/delivery.json')), policy=Path('docs/release-policy.json'), profile=value('PROFILE'),
                       run_id=value('CERTIFICATION_RUN'), attempt=int(value('CERTIFICATION_ATTEMPT')), certificate_sha256=value('CERTIFICATE'))
        write('build/receipts/' + command + '.json', delivery.promote(**request, execute=command == 'promote'))
    else: raise ValueError('unknown workflow operation')


if __name__ == '__main__':
    try: main(sys.argv[1])
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        uncertain = sys.argv[1] in ('publish-bases', 'publish-gui', 'publish-candidate', 'attach-certificate', 'promote')
        receipt = {'ok': False, 'uncertain': uncertain or bool(getattr(error, 'uncertain', False)),
                   'operation': sys.argv[1], 'error': str(error),
                   'action': 'reconcile remote state before retry' if uncertain else 'repair prerequisites and inspect retained evidence'}
        try: write('build/receipts/failure.json', receipt)
        except OSError: pass
        raise SystemExit(json.dumps(receipt))
