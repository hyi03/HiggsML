from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pandas as pd

from src.artifacts.manifest import sha256_file, write_json
from src.preprocessing.outputs import canonical_csv_bytes
from src.training.config import INPUT_COLUMNS
from src.training.dataset import FEATURE_COLUMNS
from src.training.folds import fold_index_for_identity
from tests.training_fixtures import synthetic_development_frame


def development_with_test_rows() -> pd.DataFrame:
    from src.domain.splitting import event_split
    base = synthetic_development_frame()
    copies = []
    for fold in range(5):
        current = base.copy(deep=True)
        for index, row in current.iterrows():
            event = 10000 + fold * 10000 + index * 30
            while event_split(event, int(row.channelNumber)) == "test" or fold_index_for_identity(f"{row.channelNumber}:{event}") != fold:
                event += 1
            current.loc[index, "eventNumber"] = event
            current.loc[index, "event_group_id"] = f"{row.channelNumber}:{event}"
            current.loc[index, "source_entry"] = fold * len(base) + index
            current.loc[index, "split"] = event_split(event, int(row.channelNumber))
        copies.append(current)
    development = pd.concat(copies, ignore_index=True)
    for index, feature in enumerate(FEATURE_COLUMNS):
        development[feature] = development["label"].astype("float64") * 10.0 + index / 100.0
    held_out = pd.concat([development.loc[development.label == label].iloc[:3] for label in (0, 1)],ignore_index=True).copy()
    for index, row in held_out.iterrows():
        event = 100000 + index * 100
        while event_split(event, int(row.channelNumber)) != "test":
            event += 1
        held_out.loc[index, "eventNumber"] = event
        held_out.loc[index, "event_group_id"] = f"{row.channelNumber}:{event}"
        held_out.loc[index, "source_entry"] = 1000 + index
        held_out.loc[index, "split"] = "test"
    return pd.concat([development, held_out], ignore_index=True)[list(INPUT_COLUMNS)]


def write_synthetic_preprocess_run(allowed_root: Path, *, poison_test_feature: bool = False,
                                   dataset: str = "atlas2020_4lep") -> tuple[Path, pd.DataFrame]:
    from src.dataset_binding import dataset_context
    from src.config import load_preprocess_protocol
    import yaml
    run = allowed_root / "preprocess-synthetic"
    (run / "processed").mkdir(parents=True)
    (run / "artifacts").mkdir()
    frame = development_with_test_rows()
    if dataset == "atlas2025_exactly4lep":
        from src.domain.splitting import event_split
        frame["source_sample"] = frame["source_sample"].replace({"zz_363490":"zz_700600"})
        frame["channelNumber"] = frame["channelNumber"].replace({363490:700600})
        for index,row in frame.iterrows():
            event=int(row.eventNumber)
            while event_split(event,int(row.channelNumber)) != row.split:
                event+=1
            frame.loc[index,"eventNumber"]=event
            frame.loc[index,"event_group_id"]=f"{row.channelNumber}:{event}"
        frame["source_file_id"] = [f"{dataset}:mc_{dsid}" for dsid in frame.channelNumber]
    context = dataset_context(dataset)
    protocol = load_preprocess_protocol(Path(__file__).parents[1]/"config/preprocess_protocol_v2.yaml", dataset=dataset)
    config = {"dataset_binding":context.snapshot(), "protocol_sha256":hashlib.sha256(protocol.payload).hexdigest(),
              "run_config_sha256":"2"*64,"protocol":protocol.raw,"run_config":{}}
    (run/"config.yaml").write_text(yaml.safe_dump(config),encoding="utf-8")
    write_json(run/"artifacts/cutflow.json",{"schema_version":"fixture"})
    write_json(run/"artifacts/mc_summary.json",{"schema_version":"fixture"})
    outputs=[]
    for partition,mask in (("development",frame.split!="test"),("test",frame.split=="test")):
        selected=frame.loc[mask]
        payload=canonical_csv_bytes(selected,INPUT_COLUMNS,
            integer_columns={"label","source_entry","runNumber","eventNumber","channelNumber"},
            string_columns={"split","source_sample","source_file_id","event_group_id"})
        if partition=="test" and poison_test_feature:
            lines=payload.splitlines(keepends=True)
            tokens=lines[1].rstrip(b"\n").split(b",");tokens[0]=b"test-feature-must-not-be-decoded"
            lines[1]=b",".join(tokens)+b"\n";payload=b"".join(lines)
        relative=f"processed/{partition}_events.csv.gz"
        path=run/relative;path.write_bytes(gzip.compress(payload,compresslevel=9,mtime=0))
        outputs.append({"path":relative,"sha256":sha256_file(path),"size_bytes":path.stat().st_size,
                        "row_count":len(selected),"canonical_content_sha256":hashlib.sha256(payload).hexdigest()})
    for relative in ("config.yaml","artifacts/cutflow.json","artifacts/mc_summary.json"):
        path=run/relative
        outputs.append({"path":relative,"sha256":sha256_file(path),"size_bytes":path.stat().st_size,
                        "row_count":None,"canonical_content_sha256":None})
    manifest={"schema_version":"2.0","dataset_binding":context.snapshot(),"status":"success","run_type":"preprocess",
        "protocol_id":"higgsml-preprocess-v2","started_at_utc":"fixture","completed_at_utc":"fixture",
        "inputs":list(context.samples.values()),"configuration":{"protocol_path":"config/preprocess_protocol_v2.yaml",
            "protocol_sha256":config["protocol_sha256"],"run_config_path":"fixture.yaml","run_config_sha256":"2"*64,
            "chunk_size_events":64,"full_read":True},"outputs":outputs,
        "schema":{"ordered_columns":list(INPUT_COLUMNS),"dtypes":{n:str(frame[n].dtype) for n in INPUT_COLUMNS}},
        "counts":{"totals":{"selected_count":len(frame),"split_counts":{n:int((frame.split==n).sum()) for n in ("train","validation","test")}}},
        "software":{},"platform":{},"determinism":{},"performance":{}}
    write_json(run/"artifacts/manifest.json",manifest)
    return run,frame
