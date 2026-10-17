#!/usr/bin/env python3
"""Acquire explicit retained feedback inputs once; never build or compose them.

An ordinary/minimal project does not read an acquisition request or contact a
remote. Appended/nonminimal projects require reviewed source coordinates and
pins in .github/appended-retained.json. Only the selected original descriptor
is exported for the existing conservative feedback selector.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

import appended_container as container
import appended_policy as policy
import appended_release as release
from appended_project import CONFIG_NAME, load_project

REQUEST_PATH = '.github/appended-retained.json'
REQUEST_KIND = 'foundation-appended-retained-request'
REQUEST_LIMIT = 16 * 1024
REQUEST_FIELDS = ('schema_version', 'kind', 'source_repository', 'source_tag',
                  'source_release_id', 'source_commit', 'asset', 'asset_sha256',
                  'selection_sha256', 'kernel_id')
KERNEL_FIELDS = ('id', 'archive', 'inventory', 'descriptor', 'runtime_member',
                 'output', 'original_source', 'recovery', 'evidence')


def validate_request(value):
    """Validate acquisition coordinates as data, separately from selection.json."""
    release._keys(value, REQUEST_FIELDS, label='retained feedback request')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != REQUEST_KIND):
        raise ValueError('unsupported retained feedback request schema')
    from github_release import location
    location(value['source_repository'], value['source_tag'])
    if type(value['source_release_id']) is not int or value['source_release_id'] <= 0:
        raise ValueError('retained feedback requires a positive exact source release ID')
    if (type(value['source_commit']) is not str
            or not re.fullmatch(r'[0-9a-f]{40}', value['source_commit'])
            or value['source_commit'] == '0' * 40):
        raise ValueError('retained feedback requires an exact nonzero source commit')
    for name in ('asset_sha256', 'selection_sha256'):
        release._sha(value[name])
        if value[name] == '0' * 64:
            raise ValueError('retained feedback requires nonzero independent input pins')
    release._name(value['asset'])
    release._name(value['kernel_id'])
    return dict(value)


def _reference(value, *, source=False):
    release._keys(value, ('path', 'sha256'), ('tree_sha256',) if source else (),
                  label='retained selection reference')
    container.resource_path(value['path'])
    release._sha(value['sha256'])
    if source:
        release._sha(value.get('tree_sha256'))


def select_kernel(selection, kernel_id):
    """Check the old strict selection shape, then select one explicit kernel ID.

    This does not compose the old payload or qualify any kernel. References in
    every row are checked, including rows that are not selected for feedback.
    """
    release._name(kernel_id)
    release._keys(selection, ('schema_version', 'kind', 'application', 'source',
                             'payload', 'kernels'), label='retained selection')
    if (type(selection['schema_version']) is not int or selection['schema_version'] != 1
            or selection['kind'] != 'foundation-appended-selection'):
        raise ValueError('unsupported retained selection schema')
    container._application(selection['application'])
    _reference(selection['source'], source=True)
    if selection['payload'] is not None:
        _reference(selection['payload'])
    kernels = selection['kernels']
    if type(kernels) is not list or not 1 <= len(kernels) <= 32:
        raise ValueError('retained selection requires a bounded nonempty kernel mapping')
    selected, identities, outputs = None, set(), set()
    for row in kernels:
        release._keys(row, KERNEL_FIELDS, label='retained kernel selection')
        identity, output = release._name(row['id']), release._name(row['output'])
        if identity in identities or output.casefold() in outputs or not output.endswith('.tar.gz'):
            raise ValueError('duplicate retained kernel/output or unsupported archive suffix')
        identities.add(identity)
        outputs.add(output.casefold())
        container.resource_path(row['runtime_member'])
        for name in ('archive', 'inventory', 'descriptor', 'original_source'):
            _reference(row[name], source=name == 'original_source')
        for name in ('recovery', 'evidence'):
            if type(row[name]) is not list or len(row[name]) > 128 or name == 'recovery' and not row[name]:
                raise ValueError('invalid retained ' + name + ' reference group')
            for reference in row[name]:
                _reference(reference)
        if identity == kernel_id:
            selected = row
    if selected is None:
        raise ValueError('requested retained kernel_id is absent from pinned selection')
    return selected


def prepare_feedback(root, output, *, fetch=None):
    """Fetch one pinned group and export its exact descriptor; no build fallback."""
    root = container._ordinary_path(root, directory=True)
    project = load_project(root)
    result = {'schema_version': 1, 'kind': 'foundation-appended-feedback-inputs',
              'retained': False, 'descriptor': None, 'descriptor_sha256': None,
              'qualification': 'development-feedback-only'}
    if project.mode == 'neither' and project.selected_profile == 'minimal':
        result['reason'] = 'ordinary/minimal project; retained acquisition not selected'
        return result
    request_path = root / REQUEST_PATH
    try:
        request_input = container._snapshot(request_path, REQUEST_LIMIT)
    except FileNotFoundError as error:
        raise ValueError('retained feedback requires ' + REQUEST_PATH +
                         ' with explicit source coordinates, pins and kernel_id; '
                         'no kernel build fallback is permitted') from error
    except container.ContainerError as error:
        # _ordinary_path reports a missing path before the underlying open.
        if not request_path.exists() and not request_path.is_symlink():
            raise ValueError('retained feedback requires ' + REQUEST_PATH +
                             ' with explicit source coordinates, pins and kernel_id; '
                             'no kernel build fallback is permitted') from error
        raise
    request = validate_request(release._json(request_input.content))
    configuration = container._snapshot(root / CONFIG_NAME, REQUEST_LIMIT)
    if configuration.content != project._source_bytes:
        raise ValueError('project configuration changed before retained feedback acquisition')
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    output = Path(os.path.abspath(os.fspath(output)))
    container._ordinary_path(output.parent, directory=True)
    if output == root or root in output.parents and output == request_path.parent:
        raise ValueError('retained feedback output must not replace project inputs')
    output.mkdir()  # Exclusive: never adopt a stale/partial acquisition.
    fetch = release.fetch_inputs if fetch is None else fetch
    acquisition = fetch(request['source_repository'], request['source_tag'],
                        request['source_release_id'], request['source_commit'],
                        request['asset'], request['asset_sha256'],
                        request['selection_sha256'], output / 'group')
    selection_input = container._snapshot(output / 'group/selection.json', release.MAX_JSON)
    if container.digest(selection_input.content) != request['selection_sha256']:
        raise ValueError('retained feedback selection differs from independent pin')
    row = select_kernel(release._json(selection_input.content), request['kernel_id'])
    reference = row['descriptor']
    descriptor_input = container._snapshot(output / 'group' / reference['path'], container.MAX_INDEX)
    if container.digest(descriptor_input.content) != reference['sha256']:
        raise ValueError('retained feedback descriptor differs from pinned selection reference')
    descriptor = container.validate_descriptor(container.parse_json(descriptor_input.content, 'kernel descriptor'))
    policy.validate_kernel_inputs(descriptor.get('kernel_inputs'))
    # Copy original descriptor bytes only. Do not rewrite source inventories,
    # profile, provenance or qualification while exporting feedback metadata.
    snapshots = (request_input, configuration, selection_input, descriptor_input)
    for saved in snapshots:
        container._recheck(saved)
    container._write_new(output / 'acquisition.json', container.canonical_json(acquisition), snapshots)
    descriptor_path = container._write_new(output / 'descriptor.json', descriptor_input.content, snapshots)
    result.update(retained=True, descriptor=str(descriptor_path),
                  descriptor_sha256=reference['sha256'], kernel_id=request['kernel_id'],
                  request_sha256=container.digest(request_input.content),
                  selection_sha256=request['selection_sha256'],
                  reason='one authenticated pinned retained group; original descriptor only')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('build/appended-feedback'))
    parser.add_argument('--github-output', type=Path, default=os.environ.get('GITHUB_OUTPUT'))
    parser.add_argument('--summary', type=Path, default=os.environ.get('GITHUB_STEP_SUMMARY'))
    args = parser.parse_args(argv)
    try:
        result = prepare_feedback(args.root, args.output)
        if args.github_output:
            with args.github_output.open('a', encoding='utf-8') as stream:
                stream.write('retained=' + str(result['retained']).lower() + '\n')
                stream.write('descriptor_sha256=' + (result['descriptor_sha256'] or '') + '\n')
        if args.summary:
            with args.summary.open('a', encoding='utf-8') as stream:
                stream.write('Feedback retained inputs: ' + result['reason'] +
                             '. No kernel build, composition or qualification was performed.\n')
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, TypeError, ValueError) as error:
        print('appended feedback inputs: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
