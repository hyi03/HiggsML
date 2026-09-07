from __future__ import annotations

from dataclasses import replace
import json
from math import cosh, pi
from pathlib import Path

import awkward as ak
import pandas as pd
import pytest
import uproot

from src.artifacts.manifest import sha256_file
from src.config import PreprocessRunConfig, load_preprocess_protocol
from src.config import InputBindingError
from src.preprocessing import pipeline as pipeline_module
from src.preprocessing.pipeline import execute_preprocess, prepare_table
from src.preprocessing.root_reader import iter_events


PROJECT = Path(__file__).resolve().parents[2]


def _canonical_events(dsid: int, *, mev: bool) -> dict:
    pt = [40.0, 35.0, 30.0, 25.0]
    eta = [0.2, -0.2, 0.4, -0.4]
    scale = 1000.0 if mev else 1.0
    event = {
        "runNumber": [284500, 284500],
        "eventNumber": [1001, 1002],
        "channelNumber": [dsid, dsid],
        "lep_n": [4, 4],
        "lep_pt": ak.Array([[p * scale for p in pt]] * 2),
        "lep_eta": ak.Array([eta] * 2),
        "lep_phi": ak.Array([[0.0, pi, 1.1, 1.1 + pi]] * 2),
        "lep_e": ak.Array([[p * cosh(e) * scale for p, e in zip(pt, eta)]] * 2),
        "lep_charge": ak.Array([[-1, 1, -1, 1]] * 2),
        "lep_type": ak.Array([[11, 11, 13, 13]] * 2),
        "trigE": [True, True],
        "trigM": [False, False],
        "lep_isTrigMatched": ak.Array([[True, False, False, False]] * 2),
        "lep_isTightID": ak.Array([[True] * 4] * 2),
        "lep_track_iso": ak.Array([[1.0 * scale] * 4] * 2),
        "lep_calo_iso": ak.Array([[1.0 * scale] * 4] * 2),
        "lep_d0sig": ak.Array([[1.0] * 4] * 2),
        "lep_z0": ak.Array([[0.1] * 4] * 2),
        "mcWeight": [1.0, -0.5],
    }
    return event


def _write_inputs(tmp_path: Path, dataset="atlas2020_4lep"):
    protocol=load_preprocess_protocol(PROJECT/"config/preprocess_protocol_mass_window.yaml",dataset=dataset)
    directory=tmp_path/dataset;directory.mkdir()
    paths={}
    for role,sample in protocol.samples.items():
        events=_canonical_events(sample.dsid,mev=sample.momentum_unit=="MeV")
        events.update(xsec=[28.3]*2,kfac=[1.717]*2,filteff=[0.000124]*2,sum_of_weights=[45231012.0]*2)
        physical={branch:events[name] for name,branch in sample.branches.items()}
        path=directory/protocol.dataset.samples[role]["filename"]
        with uproot.recreate(path) as root:root[sample.tree_name]=physical
        paths[role]=path
    (directory/"dataset_receipt.json").write_text(json.dumps({"status":"complete","dataset_name":dataset,
        "definition_sha256":protocol.dataset.snapshot()["definition_sha256"],
        "schema_version":"higgsml.download-receipt.v1","mc_only":True,
        "release":protocol.dataset.snapshot()["release"],"collection":protocol.dataset.snapshot()["collection"],
        "members":[dict(m,actual_size_bytes=m["size_bytes"],actual_sha256=m["sha256"]) for m in protocol.dataset.samples.values()]}),encoding="utf-8")
    return paths["higgs"],paths["zz"]


def _bound_synthetic_protocol(higgs,zz,dataset="atlas2020_4lep"):
    p=load_preprocess_protocol(PROJECT/"config/preprocess_protocol_mass_window.yaml",dataset=dataset)
    return replace(p,samples={role:replace(p.samples[role],sha256=sha256_file(path),expected_entry_count=2)
        for role,path in (("higgs",higgs),("zz",zz))})


@pytest.mark.parametrize("dataset",["atlas2020_4lep","atlas2025_exactly4lep"])
def test_micro_root_pipeline_is_chunk_independent_and_mc_only(tmp_path,dataset):
    h,z=_write_inputs(tmp_path,dataset);p=_bound_synthetic_protocol(h,z,dataset)
    one,cuts,summaries,_=prepare_table(p,PreprocessRunConfig({"higgs":h,"zz":z},1,b"fixture"))
    many,*_=prepare_table(p,PreprocessRunConfig({"higgs":h,"zz":z},100,b"fixture"))
    pd.testing.assert_frame_equal(one,many)
    assert len(one)==4 and set(one.label)=={0,1}
    assert len(cuts)==2 and all(x["selected_count"]==2 for x in summaries.values())
    assert one.groupby("source_sample").train_weight.mean().tolist()==pytest.approx([1,1])
    assert int((one.physical_weight<0).sum())==2
    assert not {"mcWeight","xsec","kfac","filteff","sum_of_weights"}&set(one.columns)


@pytest.mark.parametrize("dataset",["atlas2020_4lep","atlas2025_exactly4lep"])
def test_success_publication_is_deterministic_and_manifest_complete(tmp_path,monkeypatch,dataset):
    h,z=_write_inputs(tmp_path,dataset);protocol=_bound_synthetic_protocol(h,z,dataset)
    monkeypatch.setattr(pipeline_module,"load_preprocess_protocol",lambda *a,**k:protocol)
    config=tmp_path/"run.yaml"
    config.write_text("schema_version: '2.0'\ndata_root: .\nresources: {chunk_size_events: 1}\n")
    runs=tmp_path/"runs"
    for name in ("first","second"):
        execute_preprocess(dataset=dataset,protocol_path=PROJECT/"config/preprocess_protocol_mass_window.yaml",
            run_config_path=config,run_dir=runs/dataset/name,allowed_root=runs)
    a,b=runs/dataset/"first",runs/dataset/"second"
    for partition in ("development","test"):
        relative=f"processed/{partition}_events.csv.gz"
        assert (a/relative).read_bytes()==(b/relative).read_bytes()
    manifest=json.loads((a/"artifacts/manifest.json").read_bytes())
    assert manifest["dataset_binding"]==protocol.dataset.snapshot()
    assert len(manifest["outputs"])==5
    assert manifest["counts"]["totals"]["selected_count"]==4
    assert manifest["performance"]["peak_memory_bytes"]>0


@pytest.mark.parametrize("dataset",["atlas2020_4lep","atlas2025_exactly4lep"])
@pytest.mark.parametrize("mutation",["missing","source_entry","count","dsid"])
def test_root_schema_rejections_are_fail_closed(tmp_path,dataset,mutation):
    h,z=_write_inputs(tmp_path,dataset);p=_bound_synthetic_protocol(h,z,dataset);sample=p.samples["higgs"]
    events=_canonical_events(sample.dsid,mev=sample.momentum_unit=="MeV")
    events.update(xsec=[1.]*2,kfac=[1.]*2,filteff=[1.]*2,sum_of_weights=[10.]*2)
    physical={branch:events[name] for name,branch in sample.branches.items()}
    if mutation=="missing":physical.pop("lep_phi")
    if mutation=="source_entry":physical["source_entry"]=[0,1]
    if mutation=="dsid":physical["channelNumber"]=[999,999]
    with uproot.recreate(h) as root:root[sample.tree_name]=physical
    p=replace(p,samples={**p.samples,"higgs":replace(sample,sha256=sha256_file(h),expected_entry_count=3 if mutation=="count" else 2)})
    with pytest.raises(InputBindingError):prepare_table(p,PreprocessRunConfig({"higgs":h,"zz":z},1,b"fixture"))


def test_root_reader_ignores_unmapped_branches_and_releases_handle(tmp_path):
    h,z=_write_inputs(tmp_path);p=_bound_synthetic_protocol(h,z)
    assert len(list(iter_events(h,p.samples["higgs"],1)))==2
    h.unlink();assert not h.exists()


def test_hash_mismatch_fails_closed(tmp_path):
    h,z=_write_inputs(tmp_path);p=_bound_synthetic_protocol(h,z)
    h.write_bytes(h.read_bytes()+b"tampered")
    with pytest.raises(InputBindingError,match="SHA-256"):
        prepare_table(p,PreprocessRunConfig({"higgs":h,"zz":z},1,b"fixture"))


def test_synthetic_equivalent_profile_units_produce_same_kinematics(tmp_path):
    tables = []
    for dataset in ("atlas2020_4lep", "atlas2025_exactly4lep"):
        h, z = _write_inputs(tmp_path, dataset)
        protocol = _bound_synthetic_protocol(h, z, dataset)
        frame, *_ = prepare_table(protocol, PreprocessRunConfig({"higgs": h, "zz": z}, 1, b"fixture"))
        tables.append(frame.loc[:, list(protocol.output_columns[:20])])
    # This proves conversion of constructed equivalent inputs, not real release equivalence.
    pd.testing.assert_frame_equal(tables[0], tables[1], rtol=1e-12, atol=1e-12)
