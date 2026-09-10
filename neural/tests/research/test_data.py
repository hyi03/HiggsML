import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.research.data import (assign_roles, audit_g0, grouped_statistics, load_research_data,
                               role_for_group, write_research_data)
from src.research.errors import ResearchError
from src.research.protocol import load_protocol
from src.research.representations import ENGINEERED19, ordered_group_subsets, representation_features


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def frame_for_roles():
    p = load_protocol()
    rows = []
    for i in range(500):
        row = dict.fromkeys(ENGINEERED19, 1.)
        row.update(event_id=f"s:{i}", source_row_id=f"s:{i}", event_group_id=f"synthetic:{i}",
                   split="development", dataset="atlas2020_4lep", label=i % 2,
                   physical_weight=1., m4l=125., y4l=0.)
        rows.append(row)
    result = assign_roles(pd.DataFrame(rows), p)
    result.attrs["source_kind"] = "synthetic"
    return result


def test_representations_and_empty_shapley_baseline():
    assert [len(representation_features(n)) for n in ("mass-only", "decay7", "lab-extension", "engineered19")] == [1, 8, 10, 20]
    assert representation_features("engineered19", []) == ("m4l",)
    assert representation_features("engineered19", ["D", "A"]) == representation_features("engineered19", ["A", "D"])
    assert len(ordered_group_subsets()) == 15
    with pytest.raises(ResearchError):
        representation_features("engineered19", ["physical_weight"])


def test_seed42_batch_config_registers_all_fifteen_combinations_once():
    config = json.loads((PROJECT_ROOT / "config/research_feature_combinations_seed42.json").read_text(encoding="utf-8"))
    expected = ["".join(groups) for groups in ordered_group_subsets()]
    assert config["default_seed"] == 42
    assert config["feature_combinations"] == expected
    assert len(config["feature_combinations"]) == len(set(config["feature_combinations"])) == 15
    assert config["empty_baseline_candidate"] == "M0c"
    assert config["combination_candidate"] == "M3"


def test_roles_stable_and_variance_uses_event_groups():
    frame = frame_for_roles()
    p = load_protocol()
    shuffled = assign_roles(frame.sample(frac=1), p)
    assert shuffled.set_index("event_id").role.to_dict() == frame.set_index("event_id").role.to_dict()
    assert np.allclose(frame.yield_weight, frame.physical_weight / frame.sampling_probability)
    duplicate = pd.DataFrame({"event_group_id": ["a", "a", "b"], "yield_weight": [3., -1., 4.]})
    assert grouped_statistics(duplicate)["sumw2"] == 20


def test_assessment_poison_never_decoded_before_freeze(tmp_path):
    p, frame = load_protocol(), frame_for_roles()
    path = tmp_path / "events.jsonl"
    write_research_data(frame, path, p)
    lines = path.read_text().splitlines()
    for i in range(1, len(lines)):
        identity, payload = lines[i].split("\t", 1)
        if json.loads(identity)["role"] == "assessment":
            lines[i] = identity + "\tNOT JSON POISON"
    path.write_text("\n".join(lines) + "\n")
    result = load_research_data(path, "atlas2020_4lep", p)
    assert "assessment" not in set(result.role)
    with pytest.raises(ResearchError, match="frozen"):
        load_research_data(path, "atlas2020_4lep", p, allow_assessment=True)


def test_invalid_identity_rejected_even_for_unopened_assessment(tmp_path):
    p, frame = load_protocol(), frame_for_roles()
    path = tmp_path / "events.jsonl"
    write_research_data(frame, path, p)
    lines = path.read_text().splitlines()
    identity, payload = lines[1].split("\t", 1)
    value = json.loads(identity)
    value["split"] = "test"
    lines[1] = json.dumps(value) + "\tPOISON"
    path.write_text("\n".join(lines))
    with pytest.raises(ResearchError, match="non-development"):
        load_research_data(path, "atlas2020_4lep", p)


def test_g0_never_uses_assessment_statistics():
    p, frame = load_protocol(), frame_for_roles()
    expected = audit_g0(frame, p)
    frame.loc[frame.role == "assessment", "yield_weight"] = np.nan
    assert audit_g0(frame, p) == expected


def test_forged_assessment_role_refused_before_payload(tmp_path):
    p, frame = load_protocol(), frame_for_roles()
    path = tmp_path / "events.jsonl"
    write_research_data(frame,path,p)
    lines=path.read_text().splitlines()
    for i in range(1,len(lines)):
        identity,payload=lines[i].split("\t",1)
        value=json.loads(identity)
        if value["role"]=="assessment":
            value["role"]="train"
            lines[i]=json.dumps(value)+"\tPOISON MUST NOT DECODE"
            break
    path.write_text("\n".join(lines))
    with pytest.raises(ResearchError,match="before payload access"):
        load_research_data(path,"atlas2020_4lep",p)


def test_protocol_roundtrip_digest_and_dataset_rejection(tmp_path):
    p = load_protocol()
    path = tmp_path / "p.json"
    path.write_text(json.dumps(p.to_dict()))
    assert load_protocol(path).digest == p.digest
    with pytest.raises(ResearchError):
        load_protocol(path, "atlas2025_exactly4lep")


@pytest.mark.parametrize("section,key,value",[
    ("training","learning_rate",float("nan")),("training","batch_size",True),
    ("training","max_epochs",201),("calibration","mass_edges",[105,120,119,140]),
    ("calibration","score_edges",[0,.5,.5,1]),("calibration","min_cancellation_ratio",0),
    ("calibration","tails","silently_extend"),("g0","min_neff_signed",-1),
    ("templates","min_neff_signed",10),("inference","mu_bounds",[0,1]),
    ("inference","toy_count",2),("inference","inner_toys",0),
    ("inference","auxiliary_generation","unknown"),("matrix_element","reference_rtol",1),
    ("stress","amplitude",.2),])
def test_protocol_rejects_invalid_numerics_algorithms_and_cross_section_drift(tmp_path,section,key,value):
    p=load_protocol().to_dict()
    p[section][key]=value
    path=tmp_path/"bad.json"
    path.write_text(json.dumps(p))
    with pytest.raises(ResearchError):load_protocol(path)


def test_duplicate_protocol_key_rejected(tmp_path):
    path=tmp_path/"bad.json"
    path.write_text('{"dataset":"atlas2020_4lep","dataset":"atlas2020_4lep"}')
    with pytest.raises(ResearchError,match="duplicate"):
        load_protocol(path)


def test_mc_source_rejected_before_uproot_open(tmp_path, monkeypatch):
    from src.research.data import export_research_data
    import uproot
    monkeypatch.setattr(uproot, "open", lambda *a, **k: pytest.fail("source opened"))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "h4l-root-input-v1", "dataset": "atlas2020_4lep", "mc_only": False, "files": {}}))
    with pytest.raises(ResearchError, match="controlled MC"):
        export_research_data(manifest, tmp_path / "missing.yaml", load_protocol())


def test_root_export_selects_identity_before_payload(tmp_path, monkeypatch):
    import copy
    import math
    import awkward as ak
    import uproot
    import src.dataset_binding as binding
    from src.domain.splitting import event_split
    from src.research.data import export_research_data
    original = binding.dataset_context("atlas2020_4lep")
    members = copy.deepcopy(original.samples)
    files = {}
    rootdir = tmp_path / "atlas2020_4lep"
    rootdir.mkdir()
    numbers = {}
    for role, member in members.items():
        source = rootdir / member["filename"]
        source.write_bytes(b"synthetic ROOT fixture")
        member["size_bytes"] = source.stat().st_size
        member["entry_count"] = 2
        files[role] = dict(path=str(source), sha256=member["sha256"], verified_size_bytes=source.stat().st_size, verified_mtime_ns=source.stat().st_mtime_ns)
        numbers[role] = [next(i for i in range(100) if event_split(i, member["dsid"]) != "test"),
                         next(i for i in range(100) if event_split(i, member["dsid"]) == "test")]
    class Context:
        samples = members
        profile = original.profile
        profile_payload = original.profile_payload
        science = original.science
        def snapshot(self): return {"synthetic_root_fixture": True}
    monkeypatch.setattr(binding, "dataset_context", lambda name: Context())
    profile = tmp_path / "profile.yaml"
    profile.write_bytes(original.profile_payload)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(dict(schema_version="h4l-root-input-v1",dataset="atlas2020_4lep",mc_only=True,files=files)))
    payload_calls = []
    class Tree:
        num_entries = 2
        def __init__(self, role): self.role = role
        def keys(self): return original.profile["branches"].values()
        def arrays(self, branches, **kwargs):
            channel = members[self.role]["dsid"]
            if kwargs["library"] == "np":
                assert branches == ["eventNumber", "channelNumber"]
                return {"eventNumber":np.array(numbers[self.role]),"channelNumber":np.array([channel,channel])}
            assert kwargs["entry_start"] == 0 and kwargs["entry_stop"] == 1
            payload_calls.append(self.role)
            pt, eta = [38.,33.,27.,22.], [.2,-.2,.4,-.4]
            event = dict(lep_n=4,lep_pt=[v*1000 for v in pt],lep_eta=eta,lep_phi=[0.,math.pi,1.1,1.1+math.pi],
                lep_e=[a*math.cosh(b)*1000 for a,b in zip(pt,eta)],lep_charge=[-1,1,-1,1],lep_type=[11,11,13,13],
                trigE=True,trigM=False,lep_isTrigMatched=[True,False,False,False],lep_isTightID=[True]*4,
                lep_track_iso=[1000.]*4,lep_calo_iso=[1000.]*4,lep_d0sig=[1.]*4,lep_z0=[.1]*4,
                runNumber=1,eventNumber=numbers[self.role][0],channelNumber=channel,mcWeight=1.)
            return ak.Array({original.profile["branches"][k]:[v] for k,v in event.items()})
    class Root:
        def __init__(self, source): self.role = next(r for r,m in members.items() if m["filename"] == source.name)
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def __getitem__(self,key): return Tree(self.role)
    monkeypatch.setattr(uproot,"open",Root)
    frame = export_research_data(manifest,profile,load_protocol())
    assert len(frame) == 2 and payload_calls == ["higgs", "zz"]
    assert set(frame.split) == {"development"}
    assert all(len(v)==4 for v in frame.lep_pt)
