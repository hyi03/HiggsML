"""Publish verified draft001 report aggregates to the offline explanation.

Reads completed aggregate stages only; never events, checkpoints or raw MC.
The report selection is explicit. No scoring, training, fitting or access claim.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
WEB = Path(__file__).resolve().parents[1]
REPORT_ID = '9aab6d274a3e2d00d892c2d8fbf89b1e46f5b7a95d0bf0c085af90672ea36898'


def read_stage(directory, expected, names):
    raw = (directory / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    if manifest['status'] != 'complete' or manifest['stage'] != expected:
        raise ValueError('Unexpected aggregate stage: ' + str(directory))
    values = {}
    for name in names:
        payload = (directory / name).read_bytes()
        entry = manifest['files'][name]
        if len(payload) != entry['size_bytes'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
            raise ValueError('Aggregate binding mismatch: ' + name)
        values[name] = payload
    return manifest, values, hashlib.sha256(raw).hexdigest()


def project(source):
    names = ['binding.json', 'summary.json', 'results.json', 'spectra.json', 'protocol.json',
             'widths.csv', 'contrasts.csv', 'inclusive-reference.csv', 'mass-bins.csv',
             'yield-summary.csv', 'mass-yields.png', 'mass-shapes.png']
    manifest, payloads, manifest_hash = read_stage(source, 'draft-v2-report', names)
    if manifest['artifact_id'] != REPORT_ID:
        raise ValueError('Report is not the manuscript-selected draft001 source')
    binding = json.loads(payloads['binding.json'])
    summary = json.loads(payloads['summary.json'])
    results = json.loads(payloads['results.json'])
    spectra = json.loads(payloads['spectra.json'])
    protocol = json.loads(payloads['protocol.json'])
    if binding['source_kind'] != 'controlled_mc' or summary['scientific_status'] != 'complete':
        raise ValueError('Require the completed controlled-MC result')
    if protocol['qualification'] != summary['qualification'] or summary['qualification']['independent']:
        raise ValueError('Qualification mismatch')
    root = source.parent
    stages = {'draft-v2-evaluate': 'evaluate', 'draft-v2-freeze': 'freeze', 'draft-v2-prepare': 'prepare'}
    for up in manifest['upstreams']:
        stage = stages[up['stage']]
        upstream = json.loads((root / stage / 'manifest.json').read_bytes())
        if (upstream['artifact_id'], upstream['stage']) != (up['artifact_id'], up['stage']):
            raise ValueError('Upstream identity mismatch')
        if binding[{'evaluate': 'evaluation', 'freeze': 'freeze', 'prepare': 'prepared'}[stage] + '_artifact_id'] != up['artifact_id']:
            raise ValueError('Report binding mismatch')
    _, frozen, _ = read_stage(root / 'freeze', 'draft-v2-freeze', ['freeze.json'])
    freeze = json.loads(frozen['freeze.json'])
    _, evaluated, _ = read_stage(root / 'evaluate', 'draft-v2-evaluate', ['summary.json', 'results.json', 'spectra.json'])
    if any(evaluated[name] != payloads[name] for name in evaluated):
        raise ValueError('Report/evaluation disagreement')
    for row in summary['rows']:
        widths = [results[f"{row['subset']}:{seed}"]['interval']['width'] for seed in summary['seeds']]
        if row['widths'] != widths or row['median'] != statistics.median(widths):
            raise ValueError('Width arithmetic mismatch')
    for row in summary['contrasts']:
        delta = [results[f"{row['reduced']}:{k}"]['interval']['width'] - results[f'ABCD:{k}']['interval']['width'] for k in summary['seeds']]
        if row['differences'] != delta or row['median_difference'] != statistics.median(delta):
            raise ValueError('Paired-contrast arithmetic mismatch')
    if len(results) != 16 or any(r['status'] != 'valid' for r in results.values()):
        raise ValueError('The selected run must contain sixteen valid terminals')
    if not math.isclose(summary['inclusive_width'], results['inclusive']['interval']['width'], abs_tol=1e-14):
        raise ValueError('Shared-reference mismatch')
    models = {}
    for subset in ['ABCD', 'BCD']:
        key = subset + ':42'
        processes = {}
        for process, values in spectra[key].items():
            processes[process] = values
        models[subset] = {'threshold': freeze['models'][key]['threshold'],
                          'model_id': freeze['models'][key]['model_id'], 'processes': processes}
    public = dict(schema_version='draft-v2-website-results-v1', run_name='draft001',
        source_kind='controlled_mc', source_population='all_mc',
        report_artifact_id=manifest['artifact_id'], source_manifest_sha256=manifest_hash,
        binding=binding, protocol=protocol, summary=summary,
        intervals={k: v['interval'] for k, v in results.items()}, models=models,
        consumed_files={name: manifest['files'][name] for name in names},
        provenance={'git_commit': manifest['software']['git_commit'],
                    'git_dirty': manifest['software']['git_dirty'],
                    'python': manifest['software']['python'],
                    'platform': manifest['software']['platform']})
    return public, payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'runs/h4l-draft-v2-draft001/report')
    args = parser.parse_args()
    data, payloads = project(args.source)
    assets = WEB / 'assets'
    assets.mkdir(exist_ok=True)
    for name in ['mass-yields.png', 'mass-shapes.png', 'widths.csv', 'contrasts.csv',
                 'inclusive-reference.csv', 'mass-bins.csv', 'yield-summary.csv']:
        destination = assets / ('draft001-' + name)
        if destination.exists() and destination.read_bytes() != payloads[name]:
            raise ValueError('Different published asset; preserve and review before replacement: ' + name)
        destination.write_bytes(payloads[name])
    (WEB / 'results-data.js').write_text(
        '/* Bound draft001 aggregate projection; no event or model payloads. */\n'
        + 'globalThis.DraftResults = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n', encoding='utf-8')
    print('Published draft001: fifteen widths, shared reference, twelve paired contrasts and two unchanged report figures.')


if __name__ == '__main__':
    main()
