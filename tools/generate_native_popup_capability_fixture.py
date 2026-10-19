"""Extract production native association and option-capture policy; no SDK execution."""
import argparse
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('label_extractor', Path(__file__).with_name('generate_document_label_association_fixture.py'))
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)

def render(publisher, forms, template):
    if max(len(s.encode()) for s in (publisher, forms, template)) > 512 * 1024:
        raise ValueError('Native popup fixture source bound')
    values = {
        'ASSOCIATION_ID': extractor.function(publisher, 'static const AtomString& associationID('),
        'ASSOCIATED_CONTROL': extractor.function(publisher, 'RefPtr<HTMLElement> associatedControl('),
        'OPAQUE_OPTION': extractor.function(forms, 'static bool opaquePopupOption('),
    }
    start = extractor.unique(forms, '                bool inherited = false, terminalInherited = false;')
    tail = '                result.styleComplete = result.styleComplete && exactOption.presentation.styleKnown;'
    end = extractor.unique(forms, tail) + len(tail)
    values['OPTION_ANCESTRY'] = forms[start:end]
    prelude = extractor.unique(forms, '    if (!is<HTMLSelectElement>(control)) {')
    prelude_end = extractor.balanced(forms, forms.index('{', prelude), '{', '}')
    values['CAPTURE_PRELUDE'] = forms[prelude:prelude_end]
    values['CAPTURE_COMPLETE_INIT'] = '    bool complete = result.styleComplete && owner.subtreeComplete(result.lightSubtree);'
    extractor.unique(forms, values['CAPTURE_COMPLETE_INIT'])

    for token, value in values.items():
        placeholder = '@' + token + '@'
        extractor.unique(template, placeholder)
        template = template.replace(placeholder, value)
    if any('@' + token + '@' in template for token in values):
        raise ValueError('Unbound native popup fixture')
    return template

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publisher', type=Path, required=True)
    p.add_argument('--forms', type=Path, required=True)
    p.add_argument('--template', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    data = render(a.publisher.read_text(), a.forms.read_text(), a.template.read_text())
    if a.output.resolve() in {a.publisher.resolve(), a.forms.resolve(), a.template.resolve()}:
        raise ValueError('Fixture output overlaps input')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(data)

if __name__ == '__main__':
    main()
