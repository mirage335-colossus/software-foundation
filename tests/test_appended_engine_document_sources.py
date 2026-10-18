"""Pure source-group fixtures; inert supplier bytes are never extracted or run."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ASSEMBLER = ROOT / 'recipes/webkitwasm-document-v2/assemble_sources.py'
SPEC = importlib.util.spec_from_file_location('document_source_assembler_under_test', ASSEMBLER)
assembly = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assembly
SPEC.loader.exec_module(assembly)
contract, manifest, encoded = assembly.contract, assembly.manifest, assembly.encoded

PIN = '1' * 64
OTHER = '2' * 64
HEADER = 'include/foundation/appended/engine_provider.h'
SOURCE = 'source/main.cpp'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(root, name, raw, mode=0o644):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    for directory in (path.parent, *path.parent.parents):
        if directory == root.parent:
            break
        directory.chmod(0o755)
    path.write_bytes(raw)
    path.chmod(mode)
    return path


# Exact reverse projections derived from the closed composition source patch.
# Hash-bound offsets recover each complete prior body, without Git or ignored evidence.
COMPOSITION_REVERSE = {'2c315a2d08f8f5025f0619db73621d4aaf79dcdc970c1f5e1b7b692a045beb9b': {'postimage_bytes': 164651,
                                                                      'preimage_sha256': '2a1ef9ff3574ca31d4f182457dc7b4a83a09cd7944a8a9b410d4109485db791d',
                                                                      'reverse_edits': [[545, 591, ''],
                                                                                        [26064, 29167, '']]},
 '3c2c7beb2b582ab91fb8174aa7d5f6022ce1a4b29ec66918674f9f13fadd88ac': {'postimage_bytes': 48346,
                                                                      'preimage_sha256': '4cb8131b86f6bf1ede303053b7aa1752fab16dd66fe8b0271f97d256e0cd137b',
                                                                      'reverse_edits': [[479, 525, ''],
                                                                                        [26278, 29381, '']]},
 '4f72d4ad3d20ba76071c474564752bfa2f5e32dff203794b962da1e3de5ff598': {'postimage_bytes': 61330,
                                                                      'preimage_sha256': '5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815',
                                                                      'reverse_edits': [[176, 256, ''],
                                                                                        [5241, 5940, ''],
                                                                                        [24561, 24767, ''],
                                                                                        [31076, 41974, ''],
                                                                                        [46428,
                                                                                         46623,
                                                                                         '                            '
                                                                                         'if(transport_composition||editor.hasComposition()){poisoned=true;return '
                                                                                         'unknown();}\n'],
                                                                                        [47812,
                                                                                         47941,
                                                                                         '                                '
                                                                                         'if(editor.hasComposition())editor.cancelComposition();\n'
                                                                                         '                                '
                                                                                         'transport_composition=0;\n'],
                                                                                        [48400, 48962, ''],
                                                                                        [49329, 49911, ''],
                                                                                        [55253,
                                                                                         55331,
                                                                                         '        '
                                                                                         '}catch(...){poisoned=true;return '
                                                                                         'unknown();}\n'],
                                                                                        [56703,
                                                                                         57244,
                                                                                         '                    '
                                                                                         'if(!retirement_absent(mapping)){\n'
                                                                                         '                        '
                                                                                         'if(!material.composition||s.frame->document()!=s.document.get()||\n'],
                                                                                        [57326,
                                                                                         57510,
                                                                                         '                            '
                                                                                         's.frame->editor().compositionNode()!=s.composition_node.get()){poisoned=true;return '
                                                                                         'unknown();}\n'
                                                                                         '                        '
                                                                                         's.frame->editor().cancelComposition();\n'],
                                                                                        [58139,
                                                                                         58274,
                                                                                         '            '
                                                                                         'if(!ready()||!retirement_absent(mapping)){poisoned=true;return '
                                                                                         'unknown();}\n'],
                                                                                        [59470,
                                                                                         59548,
                                                                                         '        '
                                                                                         '}catch(...){poisoned=true;return '
                                                                                         'unknown();}\n']]},
 '6e77e9b1b47cc5e4e3d2a5dcd7600ea959c4b22eb95c763165c4ccc3c5d28a43': {'postimage_bytes': 29858,
                                                                      'preimage_sha256': 'cd5775db97976fc01d8f457474d41cbafd3ae2895efbd0a3dff49bbfe2e8f3d2',
                                                                      'reverse_edits': [[12269, 13500, '']]},
 'f6ca9055367085abe855a19b0d047034279dff1beb7dc44c8c2ab78001d602bb': {'postimage_bytes': 9317,
                                                                      'preimage_sha256': 'eda850a3b35353dc47be20f85fe16bff55058aaf83610ee0c96a7ffda5c369f2',
                                                                      'reverse_edits': [[36,
                                                                                         119,
                                                                                         '// Prototype-only '
                                                                                         'ownership policy. '
                                                                                         'The WebCore '
                                                                                         'adapter supplies '
                                                                                         'Ref<UndoStep>.\n'],
                                                                                        [133, 154, ''],
                                                                                        [173, 192, ''],
                                                                                        [209, 247, ''],
                                                                                        [340,
                                                                                         532,
                                                                                         '    explicit '
                                                                                         'UndoHistory(std::size_t '
                                                                                         'limit = 128) : '
                                                                                         'm_limit(limit) { '
                                                                                         '}\n'],
                                                                                        [533, 4304, ''],
                                                                                        [4461,
                                                                                         4878,
                                                                                         '        auto '
                                                                                         'generation = '
                                                                                         'm_generation;\n'
                                                                                         '        auto '
                                                                                         'discarded = '
                                                                                         'std::exchange(m_redo, '
                                                                                         '{ });\n'
                                                                                         '        '
                                                                                         'notifyRemoved(discarded);\n'
                                                                                         '        if '
                                                                                         '(generation != '
                                                                                         'm_generation) {\n'
                                                                                         '            '
                                                                                         'step->didRemoveFromUndoManager();\n'
                                                                                         '            '
                                                                                         'return; // A '
                                                                                         'removal callback '
                                                                                         'invalidated this '
                                                                                         'registration.\n'],
                                                                                        [4888,
                                                                                         4929,
                                                                                         '        '
                                                                                         'm_undo.push_back(std::move(step));\n'
                                                                                         '        '
                                                                                         'trim(m_undo);\n'],
                                                                                        [4935,
                                                                                         5193,
                                                                                         '\n'
                                                                                         '    bool canUndo() '
                                                                                         'const { return '
                                                                                         'm_replay == '
                                                                                         'Replay::None && '
                                                                                         '!m_undo.empty(); '
                                                                                         '}\n'
                                                                                         '    bool canRedo() '
                                                                                         'const { return '
                                                                                         'm_replay == '
                                                                                         'Replay::None && '
                                                                                         '!m_redo.empty(); '
                                                                                         '}\n'
                                                                                         '\n'],
                                                                                        [5323, 5323, '\n'],
                                                                                        [5466,
                                                                                         6333,
                                                                                         '        // Both '
                                                                                         'stacks are '
                                                                                         'detached before '
                                                                                         'script-capable '
                                                                                         'removal '
                                                                                         'callbacks.\n'
                                                                                         '        '
                                                                                         'notifyRemoved(undo);\n'
                                                                                         '        '
                                                                                         'notifyRemoved(redo);\n'],
                                                                                        [6393, 6489, ''],
                                                                                        [6530,
                                                                                         7146,
                                                                                         '\n'
                                                                                         '    static void '
                                                                                         'notifyRemoved(Stack& '
                                                                                         'steps)\n'],
                                                                                        [7152,
                                                                                         7291,
                                                                                         '        for (auto& '
                                                                                         'step : steps)\n'
                                                                                         '            '
                                                                                         'step->didRemoveFromUndoManager();\n'],
                                                                                        [7297, 7381, '\n'],
                                                                                        [7456,
                                                                                         7561,
                                                                                         '            auto '
                                                                                         'removed = '
                                                                                         'std::move(steps.front());\n'
                                                                                         '            '
                                                                                         'steps.pop_front();\n'
                                                                                         '            '
                                                                                         'removed->didRemoveFromUndoManager();\n'],
                                                                                        [7577, 8170, '\n'],
                                                                                        [8241,
                                                                                         8482,
                                                                                         '        if '
                                                                                         '(m_replay != '
                                                                                         'Replay::None || '
                                                                                         'source.empty())\n'
                                                                                         '            return '
                                                                                         'false;\n'
                                                                                         '        auto '
                                                                                         'active = '
                                                                                         'std::move(source.back());\n'
                                                                                         '        '
                                                                                         'source.pop_back();\n'],
                                                                                        [8597,
                                                                                         8774,
                                                                                         '        struct '
                                                                                         'Reset {\n'
                                                                                         '            '
                                                                                         'Replay& value;\n'
                                                                                         '            '
                                                                                         '~Reset() { value = '
                                                                                         'Replay::None; }\n'
                                                                                         '        } reset { '
                                                                                         'm_replay };\n'
                                                                                         '        if '
                                                                                         '(operation == '
                                                                                         'Replay::Undo)\n'
                                                                                         '            '
                                                                                         'active->unapply();\n'
                                                                                         '        else\n'
                                                                                         '            '
                                                                                         'active->reapply();\n'],
                                                                                        [8801,
                                                                                         8978,
                                                                                         '\n'
                                                                                         '    Stack m_undo;\n'
                                                                                         '    Stack '
                                                                                         'm_redo;\n'],
                                                                                        [9003,
                                                                                         9124,
                                                                                         '    std::size_t '
                                                                                         'm_generation { 0 '
                                                                                         '};\n'],
                                                                                        [9162, 9295, '']]},
 'd14dab28100d3689d9a04aa4a81290b50cf24cd3e00a34b2f8402d9eeca9da60': {'postimage_bytes': 61375,
 'preimage_sha256': '5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815',
 'reverse_edits': [[176, 256, ''],
                   [783, 828, ''],
                   [5286, 5985, ''],
                   [24606, 24812, ''],
                   [31121, 42019, ''],
                   [46473,
                    46668,
                    '                            '
                    'if(transport_composition||editor.hasComposition()){poisoned=true;return '
                    'unknown();}\n'],
                   [47857,
                    47986,
                    '                                '
                    'if(editor.hasComposition())editor.cancelComposition();\n'
                    '                                transport_composition=0;\n'],
                   [48445, 49007, ''],
                   [49374, 49956, ''],
                   [55298, 55376, '        }catch(...){poisoned=true;return unknown();}\n'],
                   [56748,
                    57289,
                    '                    if(!retirement_absent(mapping)){\n'
                    '                        '
                    'if(!material.composition||s.frame->document()!=s.document.get()||\n'],
                   [57371,
                    57555,
                    '                            '
                    's.frame->editor().compositionNode()!=s.composition_node.get()){poisoned=true;return '
                    'unknown();}\n'
                    '                        s.frame->editor().cancelComposition();\n'],
                   [58184,
                    58319,
                    '            if(!ready()||!retirement_absent(mapping)){poisoned=true;return '
                    'unknown();}\n'],
                   [59515, 59593, '        }catch(...){poisoned=true;return unknown();}\n']]}}
COMPOSITION_PRIOR_BYTES = {'5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815': 47742, '2a1ef9ff3574ca31d4f182457dc7b4a83a09cd7944a8a9b410d4109485db791d': 161502, 'cd5775db97976fc01d8f457474d41cbafd3ae2895efbd0a3dff49bbfe2e8f3d2': 28627, 'eda850a3b35353dc47be20f85fe16bff55058aaf83610ee0c96a7ffda5c369f2': 2662, '4cb8131b86f6bf1ede303053b7aa1752fab16dd66fe8b0271f97d256e0cd137b': 45197}

def composition_predecessor_bytes(raw):
    patch = COMPOSITION_REVERSE.get(sha(raw))
    if patch is None:
        return raw
    if len(raw) != patch['postimage_bytes']:
        raise AssertionError('Composition postimage size differs')
    for begin, end, previous in reversed(patch['reverse_edits']):
        raw = raw[:begin] + previous.encode('utf-8') + raw[end:]
    if sha(raw) != patch['preimage_sha256']:
        raise AssertionError('Exact composition reverse projection differs')
    return raw


def composition_history(imports, projection=None):
    """Check the current successor then expose its exact prior metadata to history checks."""
    imports = copy.deepcopy(imports)
    projection = copy.deepcopy(projection)
    for name, item in imports['files'].items():
        origin = item['origin']
        if origin.get('kind') != 'reviewed-native-composition-cancel-inverse-repair':
            continue
        if (set(origin) != {'kind', 'correction', 'sha256', 'source_path', 'source_only', 'supersedes'}
                or origin['correction'] != 'transaction-owned-native-composition-inverse-and-original-selection'
                or origin['sha256'] != item['sha256'] or origin['source_path'] != item['tracked_path']
                or origin['source_only'] is not True or item['sha256'] not in COMPOSITION_REVERSE):
            raise AssertionError('Exact source-only composition successor required')
        prior = origin['supersedes']
        if set(prior) != {'origin', 'sha256', 'tracked_path'} or prior['sha256'] != COMPOSITION_REVERSE[item['sha256']]['preimage_sha256']:
            raise AssertionError('Composition predecessor was restamped')
        if projection is not None:
            if projection['files'][name]['sha256'] != item['sha256']:
                raise AssertionError('Composition current projection differs')
            projection['files'][name]['sha256'] = prior['sha256']
        imports['files'][name] = {**item, 'origin': copy.deepcopy(prior['origin']),
            'sha256': prior['sha256'], 'bytes': COMPOSITION_PRIOR_BYTES[prior['sha256']],
            'tracked_path': prior['tracked_path']}
    return (imports, projection) if projection is not None else imports


class SourceAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='document-source-tiny-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.base.chmod(0o755)
        for target in ('subprocess.Popen', 'os.execv', 'os.system', 'shutil.which'):
            patcher = mock.patch(target, side_effect=AssertionError('Program launch/tool discovery is forbidden'))
            patcher.start()
            self.addCleanup(patcher.stop)

    def baseline(self, archive_padding=0):
        """A complete schema fixture, with no SDK directory or usable archive."""
        root = self.base / 'baseline'
        root.mkdir(mode=0o755)
        payloads = {
            HEADER: ((ROOT / HEADER).read_bytes(), 'interface', 0o644),
            SOURCE: (b'// Original already-patched source fixture.\n', 'source', 0o644),
            'supplier/wrapper.tar': (b'Inert wrapper archive fixture, never extracted.\n' + b'x' * archive_padding, 'source', 0o644),
            'supplier/engine.tar': (b'Inert engine archive fixture, never extracted.\n' + b'x' * archive_padding, 'source', 0o644),
            'NOTICE.txt': (b'Original fixture notice; retained exactly.\n', 'license', 0o644),
            'patches/original.patch': (b'Original patch provenance fixture, never applied.\n', 'patch', 0o644),
            'tools/fixture-entry.py': (b'# Inert executable-mode input; never executed.\n', 'tool', 0o755),
        }
        for name in manifest.HELPERS:
            mode = 0o755 if (ROOT / name).stat().st_mode & 0o111 else 0o644
            payloads[name] = ((ROOT / name).read_bytes(), 'helper', mode)
        for name, (raw, _, mode) in payloads.items():
            write(root, name, raw, mode)
        (root / 'empty-include').mkdir(mode=0o755)
        recipe = {
            'schema_version': 1, 'kind': 'foundation-appended-engine-recipe', 'producer_version': 1,
            'target': {'system': 'Emscripten', 'processor': 'wasm32',
                'triple': 'wasm32-unknown-emscripten', 'pointer_bits': 32},
            'toolchain': {'cxx_standard': 23, 'identity_sha256': PIN,
                'runtime_policy': 'paired-emscripten', 'paired_sdk_sha256': OTHER,
                'target_baseline': 'Synthetic metadata only; no SDK exists in this fixture.'},
            'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'},
            'provider': {'format': 'browser-module', 'binding': 'copied-owner-bridge',
                'abi_major': 1, 'abi_minor': 0, 'header': HEADER,
                'header_sha256': contract.BASE_HEADER_SHA256},
            'suppliers': {name: {'repository': 'https://example.invalid/' + name,
                'commit': ('a' if name == 'wrapper' else 'b') * 40,
                'archive': 'supplier/' + name + '.tar'} for name in ('wrapper', 'engine')},
            'inputs': {name: {'sha256': sha(raw), 'role': role, 'mode': mode}
                for name, (raw, role, mode) in payloads.items()},
            'patches': [{'path': 'patches/original.patch', 'tree': 'wrapper',
                'preimages': {SOURCE: sha(b'Original fixture before supplier patch.\n')},
                'postimages': {SOURCE: sha(payloads[SOURCE][0])}}],
            'licenses': ['NOTICE.txt'],
        }
        self.assertEqual(sha(payloads[HEADER][0]), contract.BASE_HEADER_SHA256)
        return self.seal(root, recipe)

    def seal(self, root, recipe):
        write(root, 'recipe.json', encoded(recipe))
        _, recipe_pin, inventory = manifest.verify_inputs(root)
        sources = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
            'producer_version': 1, 'recipe_id': recipe_pin, **inventory}
        write(root, 'sources.json', encoded(sources))
        _, sources_pin, checked = manifest.verify_sources(root)
        self.assertEqual(checked, recipe)
        return root, recipe_pin, sources_pin, recipe

    def selection(self, baseline, selected='pixel'):
        root, _, _, recipe = baseline
        selection_root = self.base / 'selection'
        selected_source = write(selection_root, 'main.cpp', b'// Document source fixture.\n')
        saved = assembly.snapshot(selected_source)
        projection = {'schema_version': 1, 'kind': 'foundation-document-v2-source-projection-v1',
            'document_profile': selected, 'source_map': {'path': 'provenance/document-source-map.json', 'sha256': PIN},
            'files': {SOURCE: {'preimage_sha256': recipe['inputs'][SOURCE]['sha256'], 'sha256': saved.sha256}},
            'physical_alias_groups': [], 'declared_source_aliases': []}
        projection_file = write(selection_root, 'projection.json', encoded(projection))
        return {SOURCE: (saved, 'source')}, [saved, assembly.snapshot(projection_file)], encoded(projection)

    def plan(self, baseline, selected='pixel', selection=None):
        selected_inputs = self.selection(baseline, selected) if selection is None else selection
        with mock.patch.object(assembly, '_maintained', return_value=selected_inputs) as maintained:
            result = assembly.prepare(baseline[0], baseline[1], baseline[2],
                document_profile=selected, repository=ROOT)
        maintained.assert_called_once_with(ROOT, selected)
        return result

    def assert_unsealed(self, output):
        self.assertFalse((output / 'sources.json').exists())

    def positive(self, selected):
        baseline = self.baseline()
        original_recipe = (baseline[0] / 'recipe.json').read_bytes()
        original_sources = (baseline[0] / 'sources.json').read_bytes()
        plan = self.plan(baseline, selected)
        output = self.base / 'new-source-group'
        result = assembly.assemble(plan, output)
        source_manifest, sources_pin, recipe = manifest.verify_sources(output)
        self.assertEqual(result['kind'], assembly.KIND)
        self.assertEqual(result['document_profile'], selected)
        self.assertIs(result['production_eligible'], False)
        self.assertEqual(result['scope'], 'source-only-no-sdk-engine-or-runtime')
        self.assertEqual(result['recipe_sha256'], source_manifest['recipe_id'])
        self.assertEqual(result['sources_sha256'], sources_pin)
        self.assertEqual(recipe['provider']['abi_major'], 1)
        self.assertEqual(recipe['provider']['abi_minor'], 1)
        self.assertEqual(recipe['provider']['header'], HEADER)
        self.assertEqual(recipe['provider']['header_sha256'], contract.BASE_HEADER_SHA256)
        self.assertEqual((output / 'provenance/document-predecessor/recipe.json').read_bytes(), original_recipe)
        self.assertEqual((output / 'provenance/document-predecessor/sources.json').read_bytes(), original_sources)
        self.assertEqual(recipe['suppliers'], baseline[3]['suppliers'])
        self.assertEqual(recipe['patches'], baseline[3]['patches'])
        self.assertEqual(recipe['licenses'], baseline[3]['licenses'])
        self.assertEqual((output / 'NOTICE.txt').read_bytes(), (baseline[0] / 'NOTICE.txt').read_bytes())
        for name in ('supplier/wrapper.tar', 'supplier/engine.tar', 'patches/original.patch'):
            self.assertEqual((output / name).read_bytes(), (baseline[0] / name).read_bytes())
        prelink = json.loads((output / 'prelink-plan.json').read_bytes())
        metadata = assembly._module(ROOT / assembly.RECIPE_ROOT / 'runtime/generate_document_metadata.py')
        driver = assembly.BUNDLE.load('appended_engine_document_maintenance')
        arguments = {'contract': contract}
        if selected == 'editor':
            arguments['editor_contract'] = assembly.BUNDLE.load('appended_engine_editor_contract')
        self.assertEqual(prelink, metadata.fixed_plan(recipe, selected, **arguments))
        self.assertEqual(prelink['configuration'], driver.profile_call(selected, 'expected_configuration'))
        self.assertEqual(prelink['provider_contract'], driver.profile_call(selected, 'provider_contract'))
        self.assertEqual(prelink['capabilities'], driver.profile_contract(selected).CAPABILITIES[selected])
        self.assertNotIn('source_recipe_sha256', prelink)
        self.assertNotIn('source_inputs_sha256', prelink)
        for name, item in recipe['inputs'].items():
            self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), item['mode'], name)
        for name in source_manifest['directories']:
            self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o755, name)
        self.assertEqual(stat.S_IMODE((output / 'sources.json').stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE((output / 'recipe.json').stat().st_mode), 0o644)
        self.assertTrue((output / 'empty-include').is_dir())
        self.assertEqual(list((output / 'empty-include').iterdir()), [])

    def test_pixel_source_group_preserves_exact_predecessors_provenance_and_modes(self):
        self.positive('pixel')

    def test_physical_source_group_has_matching_noncircular_document_prelink(self):
        self.positive('physical')

    def test_editor_source_group_has_explicit_editor_prelink_and_exact_predecessors(self):
        self.positive('editor')

    def test_independent_recipe_and_sources_pins_reject_before_maintained_selection(self):
        baseline = self.baseline()
        for recipe_pin, sources_pin in ((OTHER, baseline[2]), (baseline[1], OTHER)):
            with self.subTest(recipe_pin=recipe_pin, sources_pin=sources_pin), \
                 mock.patch.object(assembly, '_maintained', side_effect=AssertionError('selection reached')):
                with self.assertRaises(ValueError):
                    assembly.prepare(baseline[0], recipe_pin, sources_pin, document_profile='pixel')

    def test_wrong_or_missing_preimage_cannot_overwrite_an_existing_source(self):
        baseline = self.baseline()
        maintained, snapshots, raw = self.selection(baseline)
        for preimage in (OTHER, None):
            projection = json.loads(raw)
            projection['files'][SOURCE]['preimage_sha256'] = preimage
            with self.subTest(preimage=preimage), self.assertRaisesRegex(ValueError, 'preimage differs'):
                self.plan(baseline, selection=(maintained, snapshots, encoded(projection)))

    def test_postimage_must_identify_the_selected_source_bytes(self):
        baseline = self.baseline()
        maintained, snapshots, raw = self.selection(baseline)
        projection = json.loads(raw)
        projection['files'][SOURCE]['sha256'] = OTHER
        with self.assertRaisesRegex(ValueError, 'postimage differs'):
            self.plan(baseline, selection=(maintained, snapshots, encoded(projection)))

    def test_notice_replacement_is_rejected(self):
        baseline = self.baseline()
        maintained, snapshots, raw = self.selection(baseline)
        changed = assembly.snapshot(write(self.base / 'selection', 'changed-notice.txt', b'New unrelated notice.\n'))
        maintained['NOTICE.txt'] = (changed, 'license')
        with self.assertRaisesRegex(ValueError, 'notice differs'):
            self.plan(baseline, selection=(maintained, snapshots + [changed], raw))

    def test_input_changed_after_prepare_fails_before_creating_output(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        write(baseline[0], SOURCE, b'Changed original source.\n')
        output = self.base / 'output'
        with self.assertRaises(ValueError):
            assembly.assemble(plan, output)
        self.assertFalse(output.exists())

    def test_identical_bytes_with_new_inode_do_not_reuse_a_snapshot(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        old = baseline[0] / SOURCE
        replacement = write(self.base, 'replacement.cpp', old.read_bytes())
        old_identity = assembly.identity(old)
        os.replace(replacement, old)
        self.assertNotEqual(assembly.identity(old), old_identity)
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            assembly.assemble(plan, self.base / 'output')

    def test_late_input_mutation_leaves_partial_output_without_final_seal(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        original_recheck, calls = assembly._recheck, []
        def recheck(current):
            calls.append(True)
            if len(calls) == 2:
                write(baseline[0], SOURCE, b'Changed after copies completed.\n')
            return original_recheck(current)
        output = self.base / 'output'
        with mock.patch.object(assembly, '_recheck', side_effect=recheck):
            with self.assertRaises(ValueError):
                assembly.assemble(plan, output)
        self.assertTrue((output / 'recipe.json').exists())
        self.assert_unsealed(output)

    def test_output_copy_failure_preserves_partial_files_without_a_seal(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        original_copy, calls = assembly._copy, []
        def copy_file(saved, path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('Synthetic output write failure')
            return original_copy(saved, path)
        output = self.base / 'output'
        with mock.patch.object(assembly, '_copy', side_effect=copy_file):
            with self.assertRaisesRegex(OSError, 'Synthetic output'):
                assembly.assemble(plan, output)
        self.assertTrue(calls[0].exists())
        self.assert_unsealed(output)

    def test_output_mutation_before_final_verification_never_creates_a_seal(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        output = self.base / 'output'
        original_verify, calls = manifest.verify_inputs, []
        def verify(root):
            calls.append(True)
            if len(calls) == 2:
                write(output, SOURCE, b'Output changed before final verification.\n')
            return original_verify(root)
        with mock.patch.object(manifest, 'verify_inputs', side_effect=verify):
            with self.assertRaises(ValueError):
                assembly.assemble(plan, output)
        self.assert_unsealed(output)

    def test_existing_and_baseline_descendant_outputs_leave_inputs_unchanged(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        existing = self.base / 'existing'
        existing.mkdir()
        marker = write(existing, 'keep.txt', b'Keep existing user bytes.\n')
        recipe_before = (baseline[0] / 'recipe.json').read_bytes()
        for output in (existing, baseline[0] / 'nested-output', ROOT / 'recipes/forbidden-new-source-output'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                assembly.assemble(plan, output)
        self.assertEqual(marker.read_bytes(), b'Keep existing user bytes.\n')
        self.assertEqual((baseline[0] / 'recipe.json').read_bytes(), recipe_before)
        self.assertFalse((baseline[0] / 'nested-output').exists())

    def test_symlink_output_and_symlinked_input_parent_are_rejected(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        output = self.base / 'output-link'
        output.symlink_to(self.base / 'absent-target', target_is_directory=True)
        with self.assertRaises(ValueError):
            assembly.assemble(plan, output)
        alias = self.base / 'baseline-link'
        alias.symlink_to(baseline[0], target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Linked source'):
            assembly.snapshot(alias / SOURCE)

    def test_output_ancestor_with_retained_physical_identity_is_rejected(self):
        baseline = self.baseline()
        plan = self.plan(baseline)
        forbidden = next(iter(plan['forbidden_directories']))
        original_identity = assembly.identity
        def alias_identity(path):
            value = original_identity(path)
            return (*forbidden, *value[2:]) if Path(path) == self.base else value
        output = self.base / 'output'
        with mock.patch.object(assembly, 'identity', side_effect=alias_identity):
            with self.assertRaisesRegex(ValueError, 'aliases a retained'):
                assembly.assemble(plan, output)
        self.assertFalse(output.exists())

    def test_snapshot_rejects_symlinks_hardlinks_modes_and_small_budget(self):
        source = write(self.base, 'ordinary.txt', b'fixture')
        symlink = self.base / 'symlink.txt'
        symlink.symlink_to(source)
        with self.assertRaises(ValueError): assembly.snapshot(symlink)
        linked = self.base / 'hardlink.txt'
        os.link(source, linked)
        with self.assertRaises(ValueError): assembly.snapshot(linked)
        linked.unlink()
        source.chmod(0o600)
        with self.assertRaises(ValueError): assembly.snapshot(source)
        source.chmod(0o644)
        with self.assertRaises(ValueError): assembly.snapshot(source, maximum=3)

    def test_checkout_group_write_modes_normalize_without_changing_inputs(self):
        for physical, logical in ((0o664, 0o644), (0o775, 0o755)):
            path = write(self.base, 'input-' + oct(physical), b'Checkout bytes.\n', physical)
            saved = assembly.snapshot(path)
            self.assertEqual(saved.mode, logical)
            self.assertEqual(saved.identity[5], physical)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), physical)
            _, bounded = assembly.read_small(path)
            self.assertEqual(bounded.mode, logical)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), physical)
        invalid = write(self.base, 'world-writable', b'Unsafe mode.\n', 0o666)
        with self.assertRaises(ValueError): assembly.snapshot(invalid)
        with self.assertRaises(ValueError): assembly.read_small(invalid)

    def test_source_byte_budget_applies_to_cumulative_fixture_inputs(self):
        baseline = self.baseline(archive_padding=96 * 1024)
        sizes = [(baseline[0] / name).stat().st_size for name in baseline[3]['inputs']]
        limit = max(sizes + [saved.size for saved in assembly.BUNDLE.snapshots()]) + 1
        self.assertTrue(all(size < limit for size in sizes))
        self.assertGreater(sum(sizes), limit)
        with mock.patch.object(assembly, 'MAX_SOURCE_BYTES', limit), \
             mock.patch.object(assembly, '_maintained', side_effect=AssertionError('selection reached')):
            with self.assertRaisesRegex(ValueError, 'Original retained source input budget exceeded'):
                assembly.prepare(baseline[0], baseline[1], baseline[2], document_profile='pixel')

    def test_namespace_budgets_reject_before_full_source_hashing(self):
        baseline = self.baseline()
        for setting, value in (('MAX_INPUTS', 1), ('MAX_DIRECTORIES', 0)):
            with self.subTest(setting=setting), mock.patch.object(assembly, setting, value), \
                 mock.patch.object(manifest, 'verify_sources', side_effect=AssertionError('Full hashing reached')):
                with self.assertRaisesRegex(ValueError, 'bounded inventory'):
                    assembly.prepare(baseline[0], baseline[1], baseline[2], document_profile='pixel')

    def test_bounded_json_rejects_oversize_and_duplicate_keys(self):
        path = write(self.base, 'document.json', b'{"a":1,"a":2}\n')
        with self.assertRaises(ValueError): assembly.read_json(path)
        with mock.patch.object(assembly, 'MAX_SMALL_BYTES', 2):
            with self.assertRaisesRegex(ValueError, 'Oversized'):
                assembly.read_json(path)

    def test_pinned_json_cannot_return_an_earlier_read_during_replacement(self):
        before, after = b'{"v":1}\n', b'{"v":2}\n'
        path = write(self.base, 'document.json', before)
        actual_open, mutated = Path.open, []
        class ChangeAfterRead:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def fileno(self): return self.stream.fileno()
            def read(self, size=-1):
                raw = self.stream.read(size)
                if not mutated:
                    mutated.append(True)
                    previous = path.stat()
                    path.write_bytes(after)
                    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1))
                return raw
        def open_file(selected, mode='r', *args, **kwargs):
            stream = actual_open(selected, mode, *args, **kwargs)
            return ChangeAfterRead(stream) if selected == path and mode == 'rb' else stream
        with mock.patch.object(Path, 'open', new=open_file):
            with self.assertRaises(ValueError):
                assembly.read_json(path, sha(after))

    def test_foreign_cached_helper_modules_are_ignored(self):
        foreign = types.ModuleType('foreign_helper_fixture')
        foreign.__file__ = str(self.base / 'foreign.py')
        foreign.HELPERS = ('wrong',)
        with mock.patch.dict(sys.modules, {name: foreign for name in assembly.HelperBundle.NAMES}):
            bundle = assembly.HelperBundle(ROOT)
            fresh_manifest = bundle.load('appended_engine_manifest')
            fresh_contract = bundle.load('appended_engine_document_contract')
        self.assertIsNot(fresh_manifest, foreign)
        self.assertEqual(fresh_manifest.HELPERS, manifest.HELPERS)
        self.assertEqual(fresh_contract.BASE_HEADER_SHA256, contract.BASE_HEADER_SHA256)
        for saved in bundle.snapshots():
            self.assertTrue(saved.path == ROOT or ROOT in saved.path.parents)
            self.assertEqual(saved.sha256, sha(saved.path.read_bytes()))

    def test_changed_helper_bytes_are_detected_before_preparing_sources(self):
        baseline = self.baseline()
        repository = self.base / 'private-helper-copy'
        helper_name = 'tools/appended_engine_document_contract.py'
        helper = write(repository, helper_name, (ROOT / helper_name).read_bytes())
        bundle = assembly.HelperBundle(repository)
        bundle.load('appended_engine_document_contract')
        helper.write_bytes(helper.read_bytes() + b'\n# Changed after exact-byte execution.\n')
        with mock.patch.object(assembly, 'BUNDLE', bundle), \
             mock.patch.object(assembly, '_maintained', side_effect=AssertionError('selection reached')):
            with self.assertRaises(ValueError):
                assembly.prepare(baseline[0], baseline[1], baseline[2], document_profile='pixel')

    def test_projection_requires_the_profile_sources_map_and_exact_owned_bytes(self):
        saved = assembly.snapshot(write(self.base, 'main.cpp', b'Owned source.\n'))
        source_map = assembly.snapshot(write(self.base, 'map.json', b'{}\n'))
        config = {'document_profile': 'pixel', 'source_map_sha256': source_map.sha256,
            'source_bindings': {'Main.cpp': SOURCE}, 'owner_postimages': {}, 'declared_source_aliases': []}
        projection = {'schema_version': 1, 'kind': 'foundation-document-v2-source-projection-v1',
            'document_profile': 'pixel', 'source_map': {'path': 'provenance/map.json', 'sha256': source_map.sha256},
            'files': {SOURCE: {'preimage_sha256': PIN, 'sha256': saved.sha256}},
            'physical_alias_groups': [], 'declared_source_aliases': []}
        files = {SOURCE: (saved, 'source'), 'provenance/map.json': (source_map, 'config')}
        driver = assembly.BUNDLE.load('appended_engine_document_maintenance')
        assembly._validate_projection(driver, projection, config, files)
        for mutation in ('kind', 'omitted-source', 'omitted-owner', 'postimage', 'source-map', 'extra-field', 'aliases'):
            changed, changed_config = copy.deepcopy(projection), copy.deepcopy(config)
            if mutation == 'kind': changed['kind'] = 'unknown'
            elif mutation == 'omitted-source': changed['files'] = {}
            elif mutation == 'omitted-owner':
                changed['files'] = {'provenance/map.json': {'preimage_sha256': None, 'sha256': source_map.sha256}}
            elif mutation == 'postimage': changed['files'][SOURCE]['sha256'] = OTHER
            elif mutation == 'source-map': changed['source_map']['sha256'] = OTHER
            elif mutation == 'extra-field': changed['extra'] = True
            else: changed_config['declared_source_aliases'] = [{'unreviewed': True}]
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                assembly._validate_projection(driver, changed, changed_config, files)

    def maintained_smoke(self, selected, expected_imports):
        files, snapshots, raw = assembly._maintained(ROOT, selected)
        imports = json.loads((ROOT / assembly.RECIPE_ROOT / ('source-imports-' + selected + '.json')).read_bytes())
        projection = json.loads(raw)
        self.assertEqual(len(imports['files']), expected_imports)
        self.assertEqual(set(projection['files']), set(imports['files']))
        for name, item in imports['files'].items():
            self.assertEqual(files[name][0].sha256, item['sha256'], name)
            self.assertEqual(files[name][1], item['role'], name)
        driver = assembly.BUNDLE.load('appended_engine_document_maintenance')
        helpers = set(driver.required_helpers(selected))
        self.assertTrue(helpers <= set(files))
        for saved in snapshots:
            relative = saved.path.relative_to(ROOT).as_posix()
            if relative in helpers:
                self.assertEqual(files[relative][0], saved)
        if selected != 'editor':
            self.assertNotIn('tools/appended_engine_editor_contract.py', files)
        self.assertTrue(snapshots)
        self.assertTrue(any(role == 'license' for _, role in files.values()))
        self.assertEqual(files[HEADER][0].sha256, contract.BASE_HEADER_SHA256)

    def test_actual_maintained_pixel_selection_and_helper_identity_smoke(self):
        self.maintained_smoke('pixel', 95)

    def test_actual_maintained_physical_selection_and_helper_identity_smoke(self):
        self.maintained_smoke('physical', 132)

    def test_actual_maintained_editor_selection_and_helper_identity_smoke(self):
        self.maintained_smoke('editor', 159)

    def test_editor_metadata_roles_survive_actual_imports_and_assembly(self):
        maintained, _, _ = assembly._maintained(ROOT, 'editor')
        metadata = assembly._module(ROOT / assembly.RECIPE_ROOT / 'runtime/generate_document_metadata.py')
        baseline = self.baseline()
        inputs, snapshots, projection = self.selection(baseline, 'editor')
        for name, _ in metadata.EDITOR_PIN_FILES.values():
            inputs[name] = maintained[name]
            snapshots.append(maintained[name][0])
        plan = self.plan(baseline, 'editor', (inputs, snapshots, projection))
        output = self.base / 'editor-interface-source-group'
        assembly.assemble(plan, output)
        _, _, recipe = manifest.verify_sources(output)
        for name, _ in metadata.EDITOR_PIN_FILES.values():
            with self.subTest(name=name):
                self.assertEqual(metadata.retained(output / name, output, recipe['inputs'], role='interface'),
                    maintained[name][0].path.read_bytes())
                changed = copy.deepcopy(recipe['inputs'])
                changed[name]['role'] = 'source'
                with self.assertRaisesRegex(ValueError, 'required generator input is absent from recipe'):
                    metadata.retained(output / name, output, changed, role='interface')

    def test_editor_selection_keeps_original_core_headers_outside_projection(self):
        here = ROOT / assembly.RECIPE_ROOT
        imports = json.loads((here / 'source-imports-editor.json').read_bytes())
        projection = json.loads((here / 'source-projection-editor.json').read_bytes())
        imports, projection = composition_history(imports, projection)
        profile = json.loads((here / 'maintenance-profile-editor.json').read_bytes())
        capsule_sources = [item for item in imports['files'].values()
                           if item['origin'].get('capsule') == '0005-cpp-only-outcome']
        # The repaired input-profile header retains its capsule under one exact
        # source-only wrapper; count that historical capsule along with direct ones.
        input_profile = imports['files']['source/document-provider/portable/appended_engine_input_profile.hpp']
        self.assertEqual(input_profile['origin']['kind'], 'reviewed-actual-header-profile-repair')
        self.assertEqual(input_profile['origin']['supersedes']['origin']['capsule'], '0005-cpp-only-outcome')
        capsule_sources.append(input_profile)
        # The C8 guard repair likewise preserves this exact historical capsule
        # under a source-only successor; it is not new compiled evidence.
        editor_guard = imports['files']['source/foundation/third_party/appended-engine/src/ProviderGuard.cpp']
        self.assertEqual(editor_guard['origin']['kind'], 'reviewed-editor-C8-preflight-repair')
        self.assertIs(editor_guard['origin']['source_only'], True)
        self.assertEqual(editor_guard['origin']['supersedes']['origin']['capsule'], '0005-cpp-only-outcome')
        self.assertEqual(editor_guard['origin']['supersedes']['sha256'],
                         'f18e9cc64c793ed1f9bfd2e51c0e68bf64c1256131c662a6573c211553e85b9e')
        capsule_sources.append(editor_guard)
        # Metadata, Publisher and seven shared-UI callsites retain their old
        # capsule origins under explicit successor history instead.
        self.assertEqual(len(capsule_sources), 109)
        for name in ('source/engine/Source/WebCore/dom/Element.h',
                     'source/engine/Source/WebCore/page/EventHandler.h',
                     'source/engine/Source/WebCore/html/HTMLSelectElement.h',
                     'source/engine/Source/WebCore/loader/EmptyClients.h',
                     'source/engine/Source/WebCore/editing/Editor.h',
                     'source/engine/Source/WebCore/dom/DataTransfer.h',
                     'source/engine/Source/WebCore/platform/Pasteboard.h',
                     'source/engine/Source/WebCore/platform/PasteboardContext.h',
                     'source/engine/Source/WebCore/page/PagePasteboardContext.h'):
            self.assertNotIn(name, imports['files'])
            self.assertNotIn(name, projection['files'])
        self.assertFalse(any('original-headers/' in item['tracked_path'] for item in imports['files'].values()))
        self.assertFalse(any(Path(path).suffix != '.cpp' for paths in profile['owner_postimages'].values() for path in paths))
        self.assertNotIn('native_editor_controller.cpp', profile['direct_objects'])

    def test_editor_guard_successor_preserves_historical_compiled_source_map(self):
        here = ROOT / assembly.RECIPE_ROOT
        logical = 'source/foundation/third_party/appended-engine/src/ProviderGuard.cpp'
        tracked = assembly.RECIPE_ROOT + '/overlays/editor/foundation/third_party/appended-engine/src/ProviderGuard.cpp'
        previous = 'f18e9cc64c793ed1f9bfd2e51c0e68bf64c1256131c662a6573c211553e85b9e'
        expected = '6ec6546880d6736311ab8def5563da79a870dd1f68b56fdcbe947835acf817a8'
        imports = json.loads((here / 'source-imports-editor.json').read_bytes())
        projection = json.loads((here / 'source-projection-editor.json').read_bytes())
        profile = json.loads((here / 'maintenance-profile-editor.json').read_bytes())
        map_raw = (here / 'provenance/editor-source-map.json').read_bytes()
        self.assertEqual(sha(map_raw), 'a97017168b817334d1a094300e904f09110c234d734712b4d48870e2aa7b4ddb')
        self.assertEqual(imports['capsule_source_map_sha256'], sha(map_raw))
        self.assertEqual(profile['source_map_sha256'], sha(map_raw))
        self.assertEqual(projection['source_map']['sha256'], sha(map_raw))
        compiled = [row for row in json.loads(map_raw)['direct_translation_units']
                    if row['logical_target'] == 'foundation/third_party/appended-engine/src/ProviderGuard.cpp']
        self.assertEqual(compiled, [{'bytes': 67487,
            'logical_target': 'foundation/third_party/appended-engine/src/ProviderGuard.cpp',
            'path': str(ROOT / '.agent-work/appended-implementation-20261016/ndv2-provider-binding-design/implementation/versions/0005-cpp-only-outcome/source/foundation/third_party/appended-engine/src/ProviderGuard.cpp'),
            'sha256': previous}])
        item = imports['files'][logical]
        self.assertEqual((item['tracked_path'], item['sha256'], item['bytes']), (tracked, expected, 68423))
        self.assertEqual(sha((ROOT / tracked).read_bytes()), expected)
        self.assertEqual(item['origin'], {
            'kind': 'reviewed-editor-C8-preflight-repair',
            'correction': 'inert-C8-before-Host-TURN-with-in-turn-revalidation',
            'sha256': expected, 'source_path': tracked, 'source_only': True,
            'supersedes': {'origin': {
                'capsule': '0005-cpp-only-outcome',
                'logical_path': 'foundation/third_party/appended-engine/src/ProviderGuard.cpp',
                'sha256': previous, 'supersedes': {'origin': {
                    'capsule': '0003-document-physical',
                    'logical_path': 'foundation/third_party/appended-engine/src/ProviderGuard.cpp',
                    'sha256': 'dcac577c612cce0faf8692afde0481f6a0723e297aa5eba4a2c6c5e707d7333d'},
                    'sha256': 'dcac577c612cce0faf8692afde0481f6a0723e297aa5eba4a2c6c5e707d7333d'}},
                'sha256': previous, 'tracked_path': tracked}})
        self.assertEqual(projection['files'][logical], {
            'preimage_sha256': '4d7ee19b4f3d6d2bf75c559ca6d81ff00cfebbac65afacd1be74c847281bc5f8',
            'sha256': expected})
        for selected in ('pixel', 'physical'):
            other = json.loads((here / ('source-imports-' + selected + '.json')).read_bytes())
            self.assertNotEqual(other['files'][logical]['sha256'], expected)

    def test_shared_publisher_successor_keeps_exact_historical_origin(self):
        here = ROOT / assembly.RECIPE_ROOT
        name = 'source/document-provider/native/NativeDocumentV2Publisher.cpp'
        old = 'bbc219cc50258478cf84fbaf7be0c70f6b9ab9c0ac90dd6a164a70bc587db5e5'
        predecessor = '7d0b0ac92fc0929081d6f5807aeec3508fead2fabe942c325b67a8a3e5f60f95'
        header_repair = '78e59ed007bde4cd909044bb6a25a61518e6d85d0407c0287dceb6edea96c004'
        hidden_label_repair = '533984f89134872a87d2eb661a0b563f6b865805ab31ae955b2b74c2ab75c867'
        expected = '0705d9421e853b7633cc2a3df2c0448b0b53da0daf48fd2e7158f98b341b0453'
        for profile, capsule in (('pixel', '0002-document-raster'),
                                 ('physical', '0003-document-physical'),
                                 ('editor', '0005-cpp-only-outcome')):
            with self.subTest(profile=profile):
                imports = json.loads((here / ('source-imports-' + profile + '.json')).read_bytes())
                projection = json.loads((here / ('source-projection-' + profile + '.json')).read_bytes())
                item = imports['files'][name]
                self.assertEqual(item['sha256'], expected)
                self.assertEqual(sha((ROOT / item['tracked_path']).read_bytes()), expected)
                origin = item['origin']
                self.assertEqual(origin['kind'], 'reviewed-BEGIN-focus-editor-state-repair')
                self.assertEqual(origin['correction'], 'stable-focus-dependent-canEdit-and-inputMethodEnabled')
                self.assertEqual(origin['sha256'], expected)
                self.assertEqual(origin['source_path'], item['tracked_path'])
                self.assertIs(origin['source_only'], True)
                self.assertEqual(origin['supersedes']['sha256'], hidden_label_repair)
                self.assertEqual(origin['supersedes']['tracked_path'], item['tracked_path'])
                origin = origin['supersedes']['origin']
                self.assertEqual(origin['kind'], 'reviewed-hidden-label-association-repair')
                self.assertEqual(origin['correction'], 'bounded-private-excluded-label-association')
                self.assertEqual(origin['sha256'], hidden_label_repair)
                self.assertEqual(origin['source_path'], item['tracked_path'])
                self.assertIs(origin['source_only'], True)
                self.assertEqual(origin['supersedes']['sha256'], header_repair)
                self.assertEqual(origin['supersedes']['tracked_path'], item['tracked_path'])
                origin = origin['supersedes']['origin']
                self.assertEqual(origin['kind'], 'reviewed-actual-header-publisher-repair')
                self.assertEqual(origin['sha256'], header_repair)
                self.assertEqual(origin['source_path'], item['tracked_path'])
                self.assertIs(origin['source_only'], True)
                self.assertEqual(origin['correction'], 'complete-text-control-inner-text-element-definition')
                self.assertEqual(origin['supersedes']['sha256'], predecessor)
                self.assertEqual(origin['supersedes']['tracked_path'], item['tracked_path'])
                origin = origin['supersedes']['origin']
                self.assertEqual(origin['kind'], 'reviewed-publisher-successor')
                self.assertEqual(origin['sha256'], predecessor)
                self.assertEqual(origin['supersedes'], {
                    'capsule': capsule, 'logical_path': 'native/NativeDocumentV2Publisher.cpp', 'sha256': old})
                self.assertTrue(origin['source_only'])
                self.assertFalse(origin['abi_or_bounds_changed'])
                self.assertEqual(projection['files'][name], {'preimage_sha256': None, 'sha256': expected})
                self.assertEqual(projection['source_map']['sha256'], imports['capsule_source_map_sha256'])

    def test_editor_additional_owners_preserve_whole_unified_sibling_order(self):
        expected = {
            'UnifiedSource-be65d27a-9.cpp': [
                'dom/DocumentStorageAccess.cpp', 'dom/DocumentType.cpp', 'dom/DragEvent.cpp',
                '../Source/WebCore/dom/Element.cpp', 'dom/ElementData.cpp', 'dom/ElementInternals.cpp',
                'dom/ElementRareData.cpp', 'dom/ElementTextDirection.cpp'],
            'UnifiedSource-767013ce-4.cpp': [
                '../Source/WebCore/page/EventHandler.cpp', 'page/EventSource.cpp', 'page/FocusController.cpp',
                'page/Frame.cpp', 'page/FrameConsoleClient.cpp', 'page/FrameDestructionObserver.cpp',
                'page/FrameIdentifier.cpp', 'page/FrameSnapshotting.cpp'],
        }
        here = ROOT / assembly.RECIPE_ROOT
        physical = json.loads((here / 'maintenance-profile-physical.json').read_bytes())
        editor = json.loads((here / 'maintenance-profile-editor.json').read_bytes())
        shared = ['UnifiedSource-950a39b6-13.cpp', 'UnifiedSource-c57e08af-3.cpp',
                  'UnifiedSource-f34946be-3.cpp', 'UnifiedSource-be65d27a-6.cpp',
                  'PasteboardEmscripten.cpp']
        self.assertEqual(physical['engine_objects'][-5:], shared)
        self.assertEqual(editor['engine_objects'][-5:], shared)
        self.assertEqual(editor['engine_objects'][:-5], physical['engine_objects'][:-5] + list(expected))
        self.assertEqual(len(editor['direct_objects']), 35)
        self.assertEqual(sum(editor['archive_members'].values()) - len(editor['engine_objects']), 2060)
        for owner, includes in expected.items():
            with self.subTest(owner=owner):
                self.assertEqual((here / 'unified' / owner).read_bytes(),
                                 ''.join('#include "' + value + '"\n' for value in includes).encode())
                self.assertEqual(editor['source_bindings'][owner], 'source/engine/unified/' + owner)

    def test_shared_ui_owners_preserve_whole_unified_siblings_and_standalone_identity(self):
        expected = {
            'UnifiedSource-950a39b6-13.cpp': [
                'html/HTMLScriptElement.cpp', '../Source/WebCore/html/HTMLSelectElement.cpp',
                'html/HTMLSelectedContentElement.cpp', 'html/HTMLSlotElement.cpp',
                'html/HTMLSourceElement.cpp', 'html/HTMLSpanElement.cpp',
                'html/HTMLStyleElement.cpp', 'html/HTMLSummaryElement.cpp'],
            'UnifiedSource-c57e08af-3.cpp': [
                'loader/DocumentWriter.cpp', '../Source/WebCore/loader/EmptyClients.cpp',
                'loader/FTPDirectoryParser.cpp', 'loader/FetchIdioms.cpp',
                'loader/FormState.cpp', 'loader/FormSubmission.cpp',
                'loader/FrameLoadRequest.cpp', 'loader/FrameLoader.cpp'],
            'UnifiedSource-f34946be-3.cpp': [
                'editing/EditingStyle.cpp', '../Source/WebCore/editing/Editor.cpp',
                'editing/EditorCommand.cpp', 'editing/FontAttributeChanges.cpp',
                'editing/FontShadow.cpp', 'editing/FormatBlockCommand.cpp',
                'editing/FrameSelection.cpp', 'editing/HTMLInterchange.cpp'],
            'UnifiedSource-be65d27a-6.cpp': [
                'dom/DOMStringList.cpp', 'dom/DOMTZoneImpls.cpp',
                '../Source/WebCore/dom/DataTransfer.cpp', 'dom/DataTransferItem.cpp',
                'dom/DataTransferItemList.cpp', 'dom/DatasetDOMStringMap.cpp',
                'dom/DecodedDataDocumentParser.cpp', 'dom/DeviceMotionController.cpp'],
        }
        here = ROOT / assembly.RECIPE_ROOT
        for owner, includes in expected.items():
            self.assertEqual((here / 'unified' / owner).read_bytes(),
                             ''.join('#include "' + value + '"\n' for value in includes).encode())
        for selected in ('physical', 'editor'):
            profile = json.loads((here / ('maintenance-profile-' + selected + '.json')).read_bytes())
            for owner in expected:
                self.assertEqual(profile['source_bindings'][owner], 'source/engine/unified/' + owner)
            standalone = 'source/engine/Source/WebCore/platform/emscripten/PasteboardEmscripten.cpp'
            self.assertEqual(profile['source_bindings']['PasteboardEmscripten.cpp'], standalone)
            self.assertEqual(profile['owner_postimages']['PasteboardEmscripten.cpp'], [standalone])
            for name in ('HTMLSelectElement.cpp', 'EmptyClients.cpp', 'Editor.cpp',
                         'DataTransfer.cpp', 'PasteboardEmscripten.cpp'):
                self.assertNotIn(name, profile['direct_objects'])
            self.assertNotIn('Pasteboard.cpp', profile['engine_objects'])

    def test_shared_ui_selection_preserves_pixel_and_uses_physical_editor_overlays(self):
        here = ROOT / assembly.RECIPE_ROOT
        original = {
            'source/document-provider/runtime/BibCopiedDocumentBinding.cpp': (
                'source/runtime/BibCopiedDocumentBinding.cpp',
                'dfe56a0e289b843dd3b7c5f3cea41cd055202c4bae4e9391461d081a10b1ab56'),
            'source/wrapper/src/embedder/main.cpp': ('source/wrapper/src/embedder/main.cpp',
                '8c2f98835df730b17c0fb0f5bb5807c2ddaf9559797a59598173d95d02a70449'),
            'source/wrapper/src/embedder/BibFoundationServiceBridge.cpp': (
                'source/wrapper/src/embedder/BibFoundationServiceBridge.cpp',
                'a8a9e3901158e5e5bc697b427dfcbc75d465f5b4a5068db46c792cf7b75c0be8'),
        }
        pixel = json.loads((here / 'source-imports-pixel.json').read_bytes())
        for name, (tracked, pin) in original.items():
            self.assertEqual(pixel['files'][name]['tracked_path'], assembly.RECIPE_ROOT + '/' + tracked)
            self.assertEqual(pixel['files'][name]['sha256'], pin)
            self.assertEqual(sha((here / tracked).read_bytes()), pin)
        for selected in ('physical', 'editor'):
            imports = json.loads((here / ('source-imports-' + selected + '.json')).read_bytes())
            imports = composition_history(imports)
            for name, pin in (('main.cpp', '2a1ef9ff3574ca31d4f182457dc7b4a83a09cd7944a8a9b410d4109485db791d'),
                              ('BibFoundationServiceBridge.cpp', 'c9833fe476ef13afdde9c13e4c5cd288145ed6cb017e8c095a81d2339a89cb92')):
                item = imports['files']['source/wrapper/src/embedder/' + name]
                self.assertEqual(item['tracked_path'], assembly.RECIPE_ROOT + '/overlays/ui/wrapper/src/embedder/' + name)
                self.assertEqual(item['sha256'], pin)
            binding = imports['files']['source/document-provider/runtime/BibCopiedDocumentBinding.cpp']
            self.assertEqual(binding['tracked_path'], assembly.RECIPE_ROOT + '/overlays/' + selected
                             + '/runtime/BibCopiedDocumentBinding.cpp')
            for name in ('ui/BibEngineUiOwner.cpp', 'popup/BibNativePopupOwner.cpp',
                         'popup/NativePopupController.cpp', 'clipboard/BibClipboardStore.cpp'):
                logical = 'source/document-provider/' + name
                self.assertIn(logical, imports['files'])
                self.assertNotIn(logical, pixel['files'])

    def test_shared_ui_new_leaves_keep_real_supplier_and_logical_projection_preimages_distinct(self):
        here = ROOT / assembly.RECIPE_ROOT
        work = '.agent-work/appended-implementation-20261016/'
        packets = {
            'popup': 'b7d9bd5218ef53c2c06ac53e3c03b1b11252eb45ca25e4a38f421d4422c1a228',
            'clipboard': '13a95eb9637dec4a9e7827a34de79690ab70055084bb5065c6a53a203c638ea1',
        }
        suppliers = {
            'html/HTMLSelectElement.cpp': '72dbbadb8c01208192af65a97f913ac35a13db56a7b44057a7d1494e26e7757e',
            'loader/EmptyClients.cpp': '816baedf47261c9375aa9f4a8dd303f04e4266e47d4304b7443371c2c7cf3be4',
            'editing/Editor.cpp': 'f3c3bcbec9a2de12f69f10c1fe072ecb2de8afeb0d89a7a1d5c9e821bb1c2863',
            'dom/DataTransfer.cpp': '4e74e837716df0f8d417577208e0bb232e2c94e887e8c1e7ece665b4e3407bca',
            'platform/emscripten/PasteboardEmscripten.cpp': '41ed6a44ac90e299e927192a0fee3946b958d96fa87226594f707e3e97b37bcf',
        }
        primaries = {
            'UnifiedSource-950a39b6-13.cpp': 'b7f5bc891f37dad5d8b8e20a680072e4c878def9bd8fddb9eaabb7030b7bbc6a',
            'UnifiedSource-c57e08af-3.cpp': 'c68c0930d03c869117a8d7cb9570182d434f00822538ef6417e8008a9a1ef10d',
            'UnifiedSource-f34946be-3.cpp': 'a8a9444413fb7c0730496a1ac9cd1bc9fad37440ba15cd83534098583dcba88e',
            'UnifiedSource-be65d27a-6.cpp': 'a207f25f88a3420ab03a6537a69d963e7b7c8c080a66957a3e1df0844030c01a',
        }
        private = ('ui/BibEngineUiOwner.cpp', 'ui/BibEngineUiOwner.hpp',
            'popup/BibNativePopupOwner.cpp', 'popup/BibNativePopupOwner.hpp',
            'popup/BibNativePopupHooks.hpp', 'popup/NativePopupController.cpp',
            'popup/NativePopupController.hpp', 'clipboard/BibClipboardStore.cpp',
            'clipboard/BibClipboardStore.hpp', 'clipboard/BibInternalClipboard.hpp')
        for selected in ('physical', 'editor'):
            imports = json.loads((here / ('source-imports-' + selected + '.json')).read_bytes())
            projection = json.loads((here / ('source-projection-' + selected + '.json')).read_bytes())
            expected = {}
            for suffix in private:
                producer = 'native-html-clipboard-implementation-v1' if suffix.startswith('clipboard/') else 'native-html-popup-implementation-v1'
                released = ('controller/' + Path(suffix).name if suffix.startswith('popup/NativePopupController.')
                            else 'source/' + suffix)
                expected['source/document-provider/' + suffix] = work + producer + '/' + released
            for suffix in suppliers:
                producer = ('native-html-popup-implementation-v1/engine-call-sites/proposed/source/engine/'
                    if suffix.startswith(('html/', 'loader/')) else 'native-html-clipboard-implementation-v1/postimages/')
                expected['source/engine/Source/WebCore/' + suffix] = work + producer + 'Source/WebCore/' + suffix
            for owner in primaries:
                expected['source/engine/unified/' + owner] = work + 'rich-ui-retained-union-design-v1/wrapper-proposals/' + owner
            self.assertEqual(len(expected), 19)
            for name, source in expected.items():
                with self.subTest(selected=selected, source=name):
                    item = imports['files'][name]
                    origin = item['origin']
                    origin_sha256 = item['sha256']
                    if name == 'source/document-provider/popup/BibNativePopupOwner.cpp':
                        self.assertEqual(origin['kind'], 'reviewed-actual-header-popup-inlines-repair')
                        self.assertEqual(origin['correction'], 'node-element-frame-page-view-inline-definitions')
                        self.assertEqual(origin['sha256'], item['sha256'])
                        self.assertIs(origin['source_only'], True)
                        self.assertEqual(origin['source_path'], item['tracked_path'])
                        self.assertEqual(origin['supersedes']['tracked_path'], item['tracked_path'])
                        origin_sha256 = 'fbb9efa62ff6823a9ceefe179c900ddd26f559c002f6465c6a9821ee28036435'
                        self.assertEqual(origin['supersedes']['sha256'], origin_sha256)
                        origin = origin['supersedes']['origin']
                    if name == 'source/engine/Source/WebCore/platform/emscripten/PasteboardEmscripten.cpp':
                        original_sha256 = '575e0283f0aa4e9234e70781549476a6865df57ad6012ef80a2d369bf0385824'
                        repaired_sha256 = 'd105c6c16b269fcd0e5334dcdcad4a9f306945e744125257eb140cd3ebdc669e'
                        original_supplier = {
                            'path': 'third_party/WebKit/Source/WebCore/platform/emscripten/PasteboardEmscripten.cpp',
                            'sha256': suppliers['platform/emscripten/PasteboardEmscripten.cpp'],
                        }
                        predecessor = {
                            'kind': 'reviewed-shared-rich-ui-successor',
                            'selection': 'shared-ui-popup-and-internal-rich-clipboard',
                            'sha256': original_sha256, 'source_only': True,
                            'source_path': source, 'reviewed_packets': packets,
                            'original_supplier': original_supplier,
                        }
                        self.assertEqual(item['bytes'], 10733)
                        self.assertEqual(item['sha256'], repaired_sha256)
                        self.assertEqual(origin, {
                            'kind': 'reviewed-clipboard-compile-closure-successor',
                            'selection': 'clipboard-wtf-function-compile-closure',
                            'sha256': repaired_sha256, 'source_only': True,
                            'source_path': item['tracked_path'],
                            'original_supplier': original_supplier,
                            'supersedes': {'origin': predecessor,
                                'sha256': original_sha256, 'tracked_path': item['tracked_path']},
                        })
                        origin = origin['supersedes']['origin']
                        origin_sha256 = original_sha256
                    self.assertEqual(origin['kind'], 'reviewed-shared-rich-ui-successor')
                    self.assertEqual(origin['selection'], 'shared-ui-popup-and-internal-rich-clipboard')
                    self.assertEqual(origin['sha256'], origin_sha256)
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['reviewed_packets'], packets)
                    self.assertEqual(origin['source_path'], source)
                    self.assertEqual(projection['files'][name], {'preimage_sha256': None, 'sha256': item['sha256']})
            for suffix, pin in suppliers.items():
                origin = imports['files']['source/engine/Source/WebCore/' + suffix]['origin']
                self.assertEqual(origin['original_supplier'], {
                    'path': 'third_party/WebKit/Source/WebCore/' + suffix, 'sha256': pin})
            for owner, pin in primaries.items():
                origin = imports['files']['source/engine/unified/' + owner]['origin']
                self.assertEqual(origin['original_primary'], {
                    'path': 'build/webcore/WebCore/DerivedSources/unified-sources/' + owner, 'sha256': pin})

    def test_shared_ui_editor_callsites_keep_exact_nested_capsule_history(self):
        here = ROOT / assembly.RECIPE_ROOT
        imports = json.loads((here / 'source-imports-editor.json').read_bytes())
        imports = composition_history(imports)
        history = {
            'editor/BibNativeEditorBackend.cpp': (
                '98f95b8e1c4d352a60a412fb8e97730332bb15b1b8a6995d65036bab19762839', None),
            'key/NativeRawKeyDispatch.cpp': (
                '0efb91a52eee6b8f95526eac3461683252addae84ef5a10023c14beafc279325',
                '3997aa7526eb425a8bdb00a4c8f8f2c20145166054149fa2d4c220ba102177ec'),
            'key/NativeRawKeyDispatch.hpp': (
                'bd9229750368d6ee63a389645c5b99b60c6a5546dd8a7d8ead3be2f85a85f244',
                'b79be4a378ee90c4ae262f979efa26dd63dfca537f9614cd861a3d1c155b62ad'),
            'physical/BibDocumentPhysicalProvider.cpp': (
                '1ccbf5fa7d405022f139440ad2f681cadd57bea461d7a7cbd8558862e56a3e5e',
                '1ff7236a25294cf558ecd7ca164fe9e969fd305c13a2b910c7ac315c396c7b83'),
            'runtime/BibCopiedDocumentBinding.cpp': (
                '62876b58a04dca2825bbffa4803c295324083c9fb28faa8cfad3a5a344e3eb29',
                '9e1c0b10cc3b5c6c61ca0ecb1ae220e0dcbc9e7cde02aee1d15d353067d060bd'),
            'wrapper/src/embedder/main.cpp': (
                '8c2f98835df730b17c0fb0f5bb5807c2ddaf9559797a59598173d95d02a70449', None),
            'wrapper/src/embedder/BibFoundationServiceBridge.cpp': (
                'a8a9e3901158e5e5bc697b427dfcbc75d465f5b4a5068db46c792cf7b75c0be8', None),
        }
        for suffix, (pin, previous_pin) in history.items():
            wrapper = suffix.startswith('wrapper/')
            name = 'source/' + (suffix if wrapper else 'document-provider/' + suffix)
            origin = imports['files'][name]['origin']
            old = {'capsule': '0005-cpp-only-outcome', 'logical_path': suffix, 'sha256': pin}
            if previous_pin is not None:
                old['supersedes'] = {'origin': {'capsule': '0003-document-physical',
                    'logical_path': suffix, 'sha256': previous_pin}, 'sha256': previous_pin}
            tracked = assembly.RECIPE_ROOT + ('/source/' if wrapper else '/overlays/editor/') + suffix
            release = 'integration-corrections/proposed/' if suffix.startswith('physical/') else 'call-sites/proposed/'
            with self.subTest(source=name):
                selected_sha = imports['files'][name]['sha256']
                if suffix == 'editor/BibNativeEditorBackend.cpp':
                    self.assertEqual(origin['kind'], 'reviewed-actual-header-editor-inlines-repair')
                    self.assertEqual(origin['correction'], 'document-page-view-element-inline-definitions')
                    self.assertEqual(origin['sha256'], selected_sha)
                    self.assertEqual(origin['source_path'], tracked)
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['supersedes']['tracked_path'], tracked)
                    self.assertEqual(origin['supersedes']['sha256'],
                        '9c315b84feb67ca805be986ca71b3ea388c586f5639efa91b5afaea80b1a8e6e')
                    selected_sha = origin['supersedes']['sha256']
                    origin = origin['supersedes']['origin']
                if suffix == 'editor/BibNativeEditorBackend.cpp':
                    self.assertEqual(origin['kind'], 'reviewed-actual-header-editor-composition-repair')
                    self.assertEqual(origin['correction'], 'if-initializer-composition-local')
                    self.assertEqual(origin['sha256'], selected_sha)
                    self.assertEqual(origin['source_path'], tracked)
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['supersedes']['tracked_path'], tracked)
                    self.assertEqual(origin['supersedes']['sha256'],
                        '1cc5c5140b7d8855cf37df214ba396ef051f474d7783ab5d9469365784496aaa')
                    selected_sha = origin['supersedes']['sha256']
                    origin = origin['supersedes']['origin']
                if suffix == 'editor/BibNativeEditorBackend.cpp':
                    self.assertEqual(origin['kind'], 'reviewed-actual-header-editor-backend-repair')
                    self.assertEqual(origin['correction'], 'text-control-inner-elements-defining-header')
                    self.assertEqual(origin['sha256'], selected_sha)
                    self.assertEqual(origin['source_path'], tracked)
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['supersedes']['tracked_path'], tracked)
                    self.assertEqual(origin['supersedes']['sha256'],
                        '3994608abd7f8ac449f411f22b673edf3021ae9ce9d1591b229d5d6a8bd2faf2')
                    selected_sha = origin['supersedes']['sha256']
                    origin = origin['supersedes']['origin']
                if suffix == 'key/NativeRawKeyDispatch.cpp':
                    self.assertEqual(origin['kind'], 'reviewed-actual-header-raw-key-repair')
                    self.assertEqual(origin['sha256'], selected_sha)
                    self.assertEqual(origin['source_path'], tracked)
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['correction'], 'global-latin1-character-type')
                    self.assertEqual(origin['supersedes']['tracked_path'], tracked)
                    self.assertEqual(origin['supersedes']['sha256'],
                        '98ea00e3c7c543f5cf4941390aaccb981f9b570689ba254836166a1102819736')
                    selected_sha = origin['supersedes']['sha256']
                    origin = origin['supersedes']['origin']
                if suffix == 'wrapper/src/embedder/main.cpp':
                    self.assertEqual(origin['kind'], 'reviewed-actual-header-main-repair')
                    self.assertEqual(origin['sha256'], selected_sha)
                    self.assertEqual(origin['source_path'], imports['files'][name]['tracked_path'])
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['correction'], 'optional-page-identifier')
                    self.assertEqual(origin['supersedes']['tracked_path'], imports['files'][name]['tracked_path'])
                    self.assertEqual(origin['supersedes']['sha256'],
                        'b721ec17ea0b7a029cd2ace6dc2f8431ec8a340957adda4d3815646d56ad7769')
                    selected_sha = origin['supersedes']['sha256']
                    origin = origin['supersedes']['origin']
                if suffix == 'physical/BibDocumentPhysicalProvider.cpp':
                    self.assertEqual(origin['kind'], 'reviewed-actual-header-inline-repair')
                    self.assertEqual(origin['sha256'], selected_sha)
                    self.assertEqual(origin['source_path'], tracked)
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['correction'],
                        'complete-frame-page-and-local-frame-view-inline-definitions')
                    self.assertEqual(origin['supersedes']['tracked_path'], tracked)
                    self.assertEqual(origin['supersedes']['sha256'],
                        '105b7a09fb6144ed5c0397358a80df633fdcddbfcc8d0d6c525b55f6cc2191a7')
                    selected_sha = origin['supersedes']['sha256']
                    origin = origin['supersedes']['origin']
                    self.assertEqual(origin['kind'], 'reviewed-actual-header-cpp-repair')
                    self.assertEqual(origin['sha256'], selected_sha)
                    self.assertEqual(origin['source_path'], tracked)
                    self.assertIs(origin['source_only'], True)
                    self.assertEqual(origin['correction'],
                        'qualified-platform-modifier-helper-and-complete-wheel-processing-enum')
                    self.assertEqual(origin['supersedes']['tracked_path'], tracked)
                    self.assertEqual(origin['supersedes']['sha256'],
                        '82782522288f63f61d485b1fa8a92eb23ce5bb51b92527846a7411a553a28570')
                    selected_sha = origin['supersedes']['sha256']
                    origin = origin['supersedes']['origin']
                self.assertEqual(origin['kind'], 'reviewed-shared-rich-ui-successor')
                self.assertEqual(origin['selection'], 'shared-ui-popup-and-internal-rich-clipboard')
                self.assertEqual(origin['sha256'], selected_sha)
                self.assertIs(origin['source_only'], True)
                self.assertEqual(origin['reviewed_packets'], {
                    'popup': 'b7d9bd5218ef53c2c06ac53e3c03b1b11252eb45ca25e4a38f421d4422c1a228',
                    'clipboard': '13a95eb9637dec4a9e7827a34de79690ab70055084bb5065c6a53a203c638ea1'})
                self.assertEqual(origin['source_path'], '.agent-work/appended-implementation-20261016/'
                    + 'native-html-popup-implementation-v1/' + release + tracked)
                self.assertEqual(origin['supersedes'], {'origin': old, 'sha256': pin, 'tracked_path': tracked})

    def test_actual_header_profile_repair_keeps_exact_capsule_history_and_consteval_rejection(self):
        here = ROOT / assembly.RECIPE_ROOT
        logical = 'source/document-provider/portable/appended_engine_input_profile.hpp'
        tracked = assembly.RECIPE_ROOT + '/overlays/physical/portable/appended_engine_input_profile.hpp'
        previous = '0957073f93b9ea8e9f264bb9b7aff2ae247d13b122bb4856fae8cbf47942c2aa'
        expected = '2624d693e52fdab0a98129c4ba0e7d1bf491e167d3c508e9b81c21034ebe17b8'
        for selected, capsule in (('physical', '0003-document-physical'), ('editor', '0005-cpp-only-outcome')):
            with self.subTest(profile=selected):
                imports = json.loads((here / ('source-imports-' + selected + '.json')).read_bytes())
                projection = json.loads((here / ('source-projection-' + selected + '.json')).read_bytes())
                item = imports['files'][logical]
                self.assertEqual(item['tracked_path'], tracked)
                self.assertEqual(item['sha256'], expected)
                self.assertEqual(item['bytes'], 4733)
                self.assertEqual(item['origin'], {
                    'kind': 'reviewed-actual-header-profile-repair',
                    'correction': 'noexceptions-consteval-hash',
                    'sha256': expected, 'source_path': tracked, 'source_only': True,
                    'supersedes': {'origin': {'capsule': capsule,
                        'logical_path': 'portable/appended_engine_input_profile.hpp', 'sha256': previous},
                        'sha256': previous, 'tracked_path': tracked},
                })
                self.assertEqual(projection['files'][logical], {'preimage_sha256': None, 'sha256': expected})
                self.assertEqual(projection['source_map']['sha256'], imports['capsule_source_map_sha256'])
        pixel = json.loads((here / 'source-imports-pixel.json').read_bytes())
        self.assertNotIn(logical, pixel['files'])
        paths = (ROOT / tracked, ROOT / 'gui/shared/appended_engine_input_profile.hpp',
            ROOT / 'recipes/webkitwasm-native-rich4083-v1/source/document-provider/portable/appended_engine_input_profile.hpp')
        for path in paths:
            with self.subTest(header=path):
                raw = path.read_bytes()
                self.assertEqual(sha(raw), expected)
                text = raw.decode('utf-8')
                self.assertIn('#include <cstdlib>', text)
                self.assertIn('consteval Digest digest(std::string_view text)', text)
                self.assertIn('if (text.size() != 64) std::abort();', text)
                self.assertIn("if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0');", text)
                self.assertIn("if (c >= 'a' && c <= 'f') return static_cast<unsigned>(c - 'a' + 10);", text)
                self.assertEqual(text.count('std::abort();'), 2)
                self.assertNotIn('throw ', text)

    def test_actual_header_main_repair_keeps_rich_ui_history_optional_guard_and_exception_policy(self):
        here = ROOT / assembly.RECIPE_ROOT
        logical = 'source/wrapper/src/embedder/main.cpp'
        tracked = assembly.RECIPE_ROOT + '/overlays/ui/wrapper/src/embedder/main.cpp'
        previous = 'b721ec17ea0b7a029cd2ace6dc2f8431ec8a340957adda4d3815646d56ad7769'
        expected = '2a1ef9ff3574ca31d4f182457dc7b4a83a09cd7944a8a9b410d4109485db791d'
        capsule_pin = '8c2f98835df730b17c0fb0f5bb5807c2ddaf9559797a59598173d95d02a70449'
        capsule_path = assembly.RECIPE_ROOT + '/source/wrapper/src/embedder/main.cpp'
        for selected, capsule in (('physical', '0003-document-physical'), ('editor', '0005-cpp-only-outcome')):
            with self.subTest(profile=selected):
                imports = json.loads((here / ('source-imports-' + selected + '.json')).read_bytes())
                projection = json.loads((here / ('source-projection-' + selected + '.json')).read_bytes())
                imports, projection = composition_history(imports, projection)
                item = imports['files'][logical]
                self.assertEqual(item['tracked_path'], tracked)
                self.assertEqual(item['sha256'], expected)
                self.assertEqual(item['bytes'], 161502)
                old_origin = {
                    'kind': 'reviewed-shared-rich-ui-successor',
                    'selection': 'shared-ui-popup-and-internal-rich-clipboard',
                    'sha256': previous, 'source_only': True,
                    'source_path': '.agent-work/appended-implementation-20261016/'
                        + 'native-html-popup-implementation-v1/call-sites/proposed/' + capsule_path,
                    'reviewed_packets': {
                        'popup': 'b7d9bd5218ef53c2c06ac53e3c03b1b11252eb45ca25e4a38f421d4422c1a228',
                        'clipboard': '13a95eb9637dec4a9e7827a34de79690ab70055084bb5065c6a53a203c638ea1'},
                    'supersedes': {'origin': {'capsule': capsule,
                        'logical_path': 'wrapper/src/embedder/main.cpp', 'sha256': capsule_pin},
                        'sha256': capsule_pin, 'tracked_path': capsule_path},
                }
                self.assertEqual(item['origin'], {
                    'kind': 'reviewed-actual-header-main-repair', 'correction': 'optional-page-identifier',
                    'sha256': expected, 'source_path': tracked, 'source_only': True,
                    'supersedes': {'origin': old_origin, 'sha256': previous, 'tracked_path': tracked},
                })
                self.assertEqual(projection['files'][logical], {
                    'preimage_sha256': '485ea035f7886f153c5e3976d096413fe584cc65563e4b2a59c7d364d1a86373',
                    'sha256': expected})
                self.assertEqual(projection['source_map']['sha256'], imports['capsule_source_map_sha256'])
        optional_guard = ('    const auto identifier = page->identifier();\n'
            '    if (!identifier)\n'
            '        return false;\n'
            '    const auto pageIdentifier = identifier->toUInt64();\n'
            '    if (!pageIdentifier)\n'
            '        return false;')
        paths = ((ROOT / tracked, expected),
            (ROOT / 'recipes/webkitwasm-native-rich4083-v1/source/wrapper/src/embedder/main.cpp',
             '4cb8131b86f6bf1ede303053b7aa1752fab16dd66fe8b0271f97d256e0cd137b'))
        for path, pin in paths:
            with self.subTest(main=path):
                raw = composition_predecessor_bytes(path.read_bytes())
                self.assertEqual(sha(raw), pin)
                text = raw.decode('utf-8')
                self.assertEqual(text.count('const auto identifier = page->identifier();'), 1)
                self.assertIn(optional_guard, text)
                self.assertNotIn('page->identifier().toUInt64()', text)
        policies = {
            'pixel': 'e556f706b285a2cb3ef36a04ea74ab19604326c17095fa1559c4845094834f3d',
            'physical': '9017e947c7138356c83601c42248a6e0c028ba55a424f5bed5df5d6890f9efb0',
            'editor': 'f6856c5e58a7eaee06e26f7b16e923a1b6c3fe5b1750cf79a1a5e89478b4f6b5',
        }
        for selected, pin in policies.items():
            with self.subTest(exception_policy=selected):
                profile = json.loads((here / ('maintenance-profile-' + selected + '.json')).read_bytes())
                policy = {name: profile[name] for name in ('compile_literals', 'exceptions')}
                raw = (json.dumps(policy, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
                self.assertEqual(sha(raw), pin)
                self.assertNotIn('main.cpp', profile['exceptions'])
                self.assertIn('-fno-exceptions', profile['compile_literals'])
                self.assertIn('-fno-rtti', profile['compile_literals'])

    def test_actual_header_raw_key_repair_keeps_history_global_type_and_marker_paths(self):
        here = ROOT / assembly.RECIPE_ROOT
        logical = 'source/document-provider/key/NativeRawKeyDispatch.cpp'
        include = '#include <wtf/text/Latin1Character.h>\n'
        cases = (
            ('physical', assembly.RECIPE_ROOT + '/overlays/physical/key/NativeRawKeyDispatch.cpp',
             'cf73798da3493f7b6e0da645f82668e81d216782819d1d0878463ec24f584cc4',
             '66195b89b111fa34ef67eb851a29d1f1301658d7be6498e34623eed36f3c1341', 10787),
            ('editor', assembly.RECIPE_ROOT + '/overlays/editor/key/NativeRawKeyDispatch.cpp',
             '98ea00e3c7c543f5cf4941390aaccb981f9b570689ba254836166a1102819736',
             '1c305f7891339a46ac6425d96edbe17e0157b72bbf5c3434a98baae053e8ca4a', 13797),
            ('native', 'recipes/webkitwasm-native-rich4083-v1/source/document-provider/key/NativeRawKeyDispatch.cpp',
             '98ea00e3c7c543f5cf4941390aaccb981f9b570689ba254836166a1102819736',
             '1c305f7891339a46ac6425d96edbe17e0157b72bbf5c3434a98baae053e8ca4a', 13797),
        )
        for selected, tracked, previous, expected, size in cases:
            with self.subTest(raw_key=selected):
                raw = (ROOT / tracked).read_bytes()
                self.assertEqual(sha(raw), expected)
                self.assertEqual(len(raw), size)
                text = raw.decode('utf-8')
                self.assertEqual(text.count(include), 1)
                self.assertEqual(text.count('Latin1Character'), 3)
                self.assertNotIn('WTF::Latin1Character', text)
                self.assertEqual(text.count('std::span<Latin1Character> characters;'), 1)
                self.assertEqual(text.count('static_cast<Latin1Character>(compatibility->identifier[i])'), 1)
                self.assertIn('return WTF::String::fromUTF8(std::span<const char>(value.data(), value.size()));', text)
                self.assertIn('WTF::String marker = WTF::String::createUninitialized(', text)
                self.assertIn('RELEASE_ASSERT(marker.impl() && marker.impl() != canonical.impl() && !marker.impl()->isAtom());', text)
                self.assertIn('activeMarker.compare_exchange_strong(empty, marker_.impl(), std::memory_order_acq_rel)', text)
                self.assertIn('sequence, authority, authority_context, canonical, marker, event, input.location);', text)
                # Reversing only the one include and two type qualifications must
                # recover the exact old body, including every marker/span path.
                predecessor = text.replace(include, '').replace('std::span<Latin1Character>',
                    'std::span<WTF::Latin1Character>').replace('static_cast<Latin1Character>',
                    'static_cast<WTF::Latin1Character>')
                self.assertEqual(sha(predecessor.encode('utf-8')), previous)
                if selected == 'native':
                    continue
                imports = json.loads((here / ('source-imports-' + selected + '.json')).read_bytes())
                projection = json.loads((here / ('source-projection-' + selected + '.json')).read_bytes())
                item = imports['files'][logical]
                self.assertEqual(item['tracked_path'], tracked)
                self.assertEqual(item['sha256'], expected)
                self.assertEqual(item['bytes'], size)
                origin = item['origin']
                self.assertEqual(set(origin), {'kind', 'correction', 'sha256', 'source_path', 'source_only', 'supersedes'})
                self.assertEqual(origin['kind'], 'reviewed-actual-header-raw-key-repair')
                self.assertEqual(origin['correction'], 'global-latin1-character-type')
                self.assertEqual(origin['sha256'], expected)
                self.assertEqual(origin['source_path'], tracked)
                self.assertIs(origin['source_only'], True)
                self.assertEqual(set(origin['supersedes']), {'origin', 'sha256', 'tracked_path'})
                self.assertEqual(origin['supersedes']['sha256'], previous)
                self.assertEqual(origin['supersedes']['tracked_path'], tracked)
                self.assertEqual(origin['supersedes']['origin']['sha256'], previous)
                self.assertEqual(projection['files'][logical]['sha256'], expected)
                self.assertEqual(projection['source_map']['sha256'], imports['capsule_source_map_sha256'])

    def test_actual_editor_backend_defining_header_preserves_exact_predecessor(self):
        old = '3994608abd7f8ac449f411f22b673edf3021ae9ce9d1591b229d5d6a8bd2faf2'
        new = '5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815'
        logical = 'source/document-provider/editor/BibNativeEditorBackend.cpp'
        cases = (
            assembly.RECIPE_ROOT + '/overlays/editor/editor/BibNativeEditorBackend.cpp',
            'recipes/webkitwasm-native-rich4083-v1/' + logical,
        )
        for tracked in cases:
            with self.subTest(editor_backend=tracked):
                raw = composition_predecessor_bytes((ROOT / tracked).read_bytes())
                self.assertEqual(sha(raw), new)
                self.assertEqual(len(raw), 47742)
                self.assertEqual(raw.count(b'#include "TextControlInnerElements.h"\n'), 1)
                self.assertNotIn(b'#include "TextControlInnerTextElement.h"', raw)
                predecessor = raw.replace(b'#include \"DocumentPage.h\"\n', b'').replace(b'#include \"DocumentView.h\"\n', b'').replace(b'#include \"ElementInlines.h\"\n', b'').replace(b'composition_data', b'data').replace(b'#include "TextControlInnerElements.h"',
                    b'#include "TextControlInnerTextElement.h"')
                self.assertEqual(sha(predecessor), old)
        here = ROOT / assembly.RECIPE_ROOT
        imports = json.loads((here / 'source-imports-editor.json').read_bytes())
        projection = json.loads((here / 'source-projection-editor.json').read_bytes())
        imports, projection = composition_history(imports, projection)
        item = imports['files'][logical]
        self.assertEqual(item['sha256'], new)
        self.assertEqual(item['bytes'], 47742)
        self.assertEqual(item['origin']['supersedes']['sha256'], '9c315b84feb67ca805be986ca71b3ea388c586f5639efa91b5afaea80b1a8e6e')
        self.assertEqual(item['origin']['supersedes']['origin']['sha256'], '9c315b84feb67ca805be986ca71b3ea388c586f5639efa91b5afaea80b1a8e6e')
        self.assertEqual(projection['files'][logical], {'preimage_sha256': None, 'sha256': new})
        native = ROOT / 'recipes/webkitwasm-native-rich4083-v1'
        mapped = json.loads((native / 'source-imports.json').read_bytes())
        provenance_raw = (native / 'provenance.json').read_bytes()
        provenance = json.loads(provenance_raw)
        record = provenance['runtime_files'][logical]['successor']['supersedes']['origin']
        self.assertEqual(record['after_sha256'], new)
        self.assertEqual(record['successor']['supersedes']['origin']['after_sha256'], '9c315b84feb67ca805be986ca71b3ea388c586f5639efa91b5afaea80b1a8e6e')
        self.assertEqual(mapped['inputs'][logical]['origin']['record']['successor']['supersedes']['origin'], record)
        self.assertEqual(mapped['inputs'][logical]['origin']['record']['successor']['supersedes']['sha256'], new)
        self.assertEqual(mapped['inputs']['provenance.json']['sha256'], sha(provenance_raw))
        self.assertEqual(mapped['inputs']['provenance.json']['bytes'], len(provenance_raw))
        self.assertEqual(mapped['provenance']['sha256'], sha(provenance_raw))

    def test_editor_composition_local_rename_preserves_exact_scope_and_prior_header_body(self):
        expected = '9c315b84feb67ca805be986ca71b3ea388c586f5639efa91b5afaea80b1a8e6e'
        previous = '1cc5c5140b7d8855cf37df214ba396ef051f474d7783ab5d9469365784496aaa'
        cases = (
            assembly.RECIPE_ROOT + '/overlays/editor/editor/BibNativeEditorBackend.cpp',
            'recipes/webkitwasm-native-rich4083-v1/source/document-provider/editor/BibNativeEditorBackend.cpp',
        )
        for tracked in cases:
            with self.subTest(composition_scope=tracked):
                raw = composition_predecessor_bytes((ROOT / tracked).read_bytes())
                self.assertEqual(sha(raw), '5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815')
                raw = raw.replace(b'#include \"DocumentPage.h\"\n', b'').replace(b'#include \"DocumentView.h\"\n', b'').replace(b'#include \"ElementInlines.h\"\n', b'')
                self.assertEqual(sha(raw), expected)
                self.assertEqual(len(raw), 47662)
                self.assertEqual(raw.count(b'composition_data'), 8)
                self.assertEqual(raw.count(b'const auto& composition_data=std::get<E::CompositionData>(observation.data);'), 1)
                self.assertIn(b'else if(auto* data=std::get_if<E::TextData>(&observation.data)){', raw)
                self.assertIn(b'const auto& data=std::get<E::CompositionData>(observation.data);\n                if(!data.text.empty())known_cancelled=true;', raw)
                self.assertEqual(sha(raw.replace(b'composition_data', b'data')), previous)
                self.assertIn(b'if(composition_data.operation==gui_surface::CompositionOperation::begin)', raw)
                self.assertIn(b'if(composition_data.operation==gui_surface::CompositionOperation::update)', raw)
                self.assertIn(b'if(composition_data.operation==gui_surface::CompositionOperation::cancel)', raw)
                self.assertIn(b'editor.confirmComposition(native_text);transport_composition=0;', raw)

    def test_editor_inline_definition_includes_preserve_exact_composition_body(self):
        expected = '5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815'
        previous = '9c315b84feb67ca805be986ca71b3ea388c586f5639efa91b5afaea80b1a8e6e'
        cases = (
            assembly.RECIPE_ROOT + '/overlays/editor/editor/BibNativeEditorBackend.cpp',
            'recipes/webkitwasm-native-rich4083-v1/source/document-provider/editor/BibNativeEditorBackend.cpp',
        )
        for tracked in cases:
            with self.subTest(editor_inlines=tracked):
                raw = composition_predecessor_bytes((ROOT / tracked).read_bytes())
                self.assertEqual(sha(raw), expected)
                self.assertEqual(len(raw), 47742)
                prior = raw
                for header in ('DocumentPage.h', 'DocumentView.h', 'ElementInlines.h'):
                    include = ('#include "' + header + '"\n').encode()
                    self.assertEqual(raw.count(include), 1)
                    prior = prior.replace(include, b'')
                self.assertEqual(sha(prior), previous)
                self.assertEqual(prior.count(b'composition_data'), 8)

    def test_popup_inline_includes_preserve_exact_body_and_both_profile_histories(self):
        previous = 'fbb9efa62ff6823a9ceefe179c900ddd26f559c002f6465c6a9821ee28036435'
        expected = 'd8822f18b214cedf9490a758c52c06a3ca3fc70d9b5b48e9dcbe8de55e4594d9'
        logical = 'source/document-provider/popup/BibNativePopupOwner.cpp'
        tracked = assembly.RECIPE_ROOT + '/overlays/ui/popup/BibNativePopupOwner.cpp'
        native = 'recipes/webkitwasm-native-rich4083-v1/'
        for path in (tracked, native + logical):
            with self.subTest(popup_inlines=path):
                raw = (ROOT / path).read_bytes()
                self.assertEqual(sha(raw), expected)
                self.assertEqual(len(raw), 29528)
                prior = raw
                for header in ('NodeDocument.h', 'ElementInlines.h',
                               'FrameDestructionObserverInlines.h', 'DocumentPage.h', 'DocumentView.h'):
                    include = ('#include "' + header + '"\n').encode()
                    self.assertEqual(raw.count(include), 1)
                    prior = prior.replace(include, b'')
                self.assertEqual(sha(prior), previous)
                self.assertEqual(len(prior), 29377)
        for profile in ('physical', 'editor'):
            imports = json.loads((ROOT / assembly.RECIPE_ROOT / ('source-imports-' + profile + '.json')).read_bytes())
            projection = json.loads((ROOT / assembly.RECIPE_ROOT / ('source-projection-' + profile + '.json')).read_bytes())
            item = imports['files'][logical]
            self.assertEqual((item['sha256'], item['bytes'], item['tracked_path']), (expected, 29528, tracked))
            self.assertEqual(item['origin']['supersedes']['sha256'], previous)
            self.assertEqual(item['origin']['supersedes']['origin']['sha256'], previous)
            self.assertEqual(projection['files'][logical], {'preimage_sha256': None, 'sha256': expected})
        provenance_raw = (ROOT / native / 'provenance.json').read_bytes()
        provenance = json.loads(provenance_raw)
        imports = json.loads((ROOT / native / 'source-imports.json').read_bytes())
        record = provenance['runtime_files'][logical]
        self.assertEqual((record['after_sha256'], record['after_bytes']), (expected, 29528))
        self.assertEqual((record['sha256'], record['bytes'], record['preimage_sha256']), (previous, 29377, None))
        self.assertEqual(record['successor']['supersedes']['origin']['successor']['sha256'], previous)
        self.assertEqual(imports['inputs'][logical]['origin']['record'], record)
        self.assertEqual((imports['inputs'][logical]['sha256'], imports['inputs'][logical]['bytes']), (expected, 29528))
        self.assertEqual(imports['provenance']['sha256'], sha(provenance_raw))
        self.assertEqual((imports['inputs']['provenance.json']['sha256'], imports['inputs']['provenance.json']['bytes']),
                         (sha(provenance_raw), len(provenance_raw)))

    def test_editor_selector_remains_distinct_from_legacy_document_contract(self):
        driver = assembly.BUNDLE.load('appended_engine_document_maintenance')
        self.assertEqual(driver.profile_selector('editor'), 'editor')
        with self.assertRaises(ValueError):
            contract.document_selector('editor')

    def test_origin_must_name_selected_successor_not_superseded_source(self):
        name = 'source/document-provider/portable/BibEngineCopiedDocumentFacts.h'
        path = ROOT / assembly.RECIPE_ROOT / 'source-imports-pixel.json'
        actual_read = assembly.read_json
        imports, _, _ = actual_read(path)
        item = imports['files'][name]
        self.assertEqual(item['origin']['capsule'], '0003-document-physical')
        self.assertEqual(item['origin']['sha256'], item['sha256'])
        self.assertNotEqual(item['origin']['supersedes']['sha256'], item['sha256'])
        def stale_origin(current, pin=None):
            value, raw, saved = actual_read(current, pin)
            if current == path:
                value['files'][name]['origin']['sha256'] = item['origin']['supersedes']['sha256']
            return value, raw, saved
        with mock.patch.object(assembly, 'read_json', side_effect=stale_origin), \
             self.assertRaisesRegex(ValueError, 'origin differs'):
            assembly._maintained(ROOT, 'pixel')


    def test_composition_inverse_source_successor_preserves_shared_ui_and_exact_preimages(self):
        here = ROOT / assembly.RECIPE_ROOT
        actual = json.loads((here / 'source-imports-editor.json').read_bytes())
        projection = json.loads((here / 'source-projection-editor.json').read_bytes())
        historical, old_projection = composition_history(actual, projection)
        names = (
            'source/document-provider/editor/BibNativeEditorBackend.cpp',
            'source/wrapper/src/embedder/main.cpp',
            'source/wrapper/src/embedder/BibPageClients.h',
            'source/wrapper/src/embedder/BibUndoHistory.h')
        self.assertEqual(len(actual['files']), 159)
        for name in names:
            item, prior = actual['files'][name], historical['files'][name]
            raw = (ROOT / item['tracked_path']).read_bytes()
            self.assertEqual(sha(raw), item['sha256'])
            self.assertEqual(len(raw), item['bytes'])
            self.assertEqual(sha(composition_predecessor_bytes(raw)), prior['sha256'])
            self.assertEqual(projection['files'][name]['preimage_sha256'], old_projection['files'][name]['preimage_sha256'])
            self.assertEqual(item['origin']['supersedes']['origin'], prior['origin'])
        main = actual['files']['source/wrapper/src/embedder/main.cpp']
        self.assertEqual(main['tracked_path'], assembly.RECIPE_ROOT + '/overlays/editor/wrapper/src/embedder/main.cpp')
        self.assertEqual(main['origin']['supersedes']['tracked_path'], assembly.RECIPE_ROOT + '/overlays/ui/wrapper/src/embedder/main.cpp')
        physical = json.loads((here / 'source-imports-physical.json').read_bytes())
        shared = physical['files']['source/wrapper/src/embedder/main.cpp']
        self.assertEqual(sha((ROOT / shared['tracked_path']).read_bytes()), '2a1ef9ff3574ca31d4f182457dc7b4a83a09cd7944a8a9b410d4109485db791d')
        bridge = 'source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h'
        item = actual['files'][bridge]
        self.assertEqual((item['sha256'], item['bytes'], item['mode'], item['role']),
            ('1572b86481c93b9568c781ababc9f6645f505a038704f91236192e31a4208118', 592, 420, 'source'))
        self.assertEqual(projection['files'][bridge], {'preimage_sha256': None, 'sha256': item['sha256']})
        self.assertEqual(item['origin']['kind'], 'reviewed-native-composition-undo-private-bridge')
        self.assertIs(item['origin']['source_only'], True)
        self.assertNotIn('supersedes', item['origin'])
        self.assertNotIn(bridge, physical['files'])
        native = ROOT / 'recipes/webkitwasm-native-rich4083-v1'
        for name in names:
            raw = (native / name).read_bytes()
            self.assertIn(sha(raw), COMPOSITION_REVERSE)
            self.assertNotEqual(raw, composition_predecessor_bytes(raw))
        self.assertEqual(sha((here / 'provenance/editor-source-map.json').read_bytes()),
            'a97017168b817334d1a094300e904f09110c234d734712b4d48870e2aa7b4ddb')

if __name__ == '__main__':
    unittest.main()
