import copy

import numpy as np
import pandas as pd
import pytest

from higgsml.inference.likelihood import paired_event_toys, run_t2_procedure
from higgsml.inference.seed_blocks import canonical_seed_blocks, pairing_contract
from higgsml.inference.seed_evaluation import evaluate_seed_block, make_t2_outer_multiplicities
from higgsml.inference.templates import build_templates
from higgsml.protocol import DIAGNOSTICS, load_protocol


def population(role, *, prefix=None):
    prefix = prefix or role
    return pd.DataFrame([dict(dataset="atlas2020_4lep", role=role,
        event_group_id=f"{prefix}:{i}", event_id=f"{prefix}:{i}", label=i % 2,
        m4l=125., yield_weight=1., physical_weight=1., category=int(i >= 40))
        for i in range(80)])


def protocol():
    value = load_protocol().to_dict()
    value["diagnostics"] = copy.deepcopy(DIAGNOSTICS)
    value["templates"].update(min_neff_signed=2.)
    value["inference"].update(toy_count=2, outer_replicas=1, inner_toys=1)
    return value


def block_inputs(block):
    p = protocol()
    parent = population("template")
    base = build_templates(parent, mass_edges=[105., 140.], mapping_id="placeholder",
                           candidate_id="M3", thresholds=p["templates"])
    templates, bundles = {}, {}
    for key in block.candidate_keys:
        template = copy.deepcopy(base)
        template.update(mapping_id=key, candidate_id=key, seed=block.seed)
        templates[key] = template
        bundles[key] = {"mapping_id": key}
    grid = {"status": "valid", "family_id": "engineered19_raw_T1_m4l_off_attribution_v1",
            "mass_edges": [105., 140.], "templates": templates}
    return p, grid, bundles, parent


def fixed_categories(bundle, frame):
    return frame


@pytest.mark.parametrize('case',['empty','signal_only','background_only','missing_process'])
def test_sparse_parent_publishes_zero_attempt_terminal(tmp_path,case):
    from higgsml.inference.seed_evaluation_state import (
        SeedEvaluationBinding,claim_seed_evaluation,publish_seed_evaluation_terminal,read_seed_evaluation_terminal)
    block=canonical_seed_blocks()[0]
    p,grid,bundles,parent=block_inputs(block)
    parent=parent.assign(role='assessment')
    if case=='empty': parent=parent.iloc[:0]
    elif case=='signal_only': parent=parent.loc[parent.label==1]
    elif case=='background_only': parent=parent.loc[parent.label==0]
    else:
        parent=parent.assign(process=parent.label.map({0:'background',1:'signal'}))
        for template in grid['templates'].values():
            for sample in template['samples']:
                sample['name']='signal' if sample['is_signal'] else 'background'
            absent=copy.deepcopy(template['samples'][0]); absent.update(name='missing-background',is_signal=False)
            template['samples'].append(absent)
    result=evaluate_seed_block(grid,bundles,parent,p,block=block,stage='assessment',mu=1,count=2,
        toy_base_seed=42,layer='T0',t1_validation=None,prepared_id='prepared',freeze_id='freeze',categorize=fixed_categories)
    assert result['scientific_status']=='insufficient_statistics'
    assert result['generated_physical_toys']==0 and len(result['candidate_results'])==16
    assert all(row['attempted_fits']==0 and row['missing_fit_indexes']==[0,1] for row in result['candidate_results'])
    assert result['joint_support']['summary']['missing_processes']
    binding=SeedEvaluationBinding('population','freeze','spec','plan','within_seed','assessment',1,42,
        block.candidate_keys,{'test':'synthetic'}, {'planned_toys_per_candidate':2},result['rng'])
    output=tmp_path/'cell'
    claim_seed_evaluation(claims_root=tmp_path,output_dir=output,binding=binding)
    publish_seed_evaluation_terminal(output_dir=output,allowed_root=tmp_path,claims_root=tmp_path,
        dataset=p['dataset'],protocol=p,binding=binding,terminal=result)
    _,terminal=read_seed_evaluation_terminal(output_dir=output,claims_root=tmp_path,dataset=p['dataset'],protocol=p,binding=binding)
    assert terminal['scientific_status']=='insufficient_statistics'


@pytest.mark.parametrize('field,value',[('label',2),('role','validation'),('dataset','wrong'),('yield_weight',float('nan'))])
def test_sparse_parent_malformed_input_still_execution_error(field,value):
    from higgsml.errors import ResearchError,ResearchStateError
    block=canonical_seed_blocks()[0]; p,grid,bundles,parent=block_inputs(block)
    parent=parent.loc[parent.label==1].assign(role='assessment')
    parent.loc[parent.index[0],field]=value
    with pytest.raises(ResearchError) as failure:
        evaluate_seed_block(grid,bundles,parent,p,block=block,stage='assessment',mu=1,count=2,
            toy_base_seed=42,layer='T0',t1_validation=None,prepared_id='prepared',freeze_id='freeze',categorize=fixed_categories)
    assert not isinstance(failure.value,ResearchStateError)


@pytest.mark.filterwarnings("ignore:jsonschema.RefResolver is deprecated")
def test_actual_16way_t0_is_serial_parallel_deterministic_and_seed_streams_split():
    pytest.importorskip("pyhf")
    block42, block43 = canonical_seed_blocks()[:2]
    p, grid42, bundles42, parent = block_inputs(block42)
    arguments = dict(parent=parent, protocol=p, block=block42, stage="model-self",
        mu=1, count=2, toy_base_seed=7301, layer="T0", t1_validation=None,
        prepared_id="prepared", freeze_id="freeze", categorize=fixed_categories)
    serial = evaluate_seed_block(grid42, bundles42, workers=1, **arguments)
    parallel = evaluate_seed_block(grid42, bundles42, workers=2, worker_threads=1, **arguments)
    assert serial == parallel
    assert serial["scientific_status"] == "valid"
    assert serial["generated_physical_toys"] == 2
    assert {(row["attempted_fits"], row["completed_fits"], row["valid_fits"])
            for row in serial["candidate_results"]} == {(2, 2, 2)}
    observations = [row["result"]["toys"]["results"][0]["observations"]
                    for row in serial["candidate_results"]]
    assert all(value == observations[0] for value in observations[1:])

    p, grid43, bundles43, parent43 = block_inputs(block43)
    other = evaluate_seed_block(grid43, bundles43, parent43, p, block=block43,
        stage="model-self", mu=1, count=2, toy_base_seed=7301, layer="T0",
        t1_validation=None, prepared_id="prepared", freeze_id="freeze",
        categorize=fixed_categories)
    assert other["rng"]["stream_id"] != serial["rng"]["stream_id"]
    assert other["auxiliary_rng"][block43.candidate_keys[0]]["stream_id"] != serial["auxiliary_rng"][block42.candidate_keys[0]]["stream_id"]


def test_actual_t2_outer_plan_maps_both_parents_and_runs_inner_shared_poisson():
    calibration = population("calibration")
    template = population("template")
    mother = population("assessment")
    plan = make_t2_outer_multiplicities(calibration,
        contract_digest=pairing_contract()["contract_digest"], outer_replicas=1,
        toy_base_seed=991)
    applied = []

    def fit_mapping(bootstrap):
        return {"mapping_id": "outer-map", "bundles": {}}

    def apply_mapping(mapping, frame):
        applied.append((mapping["mapping_id"], next(iter(frame.role))))
        return frame.assign(mapped_category=frame.category)

    def evaluate(mapped_template, mapped_mother, mapping, inner_toys, inner_seed):
        assert mapping["mapping_id"] == "outer-map"
        combined = pd.concat([mapped_template.assign(role="template")], ignore_index=True)
        result = paired_event_toys(combined, category_columns={"candidate": "mapped_category"},
            mass_edges=[105., 140.], mu=1., count=inner_toys, seed=inner_seed,
            mother_id="template-parent", parent_role="template")
        assert len(result["observations"]["candidate"]) == 1
        assert mapped_template.mapped_category.tolist() == template.category.tolist()
        assert mapped_mother.mapped_category.tolist() == mother.category.tolist()
        return {"status": "valid", "inner": result}

    output = run_t2_procedure(calibration, template, mother,
        fit_mapping=fit_mapping, apply_mapping=apply_mapping, evaluate=evaluate,
        outer_replicas=1, inner_toys=1, seed=991, model_id="model", mother_id="mother",
        outer_multiplicities=plan, inner_seed_factory=lambda outer: 12345)
    assert output["status"] == "valid"
    assert applied == [("outer-map", "template"), ("outer-map", "assessment")]
    assert list(output["replicas"][0]["bootstrap_group_multiplicities"]) == plan["groups"]
