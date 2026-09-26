"""Verify the deliberately selected paper snapshot before rendering either draft."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / 'paper/selected-snapshot.json'


def load_snapshot(directory=None, *, selection=SELECTION, refreshed=False):
    selected = json.loads(Path(selection).read_text(encoding='utf-8'))
    directory = Path(directory) if directory else ROOT / selected['directory']
    raw = (directory / 'results.json').read_bytes()
    provenance_raw = (directory / 'provenance.json').read_bytes()
    provenance = json.loads(provenance_raw)
    data = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if (digest != selected['snapshot_sha256'] or digest != provenance['snapshot_sha256']
            or (not refreshed and hashlib.sha256(provenance_raw).hexdigest() != selected['provenance_sha256'])
            or data['report_artifact_id'] != selected['report_artifact_id']
            or provenance['report_artifact_id'] != selected['report_artifact_id']):
        raise ValueError('Selected manuscript snapshot identity/hash mismatch; reconcile both drafts before selecting new evidence')
    return data


def mc_interval(data, estimand, *, level='interval95', field=None, **identity):
    """Return a published complete-budget percentile range, never a seed interval.

    Missing/failed evidence remains missing. A valid bootstrap with malformed or
    ambiguous exports is an error rather than silently drawing an empty error bar.
    """
    bootstrap = data['bootstrap']
    if bootstrap['status'] != 'valid':
        return None
    if bootstrap['valid_replicas'] != bootstrap['planned_replicas']:
        raise ValueError('Incomplete MC bootstrap cannot supply percentile ranges')
    found = [r for r in data['bootstrap_intervals'] if r['estimand'] == estimand
             and all(r.get(k) == v for k, v in identity.items())]
    if len(found) != 1:
        raise ValueError('Missing or ambiguous MC bootstrap estimand')
    row = found[0]
    if row['status'] != 'valid':
        raise ValueError('MC bootstrap row status mismatch')
    value = json.loads(row[field])[level] if field else json.loads(row[level])
    import math
    if len(value) != 2 or not all(math.isfinite(x) for x in value) or value[0] > value[1]:
        raise ValueError('Invalid MC bootstrap percentile range')
    return value
