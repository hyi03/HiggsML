from types import SimpleNamespace
import numpy as np
import pytest

from scripts import mela_kinematic_adapter as adapter
from src.domain.reconstruction import normalize_leptons,reconstruct_candidate
from src.domain.angular5 import build_angular5
from src.research.errors import ResearchError, ResearchStateError


def event_from_vectors(p4):
    pt=np.linalg.norm(p4[:,:2],axis=1)
    event=dict(lep_pt=pt.tolist(),lep_eta=np.arcsinh(p4[:,2]/pt).tolist(),lep_phi=np.arctan2(p4[:,1],p4[:,0]).tolist(),
               lep_e=p4[:,3].tolist(),lep_charge=[-1,1,-1,1],lep_type=[11,11,13,13])
    normal=normalize_leptons(event,"GeV")
    candidate=reconstruct_candidate(normal)
    result={"lep_pt":normal.pt.tolist(),"lep_eta":normal.eta.tolist(),"lep_phi":normal.phi.tolist(),"lep_e":normal.energy.tolist(),
            "lep_charge":normal.charge.tolist(),"lep_type":normal.flavour.tolist(),"pairing":[list(candidate.pairing.z1_indices),list(candidate.pairing.z2_indices)]}
    return result,candidate


def coordinates():
    return dict(m4l=125.,mZ1=80.,mZ2=25.,cos_theta_star=.3,cos_theta_1=-.4,cos_theta_2=.6,
                phi_decay_planes=1.2,phi_production_plane=-.8)


def test_massless_canonical_decay_coordinate_roundtrip_and_zero_lab_momentum():
    rng=np.random.default_rng(2)
    for i in range(20):
        c=coordinates()
        for key in ("cos_theta_star","cos_theta_1","cos_theta_2"):
            c[key]=float(rng.uniform(-.9,.9))
        for key in ("phi_decay_planes","phi_production_plane"):
            c[key]=float(rng.uniform(-3.,3.))
        vectors=adapter.canonical_vectors(c)
        assert np.allclose(vectors.sum(axis=0),[0,0,0,125.],atol=1e-11)
        assert np.allclose(vectors[:,3]**2-(vectors[:,:3]**2).sum(axis=1),0.,atol=1e-10)
        _,candidate=event_from_vectors(vectors)
        rebuilt=build_angular5(candidate)
        for key,value in rebuilt.items():
            assert value==pytest.approx(c[key],abs=1e-12)
        assert candidate.z1.mass==pytest.approx(c["mZ1"])
        assert candidate.z2.mass==pytest.approx(c["mZ2"])


def test_optional_mela_calls_source_bound_api_with_canonical_rest_inputs(monkeypatch):
    event,_=event_from_vectors(adapter.canonical_vectors(coordinates()))
    calls=[]
    class Mela:
        def __init__(self,*args):calls.append(("init",args))
        def setCandidateDecayMode(self,arg):calls.append(("decay",arg))
        def setInputEvent(self,particles,associated,mothers,isgen):
            calls.append(("inputs",particles,associated,mothers,isgen))
        def setProcess(self,*args):calls.append(("process",args))
        def computeP(self,constant):calls.append(("compute",constant));return 2. if len([x for x in calls if x[0]=="compute"])==1 else 3.
        def resetInputEvent(self):calls.append(("reset",))
    module=SimpleNamespace(Mela=Mela,VerbosityLevel=SimpleNamespace(SILENT=0),
        CandidateDecayMode=SimpleNamespace(CandidateDecay_ZZ="ZZ"),SimpleParticleCollection_t=list,
        SimpleParticle_t=lambda pid,*p4:(pid,*p4),Process=SimpleNamespace(HSMHiggs="HSMHiggs",bkgZZ="bkgZZ"),
        MatrixElement=SimpleNamespace(JHUGen="JHUGen",MCFM="MCFM"),Production=SimpleNamespace(ZZGG="ZZGG",ZZQQB="ZZQQB"))
    receipt={"source_commit":adapter.SOURCE_COMMIT,"extension_sha256":"synthetic"}
    monkeypatch.setattr(adapter,"_load_runtime",lambda:(module,receipt))
    backend=dict(name="JHUGenMELA",version=adapter.SOURCE_COMMIT,configuration_sha256=adapter.configuration_digest(receipt))
    assert adapter.compute_probabilities(event,backend,adapter.PROCESS)=={"p_signal":2.,"p_background":3.}
    particles=next(c[1] for c in calls if c[0]=="inputs")
    assert np.allclose(np.array(particles)[:,1:].sum(axis=0),[0,0,0,125.],atol=1e-10)
    assert all(c[1] is False for c in calls if c[0]=="compute")
    assert calls[-1]==("reset",)
    with pytest.raises(ResearchError,match="unsupported pinned"):
        adapter.compute_probabilities(event,backend,{**adapter.PROCESS,"background":"different"})


def test_mela_missing_runtime_evidence_and_degenerate_coordinates_refused(monkeypatch):
    monkeypatch.delenv("H4L_MELA_BUILD_RECEIPT",raising=False)
    with pytest.raises(ResearchStateError,match="BUILD_RECEIPT"):
        adapter._load_runtime()
    with pytest.raises(ResearchError,match="degenerate"):
        adapter.canonical_vectors({**coordinates(),"cos_theta_star":1.})
