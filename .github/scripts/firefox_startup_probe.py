"""Temporary native Firefox startup comparison; never release qualification."""
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_plan


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('20', '120'):
        raise ValueError('one explicitly bounded startup limit required')
    seconds = int(sys.argv[1])
    output = ROOT / 'build/firefox-startup-probe'
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'gui/tests/browser_test.py'
    original = source.read_text()
    needle = 'deadline=time.monotonic()+20'
    if original.count(needle) != 2:
        raise ValueError('probe requires the exact two existing startup deadlines')
    selection = ci_plan.browser_prerequisite('linux-aarch64', 'ubuntu-24.04', 'hosted-web')
    prerequisite = ci_plan.inspect_host_firefox(selection)
    result = dict(release_qualification=False,
                  source_commit=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
                  attempt=int(os.environ['GITHUB_RUN_ATTEMPT']), platform=platform.platform(),
                  python=sys.version, prerequisite=prerequisite,
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), trials=[])
    (output / 'prerequisite.json').write_text(json.dumps(result, indent=2) + '\n')
    for index in (1,):
        text = original.replace(needle, 'deadline=time.monotonic()+' + str(seconds), 1)
        module = types.ModuleType('firefox_startup_probe_' + str(index))
        module.__file__ = str(source)
        sys.modules[module.__name__] = module
        exec(compile(text, str(source), 'exec'), module.__dict__)
        directory = output / ('trial-' + str(index))
        directory.mkdir()
        trial = dict(index=index, startup_seconds=seconds,
                     fixture_sha256=hashlib.sha256(text.encode()).hexdigest())
        started = time.monotonic()
        def connect(*args, **kwargs):
            connection = socket.create_connection(*args, **kwargs)
            trial['automation_connection_seconds'] = round(time.monotonic() - started, 3)
            return connection
        # Instrument only this fixture's binding, never the process-wide socket module.
        module.socket = types.SimpleNamespace(**vars(socket))
        module.socket.create_connection = connect
        try:
            with module.browser_workspace(directory) as workspace:
                browser = module.Browser(prerequisite['executable'], workspace)
                try:
                    trial.update(status='ready', browser_version=browser.capabilities.get('browserVersion'),
                                 ready_seconds=round(time.monotonic() - started, 3))
                finally:
                    browser.close()
        except module.BrowserCleanupError:
            # Uncertain writers retain their workspace; publish no completed result.
            raise
        except (OSError, RuntimeError, ValueError) as error:
            trial.update(status='failed', error_type=type(error).__name__, error=str(error))
        finally:
            sys.modules.pop(module.__name__, None)
        trial.update(elapsed_seconds=round(time.monotonic() - started, 3), writers_stopped=True)
        result['trials'].append(trial)
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(trial), flush=True)
    if source.read_text() != original:
        raise ValueError('diagnostic changed the source fixture')


if __name__ == '__main__':
    main()
