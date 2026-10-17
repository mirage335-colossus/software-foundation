#!/usr/bin/env python3
"""Check the real OS self-path from a relocated copied probe and launch aliases."""
import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import process_tree


def run(argv, cwd, log, env=None):
    with log.open('xb') as stream:
        owner = process_tree.launch([str(arg) for arg in argv], str(cwd), stream, env=env)
        try:
            code = owner.wait(timeout=20)
            owner.finish()
        except BaseException:
            owner.terminate()
            raise
        finally:
            owner.close()
    output = log.read_text(encoding='utf-8', errors='replace')
    sys.stdout.write(output)
    if code:
        raise RuntimeError('self-relative path probe exited with status ' + str(code))
    matches = re.findall(r'^PASS self-relative-path assertions=([1-9][0-9]*)$', output, re.MULTILINE)
    if len(matches) != 1:
        raise RuntimeError('self-relative path probe omitted its complete assertion result')
    return int(matches[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe', type=Path)
    args = parser.parse_args()
    probe = args.probe.resolve(strict=True)
    if not probe.is_file():
        parser.error('probe must be an existing executable file')
    container = Path(tempfile.mkdtemp(prefix='foundation-self-relative-')).resolve()
    cleanup = False
    try:
        install = container / 'relocated installation'
        bindir = install / 'bin'
        runtime = install / 'share' / 'runtime'
        elsewhere = container / 'different working directory'
        bindir.mkdir(parents=True)
        runtime.mkdir(parents=True)
        elsewhere.mkdir()
        copied = bindir / ('path probe.exe' if os.name == 'nt' else 'path probe')
        shutil.copy2(probe, copied)
        (runtime / 'dangling-installed-path').symlink_to(runtime / 'absent-symlink-target')
        hint = '../share/runtime'
        assertions = run([copied, hint, runtime], elsewhere, container / 'absolute.log')
        env = os.environ.copy()
        env['PATH'] = str(bindir)
        assertions += run([copied.name, hint, runtime], elsewhere, container / 'path.log', env)
        launcher = elsewhere / ('launcher.exe' if os.name == 'nt' else 'launcher with space')
        launcher.symlink_to(copied)
        assertions += run([launcher, hint, runtime], elsewhere, container / 'symlink.log')
        cleanup = True
        print('PASS self-relative-path launches=3 assertions=' + str(assertions) + ' failures=0 skips=0')
        return 0
    except BaseException as error:
        print('self-relative path fixture: ' + str(error) + '\nRetained fixture: ' + str(container), file=sys.stderr)
        return 1
    finally:
        if cleanup:
            shutil.rmtree(container)


if __name__ == '__main__':
    raise SystemExit(main())
