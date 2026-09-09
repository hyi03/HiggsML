"""Synthetic four-lepton reconstruction through the public research stages."""
import json
import math

import numpy as np
import pandas as pd
import pytest
import torch

from src.cli.research import build_parser
from src.config import load_preprocess_protocol
from src.domain.selection import SelectionConfig, select_event
from src.domain.features import build_candidate_features
from src.domain.angular5 import build_angular5
from src.research.artifacts import read_run
from src.research.data import assign_roles, write_research_data
from src.research.protocol import load_protocol, DEFAULT_PATH
from src.research.workflow import execute


def synthetic_four_leptons(count=1800):
    rng = np.random.default_rng(431)
    legacy = load_preprocess_protocol('config/preprocess_protocol_mass_window.yaml', dataset='atlas2020_4lep')
    selection = SelectionConfig.from_mapping(legacy.selection)
    rows = []
    for i in range(count):
        label = i % 2
        pt = np.array([38.,33.,27.,22.]) * rng.uniform(.92,1.08,4)
        eta = np.array([.2,-.2,.4,-.4]) + rng.normal(0,.16,4)
        phi = np.array([0.,math.pi,1.1,1.1+math.pi]) + rng.normal(0,.2,4)
        energy = pt*np.cosh(eta)
        mass = np.sqrt(energy.sum()**2-(pt*np.cos(phi)).sum()**2-(pt*np.sin(phi)).sum()**2-(pt*np.sinh(eta)).sum()**2)
        target = rng.uniform(105.1,139.9)
        pt *= target/mass
        energy = pt*np.cosh(eta)
        event = dict(lep_n=4,lep_pt=(pt*1000).tolist(),lep_eta=eta.tolist(),lep_phi=phi.tolist(),
            lep_e=(energy*1000).tolist(),lep_charge=[-1,1,-1,1],lep_type=[11,11,13,13],
            trigE=True,trigM=False,lep_isTrigMatched=[True,False,False,False],lep_isTightID=[True]*4,
            lep_track_iso=[1000.]*4,lep_calo_iso=[1000.]*4,lep_d0sig=[1.]*4,lep_z0=[.1]*4,
            runNumber=1,eventNumber=i,channelNumber=345060 if label else 363490,mcWeight=1.)
        selected = select_event(event,selection,'MeV')
        if not selected.accepted:
            continue
        c = selected.candidate
        row = build_candidate_features(event,c)
        row.update(build_angular5(c))
        vector = c.four_lepton
        row.update(event_id=f'synthetic:{i}',source_row_id=f'synthetic:{i}',event_group_id=f'synthetic:{i}',
            split='development',dataset='atlas2020_4lep',label=label,physical_weight=.02,
            y4l=.5*np.log((vector.energy+vector.pz)/(vector.energy-vector.pz)),
            lep_pt=c.normalized.pt.tolist(),lep_eta=c.normalized.eta.tolist(),lep_phi=c.normalized.phi.tolist(),
            lep_e=c.normalized.energy.tolist(),lep_charge=c.normalized.charge.tolist(),lep_type=c.normalized.flavour.tolist(),
            pairing=[list(c.pairing.z1_indices),list(c.pairing.z2_indices)])
        rows.append(row)
    result = assign_roles(pd.DataFrame(rows),load_protocol())
    result.attrs['source_kind'] = 'synthetic'
    return result


def test_synthetic_end_to_end_and_scientific_blockers(tmp_path):
    pytest.importorskip('pyhf', reason='full numerical pipeline uses the optional research environment')
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        protocol = load_protocol().to_dict()
        frame = synthetic_four_leptons()
        source = tmp_path/'source.jsonl'
        write_research_data(frame,source,protocol)
        def stage(command, name, *extra):
            args = build_parser().parse_args([command,'--dataset','atlas2020_4lep',
                '--protocol',str(DEFAULT_PATH),'--run-dir',str(tmp_path/name),*map(str,extra)])
            result = execute(args,allowed_root=tmp_path)
            return read_run(tmp_path/name,dataset='atlas2020_4lep',protocol=protocol,allow_terminal=True),result
        prepared,_ = stage('prepare','prepared','--events',source)
        assert prepared.read_json('audit.json')['status']=='passed'
        assert prepared.manifest['source_kind']=='synthetic'
        calibrations = []
        for candidate in ('M0c','M2','M3'):
            model,_ = stage('train',candidate,'--input-run',prepared.path,'--candidate',candidate)
            assert model.read_json('model.json')['architecture'][0] == {'M0c':1,'M2':8,'M3':20}[candidate]
            for transform in (('raw',) if candidate=='M0c' else ('raw','physical')):
                calibration,_ = stage('calibrate',candidate+'-'+transform,'--input-run',prepared.path,
                                      '--model-run',model.path,'--transform',transform)
                calibrations += ['--calibration-run',str(calibration.path)]
        templates,_ = stage('templates','templates','--input-run',prepared.path,*calibrations)
        grid = templates.read_json('templates.json')
        assert grid['status']=='valid'
        assert set(grid['templates'])=={'M0','M0c:42','M2:42','M3:42','M4:42','M5:42'}
        assert templates.read_json('g1.json')['status']!='passed'
        inference,_ = stage('infer','t0','--template-run',templates.path,'--layer','T0')
        assert all(v['status']=='valid' for v in inference.read_json('inference.json').values())
        blocked,_ = stage('infer','t1','--template-run',templates.path,'--layer','T1')
        assert all(v['status']=='template_stat_model_unvalidated' for v in blocked.read_json('inference.json').values())
        expanded,result = stage('train','expanded','--input-run',prepared.path,'--candidate','M6','--strength','.1')
        assert result['status']=='g1_not_passed'
        frozen,result = stage('freeze','freeze','--input-run',prepared.path,'--template-run',templates.path)
        assert result['status']=='g1_not_passed'
        report,_ = stage('report','report','--result-run',inference.path)
        assert report.read_json('report.json')['primary_comparison']['status']=='primary_comparison_incomplete'
        assert (report.path/'report.md').is_file()
    finally:
        torch.set_num_threads(old_threads)
