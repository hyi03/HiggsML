"""Linux/WSL external ME runner with an explicit, hash-bound Python adapter.

The supplied module must define compute_probabilities(event, backend, process)
returning {p_signal, p_background}. It owns the verified MELA API and settings;
this runner does not claim or simulate an installed MELA implementation.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.research.errors import ResearchError
from src.research.protocol import canonical


def run_adapter(inputs, module_path, module_sha256):
    path = Path(module_path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != module_sha256:
        raise ResearchError("external adapter SHA256 mismatch")
    if inputs.get("schema_version") != "h4l-me-input-v1" or inputs.get("units") != "GeV":
        raise ResearchError("external ME input schema/units mismatch")
    if inputs.get("probability_definition") != "kinematic_decay7_at_fixed_m4l_no_mass_pdf":
        raise ResearchError("only kinematic decay probabilities at fixed mass are supported")
    expected = hashlib.sha256(canonical({k:v for k,v in inputs.items() if k != "input_digest"})).hexdigest()
    if inputs.get("input_digest") != expected:
        raise ResearchError("external ME input digest mismatch")
    spec = importlib.util.spec_from_file_location("h4l_verified_external_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "compute_probabilities", None)):
        raise ResearchError("adapter requires compute_probabilities(event, backend, process)")
    if getattr(module, "PROBABILITY_DEFINITION", None) != inputs["probability_definition"]:
        raise ResearchError("adapter must declare the bound kinematic probability definition")
    events = []
    for event in inputs["events"]:
        value = module.compute_probabilities(event, inputs["backend"], inputs["process"])
        if not isinstance(value, dict) or set(value) != {"p_signal", "p_background"}:
            raise ResearchError("adapter probability contract mismatch")
        array = np.array([value["p_signal"], value["p_background"]],float)
        if not np.isfinite(array).all() or (array<0).any() or array.sum()<=0:
            raise ResearchError("adapter returned invalid probabilities")
        events.append(dict(event_id=event["event_id"], input_digest=event["input_digest"],
                           p_signal=float(array[0]),p_background=float(array[1])))
    result = dict(schema_version="h4l-me-output-v1", input_digest=inputs["input_digest"],
                backend=inputs["backend"],process=inputs["process"],units=inputs["units"],events=events,
                probability_definition=inputs["probability_definition"],
                adapter_sha256=module_sha256,scientific_validation="requires_independent_reference_import")
    if callable(getattr(module,"adapter_metadata",None)):
        result["adapter_metadata"]=module.adapter_metadata()
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True)
    parser.add_argument("--adapter",required=True)
    parser.add_argument("--adapter-sha256",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args(argv)
    try:
        result=run_adapter(json.loads(Path(args.input).read_text()),args.adapter,args.adapter_sha256)
        with Path(args.output).open("x",encoding="utf-8") as stream:
            json.dump(result,stream,sort_keys=True,allow_nan=False)
            stream.write("\n")
    except (ResearchError,OSError,ValueError,ImportError) as exc:
        print(str(exc),file=sys.stderr)
        return 3
    return 0


if __name__=="__main__":
    raise SystemExit(main())
