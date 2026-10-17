"""The maintained fixture generator reads only selected source and template files."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('label_fixture_generator',
    ROOT/'tools/generate_document_label_association_fixture.py')
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)
SOURCE = ROOT/'recipes/webkitwasm-document-v2/source/native/NativeDocumentV2Publisher.cpp'
TEMPLATE = ROOT/'tests/fixtures/document_label_association/branch_fixture.cpp.in'


class DocumentLabelFixtureTests(unittest.TestCase):
    def test_actual_source_blocks_and_behavior_cases_are_the_generated_consumer(self):
        source, template = SOURCE.read_text(), TEMPLATE.read_text()
        result = generator.render(source, template)
        self.assertIn(generator.function(source, 'Session::LabelState excludedLabelAssociation('), result)
        self.assertIn(generator.function(source, 'void Session::attachLabels('), result)
        self.assertIn(generator.function(source, 'bool normalizeBeginTextSelection('), result)
        self.assertIn('unresolved exact unrelated ID permits stable equality', result)
        self.assertIn('original default missing-label state reproduces V5 global poison', result)
        self.assertIn('repeated Begin accepts stable flags4 to21 after blur/refocus', result)
        self.assertIn('unavailable authoritative input-method state rejects', result)
        self.assertFalse(any('@'+token+'@' in result for token in generator.TOKENS))

    def test_function_extent_ignores_comment_and_quoted_delimiters(self):
        source = 'void selected() { const char* s="}\\\"{"; /* } */ // {\n if (s) {} }\nvoid other() {}'
        self.assertEqual(generator.function(source, 'void selected()'), source.split('\nvoid other')[0])

    def test_missing_or_duplicate_actual_definition_is_rejected(self):
        source, template = SOURCE.read_text(), TEMPLATE.read_text()
        signature = 'Session::LabelState excludedLabelAssociation('
        for changed in (source.replace(signature, 'renamed('), source+'\n'+signature):
            with self.subTest(changed=changed[-80:]), self.assertRaisesRegex(ValueError, 'one source boundary'):
                generator.render(changed, template)

    def test_truncated_and_unsupported_literals_fail_closed(self):
        for source in ('void selected() {', 'void selected() { /* no close',
                       'void selected() { const char* s="no close;',
                       'void selected() { const char* s=R"(body)"; }'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                generator.function(source, 'void selected()')

    def test_equality_must_have_one_complete_expression(self):
        source, template = SOURCE.read_text(), TEMPLATE.read_text()
        selection = 'std::all_of(native.labels.begin(), native.labels.end(),'
        start = source.index(selection)
        end = generator.balanced(source, source.index('(', start), '(', ')')
        for changed in (source.replace(selection, 'other('), source+'\n'+selection,
                        source[:end]+','+source[end+1:]):
            with self.subTest(changed=changed[-80:]), self.assertRaises(ValueError):
                generator.render(changed, template)

    def test_both_active_publishers_generate_identical_tested_code(self):
        native = ROOT/'recipes/webkitwasm-native-rich4083-v1/source/document-provider/native/NativeDocumentV2Publisher.cpp'
        template = TEMPLATE.read_text()
        self.assertEqual(generator.render(SOURCE.read_text(), template),
                         generator.render(native.read_text(), template))

    def test_begin_baseline_guard_is_extracted_verbatim_not_reimplemented(self):
        source, template = SOURCE.read_text(), TEMPLATE.read_text()
        start = source.index('if (focusBaseline) {')
        end = generator.balanced(source, source.index('{', start), '{', '}')
        self.assertIn(source[start:end], generator.render(source, template))

    def test_begin_guard_missing_duplicate_or_unbalanced_boundary_rejects(self):
        source, template = SOURCE.read_text(), TEMPLATE.read_text()
        signature = 'if (focusBaseline) {'
        start = source.index(signature)
        for changed in (source.replace(signature, 'if (otherBaseline) {'),
                        source+'\n'+signature, source[:start]+signature):
            with self.subTest(changed=changed[-80:]), self.assertRaises(ValueError):
                generator.render(changed, template)

    def test_missing_or_duplicate_template_token_does_not_guess(self):
        source, template = SOURCE.read_text(), TEMPLATE.read_text()
        for token in generator.TOKENS:
            placeholder = '@'+token+'@'
            for changed in (template.replace(placeholder, ''), template+placeholder):
                with self.subTest(token=token), self.assertRaisesRegex(ValueError, 'one source boundary'):
                    generator.render(source, changed)

    def test_byte_and_nul_bounds_apply_before_generation(self):
        source, template = SOURCE.read_text(), TEMPLATE.read_text()
        for raw, layout in ((source+'x'*generator.MAX_SOURCE, template),
                            (source, template+'x'*generator.MAX_TEMPLATE),
                            (source+'\0', template), (source, template+'\0')):
            with self.subTest(lengths=(len(raw),len(layout))), self.assertRaises(ValueError):
                generator.render(raw, layout)

    def test_owned_output_can_be_regenerated_without_mutating_inputs(self):
        with tempfile.TemporaryDirectory(prefix='document-label-fixture-') as name:
            out = Path(name)/'fixture.cpp'
            source, template = SOURCE.read_bytes(), TEMPLATE.read_bytes()
            generator.generate(SOURCE, TEMPLATE, out)
            first = out.read_bytes()
            generator.generate(SOURCE, TEMPLATE, out)
            self.assertEqual(out.read_bytes(), first)
            self.assertEqual(SOURCE.read_bytes(), source)
            self.assertEqual(TEMPLATE.read_bytes(), template)

    def test_failed_extraction_preserves_existing_output(self):
        with tempfile.TemporaryDirectory(prefix='document-label-fixture-') as name:
            base = Path(name); source = base/'source.cpp'; out = base/'fixture.cpp'
            source.write_text('void unrelated() {}');out.write_bytes(b'previous complete fixture\n')
            with self.assertRaises(ValueError):
                generator.generate(source, TEMPLATE, out)
            self.assertEqual(out.read_bytes(), b'previous complete fixture\n')

    def test_input_overlap_and_nonordinary_output_are_rejected(self):
        for out in (SOURCE, TEMPLATE):
            with self.subTest(out=out), self.assertRaisesRegex(ValueError, 'overlaps'):
                generator.generate(SOURCE, TEMPLATE, out)
        with tempfile.TemporaryDirectory(prefix='document-label-fixture-') as name:
            with self.assertRaisesRegex(ValueError, 'ordinary file'):
                generator.generate(SOURCE, TEMPLATE, Path(name))


if __name__ == '__main__':
    unittest.main()
