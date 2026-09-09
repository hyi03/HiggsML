"""Optional JHUGenMELA Python adapter for the registered kinematic comparison.

Source API pin: JHUGen/JHUGenMELA commit
10d36ced1d71b5e4e21abb1c9834a02570bf31c0. Python bindings expose Mela,
SimpleParticle_t(id,px,py,pz,E), SimpleParticleCollection_t(list), setProcess,
setInputEvent, resetInputEvent and computeP(useConstant)->float. See the source
evidence note in docs/research; this adapter never calls computePM4l.

The operator installs the pinned MELA build separately in Linux/WSL and sets
H4L_MELA_BUILD_RECEIPT to JSON {source_commit, extension_sha256}. Its exact
content is included in configuration_digest. Receipt source provenance still
requires independent validation; a digest does not prove a claimed build origin.
Run in an isolated working directory: upstream Mela creates Pdfdata symlinks.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path

import numpy as np

from src.domain.angular5 import build_angular5, boost
from src.domain.four_vectors import FourVector
from src.domain.reconstruction import normalize_leptons, reconstruct_candidate
from src.research.errors import ResearchError, ResearchStateError
from src.research.protocol import canonical

SOURCE_COMMIT = "10d36ced1d71b5e4e21abb1c9834a02570bf31c0"
PROBABILITY_DEFINITION = "kinematic_decay7_at_fixed_m4l_no_mass_pdf"
SETTINGS = {"source_commit":SOURCE_COMMIT,"sqrt_s_tev":13.,"higgs_pole_mass_gev":125.,
            "input":"canonical_massless_decay7_rest_frame","useConstant":False,
            "probability_definition":PROBABILITY_DEFINITION,
            "signal":["HSMHiggs","JHUGen","ZZGG"],"background":["bkgZZ","MCFM","ZZQQB"],
            "pdf":"pinned_MELA_defaults_NNPDF30_lo_as_0130_member0"}
PROCESS = {"signal":"HSMHiggs/JHUGen/ZZGG","background":"bkgZZ/MCFM/ZZQQB",
           "pdf":SETTINGS["pdf"],"approximation":"massless_2e2mu_fixed_mass_no_interference_no_mass_pdf"}


def adapter_metadata():
    return {"source_repository":"https://github.com/JHUGen/JHUGenMELA","source_commit":SOURCE_COMMIT,
            "settings":SETTINGS,"process":PROCESS,
            "runtime_build_receipt":json.loads(Path(os.environ["H4L_MELA_BUILD_RECEIPT"]).read_text()),
            "scientific_numerical_validation":"pending_independent_reference",
            "build_origin":"receipt_claim_with_extension_sha256_binding_not_independent_build_attestation"}


def configuration_digest(receipt):
    return hashlib.sha256(canonical({"settings":SETTINGS,"runtime_receipt":receipt})).hexdigest()


def _load_runtime():
    path=os.environ.get("H4L_MELA_BUILD_RECEIPT")
    if not path:
        raise ResearchStateError("H4L_MELA_BUILD_RECEIPT is required",status="mela_runtime_unverified")
    try:
        receipt=json.loads(Path(path).read_text())
        if set(receipt)!={"source_commit","extension_sha256"} or receipt["source_commit"]!=SOURCE_COMMIT:
            raise ResearchError("MELA build receipt source/schema mismatch")
        module=importlib.import_module("Mela")
        if not module.__file__ or hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()!=receipt["extension_sha256"]:
            raise ResearchError("loaded MELA extension differs from build receipt")
        return module,receipt
    except (ImportError,OSError,ValueError) as exc:
        if isinstance(exc,ResearchError):
            raise
        raise ResearchStateError("pinned MELA runtime unavailable",status="dependency_missing") from exc


def canonical_vectors(coordinates):
    """Construct four massless leptons from exactly repository decay7 + m4l.

    Rows are Z1 negative/positive, Z2 negative/positive. Overall azimuth, y4l
    and pt4l are fixed, so additional lab information cannot reach computeP.
    Angles use the repository's signed plane-normal convention, not assumed
    equivalence to upstream MELA angle names.
    """
    names=("m4l","mZ1","mZ2","cos_theta_star","cos_theta_1","cos_theta_2","phi_decay_planes","phi_production_plane")
    values=np.array([coordinates[k] for k in names],float)
    if not np.isfinite(values).all():
        raise ResearchError("nonfinite decay coordinates")
    m,m1,m2,cs,c1,c2,phi,phi1=values
    if not 105<=m<140 or min(m1,m2)<=0 or m1+m2>=m or max(abs(cs),abs(c1),abs(c2))>=1 or max(abs(phi),abs(phi1))>np.pi:
        raise ResearchError("unsupported or degenerate decay coordinate support")
    momentum=np.sqrt((m*m-(m1+m2)**2)*(m*m-(m1-m2)**2))/(2*m)
    n=np.array([np.sqrt(1-cs*cs),0.,cs])
    ex=np.array([cs,0.,-np.sqrt(1-cs*cs)])
    ey=np.array([0.,1.,0.])
    e1=(m*m+m1*m1-m2*m2)/(2*m)
    e2=(m*m+m2*m2-m1*m1)/(2*m)
    d1=-np.sqrt(1-c1*c1)*(np.cos(phi1)*ex+np.sin(phi1)*ey)+c1*n
    d2=np.sqrt(1-c2*c2)*(np.cos(phi1+phi)*ex+np.sin(phi1+phi)*ey)-c2*n
    vectors=[]
    for mass,direction,velocity in ((m1,d1,momentum/e1*n),(m2,d2,-momentum/e2*n)):
        for sign in (1.,-1.):
            # Repository boost(v,beta) transforms into the beta frame; use -v
            # to boost each Z rest-frame daughter into the Higgs rest frame.
            vector=boost(FourVector(mass/2,*(sign*mass/2*direction)),tuple(-velocity))
            vectors.append([vector.px,vector.py,vector.pz,vector.energy])
    return np.array(vectors)


def _event_coordinates(event):
    normalized=normalize_leptons(event,"GeV")
    candidate=reconstruct_candidate(normalized)
    if candidate is None or sorted(abs(int(v)) for v in normalized.flavour)!=[11,11,13,13]:
        raise ResearchError("MELA adapter requires valid 2e2mu pairing")
    if event.get("pairing") != [list(candidate.pairing.z1_indices),list(candidate.pairing.z2_indices)]:
        raise ResearchError("MELA adapter pairing differs from export")
    coordinates=build_angular5(candidate)
    coordinates.update(m4l=candidate.four_lepton.mass,mZ1=candidate.z1.mass,mZ2=candidate.z2.mass)
    first=abs(candidate.leptons[candidate.pairing.z1_indices[0]].flavour)
    second=abs(candidate.leptons[candidate.pairing.z2_indices[0]].flavour)
    return coordinates,[first,-first,second,-second]


def compute_probabilities(event, backend, process):
    if backend.get("name")!="JHUGenMELA" or backend.get("version")!=SOURCE_COMMIT or process!=PROCESS:
        raise ResearchError("unsupported pinned MELA backend/process/PDF/approximation")
    coordinates,ids=_event_coordinates(event)
    vectors=canonical_vectors(coordinates)
    module,receipt=_load_runtime()
    if backend.get("configuration_sha256")!=configuration_digest(receipt):
        raise ResearchError("MELA runtime/settings configuration digest mismatch")
    try:
        mela=module.Mela(SETTINGS["sqrt_s_tev"],SETTINGS["higgs_pole_mass_gev"],module.VerbosityLevel.SILENT)
        mela.setCandidateDecayMode(module.CandidateDecayMode.CandidateDecay_ZZ)
        particles=module.SimpleParticleCollection_t([module.SimpleParticle_t(int(pid),*map(float,p4)) for pid,p4 in zip(ids,vectors)])
        mela.setInputEvent(particles,None,None,False)
        try:
            mela.setProcess(module.Process.HSMHiggs,module.MatrixElement.JHUGen,module.Production.ZZGG)
            signal=float(mela.computeP(False))
            mela.setProcess(module.Process.bkgZZ,module.MatrixElement.MCFM,module.Production.ZZQQB)
            background=float(mela.computeP(False))
        finally:
            mela.resetInputEvent()
    except (AttributeError,TypeError) as exc:
        raise ResearchStateError("installed MELA Python API differs from source pin",status="dependency_version_mismatch") from exc
    if not np.isfinite([signal,background]).all() or min(signal,background)<0 or signal+background<=0:
        raise ResearchError("MELA returned invalid probabilities")
    return {"p_signal":signal,"p_background":background}
