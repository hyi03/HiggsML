import copy
import pytest
import pandas as pd
from src.research.errors import ResearchError, ResearchStateError
from src.research.matrix_element import export_me_inputs, import_me_results, _digest
from src.research.protocol import load_protocol


def fixture():
    p = load_protocol()
    f = pd.DataFrame([dict(event_id="a", event_group_id="g", split="development", lep_pt=[40,30,20,10],
        lep_eta=[.1,.2,.3,.4],lep_phi=[0,1,2,3],lep_e=[50,40,30,20],lep_charge=[1,-1,1,-1],lep_type=[11,11,13,13],pairing=[[0,1],[2,3]])])
    i = export_me_inputs(f,p,dict(name="external-fixture",version="1",configuration_sha256="a"*64),
                         dict(signal="synthetic-s",background="synthetic-b",pdf="synthetic",approximation="software-only"))
    r = {k:copy.deepcopy(i[k]) for k in ("backend","process","units","input_digest","probability_definition")}
    r.update(schema_version="h4l-me-output-v1",adapter_sha256='a'*64,events=[dict(event_id="a",input_digest=i["events"][0]["input_digest"],p_signal=2.,p_background=3.)])
    ref = {k:copy.deepcopy(i[k]) for k in ("backend","process","units","probability_definition")}
    event={"synthetic_independent_reference":1}
    ref.update(status="validated",adapter_sha256='a'*64,evidence_id="synthetic-test-only",checks=[dict(event_input=event,input_digest=_digest(event),adapter_sha256='a'*64,expected=[2.,3.],actual=[2.,3.])])
    return p,i,r,ref


def test_me_bound_reference_import_and_missing_reference():
    p,i,r,ref=fixture()
    assert import_me_results(i,r,ref,p).me_score.iloc[0] == .4
    with pytest.raises(ResearchStateError) as e:
        import_me_results(i,r,None,p)
    assert e.value.status == "blocked_missing_reference"


@pytest.mark.parametrize("mutation", ["row", "unit", "backend", "process", "reference", "negative", "duplicate", "adapter", "check_adapter"])
def test_me_rejects_binding_and_numerical_errors(mutation):
    p,i,r,ref=fixture()
    if mutation=="row":r["events"]=[]
    if mutation=="unit":r["units"]="MeV"
    if mutation=="backend":r["backend"]["version"]="2"
    if mutation=="process":r["process"]["signal"]="other"
    if mutation=="reference":ref["checks"][0]["actual"]=[20.,3.]
    if mutation=="negative":r["events"][0]["p_signal"]=-1.
    if mutation=="duplicate":r["events"]*=2
    if mutation=="adapter":r['adapter_sha256']='b'*64
    if mutation=="check_adapter":ref['checks'][0]['adapter_sha256']='b'*64
    with pytest.raises(ResearchError):import_me_results(i,r,ref,p)


def test_external_adapter_runner_hash_and_contract(tmp_path):
    import hashlib
    from scripts.research_mela import run_adapter
    p,i,r,ref=fixture()
    adapter=tmp_path / "synthetic_adapter.py"
    adapter.write_text("PROBABILITY_DEFINITION = 'kinematic_decay7_at_fixed_m4l_no_mass_pdf'\ndef compute_probabilities(event, backend, process):\n    return {'p_signal':2.,'p_background':3.}\n")
    digest=hashlib.sha256(adapter.read_bytes()).hexdigest()
    output=run_adapter(i,adapter,digest)
    ref['adapter_sha256']=digest
    ref['checks'][0]['adapter_sha256']=digest
    assert import_me_results(i,output,ref,p).me_score.iloc[0]==.4
    with pytest.raises(ResearchError,match="SHA256"):
        run_adapter(i,adapter,"0"*64)
