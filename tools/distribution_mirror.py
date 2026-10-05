#!/usr/bin/env python3
"""Publish stable native repository URLs after immutable channel acceptance.

Only this separate mirror may replace indexes. Packages, keys, the source
channel and the certified application inventory remain immutable. Call under
the existing release lifecycle lock; this module never starts a workflow.
"""
from pathlib import Path
import tempfile

import distribution_release as channel

MUTABLE = {'Packages', 'Packages.gz', 'repository.json', 'Release', 'Release.gpg',
           'InRelease', 'software-foundation.db', 'software-foundation.db.sig',
           'software-foundation.files', 'software-foundation.files.sig', 'INSTALL.md'}


def tag_for(target):
    return 'packages-' + channel.TARGETS[target][0]


def base_url(repository, target):
    return 'https://github.com/' + repository + '/releases/download/' + tag_for(target) + '/'


def instructions(value, selected):
    req = value['request']; url = base_url(req['repository'], req['target'])
    # Keep the immutable channel's historical instruction templates unchanged.
    text = channel.instructions(req, value['backends'], native_only=True).decode()
    text = text[text.index('APT: '):text.index('\n\nAvailable variants:')]
    text = text.replace(channel.base_url(req), url)
    text = text.replace('software-foundation-core=' + req['version'] + '+r' + str(req['package_release']), 'software-foundation-core')
    text = text.replace('same immutable release root', 'same stable repository URL')
    text = text[:text.index('Gentoo: ')] + (
        'Gentoo: configure the existing trusted distro_client.py Portage adapter with '
        '`selection: {"track":"qualified"}` and run `sudo emaint sync -r software-foundation-bin`. '
        'Keep the operator-trusted tool tree, signing fingerprint and policy configuration. '
        'See https://github.com/' + req['repository'] + '/blob/main/docs/distribution-release.md '
        'for the one-time setup.'
    )
    if req['target'] != 'linux-x86_64':
        text = text[:text.index('Arch: ')] + 'Arch and Gentoo native qualification is currently limited to x86_64.'
    prefix = (f'# Stable package repository {tag_for(req["target"])}\n\n'
        f'Accepted immutable source: https://github.com/{req["repository"]}/releases/tag/{value["tag"]}\n\n'
        f'Distribution manifest SHA256: `{selected["manifest_sha256"]}`. '
        'Verify the original signed channel there with `distribution_release.py fetch --native-only` '
        'and the exact manifest digest before configuration.\n\n'
        f'Independently trusted signing fingerprint: `{req["trusted_fingerprint"]}`. '
        'An adjacent downloaded key alone does not establish trust.\n\n')
    return (prefix + text + '\n\nAvailable variants: ' + ', '.join(value['backends']) + '.\n\n'
            'The stable URL tracks accepted channels; versioned package files are retained. '
            'Index replacement is not atomic: retry a failed refresh after publication completes. '
            'Never disable signature or expiry checks.\n').encode()


def identity(value, directory):
    req = value['request']
    return {key: req[key] for key in ('sequence', 'version', 'package_release')} | {
        'tag': value['tag'], 'manifest_sha256': channel.archive.digest(Path(directory) / 'distribution.json')}


def matches(row, expected):
    return row['size'] == expected['size'] and row['digest'] == 'sha256:' + expected['sha256']


def latest_application(remote, value):
    req = value['request']
    info = remote.info(remote.transport.json(remote.base + '/releases/latest'), req['application_tag'])
    if info['id'] != value['application_release_id'] or info['draft'] or info['prerelease']:
        raise ValueError('package mirror requires the current certified Latest application')
    assets = remote.assets(info)
    if assets.get('release.json', {}).get('digest') != 'sha256:' + req['inventory_sha256']:
        raise ValueError('Latest application inventory differs from accepted channel')
    return info


def accepted_channel(remote, value, directory, selected):
    req = value['request']; info = remote.published(value['tag']); assets = remote.assets(info)
    body = channel.delivery.parse(info.get('body', ''))
    expected = dict(value['files'])
    expected.update({name: channel.asset_info(Path(directory) / name) for name in channel.CONTROL})
    if (info['prerelease'] or set(body) != {'kind', 'manifest_sha256', 'native_qualification'} or
            body['kind'] != 'signed-distribution' or body['manifest_sha256'] != selected['manifest_sha256']):
        raise ValueError('package mirror requires an accepted native channel')
    channel.native_marker(body['native_qualification'], req['target'])
    if set(assets) != set(expected) or any(not matches(assets[name], row) for name, row in expected.items()):
        raise ValueError('accepted channel assets differ from signed inventory')
    remote.unchanged(value['tag'], info, assets, req['packager_commit'])


def state_for(info, req):
    state = channel.delivery.parse(info.get('body', ''))
    fields = {'schema_version', 'kind', 'target', 'trusted_fingerprint', 'tag_commit', 'current', 'pending', 'files'}
    if (not isinstance(state, dict) or set(state) != fields or state['schema_version'] != 1 or
            state['kind'] != 'package-mirror' or state['target'] != req['target'] or
            state['trusted_fingerprint'] != req['trusted_fingerprint'] or
            not channel.delivery.OID.fullmatch(str(state['tag_commit'])) or not isinstance(state['files'], dict)):
        raise ValueError('foreign package mirror identity; preserve it')
    for name, row in state['files'].items():
        channel.delivery.valid_name(name)
        if (not isinstance(row, dict) or set(row) != {'size', 'sha256'} or type(row['size']) is not int or
                not 0 <= row['size'] <= channel.MAX_ASSET or not channel.delivery.SHA.fullmatch(str(row['sha256']))):
            raise ValueError('invalid retained package mirror inventory')
    for item in (state['current'], state['pending']):
        if item is not None:
            if (not isinstance(item, dict) or set(item) != {'tag', 'manifest_sha256', 'sequence', 'version', 'package_release'} or
                    not channel.delivery.positive(item['sequence']) or
                    not channel.delivery.SHA.fullmatch(str(item['manifest_sha256']))):
                raise ValueError('invalid package mirror generation')
            channel.delivery.valid_name(item['tag']); channel.distro.version_key(item)
    return state


def reconcile(assets, state, incoming):
    """Admit only retained bytes, or exact bytes of the recorded in-flight update."""
    previous = state['files']; pending = state['pending'] is not None
    if set(assets) - (set(previous) | set(incoming)):
        raise ValueError('unowned mirror assets; preserve them')
    for name, old in previous.items():
        if name not in assets and not (pending and name in MUTABLE):
            raise ValueError('retained mirror asset is missing')
        if name in incoming and name not in MUTABLE and incoming[name] != old:
            raise ValueError('same-name package or key bytes changed')
    for name, row in assets.items():
        allowed = [previous[name]] if name in previous else []
        if pending and name in incoming: allowed.append(incoming[name])
        if not any(matches(row, expected) for expected in allowed):
            raise ValueError('mirror asset differs from retained or pending bytes')


def publish(directory, policy, trusted, *, execute=False, transport=None):
    """Mirror exactly verified native bytes; plan by default, no implicit rebuild."""
    directory = Path(directory)
    value = channel.verify_native(directory, policy, trusted); req = value['request']
    selected = identity(value, directory); tag = tag_for(req['target'])
    result = channel.delivery.plan('publish-package-mirror', req['repository'], tag=tag,
        channel=selected, url=base_url(req['repository'], req['target']))
    if not execute: return result
    remote = channel.delivery.Remote(req['repository'], transport)

    def act():
        remote.visible(); accepted_channel(remote, value, directory, selected)
        latest_application(remote, value)
        with tempfile.TemporaryDirectory(prefix='foundation-mirror-') as temporary:
            root = Path(temporary)
            channels = channel.archive.extract(directory / 'channels.tar.gz', root / 'channels', max_bytes=channel.distro.MAX_BYTES * 2)
            staged = root / 'staged'; staged.mkdir()
            projections = [(value['apt_files'], channels / 'apt')]
            if req['target'] == 'linux-x86_64':
                projections.append((value['arch_files'], channels / 'native/arch'))
            for names, source in projections:
                for name in names:
                    channel.delivery.valid_name(name)
                    if channel.asset_info(source / name) != value['files'][name]:
                        raise ValueError('verified native projection changed')
                    channel.copy_new(source / name, staged / name)
            (staged / 'INSTALL.md').write_bytes(instructions(value, selected))
            incoming = {path.name: channel.asset_info(path) for path in staged.iterdir()}
            info = remote.find(tag, required=False)
            if info is None:
                state = dict(schema_version=1, kind='package-mirror', target=req['target'],
                    trusted_fingerprint=trusted, tag_commit=req['packager_commit'], current=None, pending=selected, files={})
                info = channel.initialize_channel(remote, tag, req['packager_commit'], channel.archive.encoded(state).decode())
            state = state_for(info, req); assets = remote.assets(info)
            if info['name'] != tag or remote.reference(tag) != state['tag_commit']:
                raise ValueError('package mirror release or tag identity changed')
            if state['pending'] not in (None, selected):
                raise ValueError('reconcile the previous interrupted mirror generation first')
            current = state['current']
            if current and current != selected and (selected['sequence'] <= current['sequence'] or
                    channel.distro.version_key(selected) <= channel.distro.version_key(current)):
                raise ValueError('package mirror update would roll back or replace a generation')
            if current == selected and any(state['files'].get(name) != row for name, row in incoming.items()):
                raise ValueError('same-generation mirror content changed')
            reconcile(assets, state, incoming)
            expected = dict(state['files'], **incoming)
            if len(expected) > 1000 or any(row['size'] > channel.MAX_ASSET for row in expected.values()):
                raise ValueError('retained package mirror exceeds GitHub asset limits')
            remote.unchanged(tag, info, assets, state['tag_commit'])
            if state['pending'] is None and current != selected:
                state = dict(state, pending=selected)
                remote.change('/releases/' + str(info['id']), method='PATCH', body={'body': channel.archive.encoded(state).decode()})
                info = remote.by_id(info['id'], tag)
                if state_for(info, req) != state: raise ValueError('mirror update intent was not retained')
            # Immutable packages precede every replaceable index. Never replay an
            # uncertain DELETE/upload automatically; the saved pending identity
            # permits a later exact-input retry after complete reconciliation.
            payloads = [name for name in incoming if name not in MUTABLE and name not in assets]
            channel.delivery.upload_files(remote, tag, [staged / name for name in payloads], release_info=info)
            order = sorted(set(incoming) & MUTABLE, key=lambda name: (name == 'InRelease', name))
            latest_application(remote, value)
            for name in order:
                if name in assets and matches(assets[name], incoming[name]): continue
                if name in assets:
                    remote.change('/releases/assets/' + str(assets[name]['id']), method='DELETE')
                remote.upload_to(info, staged / name)
            final = remote.by_id(info['id'], tag); after = remote.assets(final)
            if set(after) != set(expected) or any(not matches(after[name], row) for name, row in expected.items()):
                raise ValueError('package mirror inventory readback differs')
            readback = root / 'readback'; readback.mkdir()
            channel.delivery.download_files(remote, after,
                [(name, readback / name, incoming[name]['sha256']) for name in incoming])
            accepted_channel(remote, value, directory, selected)
            latest_application(remote, value)
            complete = dict(state, current=selected, pending=None, files=expected)
            if state != complete or final['draft'] or final['prerelease']:
                remote.change('/releases/' + str(info['id']), method='PATCH', body={
                    'body': channel.archive.encoded(complete).decode(), 'draft': False, 'prerelease': False, 'make_latest': 'false'})
            final = remote.by_id(info['id'], tag)
            if (final['draft'] or final['prerelease'] or state_for(final, req) != complete or
                    remote.assets(final) != after or remote.reference(tag) != state['tag_commit']):
                raise ValueError('package mirror completion differs; inspect remote state')
            remote.not_latest(final)
            latest = latest_application(remote, value)
            note = '\n\nSigned ' + channel.TARGETS[req['target']][0] + ' package repository: [installation instructions](' + result['url'] + 'INSTALL.md).'
            body = latest.get('body') or ''
            if note not in body:
                body += note
                remote.change('/releases/' + str(latest['id']), method='PATCH', body={'body': body})
                if latest_application(remote, value).get('body') != body:
                    raise ValueError('Latest package instructions readback differs')
            return dict(result, execute=True, release_id=info['id'], files=expected)
    return channel.delivery.run_mutation(remote, act)
