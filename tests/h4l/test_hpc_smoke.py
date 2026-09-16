"""HPC functional checks restricted to <=2 workers, one thread and tiny fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from higgsml.hpc import ENV, THREAD_ENV, GIB


@pytest.fixture
def tiny_hpc(monkeypatch):
    import torch
    from threadpoolctl import threadpool_limits
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    for key in THREAD_ENV:
        monkeypatch.setenv(key, '1')
    monkeypatch.setenv(ENV, json.dumps(dict(workers=2, worker_threads=1,
        cpu_budget=2, memory_bytes=8*GIB, worker_memory_bytes=GIB,
        score_cache_bytes=8*1024*1024, root_threads=1)))
    try:
        with threadpool_limits(limits=1):
            yield
    finally:
        torch.set_num_threads(previous)


def test_small_process_pool_and_exception_cleanup(tiny_hpc):
    from tests.h4l.test_performance_refactor import test_ordered_process_execution_and_exception_cleanup
    test_ordered_process_execution_and_exception_cleanup()


def test_tiny_t2_preserves_conditional_random_draws(tiny_hpc):
    from tests.h4l.test_performance_refactor import test_t2_workers_preserve_conditional_rng_and_failure_records
    test_t2_workers_preserve_conditional_rng_and_failure_records()


def test_three_toys_and_two_assessment_observations(tiny_hpc):
    from tests.h4l.test_performance_refactor import (
        test_toy_workers_equal_serial, test_assessment_worker_pairing_and_auxiliary_equal_serial)
    test_toy_workers_equal_serial()
    test_assessment_worker_pairing_and_auxiliary_equal_serial()


def test_two_bootstrap_replicas_retain_failure_denominators(tiny_hpc, monkeypatch):
    from tests.h4l.test_mass_off_attribution import test_mc_bootstrap_workers_preserve_draws_order_and_failures
    test_mc_bootstrap_workers_preserve_draws_order_and_failures(monkeypatch)


def test_bootstrap_cached_scores_preserve_resampling_and_reduce_predictions(tiny_hpc, monkeypatch):
    import numpy as np
    import pandas as pd
    from higgsml.inference import bootstrap, assessment
    from higgsml.inference.attribution import BUDGETS, candidate_keys, FAMILY
    from higgsml.protocol import load_protocol
    monkeypatch.setitem(BUDGETS['mc_bootstrap'], 'replicas', 2)
    protocol = load_protocol().to_dict()
    bundles = {key: dict(candidate_id='M3', model={}, model_id=key, mapping_id=key,
                        mapping=None, transform='raw', seed=42) for key in candidate_keys()}
    grid = dict(templates={key: {} for key in bundles}, mass_edges=[105., 140.], family_id=FAMILY)
    def frame(role):
        return pd.DataFrame(dict(role=role, event_id=[f'{role}-{i}' for i in range(4)],
            event_group_id=[f'{role}-{i}' for i in range(4)], label=[0, 1, 0, 1],
            m4l=120., physical_weight=1., yield_weight=1., score=[.1, .3, .7, .9]))
    calls = []
    def predict(model, population):
        calls.append(len(population))
        return population.score.to_numpy()
    monkeypatch.setattr(bootstrap, 'predict_discriminant', predict)
    monkeypatch.setattr(assessment, 'predict_discriminant', predict)
    monkeypatch.setattr(bootstrap, 'fit_thresholds', lambda *a, **k: {})
    monkeypatch.setattr(bootstrap, 'assign_categories', lambda thresholds, scores, **k: (scores > .5).astype(int))
    monkeypatch.setattr(assessment, 'categorize_bundle',
        lambda bundle, population: population.assign(category=(predict(bundle['model'], population) > .5).astype(int)))
    # No likelihood fit or report work: retain a declared support failure per candidate.
    monkeypatch.setattr(bootstrap, 'build_templates', lambda *a, **k: {'status': 'insufficient_statistics'})
    args = (grid, bundles, frame('calibration'), frame('template'), protocol)
    policy = os.environ[ENV]
    monkeypatch.delenv(ENV)
    baseline = bootstrap.mass_off_mc_bootstrap(*args, t1_validation={}, workers=1)
    baseline_calls = len(calls)
    calls.clear()
    monkeypatch.setenv(ENV, policy)
    optimized = bootstrap.mass_off_mc_bootstrap(*args, t1_validation={}, workers=1)
    assert optimized == baseline
    assert len(calls) < baseline_calls


def test_model_self_fallback_and_metrics_with_stubbed_fits(tiny_hpc, monkeypatch, tmp_path):
    from tests.h4l.test_mass_off_attribution import test_model_self_joint_generation_and_process_marginals
    test_model_self_joint_generation_and_process_marginals(monkeypatch, tmp_path)
    records = list((tmp_path / '.hpc-executions').glob('*.json'))
    assert len(records) == 2
    assert all(json.loads(path.read_text())['status'] == 'returned' for path in records)


def test_hpc_interval_cache_matches_non_hpc_on_one_bin(tiny_hpc, monkeypatch):
    from tests.h4l.test_inference import single_bin
    from higgsml.inference.likelihood import run_toys
    policy = os.environ[ENV]
    monkeypatch.delenv(ENV)
    baseline = run_toys(single_bin(), count=2, workers=1)
    monkeypatch.setenv(ENV, policy)
    optimized = run_toys(single_bin(), count=2, workers=1)
    assert optimized == baseline


def test_parallel_fallback_two_candidates_two_toys(tiny_hpc, monkeypatch):
    from tests.h4l.test_inference import single_bin
    from higgsml.inference.attribution_workflow import _model_self_fallback
    evidence = dict(status='validated', evidence_id='synthetic-only', correlation='independent_process_bins',
                    auxiliary='poisson_tau_gamma', modifier='shapesys', pyhf_version='0.7.6')
    templates = {'b': single_bin(), 'a': single_bin()}
    args = dict(mu=1, count=2, seed=42, t1=evidence, auxiliary_generation='regenerated')
    policy = os.environ[ENV]
    monkeypatch.delenv(ENV)
    baseline = _model_self_fallback(templates, **args)
    monkeypatch.setenv(ENV, policy)
    completed = []
    result = _model_self_fallback(templates, **args, workers=2, progress=lambda: completed.append(1))
    assert result == baseline
    assert list(result) == ['a', 'b'] and len(completed) == 4


@pytest.mark.parametrize('script,extra', [
    ('h4l_all.py', ['--plan-only']),
    ('h4l_off_run.py', ['--source-run-name', 'test01', '--run-name', 'smoke-unused', '--evaluation', '--plan'])])
def test_cli_hpc_two_workers_planning_only(script, extra):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env.pop(ENV, None)
    env.update({key: '1' for key in THREAD_ENV})
    # Plan-only entry checks must not depend on free RAM while other user jobs run.
    # Exercise the real parser/activation with a mocked two-CPU allocation; launch no work.
    bootstrap = ('import sys,runpy; from higgsml import hpc; '
                 'hpc.available_resources=lambda:(2,8*hpc.GIB); '
                 "path=sys.argv.pop(1); runpy.run_path(path,run_name='__main__')")
    result = subprocess.run([sys.executable, '-c', bootstrap, str(root/'scripts'/script), '--HPC',
        '--hpc-workers', '2', '--hpc-worker-memory-gb', '.125', '--hpc-score-cache-gb', '.0625', *extra],
        cwd=root, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'HPC resources:' in result.stdout
    assert '"workers": 2' in result.stdout and '"worker_threads": 1' in result.stdout
