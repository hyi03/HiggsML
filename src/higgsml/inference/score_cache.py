"""Bounded, call-local raw scores; never cache fitted thresholds or mappings."""
import numpy as np
import pandas as pd

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError
from higgsml.performance import timer, add


class RawScoreCache:
    def __init__(self, bundles, populations, predict, max_bytes):
        self.tables = {}
        self.used = 0
        with timer('raw_score_cache'):
            for key, bundle in bundles.items():
                if bundle.get('candidate_id') == 'M0off':
                    continue
                try:
                    identity = digest_json({'model_id': bundle.get('model_id'), 'model': bundle.get('model'),
                                            'me_scores': bundle.get('me_scores')})
                except (ResearchError, ValueError, TypeError):
                    continue
                for role, frame in populations.items():
                    if 'event_id' not in frame or frame.event_id.duplicated().any():
                        continue
                    estimate = int(frame.event_id.memory_usage(index=False, deep=True)) + 48 * len(frame)
                    if self.used + estimate > max_bytes:
                        continue
                    try:
                        values = np.asarray(predict(bundle, frame), dtype=float)
                        if values.shape != (len(frame),) or not np.isfinite(values).all():
                            continue
                        table = pd.Series(values, index=pd.Index(frame.event_id))
                        # Force index allocation before counting its memory.
                        table.index.get_indexer(table.index)
                        size = int(table.memory_usage(index=True, deep=True))
                        if self.used + size > max_bytes:
                            continue
                        table.to_numpy().flags.writeable = False
                        self.tables[(key, role)] = (identity, table)
                        self.used += size
                    except Exception:
                        # Preserve the original task-local error and RNG timing.
                        continue
        add('score_cache_bytes', self.used)

    def get(self, key, role, frame):
        item = self.tables.get((key, role))
        if item is None:
            return None
        _, table = item
        positions = table.index.get_indexer(frame.event_id)
        if (positions < 0).any():
            return None
        add('raw_score_cache_hits')
        return table.to_numpy()[positions]
