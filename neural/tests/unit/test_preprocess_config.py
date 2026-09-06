from pathlib import Path
import pytest
import yaml
from src.config import InputBindingError,load_preprocess_protocol,load_preprocess_run_config
PROJECT=Path(__file__).parents[2]

@pytest.mark.parametrize("dataset,profile,zz,count",[("atlas2020_4lep","mini",363490,164716),("atlas2025_exactly4lep","analysis",700600,419943)])
def test_checked_in_protocol_freezes_scientific_contract(dataset,profile,zz,count):
    p=load_preprocess_protocol(PROJECT/"config/preprocess_protocol_v2.yaml",dataset=dataset)
    assert p.protocol_id=="higgsml-preprocess-v2"
    assert p.samples["higgs"].tree_name==p.samples["zz"].tree_name==profile
    assert p.samples["zz"].dsid==zz and p.samples["higgs"].expected_entry_count==count
    assert p.output_columns[-2:]==("source_file_id","event_group_id")
    assert p.selection["m4l_window_gev"]==[105.0,160.0]

@pytest.mark.parametrize("field",["luminosity_pb","selection","split","serialization","output_columns"])
def test_protocol_rejects_frozen_contract_drift(tmp_path,field):
    raw=yaml.safe_load((PROJECT/"config/preprocess_protocol_v2.yaml").read_bytes());raw[field]=None
    path=tmp_path/"changed.yaml";path.write_text(yaml.safe_dump(raw))
    with pytest.raises(InputBindingError):load_preprocess_protocol(path,dataset="atlas2020_4lep")

def test_old_protocol_is_rejected():
    with pytest.raises(InputBindingError):load_preprocess_protocol(PROJECT/"config/preprocess_protocol_v1.yaml",dataset="atlas2020_4lep")

def test_debug_protocol_disables_m4l_window_without_hash_seal():
    p=load_preprocess_protocol(PROJECT/"config/preprocess_protocol_debug.yaml",dataset="atlas2020_4lep")
    assert p.protocol_id=="higgsml-preprocess-debug"
    assert p.selection["m4l_window_gev"] is None

def test_run_config_accepts_only_data_root_and_resources(tmp_path):
    p=tmp_path/"run.yaml";p.write_text("schema_version: '2.0'\ndata_root: input\nresources: {chunk_size_events: 17}\n")
    cfg=load_preprocess_run_config(p,dataset="atlas2020_4lep")
    assert cfg.chunk_size_events==17
    assert cfg.sample_paths["higgs"].parent==tmp_path/"input/atlas2020_4lep"
    p.write_text("schema_version: '1.0'\nsamples: {}\nresources: {}\n")
    with pytest.raises(InputBindingError):load_preprocess_run_config(p,dataset="atlas2020_4lep")

def test_duplicate_yaml_key_is_rejected(tmp_path):
    p=tmp_path/"run.yaml";p.write_text("schema_version: '2.0'\nschema_version: '2.0'\n")
    with pytest.raises(InputBindingError,match="duplicate"):load_preprocess_run_config(p,dataset="atlas2020_4lep")
