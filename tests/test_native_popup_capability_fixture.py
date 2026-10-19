"""Source extraction joins both active producers; no WebCore/SDK execution."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_popup_generator', ROOT/'tools/generate_native_popup_capability_fixture.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
class NativePopupFixtureTests(unittest.TestCase):
    def inputs(self, root='recipes/webkitwasm-document-v2/source'):
        return ((ROOT/root/'native/NativeDocumentV2Publisher.cpp').read_text(),
                (ROOT/root/'native/NativeFormsV2Combined.cpp').read_text(),
                (ROOT/'tests/fixtures/native_popup_capability/branch_fixture.cpp.in').read_text())
    def test_actual_association_and_option_capture_are_extracted_complete(self):
        publisher,forms,template=self.inputs()
        result=generator.render(publisher,forms,template)
        for signature in ('static const AtomString& associationID(', 'RefPtr<HTMLElement> associatedControl('):
            self.assertIn(generator.extractor.function(publisher,signature),result)
        self.assertIn(generator.extractor.function(forms,'static bool opaquePopupOption('),result)
        self.assertNotIn('@OPTION_ANCESTRY@',result)
        self.assertIn('CSS-only hidden optgroup is not author privacy',result)
    def test_both_active_producers_use_the_same_selected_policy(self):
        self.assertEqual(generator.render(*self.inputs()),generator.render(*self.inputs('recipes/webkitwasm-native-rich4083-v1/source/document-provider')))
    def test_missing_duplicate_or_truncated_source_refuses(self):
        p,f,t=self.inputs()
        for bad in (p.replace('associationID(', 'renamed('),p+'\nstatic const AtomString& associationID(',p[:p.index('static const AtomString& associationID(')+40]):
            with self.assertRaises(ValueError):generator.render(bad,f,t)
    def test_redacted_branch_never_reads_hidden_option_fields(self):
        _,forms,_=self.inputs()
        start=generator.extractor.unique(forms,'                if (row.omitted) {')
        end=generator.extractor.unique(forms,'                bool optionStyle = owner.attributes(*option, exactOption.attributes, bounds);')
        branch=forms[start:end]
        self.assertIn('if (!opaquePopupOption(state, exactOption.presentation)) complete = false;',branch)
        for forbidden in ('displayLabel(', 'option->value(', 'rawSubtree(', 'owner.attributes('):
            self.assertNotIn(forbidden,branch)
        self.assertIn('state.options.push_back(std::move(row));',branch)
        self.assertIn('continue;',branch)
    def test_select_capture_prelude_is_exclusive_and_precedes_complete_init(self):
        _,forms,_=self.inputs()
        body=generator.extractor.function(forms,'Session::Capture Session::PreparedRead::capture(')
        signature='    if (!is<HTMLSelectElement>(control)) {'
        start=generator.extractor.unique(body,signature)
        end=generator.extractor.balanced(body,body.index('{',start),'{','}')
        self.assertIn('owner.rawSubtree(*this, control, result.lightSubtree, false);',body[start:end])
        self.assertEqual(body.count('owner.rawSubtree(*this, control, result.lightSubtree, false);'),1)
        self.assertLess(end,body.index('bool complete = result.styleComplete && owner.subtreeComplete(result.lightSubtree);'))
        self.assertLess(body.index('bool complete ='),body.index('size_t selectDepth = 0, preflightOptions = 0;'))
        self.assertLess(body.index('if (input && input->isSecureField())'),start)
    def test_template_tokens_are_closed(self):
        p,f,t=self.inputs()
        for token in ('ASSOCIATION_ID','ASSOCIATED_CONTROL','OPAQUE_OPTION','OPTION_ANCESTRY','CAPTURE_PRELUDE','CAPTURE_COMPLETE_INIT'):
            with self.assertRaises(ValueError):generator.render(p,f,t.replace('@'+token+'@',''))
if __name__=='__main__':unittest.main()
