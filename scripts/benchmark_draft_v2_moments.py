#!/usr/bin/env python3
"""Synthetic same-task benchmark: explicit group copies versus cached moments.

No MC reads, persisted research artifacts, likelihood fits, or speedup target.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from higgsml.draft_v2.validation_statistics import GroupMoments
from higgsml.draft_v2.validation_execution import numeric_threads
from higgsml.inference.statistics import GroupBinStatistics


def benchmark(groups=4000, repeats=10):
    rng = np.random.default_rng(912)
    codes = np.repeat(np.arange(groups), 3)
    bins = rng.integers(0, 2, len(codes))
    weights = rng.normal(.1, .2, len(codes))
    draws = [rng.multinomial(groups, np.full(groups, 1/groups)) for _ in range(repeats)]
    with numeric_threads():
        started = perf_counter()
        reference = []
        for counts in draws:
            selected = np.repeat(np.arange(groups), counts)
            indices = (selected[:, None]*3+np.arange(3)).ravel()
            new_groups = np.repeat(np.arange(groups), 3)
            reference.append(GroupBinStatistics(new_groups, bins[indices], weights[indices], 2).moments())
        explicit_seconds = perf_counter()-started
        started = perf_counter()
        cache = GroupMoments(codes, bins, weights, groups, 2)
        setup_seconds = perf_counter()-started
        started = perf_counter()
        optimized = [cache.weighted(counts).moments() for counts in draws]
        optimized_seconds = perf_counter()-started
    for left, right in zip(reference, optimized):
        for a, b in zip(left, right):
            np.testing.assert_allclose(a, b, rtol=1e-11, atol=1e-10)
    return dict(scope='synthetic_software_moments_only_not_end_to_end_runtime', groups=groups,
        rows_per_group=3, replicates=repeats, explicit_seconds=explicit_seconds,
        optimized_setup_seconds=setup_seconds, optimized_repeats_seconds=optimized_seconds,
        optimized_total_seconds=setup_seconds+optimized_seconds,
        equality_rtol=1e-11, equality_atol=1e-10, numerical_threads=1,
        platform=platform.platform(), python=platform.python_version(), numpy=np.__version__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--groups', type=int, default=4000)
    parser.add_argument('--repeats', type=int, default=10)
    args = parser.parse_args()
    if args.groups < 1 or args.repeats < 1:
        parser.error('groups/repeats must be positive')
    print(json.dumps(benchmark(args.groups, args.repeats), indent=2))
