"""Extract the actual popup-owner getter preflight, without WebCore/SDK."""
import argparse,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('extractor',Path(__file__).with_name('generate_document_label_association_fixture.py'))
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
def render(source,template):
    if max(len(source),len(template))>512*1024:raise ValueError('Source bound')
    body=e.function(source,'bool popupSourceBound(')
    if source.count('    if(!popupSourceBound(*select))return false;')!=2:raise ValueError('Refresh/commit wiring')
    for signature in ('bool NativePopupMenu::refresh(', 'bool NativePopupMenu::commit('):
        f=e.function(source,signature)
        if f.index('popupSourceBound(*select)')>f.index('select->listItems()'):raise ValueError('Preflight order')
    e.unique(template,'@POPUP_SOURCE_BOUND@')
    return template.replace('@POPUP_SOURCE_BOUND@',body)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','template','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();text=render(a.source.read_text(),a.template.read_text())
    if a.output.resolve() in (a.source.resolve(),a.template.resolve()):raise ValueError('Overlapping output')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
if __name__=='__main__':main()
