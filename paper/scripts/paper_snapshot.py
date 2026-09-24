"""Verify the deliberately selected paper snapshot before rendering either draft."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / 'paper/evidence/selected-snapshot.json'


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
