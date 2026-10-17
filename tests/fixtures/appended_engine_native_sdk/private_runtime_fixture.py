"""Inert private-runtime selection facts layered on the unchanged SDK fixture.

No program, archive, compiler query or link produced these synthetic records.
The five ``.a``/``.o`` leaves are ordinary text, never executable/linkable inputs.
This module imports only the fixture helpers, never the SDK adapter. Positive
unit tests must explicitly patch only the adapter's policy trust-anchor constant
to ``synthetic_policy_sha256``; no production validator is replaced here.
"""

import copy
import importlib.util
import json
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    'native_sdk_private_runtime_base_fixture', Path(__file__).with_name('fixture.py'))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

SOURCE_POLICY_PATH = 'recipes/webkitwasm-native-rich4083-v1/producer/private-cpp-runtime-policy-v1.json'
SOURCE_POLICY_SHA256 = '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc'
RUNTIME_ROLES = ('libstdcxx', 'libgcc', 'libgcc_eh', 'crtbeginS', 'crtendS')
QUERY_ROLES = RUNTIME_ROLES + ('dumpmachine', 'sysroot', 'search_dirs')


class Fixture(_base.Fixture):
    """Add five inert SDK leaves and an original eight-query fixture record.

    ``flush_private_runtime`` serializes mutable policy/selection dictionaries
    without repairing their joins. Deliberate bad pins, paths or other semantic
    changes therefore survive a flush. Raw-stream mutations use the dedicated
    helper, which refreshes only that stream's containing reference.

    Base ``flush`` is deliberately not overridden: base initialization and
    ordinary SDK request updates keep their existing behavior. Constructing this
    fixture does not add fields to the old request, host, observations or binding
    schemas, and does not attach a raw private-runtime toolchain.
    """

    def __init__(self, parent, repository_root, *, group_names=None):
        super().__init__(parent, repository_root, group_names=group_names)
        source_raw = (Path(repository_root) / SOURCE_POLICY_PATH).read_bytes()
        if _base.sha(source_raw) != SOURCE_POLICY_SHA256:
            raise ValueError('Frozen source private-runtime policy changed')
        self.synthetic_policy = json.loads(source_raw)
        self.private_runtime_support_directory = (
            'lib/gcc/' + _base.TARGET['triple'] + '/' + self.versions['cxx'])
        self.private_runtime_relative_paths = {}
        self.private_runtime_files = {}
        for role in RUNTIME_ROLES:
            basename = self.synthetic_policy['roles'][role]['basename']
            directory = (self.sysroot + '/usr/lib' if role == 'libstdcxx'
                         else self.private_runtime_support_directory)
            relative = directory + '/' + basename
            raw = ('INERT SYNTHETIC private runtime ' + role + '; NEVER LINK OR EXTRACT\n').encode('ascii')
            path = _base.write(self.sdk / relative, raw, 0o644)
            self.private_runtime_relative_paths[role] = relative
            self.private_runtime_files[role] = {
                'path': str(path), 'sha256': _base.sha(raw), 'bytes': len(raw)}

        self.manifest['files'] = {
            name: digest for name, digest in _base.inventory(self.sdk)['files'].items()
            if name != 'sdk.json'}
        self.rebind_manifest()

        # A retained synthetic pre-install manifest is distinct from sdk.json,
        # whose installed_root/archive_sha256 joins remain the original fixture's.
        original_manifest = copy.deepcopy(self.manifest)
        original_manifest.pop('installed_root')
        original_manifest.pop('archive_sha256')
        self.synthetic_original_manifest_raw = _base.encoded(original_manifest)
        self.synthetic_original_manifest_path = _base.write(
            self.inputs / 'private-runtime-original-manifest.json',
            self.synthetic_original_manifest_raw)
        self.synthetic_policy['sdk_recipe_id'] = self.recipe
        self.synthetic_policy['original_manifest_sha256'] = _base.sha(
            self.synthetic_original_manifest_raw)
        for role in RUNTIME_ROLES:
            self.synthetic_policy['roles'][role]['sha256'] = self.private_runtime_files[role]['sha256']
            self.synthetic_policy['roles'][role]['paths'] = [self.private_runtime_relative_paths[role]]

        self.synthetic_policy_path = self.inputs / 'private-runtime-policy.json'
        self.private_runtime_selection_path = self.inputs / 'private-runtime-selection.json'
        self.query_environment = {
            'PATH': ':'.join(sorted({str(Path(tool['path']).parent)
                                    for tool in self.observations['tools'].values()})),
            'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
            'SOURCE_DATE_EPOCH': self.request['policy']['source_date_epoch']}
        self.private_runtime_selection = {
            'schema_version': 1,
            'kind': self.synthetic_policy['selection_kind'],
            'scope': self.synthetic_policy['selection_scope'],
            'policy_sha256': self.synthetic_policy_sha256,
            'sdk_manifest_sha256': self.request['sdk']['manifest_sha256'],
            'compiler_sha256': self.observations['tools']['cxx']['sha256'],
            'selected': copy.deepcopy(self.private_runtime_files),
            'commands': {},
            'ownership': {'closed': True, 'descendants_closed': True, 'logs_closed': True}}
        self._private_raw_paths = {}
        common = [self.observations['tools']['cxx']['path'],
                  '--sysroot=' + str(self.sdk / self.sysroot),
                  *self.synthetic_policy['query_driver_options']]
        support = str(self.sdk / self.private_runtime_support_directory)
        output = {role: self.private_runtime_files[role]['path'] + '\n'
                  for role in RUNTIME_ROLES}
        output.update({
            'dumpmachine': _base.TARGET['triple'] + '\n',
            'sysroot': str(self.sdk / self.sysroot) + '\n',
            'search_dirs': ('install: ' + support + '/\nprograms: =' +
                str(self.sdk / 'bin') + ':' + str(self.sdk / 'libexec') +
                '\nlibraries: =' + str(self.sdk / self.sysroot / 'usr/lib') +
                ':' + support + '\n')})
        queries = {role: '-print-file-name=' + self.synthetic_policy['roles'][role]['basename']
                   for role in RUNTIME_ROLES}
        queries.update({'dumpmachine': '-dumpmachine', 'sysroot': '-print-sysroot',
                        'search_dirs': '-print-search-dirs'})
        for role in QUERY_ROLES:
            command = self.command('private-runtime-' + role, common + [queries[role]], output[role])
            command.update({'environment': dict(self.query_environment), 'cwd': str(self.inputs)})
            self.private_runtime_selection['commands'][role] = command
            for stream in ('stdout', 'stderr'):
                self._private_raw_paths[(role, stream)] = self.inputs / command[stream]['path']
        self.flush_private_runtime()

    @property
    def synthetic_policy_raw(self):
        """Canonical bytes for the current mutable synthetic policy dictionary."""
        return _base.encoded(self.synthetic_policy)

    @property
    def synthetic_policy_sha256(self):
        return _base.sha(self.synthetic_policy_raw)

    @property
    def private_runtime_selection_ref(self):
        """Current ordinary REF resolved from this fixture's inputs directory."""
        return self.ref(self.private_runtime_selection_path)

    def synthetic_binding(self):
        """Return fixture input joins for the three private-runtime public APIs.

        This is synthetic caller data, not an adapter-produced admission result.
        Original tool pins and the request manifest pin are preserved, while the
        current fake SDK walk supplies the complete files/modes maps. A changed
        fake body is never silently promoted to an original tool observation.
        """
        complete = _base.inventory(self.sdk)
        tools = {role: {key: self.observations['tools'][role][key]
                        for key in ('path', 'sha256', 'version')}
                 for role in self.program_paths}
        return {
            'root': str(self.sdk), 'metadata': copy.deepcopy(self.manifest),
            'files': complete['files'], 'modes': complete['modes'],
            'tool_paths': tools,
            'compiler': {'family': 'gcc', 'frontend': 'gcc',
                         'version': tools['cxx']['version'], 'triple': _base.TARGET['triple']},
            'sysroot': self.sysroot,
            'sdk_manifest_sha256': self.request['sdk']['manifest_sha256'],
            'policy': copy.deepcopy(self.request['policy'])}

    def flush_private_runtime(self):
        """Persist fixture documents without repairing deliberate bad joins.

        To exercise a deeper policy-validation branch after changing the policy,
        a test must explicitly update the selection's policy_sha256 itself.
        This operation does not change the base request or interpreter facts.
        """
        _base.write(self.synthetic_policy_path, self.synthetic_policy_raw)
        _base.document(self.private_runtime_selection_path, self.private_runtime_selection)
        return self.private_runtime_selection_ref

    def rewrite_private_raw(self, role, raw, *, stream='stdout'):
        """Replace one owned synthetic raw leaf and refresh only its raw REF."""
        if role not in QUERY_ROLES or stream not in ('stdout', 'stderr'):
            raise ValueError('Unknown synthetic private-runtime query or stream')
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        elif not isinstance(raw, bytes):
            raise TypeError('Synthetic private-runtime raw data must be str or bytes')
        path = self._private_raw_paths[(role, stream)]
        _base.write(path, raw)
        self.private_runtime_selection['commands'][role][stream] = self.ref(path)
        return self.flush_private_runtime()
