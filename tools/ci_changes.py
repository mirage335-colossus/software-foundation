#!/usr/bin/env python3
"""Conservative local-Git selection for development feedback, never qualification."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

# Only reviewed, non-installed narrative documents may omit compile/GUI work.
# New paths, manuals, release policies, schemas and installed text stay full.
DOCUMENTS = frozenset({
    'README.md', 'AGENTS.md', 'COMPILE', 'RELEASE',
    'docs/README.md', 'docs/architecture.md', 'docs/ci.md',
    'docs/development-speed.md', 'docs/testing.md', 'docs/validation.md',
    'docs/documentation.md', 'docs/maintenance.md',
    'docs/agent-coordination.md', 'docs/agent-recipes.md', 'docs/agent-lifecycle.md',
})
COMMIT = re.compile(r'[0-9a-f]{40}')


def classify(paths):
    """An absent/incomplete change inventory never authorizes omitted work."""
    paths = list(paths)
    docs_only = bool(paths) and all(path in DOCUMENTS for path in paths)
    return {'schema_version': 1, 'scope': 'documents' if docs_only else 'full',
            'build': not docs_only, 'gui': not docs_only, 'workflow_lint': not docs_only,
            'changed_paths': paths,
            'reason': 'Only reviewed narrative documents changed.' if docs_only
                      else 'Source, policy, unknown paths or an empty change set require full feedback.'}


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20).stdout


def commit(value):
    if not isinstance(value, str) or not COMMIT.fullmatch(value) or value == '0' * 40:
        raise ValueError('an exact nonzero commit is required')
    return value


def changed_paths(root, event_name, event, expected_head):
    """Compare the tested merge/tree with its exact event baseline, without APIs.

    Depth-two checkouts contain a PR merge's first parent. A multi-commit push
    may lack its previous tip; that condition deliberately selects full work.
    --no-renames makes moves include both deleted and added paths.
    """
    head = commit(expected_head)
    if git(root, 'rev-parse', 'HEAD').decode().strip() != head:
        raise ValueError('checked-out source differs from the event commit')
    if event_name == 'pull_request':
        base = commit(event['pull_request']['base']['sha'])
        if git(root, 'rev-parse', 'HEAD^1').decode().strip() != base:
            raise ValueError('the tested PR merge does not have the event base parent')
        commit(event['pull_request']['head']['sha'])
        if git(root, 'rev-parse', 'HEAD^2').decode().strip() != event['pull_request']['head']['sha']:
            raise ValueError('the tested PR merge does not have the event head parent')
    elif event_name == 'push':
        base = commit(event['before'])
        if commit(event['after']) != head or event.get('deleted'):
            raise ValueError('push event does not identify the checked-out live tip')
    else:
        raise ValueError('unsupported feedback event')
    raw = git(root, 'diff', '--name-only', '--no-renames', '-z', base, head, '--')
    if raw and not raw.endswith(b'\0'):
        raise ValueError('incomplete changed-path output')
    return [item.decode('utf-8', errors='strict') for item in raw.split(b'\0') if item]


def select(root, event_name, event, expected_head):
    try:
        return classify(changed_paths(root, event_name, event, expected_head))
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        result = classify([])
        result['reason'] = 'Complete change inventory unavailable; full feedback selected (' + type(error).__name__ + ').'
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--event', type=Path, default=os.environ.get('GITHUB_EVENT_PATH'))
    parser.add_argument('--event-name', default=os.environ.get('GITHUB_EVENT_NAME', ''))
    parser.add_argument('--head', default=os.environ.get('GITHUB_SHA', ''))
    parser.add_argument('--github-output', type=Path, default=os.environ.get('GITHUB_OUTPUT'))
    parser.add_argument('--summary', type=Path, default=os.environ.get('GITHUB_STEP_SUMMARY'))
    args = parser.parse_args(argv)
    try:
        event = json.loads(args.event.read_text(encoding='utf-8')) if args.event else {}
    except (OSError, ValueError):
        event = {}
    result = select(args.root, args.event_name, event, args.head)
    if args.github_output:
        with args.github_output.open('a', encoding='utf-8') as stream:
            for key in ('build', 'gui', 'workflow_lint'):
                stream.write(f'{key}={str(result[key]).lower()}\n')
            stream.write('scope=' + result['scope'] + '\n')
    if args.summary:
        with args.summary.open('a', encoding='utf-8') as stream:
            stream.write('Development feedback: ' + result['scope'] + '. ' + result['reason'] + '\n')
            if result['scope'] == 'documents':
                stream.write('Documentation checks run; compile, GUI and workflow syntax work omitted.\n')
            stream.write('This selection does not qualify a candidate or release.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
