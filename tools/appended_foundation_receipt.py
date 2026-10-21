#!/usr/bin/env python3
"""Convert independently accepted real editor runtime evidence to a kernel receipt.

This is a passive, pinned-evidence adapter. It never executes received source,
builds a kernel, launches a browser, or promotes a parser fixture. The selected
independent reader owns verification of the complete original stream; this
adapter checks its exact input/caller/construction joins and captured bootstrap
observations before using the unchanged document producer's receipt validator.
"""
import argparse
import base64
import binascii
import copy
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys

import appended_container as container
import appended_engine_document_contract as contract
import appended_engine_editor_contract as editor
import appended_engine_document_consumer as consumer
import appended_engine_manifest as manifest
import package_appended_engine_document_wasm as producer

ACCEPTANCE_KIND = 'foundation-editor-runtime-acceptance-v1'
WITNESS_KIND = 'foundation-editor-bootstrap-observation-v1'
RECORD_FIELDS = ('path', 'bytes', 'sha256', 'mode', 'dev', 'ino', 'mtime_ns', 'ctime_ns', 'nlink')
RECORD_ROLES = ('construction', 'runtime_input', 'runtime_result', 'runtime_caller',
                'header', 'seal', 'readback', 'reader_owner')
CHECKS = producer.BASE_CHECKS + producer.DOCUMENT_CHECKS + producer.PHYSICAL_CHECKS + producer.EDITOR_CHECKS
ORDER = ('kernel_editor_facts_before_engine_factory', 'engine_describe_before_kernel_configure',
         'kernel_configure_before_start')
BOOTSTRAP = contract.BOOTSTRAP_CHECKS
ARTIFACTS = ('kernel_factory', 'kernel_wasm', 'engine_factory', 'engine_wasm')
CALLS = {
    'compiled_profile': ('kernel', 'gui_web_engine_profile_v1'),
    'compiled_editor_profile': ('kernel', 'gui_web_engine_editor_describe_v1'),
    'engine_facts': ('engine', 'bib_engine_wasm_editor_facts_v1'),
    'engine_configure': ('engine', 'bib_engine_wasm_editor_configure_v1'),
    'marker_before': ('engine', 'bib_engine_wasm_bridge_v1'),
    'marker_after': ('engine', 'bib_engine_wasm_bridge_v1'),
    'describe': ('engine', 'bib_engine_wasm_dispatch_v1'),
    'kernel_configure': ('kernel', 'gui_web_engine_dispatch_v1'),
    'start': ('engine', 'bib_engine_wasm_dispatch_v1'),
}
MAX_WITNESS = 256 * 1024
MAX_CALL_BYTES = 16384


def need(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, names, label):
    need(type(value) is dict and set(value) == set(names), label + ' fields differ')


def sha(value):
    need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None, 'Invalid SHA256')
    return value


def integer(value, minimum=0, maximum=(1 << 64) - 1):
    need(type(value) is int and minimum <= value <= maximum, 'Invalid strict integer')
    return value


def epoch(value):
    need(type(value) is str and re.fullmatch(r'[1-9][0-9]{0,19}', value) is not None,
         'Canonical nonzero Worker identity required')
    return integer(int(value), 1)


def stream_json(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def physical(record):
    keys(record, RECORD_FIELDS, 'physical record')
    path = Path(record['path'])
    need(path.is_absolute() and str(path) == os.path.normpath(str(path)), 'Canonical absolute record path required')
    sha(record['sha256'])
    for name in set(RECORD_FIELDS) - {'path', 'sha256'}:
        integer(record[name])
    need(record['nlink'] == 1 and record['dev'] > 0 and record['ino'] > 0 and record['mode'] <= 0o7777,
         'Private single-link physical record required')
    return record


def snapshot_record(saved):
    state = saved.path.lstat()
    need(stat.S_ISREG(state.st_mode) and state.st_nlink == 1, 'Private regular input required')
    return dict(path=str(saved.path), bytes=len(saved.content), sha256=container.digest(saved.content),
        mode=stat.S_IMODE(state.st_mode), dev=state.st_dev, ino=state.st_ino,
        mtime_ns=state.st_mtime_ns, ctime_ns=state.st_ctime_ns, nlink=state.st_nlink)


def read_record(record, snapshots):
    physical(record)
    saved = container._snapshot(record['path'], manifest.MAX_MANIFEST)
    need(snapshot_record(saved) == record, 'Selected evidence physical identity differs: ' + record['path'])
    snapshots.append(saved)
    return contract.strict_json(saved.content, 'selected Foundation evidence')


def report(value):
    keys(value, ('schema_version', 'primary_returncode', 'descendants_outlived', 'terminated', 'reaped', 'error'),
         'natural closure report')
    need(type(value['schema_version']) is int and value['schema_version'] == 1
         and type(value['primary_returncode']) is int and value['primary_returncode'] == 0
         and value['descendants_outlived'] is False and value['terminated'] is False
         and type(value['reaped']) is int and value['reaped'] >= 1 and value['error'] is None,
         'Successful natural process/descendant closure required')


def caller(value):
    integer(value['actual_session'], 1)
    keys(value['actual_tool_result'], ('chunk_id', 'exit_code'), 'actual caller tool result')
    chunk = value['actual_tool_result']['chunk_id']
    need(type(chunk) is str and 0 < len(chunk) <= 128
         and type(value['actual_tool_result']['exit_code']) is int
         and value['actual_tool_result']['exit_code'] == 0, 'Original caller zero required')


def payload(value):
    keys(value, ('bytes', 'sha256', 'base64'), 'captured native payload')
    integer(value['bytes'], 0, MAX_CALL_BYTES)
    sha(value['sha256'])
    text = value['base64']
    need(type(text) is str and len(text) <= 4 * ((MAX_CALL_BYTES + 2) // 3), 'Bounded native base64 required')
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError('Invalid captured native base64') from error
    need(base64.b64encode(raw).decode('ascii') == text and len(raw) == value['bytes']
         and container.digest(raw) == value['sha256'], 'Captured native bytes/count/hash differ')
    return raw


def copied(raw, receipt, operation, worker):
    size = 80 if receipt else 72
    need(len(raw) >= size, 'Truncated copied bootstrap original')
    magic, version, kind, total, reserved = struct.unpack_from('<4sHHII', raw)
    target = struct.unpack_from('<QQQQ', raw, 16)
    source, reserved2, body_size, reserved3 = struct.unpack_from('<IIII', raw, 56)
    need(magic == b'FKB1' and version == 1 and kind == (operation | 0x8000 if receipt else operation)
         and total == len(raw) and body_size == len(raw) - 72 and source == 0
         and reserved == reserved2 == reserved3 == 0 and target[0] == worker,
         'Copied bootstrap header/Worker identity differs')
    if receipt:
        need(struct.unpack_from('<II', raw, 72) == (0, 0), 'Bootstrap native status is not successful')
    return target, raw[size:]


def validate_bootstrap_observation(value):
    """Check typed captured originals; no native execution or input discovery."""
    keys(value, ('schema_version', 'kind', 'run_id', 'subject_sha256', 'schedule_sha256', 'worker',
        'source', 'toolchain', 'artifacts', 'host_assets', 'compiled_profile', 'compiled_editor_profile',
        'engine_profile', 'engine_bootstrap', 'ordinals', 'paired_calls', 'binding'), 'bootstrap observation')
    need(len(contract.canonical_json(value)) <= MAX_WITNESS and type(value['schema_version']) is int
         and value['schema_version'] == 1 and value['kind'] == WITNESS_KIND, 'Bounded typed bootstrap observation required')
    sha(value['subject_sha256']); sha(value['schedule_sha256'])
    need(type(value['run_id']) is str and re.fullmatch(r'[0-9a-f]{32}', value['run_id']) is not None,
         'Exact runtime identity required')
    keys(value['worker'], ('slot', 'epoch'), 'selected Worker')
    need(type(value['worker']['slot']) is int and value['worker']['slot'] == 1, 'Deterministic first Worker required')
    worker = epoch(value['worker']['epoch'])
    profile = editor.validate_engine_profile(value['engine_profile'], editor_profile='editor')
    keys(value['paired_calls'], CALLS, 'paired bootstrap calls')
    observed = {}; identities = set(); ordinals = set()
    for name, (role, export) in CALLS.items():
        call = value['paired_calls'][name]
        keys(call, ('worker', 'call', 'enter_ordinal', 'return_ordinal', 'role', 'export', 'args',
                    'native_result', 'request_span', 'output_span', 'request', 'output'), 'paired ' + name)
        need(type(call['worker']) is int and call['worker'] == 1 and call['role'] == role and call['export'] == export,
             'Paired native role/export/Worker differs')
        integer(call['call'], 1); integer(call['enter_ordinal'], 1); integer(call['return_ordinal'], 1)
        integer(call['request_span'], 1); integer(call['output_span'], 1)
        need(call['enter_ordinal'] < call['return_ordinal'] and call['call'] not in identities
             and not {call['enter_ordinal'], call['return_ordinal']} & ordinals, 'Native call identity/order reused')
        identities.add(call['call']); ordinals.update((call['enter_ordinal'], call['return_ordinal']))
        need(type(call['args']) is list and len(call['args']) <= 5, 'Fixed native argument list required')
        for argument in call['args']:
            integer(argument, 0, (1 << 32) - 1)
        integer(call['native_result'], -(1 << 31), (1 << 32) - 1)
        observed[name] = (payload(call['request']), payload(call['output']))
    calls = value['paired_calls']
    for name, result in (('compiled_profile', 2), ('marker_before', 0), ('marker_after', 65536)):
        need(calls[name]['args'] == [] and calls[name]['native_result'] == result
             and observed[name] == (b'', b''), 'Actual scalar getter/marker differs: ' + name)
    need(calls['engine_configure']['args'] == [worker & 0xffffffff, worker >> 32]
         and calls['engine_configure']['native_result'] == 0 and observed['engine_configure'] == (b'', b''),
         'Actual configure lost the full Worker identity')
    for name in ('compiled_editor_profile', 'engine_facts'):
        raw = observed[name][1]; call = calls[name]
        need(observed[name][0] == b'' and len(call['args']) == 2 and call['args'][0] > 0
             and 0 < len(raw) == call['native_result'] < call['args'][1] and len(raw) <= 4095
             and b'\0' not in raw and contract.strict_json(raw) == profile, 'Actual facts bytes/result differ')
    bootstrap = editor.validate_bootstrap(value['engine_bootstrap']['engine'], editor_profile='editor', engine_profile=profile)
    keys(value['engine_bootstrap'], ('engine', 'order'), 'engine bootstrap')
    keys(value['engine_bootstrap']['order'], ORDER, 'bootstrap order checks')
    need(all(x == 'passed' for x in value['engine_bootstrap']['order'].values())
         and all(x == 'passed' for x in bootstrap['checks'].values()), 'Complete bootstrap/order proof required')
    marker = value['compiled_profile']
    need(marker == dict(export=CALLS['compiled_profile'][1], signature={'params': [], 'results': ['i32']},
                        observed_result=2, before_configure=True), 'Compiled profile observation differs')
    facts = value['compiled_editor_profile']; expected_output = base64.b64encode(observed['compiled_editor_profile'][1]).decode('ascii')
    need(facts == dict(export=CALLS['compiled_editor_profile'][1], signature={'params': ['i32', 'i32'], 'results': ['i32']},
        observed_result=profile, observed_output=expected_output, observed_bytes=calls['compiled_editor_profile']['native_result'],
        before_engine_factory=True, before_configure=True), 'Compiled editor observation differs from original bytes')
    need(bootstrap['worker_epoch'] == bootstrap['first_start_worker_epoch'] == value['worker']['epoch']
         and bootstrap['engine_facts']['observed_output'] == calls['engine_facts']['output']['base64']
         and bootstrap['engine_facts']['observed_bytes'] == calls['engine_facts']['native_result']
         and bootstrap['engine_configure']['worker_lo'] == calls['engine_configure']['args'][0]
         and bootstrap['engine_configure']['worker_hi'] == calls['engine_configure']['args'][1]
         and bootstrap['engine_configure']['observed_result'] == calls['engine_configure']['native_result']
         and bootstrap['marker_before'] == calls['marker_before']['native_result']
         and bootstrap['marker_after'] == calls['marker_after']['native_result'], 'Engine bootstrap differs from paired calls')
    for name, operation in (('describe', 0), ('kernel_configure', 1), ('start', 1)):
        call = calls[name]; sent, received = observed[name]
        need(len(call['args']) == 5 and call['args'][0] == operation and call['args'][1] > 0
             and call['args'][2] == len(sent) and call['args'][3] > 0
             and call['native_result'] == len(received) <= call['args'][4], 'Copied native measured lengths differ')
        target, _ = copied(sent, False, operation, worker)
        returned, body = copied(received, True, operation, worker)
        if name == 'start':
            need(returned[1] > 0 and body == struct.pack('<iI', 0, 2), 'Actual START did not commit successfully')
        else:
            need(target == returned == (worker, 0, 0, 0), 'Bootstrap copied target differs')
        if name == 'describe':
            need(contract.strict_json(body) == profile == bootstrap['describe_profile'], 'Actual DESCRIBE profile differs')
    order = value['ordinals']
    keys(order, ('worker', 'factory_ordinals', 'compiled_marker', 'kernel_facts', 'engine_facts', 'configure',
                'marker_before', 'marker_after', 'describe', 'kernel_configure', 'start', 'ready', 'full_target'), 'bootstrap ordinals')
    need(type(order['worker']) is int and order['worker'] == 1, 'Bootstrap ordinal Worker differs')
    names = {'compiled_profile': 'compiled_marker', 'compiled_editor_profile': 'kernel_facts',
             'engine_configure': 'configure', **{x: x for x in ('engine_facts', 'marker_before', 'marker_after', 'describe', 'kernel_configure', 'start')}}
    for name, key in names.items():
        need(order[key] == calls[name]['return_ordinal'], 'Bootstrap ordinal/call mismatch: ' + name)
    keys(order['factory_ordinals'], ('kernel', 'engine'), 'factory ordinals')
    for pair in order['factory_ordinals'].values():
        need(type(pair) is list and len(pair) == 2, 'Factory import/create pair required')
        integer(pair[0], 1); integer(pair[1], pair[0] + 1)
    need(calls['compiled_profile']['return_ordinal'] < order['factory_ordinals']['engine'][0]
         and calls['compiled_editor_profile']['return_ordinal'] < order['factory_ordinals']['engine'][0],
         'Kernel facts were not observed before the engine factory')
    sequence = ('marker_before', 'engine_facts', 'engine_configure', 'marker_after', 'describe', 'kernel_configure', 'start')
    need(all(calls[a]['return_ordinal'] < calls[b]['enter_ordinal'] for a, b in zip(sequence, sequence[1:])),
         'Actual bootstrap call ordering differs')
    integer(order['ready'], calls['start']['return_ordinal'] + 1)
    need(type(order['full_target']) is list and len(order['full_target']) == 4
         and order['full_target'][0] == value['worker']['epoch'], 'Full ready target differs')
    for item in order['full_target']:
        epoch(item)
    return value


def _passed_rows(rows, names):
    keys(rows, names, 'complete readback predicates')
    for row in rows.values():
        keys(row, ('status', 'proof', 'reason'), 'independent predicate')
        need(row['status'] == 'passed' and type(row['proof']) is dict and bool(row['proof'])
             and row['reason'] is None, 'Every independent predicate must pass with evidence')


def derive_receipt(acceptance, evidence, *, factory, wasm, host_assets):
    """Pure projection from the independently selected complete evidence set."""
    keys(acceptance, ('schema_version', 'kind', 'scope', 'status', 'records', 'reader_caller', 'build_origin'), 'runtime acceptance')
    need(type(acceptance['schema_version']) is int and acceptance['schema_version'] == 1
         and acceptance['kind'] == ACCEPTANCE_KIND and acceptance['scope'] == 'foundation-rich-kernel-runtime'
         and acceptance['status'] == 'accepted', 'Accepted real Foundation runtime evidence required; fixtures are ineligible')
    keys(acceptance['records'], RECORD_ROLES, 'selected evidence records'); keys(evidence, RECORD_ROLES, 'loaded evidence')
    records = acceptance['records']
    for record in records.values(): physical(record)
    caller(acceptance['reader_caller'])
    owner = evidence['reader_owner']
    need(type(owner['returncode']) is int and owner['returncode'] == 0 and owner['closed'] is True
         and owner['log_closed'] is True, 'Independent reader owner is not closed successfully')
    report(owner['supervisor_report'])
    construction = evidence['construction']
    need(construction['kind'] == 'Root-Foundation-actual-BOTH36-readback-acceptance-v1'
         and construction['status'] == 'accepted-construction-full-readback' and construction['full_construction_bound'] is True,
         'Matching accepted complete construction required')
    caller(construction['actual_readback_original_caller'])
    report(construction['actual_readback_original_caller']['owner_result']['supervisor_report'])
    runtime = evidence['runtime_result']; actual_caller = evidence['runtime_caller']
    caller(actual_caller); report(actual_caller['qualified_process_report'])
    need(actual_caller['kind'] == 'Root-Foundation-full-BOTH-original-caller-closed-v1'
         and type(actual_caller['caller_observed_exit']) is int and actual_caller['caller_observed_exit'] == 0
         and actual_caller['streams_and_descendants_closed'] is True
         and actual_caller['input'] == records['runtime_input'] and actual_caller['result'] == records['runtime_result']
         and actual_caller['seal_record'] == records['seal'], 'Original runtime caller/selected records differ')
    need(runtime['kind'] == 'foundation-original-stream-root-closure-v2'
         and type(runtime['caller_exit']) is int and runtime['caller_exit'] == 0
         and runtime['nonseal_writers_joined'] is True and runtime['seal_writer_joined'] is True
         and runtime['seal_record'] == records['seal'], 'Actual runtime closure is incomplete')
    report(runtime['capture_helper_report']); report(runtime['seal_writer_report'])
    result = evidence['readback']; observation = result['observation']
    need(result['kind'] == 'DERIVED-Foundation-full-BOTH-readback-v1' and result['status'] == 'observed-full'
         and result['full_23_3_6'] is True and result['inputs_rechecked'] is True
         and observation['kind'] == 'private-original-v2-complete-causal-results-v1'
         and observation['trusted_closure'] is True and observation['unfinished'] == [], 'Complete trusted 23+3+6 readback required')
    for group, names in (('runtime', CHECKS), ('ordering', ORDER), ('bootstrap', BOOTSTRAP)):
        _passed_rows(observation[group], names)
    selected_runtime = {k: records['runtime_' + k] for k in ('input', 'result', 'caller')}
    need(result['runtime'] == selected_runtime and result['foundation']['acceptance'] == records['construction'],
         'Readback runtime/construction selection crossed')
    witness = validate_bootstrap_observation(result['receipt_observation'])
    header = evidence['header']; packet = evidence['runtime_input']; seal = evidence['seal']; subject = header['subject']
    need(header['kind'] == 'foundation-original-stream-header-v2' and header['subject_sha256'] == container.digest(stream_json(subject))
         and header['run_id'] == runtime['run'] == observation['run_id'] == packet['run_id'] == witness['run_id']
         and subject == packet['subject'] and subject['profile'] == 'both' and subject['document_profile'] == 'editor',
         'Runtime subject/run/profile identity differs')
    need(packet['armed'] is True and packet['grant'] == 'root-authorized-foundation-original-stream-native-terminal-v1'
         and packet['schedule']['subject_sha256'] == header['subject_sha256']
         and container.digest(stream_json(packet['schedule'])) == header['schedule_sha256'] == witness['schedule_sha256']
         and len(packet['schedule']['slots']) == 23, 'Complete armed schedule identity differs')
    slot = packet['schedule']['slots'][0]
    need(slot['slot'] == 1 and slot['worker_epoch'] == witness['worker']['epoch'], 'Selected first Worker differs')
    streams = result['stream_records']; keys(streams, ('header', 'schedule', 'events', 'data', 'seal'), 'original stream records')
    for record in streams.values(): physical(record)
    need(streams['header'] == records['header'] and streams['seal'] == records['seal']
         and witness['subject_sha256'] == header['subject_sha256']
         and witness['binding'] == dict(runtime=selected_runtime, construction_readback=records['construction'],
              construction=construction['construction_record'], stream_records=streams), 'Bootstrap witness record binding crossed')
    need(seal['run_id'] == header['run_id'] and seal['subject_sha256'] == header['subject_sha256']
         and seal['schedule_sha256'] == header['schedule_sha256'] and type(seal['caller_exit']) is int
         and seal['caller_exit'] == 0 and seal['closed'] is True and seal['writers_joined'] is True
         and seal['status'] in ('collected', 'complete-originals-native-terminal'), 'Original stream seal is unsuccessful')
    for name in ('header', 'schedule', 'events', 'data'):
        need(all(seal['files'][name][field] == streams[name][field] for field in ('bytes', 'sha256')),
             'Stream seal original byte binding differs')
    workers = observation['runtime']['compiled_profile_query']['proof']['predicate']['raw']['workers']
    need(type(workers) is list and len(workers) == 23 and {r['worker'] for r in workers} == set(range(1, 24))
         and [r for r in workers if r['worker'] == 1] == [witness['ordinals']], 'Captured bootstrap differs from checked worker evidence')
    for group in ('ordering', 'bootstrap'):
        for row in observation[group].values():
            need(row['proof']['workers'] == workers, 'Bootstrap predicate evidence crossed')
    normal = lambda table: {name: {key: table[name][key] for key in ('bytes', 'sha256')} for name in ARTIFACTS}
    need(witness['source'] == subject['source'] == construction['source']
         and witness['toolchain'] == subject['toolchain'] and witness['host_assets'] == subject['host_assets']
         and witness['artifacts'] == normal(subject['artifacts']) == normal(construction['artifacts'])
         and witness['engine_profile'] == subject['engine_profile'], 'Construction/runtime/observed facts differ')
    need(subject['artifacts']['kernel_wasm']['lookup_name'] == producer.WASM_NAME, 'Compiled kernel Wasm lookup differs')
    names = producer.asset_names(document_profile='editor')
    need(type(host_assets) is dict and set(host_assets) == set(names), 'Exact editor asset graph required')
    asset_hashes = {name: container.digest(raw) for name, raw in host_assets.items()}
    need(all(subject['host_assets'].get(name) == digest for name, digest in asset_hashes.items()),
         'Host assets differ from accepted runtime originals')
    for name, data in (('kernel_factory', factory), ('kernel_wasm', wasm)):
        need(type(data) is bytes and witness['artifacts'][name] == dict(bytes=len(data), sha256=container.digest(data)),
             'Actual kernel artifact differs from accepted runtime')
    manifest.text(acceptance['build_origin'], 'actual Foundation build origin')
    receipt = dict(schema_version=1, kind=producer.EDITOR_RECEIPT_KIND, scope='foundation-rich-kernel-runtime',
        status='passed', profile='both', document_profile='editor', source=copy.deepcopy(witness['source']),
        toolchain=copy.deepcopy(witness['toolchain']), artifacts=dict(factory=copy.deepcopy(witness['artifacts']['kernel_factory']),
            wasm={**witness['artifacts']['kernel_wasm'], 'lookup_name': producer.WASM_NAME}),
        wasm_facts=consumer.scan_wasm(wasm), compiled_profile=copy.deepcopy(witness['compiled_profile']),
        compiled_editor_profile=copy.deepcopy(witness['compiled_editor_profile']), engine_profile=copy.deepcopy(witness['engine_profile']),
        engine_bootstrap=copy.deepcopy(witness['engine_bootstrap']), host_assets=asset_hashes,
        checks={name: observation['runtime'][name]['status'] for name in CHECKS}, build_origin=acceptance['build_origin'])
    raw = contract.canonical_json(receipt)
    _, eligible = producer.inspect_kernel_receipt(raw, container.digest(raw), factory, wasm, 'both', witness['engine_profile'],
        document_profile='editor', expected_kernel_inputs=witness['source']['kernel_inputs_sha256'], host_assets=asset_hashes)
    need(eligible is True, 'Derived real kernel receipt did not satisfy the unchanged editor producer')
    return receipt


def convert(acceptance_path, acceptance_sha256, *, factory_path, wasm_path, assets, output):
    snapshots = []
    selected = container._snapshot(acceptance_path, 1024 * 1024); snapshots.append(selected)
    need(container.digest(selected.content) == sha(acceptance_sha256), 'Independent runtime acceptance pin differs')
    acceptance = contract.strict_json(selected.content, 'Foundation runtime acceptance')
    keys(acceptance['records'], RECORD_ROLES, 'selected evidence records')
    evidence = {role: read_record(acceptance['records'][role], snapshots) for role in RECORD_ROLES}
    identities = {(record['dev'], record['ino']) for record in acceptance['records'].values()}
    need(len(identities) == len(RECORD_ROLES), 'Evidence roles alias the same physical file')
    factory = container._snapshot(factory_path, producer.MAX_FACTORY); wasm = container._snapshot(wasm_path, producer.MAX_KERNEL_WASM)
    snapshots.extend((factory, wasm)); blobs = {}
    root = container._ordinary_path(assets, directory=True)
    for name in producer.asset_names(document_profile='editor'):
        saved = container._snapshot(root / name, producer.MAX_MODULE); snapshots.append(saved); blobs[name] = saved.content
    receipt = derive_receipt(acceptance, evidence, factory=factory.content, wasm=wasm.content, host_assets=blobs)
    raw = contract.canonical_json(receipt)
    destination = Path(output).absolute(); container._ordinary_path(destination.parent, directory=True)
    need(str(destination) not in {str(s.path) for s in snapshots}, 'Output overwrites a selected input')
    for saved in snapshots: container._recheck(saved)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o444)
    with os.fdopen(fd, 'wb') as stream: stream.write(raw)
    return dict(kind='foundation-editor-kernel-receipt-conversion-v1', output=str(destination),
        receipt_sha256=container.digest(raw), acceptance_sha256=acceptance_sha256,
        source=receipt['source'], actual_runtime_executed=False, release_qualified=False)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acceptance', type=Path, required=True); p.add_argument('--acceptance-sha256', required=True)
    p.add_argument('--factory', type=Path, required=True); p.add_argument('--wasm', type=Path, required=True)
    p.add_argument('--assets', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    print(json.dumps(convert(args.acceptance, args.acceptance_sha256, factory_path=args.factory,
        wasm_path=args.wasm, assets=args.assets, output=args.output), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        print('foundation-receipt: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
