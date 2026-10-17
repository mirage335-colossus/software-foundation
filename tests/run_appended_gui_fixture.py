#!/usr/bin/env python3
"""Run one appended GUI fixture in a fresh supervised temporary container."""
import sys

sys.dont_write_bytecode = True

import argparse
import os
from pathlib import Path
import re
import shutil
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import process_tree


class FixtureFailure(RuntimeError):
    pass


class UncertainCompletion(FixtureFailure):
    pass


def existing_file(value):
    try:
        path = Path(value).resolve(strict=True)
    except (OSError, ValueError) as error:
        raise argparse.ArgumentTypeError('unavailable fixture file: ' + value) from error
    if not path.is_file():
        raise argparse.ArgumentTypeError('expected a regular file: ' + value)
    return path


def case_name(value):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,127}', value):
        raise argparse.ArgumentTypeError('expected one fixture case name')
    return value


def diagnostics(path):
    with path.open('r', encoding='utf-8', errors='replace') as stream:
        for block in iter(lambda: stream.read(65536), ''):
            sys.stdout.write(block)
    sys.stdout.flush()


def run_child(argv, container, log, *, quiet_success=False):
    """Read evidence only after the supervisor confirms all writers finished."""
    failure = None
    cleanup_errors = []
    with log.open('xb') as stream:
        try:
            owner = process_tree.launch([str(arg) for arg in argv], str(container), stream)
        except BaseException as error:
            raise UncertainCompletion('child launch did not confirm cleanup: ' + str(error)) from error
        try:
            code = owner.wait(timeout=20)
            owner.finish()
        except BaseException as error:
            failure = error
            try:
                owner.terminate()
            except BaseException as cleanup:
                cleanup_errors.append('terminate: ' + str(cleanup))
        finally:
            try:
                owner.close()
            except BaseException as cleanup:
                cleanup_errors.append('close: ' + str(cleanup))
    if cleanup_errors:
        raise UncertainCompletion('; '.join([str(failure), *cleanup_errors]))
    if failure is not None:
        diagnostics(log)
        raise FixtureFailure('child supervision failed: ' + str(failure)) from failure
    if code != 0:
        diagnostics(log)
        raise FixtureFailure('child exited with status ' + str(code))
    if not quiet_success:
        diagnostics(log)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    loader = modes.add_parser('loader')
    loader.add_argument('case', type=case_name)
    loader.add_argument('test_binary', type=existing_file)
    loader.add_argument('fixture_dso', type=existing_file)
    editor = modes.add_parser('editor')
    editor.add_argument('codec_binary', type=existing_file)
    editor.add_argument('node_exe', type=existing_file)
    editor.add_argument('protocol_js', type=existing_file)
    args = parser.parse_args(argv)
    if not (sys.platform.startswith('linux') or os.name == 'nt'):
        parser.error('fixture supervision requires Linux or Windows')
    container = Path(tempfile.mkdtemp(prefix='foundation-appended-gui-')).resolve()
    cleanup = True
    try:
        if args.mode == 'loader':
            group = container / 'group'
            run_child([args.test_binary, args.case, group, args.fixture_dso],
                      container, container / 'loader.log')
        else:
            fixtures = container / 'editor-fixtures.json'
            run_child([args.codec_binary, '--emit-editor-fixtures'], container,
                      fixtures, quiet_success=True)
            run_child([args.node_exe, args.protocol_js, fixtures],
                      container, container / 'editor-protocol.log')
    except UncertainCompletion as error:
        cleanup = False
        print('appended GUI fixture: ' + str(error) + '\nRetained fixture container: ' + str(container),
              file=sys.stderr)
        return 1
    except BaseException as error:
        print('appended GUI fixture: ' + str(error), file=sys.stderr)
        return 1
    finally:
        if cleanup:
            shutil.rmtree(container)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
