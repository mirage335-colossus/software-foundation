"""Generate an SDK-free branch fixture from the maintained Publisher source.

The template supplies a tiny DOM boundary. Association capture, label joining,
equality and Begin's focus-baseline guard are copied from production.
This generator never compiles or executes the resulting C++.
"""
import argparse
from pathlib import Path
import os
import tempfile

MAX_SOURCE = 512 * 1024
MAX_TEMPLATE = 128 * 1024
TOKENS = ('EXCLUDED_LABEL_ASSOCIATION', 'ATTACH_LABELS', 'LABEL_EVIDENCE_COMPLETE',
          'BEGIN_FOCUS_SELECTION', 'BEGIN_FOCUS_BASELINE')


def unique(source, needle):
    if source.count(needle) != 1:
        raise ValueError('Expected one source boundary: ' + needle)
    return source.index(needle)


def balanced(source, start, opening, closing):
    """Balance one C++ delimiter while skipping comments and quoted literals."""
    depth, i = 1, start + 1
    while i < len(source):
        if source.startswith('//', i):
            end = source.find('\n', i + 2)
            i = len(source) if end < 0 else end + 1
            continue
        if source.startswith('/*', i):
            end = source.find('*/', i + 2)
            if end < 0:
                raise ValueError('Unterminated source comment')
            i = end + 2
            continue
        if source.startswith('R"', i):
            raise ValueError('Raw C++ literals require an explicit extractor update')
        if source[i] in ('"', "'"):
            quote = source[i]
            i += 1
            while i < len(source) and source[i] != quote:
                if source[i] == '\\':
                    i += 1
                i += 1
            if i >= len(source):
                raise ValueError('Unterminated source literal')
        elif source[i] == opening:
            depth += 1
        elif source[i] == closing:
            depth -= 1
            if not depth:
                return i + 1
        i += 1
    raise ValueError('Unbalanced source block')


def function(source, signature):
    start = unique(source, signature)
    body = source.find('{', start)
    if body < 0:
        raise ValueError('Source definition is missing its body')
    return source[start:balanced(source, body, '{', '}')]


def render(source, template):
    if len(source.encode('utf-8')) > MAX_SOURCE or len(template.encode('utf-8')) > MAX_TEMPLATE:
        raise ValueError('Fixture source byte bound exceeded')
    if '\0' in source or '\0' in template:
        raise ValueError('NUL in fixture source')
    helper = function(source, 'Session::LabelState excludedLabelAssociation(')
    join = function(source, 'void Session::attachLabels(')
    selection = 'std::all_of(native.labels.begin(), native.labels.end(),'
    start = unique(source, selection)
    opening = source.index('(', start)
    end = balanced(source, opening, '(', ')')
    if source[end:end+1] != ';':
        raise ValueError('Label evidence expression extent differs')
    expression = source[start:end].replace('native.labels', 'labels')
    equality = ('bool labelEvidenceComplete(Session::PreparedRead& read, '
                'const std::vector<Session::LabelState>& labels) {\n'
                '    return ' + expression + ';\n}\n')
    focus_selection = function(source, 'bool normalizeBeginTextSelection(')
    focus_start = unique(source, 'if (focusBaseline) {')
    focus_end = balanced(source, source.index('{', focus_start), '{', '}')
    focus = ('bool beginFocusBaseline(Session& session, Session::PreparedRead& read, '
             'const Session::Capture* focusBaseline) {\n'
             + source[focus_start:focus_end] + '\n    return true;\n}\n')
    for token, value in zip(TOKENS, (helper, join, equality, focus_selection, focus)):
        placeholder = '@' + token + '@'
        unique(template, placeholder)
        template = template.replace(placeholder, value)
    if any('@' + token + '@' in template for token in TOKENS):
        raise ValueError('Unbound fixture token')
    return template


def generate(source, template, output):
    source, template, output = map(Path, (source, template, output))
    if output.resolve() in (source.resolve(), template.resolve()):
        raise ValueError('Fixture output overlaps an input')
    raw = source.read_bytes()
    layout = template.read_bytes()
    if len(raw) > MAX_SOURCE or len(layout) > MAX_TEMPLATE:
        raise ValueError('Fixture source byte bound exceeded')
    rendered = render(raw.decode('utf-8'), layout.decode('utf-8')).encode('utf-8')
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise ValueError('Fixture output is not an ordinary file')
    # Only the caller-owned generated output is replaced, after all extraction
    # and validation succeeded. Inputs are never modified.
    fd, name = tempfile.mkstemp(prefix=output.name + '.', dir=output.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(rendered)
        os.replace(name, output)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    generate(args.source, args.template, args.output)


if __name__ == '__main__':
    main()
