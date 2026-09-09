import copy
import numpy as np
import pytest

from src.research.diagnostics import signed_mu_fit, signed_mu_summary
from src.research.errors import ResearchError
from src.research.protocol import DIAGNOSTICS, DEFAULT_PATH, load_protocol
from src.research.inference import build_model, profile_interval, run_toys


def template(signal=(10.,), background=(20.,)):
    def sample(name, values, is_signal):
        return dict(name=name, yield_=list(values), is_signal=is_signal)
    samples = [sample('s', signal, True), sample('b', background, False)]
    for row in samples:
        row['yield'] = row.pop('yield_')
        row.update(variance=[1.]*len(signal), covariance=np.eye(len(signal)).tolist())
    return dict(status='valid', active_bins=list(range(len(signal))), samples=samples,
                mapping_id='synthetic', candidate_id='M0')


@pytest.mark.parametrize('observed,expected', [(15.,-.5), (20.,0.), (25.,.5)])
def test_signed_single_bin_analytic_mle(observed, expected):
    result = signed_mu_fit(template(), [observed], DIAGNOSTICS['signed_mu'])
    assert result['status'] == 'valid'
    assert result['muhat'] == pytest.approx(expected, abs=1e-8)
    assert result['minimum_expected_rate'] > 0
    assert result['nuisance_policy'] == 'fixed_nominal_no_T1_profiling'


def test_physical_intervals_keep_zero_bound_and_same_toys_get_separate_diagnostic():
    pytest.importorskip('pyhf')
    model, _ = build_model(template())
    assert profile_interval(model, [15.])['muhat'] == pytest.approx(0., abs=1e-6)
    result = run_toys(template(), mu=0., count=4, signed_diagnostic=DIAGNOSTICS['signed_mu'])
    assert result['signed_mu_diagnostic']['budget'] == 4
    assert all('signed_mu_diagnostic' in toy for toy in result['results'])
    assert all(toy['intervals'][0]['lower'] == 0. for toy in result['results'])
    legacy = run_toys(template(), mu=0., count=1)
    assert 'signed_mu_diagnostic' not in legacy['results'][0]


def test_multibin_positive_domain_and_no_fake_finite_mle():
    result = signed_mu_fit(template((10., 1.), (20., .1)), [10., 0.], DIAGNOSTICS['signed_mu'])
    assert result['search_bounds'][0] > -.1
    assert result['minimum_expected_rate'] > 0
    assert result['status'] == 'search_bound_reached'
    zero = signed_mu_fit(template(), [0.], DIAGNOSTICS['signed_mu'])
    assert zero['status'] == 'search_bound_reached'
    assert signed_mu_summary([zero])['nonvalid_fits'] == 1
    assert signed_mu_summary([zero])['signed_mean_valid_fits'] is None


def test_invalid_support_observations_and_contract():
    for t in (template((0.,), (20.,)), template((10.,), (0.,))):
        assert signed_mu_fit(t, [0.], DIAGNOSTICS['signed_mu'])['status'] == 'signed_domain_unavailable'
    for n in ([-1.], [np.nan], [2., 3.]):
        with pytest.raises(ResearchError):
            signed_mu_fit(template(), n, DIAGNOSTICS['signed_mu'])
    with pytest.raises(ResearchError):
        signed_mu_fit(template((-1.,)), [2.], DIAGNOSTICS['signed_mu'])
    bad = copy.deepcopy(DIAGNOSTICS['signed_mu']); bad['nuisance_policy'] = 'profile_T1'
    with pytest.raises(ResearchError):
        signed_mu_fit(template(), [2.], bad)


def test_versioned_diagnostics_preserve_v1_and_reject_changed_rules(tmp_path):
    import json
    old = load_protocol(DEFAULT_PATH.with_name('research_protocol_v1.json')).to_dict()
    assert old['schema_version'] == 'h4l-research-v1' and 'diagnostics' not in old
    new = load_protocol().to_dict()
    assert new['diagnostics'] == DIAGNOSTICS
    new['diagnostics']['signed_mu']['mu_bounds'][0] = -100
    changed = tmp_path/'protocol.json'; changed.write_text(json.dumps(new))
    with pytest.raises(ResearchError, match='diagnostic'):
        load_protocol(changed)
