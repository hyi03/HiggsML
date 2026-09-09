import copy
import json
import numpy as np
import pandas as pd
import pytest
import torch

from src.research.discriminants import (ResearchClassifier, train_discriminant,
    predict_discriminant, effective_lambda, TRAINING, digest)
from src.research.errors import ResearchError, ResearchStateError
from src.research.protocol import load_protocol
from src.research.representations import representation_features, ordered_group_subsets


def frame():
    rng = np.random.default_rng(2)
    rows = 72
    data = pd.DataFrame({n:rng.normal(size=rows) for n in representation_features('engineered19')})
    data['m4l'] = np.tile(np.linspace(105.1,139.9,36),2)
    data['y4l'] = rng.normal(size=rows)
    data['label'] = np.tile(np.repeat([0,1],18),2)
    data['role'] = ['train']*36+['validation']*36
    data['dataset']='atlas2020_4lep'
    data['event_group_id']=[str(i) for i in range(rows)]
    data['physical_weight']=np.tile([1.,2.],rows//2)
    return data


@pytest.fixture(autouse=True)
def single_thread():
    old=torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def test_dimensions_and_all_subsets():
    for name,count in [('mass-only',1),('decay7',8),('lab-extension',10),('engineered19',20)]:
        inputs=representation_features(name)
        assert len(inputs)==count
        assert ResearchClassifier(count)(torch.zeros(2,count)).shape==(2,)
    assert len(ordered_group_subsets())==15
    for groups in ordered_group_subsets(include_empty=True):
        assert representation_features('engineered19',groups=groups)[-1]=='m4l'


def test_ordinary_train_only_scaler_determinism_and_safe_roundtrip():
    data=frame()
    data.loc[data.role=='validation','m4l']+=100
    protocol=load_protocol()
    a=train_discriminant(data,protocol,'M0c')
    b=train_discriminant(data,protocol,'M0c')
    assert a['model_id']==b['model_id']
    assert a['scaler']['mean']==pytest.approx([data.loc[data.role=='train','m4l'].mean()])
    assert 1<=a['selected_epoch']<=200
    assert a['checkpoint_rule'].startswith('validation-absolute')
    assert np.array_equal(predict_discriminant(a,data),predict_discriminant(json.loads(json.dumps(a)),data))
    broken=copy.deepcopy(a)
    broken['scaler']['mean'][0]+=1
    with pytest.raises(ResearchError,match='digest'):
        predict_discriminant(broken,data)


def test_fixed_200_matched_zero_and_lambda_schedule(monkeypatch):
    data=frame()
    protocol=load_protocol()
    a=train_discriminant(data,protocol,'M3-fixed200')
    b=train_discriminant(data,protocol,'M3-fixed200')
    assert a['state_dict']==b['state_dict']
    assert a['selected_epoch']==b['selected_epoch']==200
    assert len(a['history'])==200
    # Check that the M6 branch shares initialization/order with its fixed200
    # control, while the public API still forbids an unregistered M6-zero run.
    with monkeypatch.context() as controlled:
        controlled.setattr('src.research.discriminants.effective_lambda',lambda epoch,target:0.)
        paired=train_discriminant(data,protocol,'M6',target_lambda=.05)
    assert paired['state_dict']==a['state_dict']
    c=train_discriminant(data,protocol,'M6',target_lambda=.2)
    assert c['effective_lambda']==.2 and c['selected_epoch']==200
    assert [c['history'][i-1]['effective_lambda'] for i in [1,5,6,15,16,200]]==pytest.approx([0,0,.02,.2,.2,.2])
    assert c['state_dict']!=a['state_dict']
    with pytest.raises(ResearchError):
        train_discriminant(data,protocol,'M6',target_lambda=0.)


def test_training_rule_and_role_cannot_be_bypassed():
    protocol=load_protocol().to_dict()
    protocol['training']['max_epochs']=2
    with pytest.raises(ResearchError,match='sealed'):
        train_discriminant(frame(),protocol,'M6')
    data=frame()
    data.loc[0,'role']='assessment'
    with pytest.raises(ResearchError,match='role'):
        train_discriminant(data,load_protocol())
    data=frame()
    data.loc[36,'event_group_id']=data.loc[0,'event_group_id']
    with pytest.raises(ResearchError,match='crosses'):
        train_discriminant(data,load_protocol())
    with pytest.raises(ResearchError,match='derive'):
        train_discriminant(frame(),load_protocol(),'M5')


def test_bad_mass_bins_fail_before_fixed_training():
    data=frame()
    data['m4l']=125.
    with pytest.raises(ResearchStateError) as exc:
        train_discriminant(data,load_protocol(),'M6',target_lambda=.1)
    assert exc.value.status=='insufficient_statistics'
