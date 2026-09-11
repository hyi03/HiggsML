"""MC research export with identity-first reads and role-aware payload access."""
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .errors import ResearchError, ResearchStateError
from .protocol import canonical, protocol_dict
from .representations import ENGINEERED19

ROLES = ("train", "validation", "calibration", "template", "assessment")
IDENTITY = ("event_id", "source_row_id", "event_group_id", "split", "dataset", "label", "role")


def current_rss_bytes():
    """Return current resident bytes using only the standard library."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        "peak", "working", "qpp", "qp", "qpnp", "qnp",
                        "page", "peakpage", "private",
                    )
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            # ctypes function signatures are process-global and another caller
            # may have registered its private structure pointer type.
            get_memory_info.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
            get_memory_info.restype = wintypes.BOOL
            if get_memory_info(
                wintypes.HANDLE(-1), ctypes.byref(counters), counters.cb
            ):
                return int(counters.working)
        except (AttributeError, OSError, ctypes.ArgumentError):
            return None
    try:
        resident_pages = int(Path("/proc/self/statm").read_text().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, IndexError, OSError, ValueError):
        return None


class PrepareProgressReporter:
    """Emit low-frequency prepare throughput without changing event processing."""

    def __init__(self, metrics, *, interval_seconds=10.0, clock=None,
                 rss_reader=None, stream=None):
        self.metrics = metrics
        self.interval_seconds = interval_seconds
        self.clock = clock or time.perf_counter
        self.rss_reader = rss_reader or current_rss_bytes
        self.stream = stream or sys.stderr
        self.started = self.clock()
        self.next_report = self.started + interval_seconds

    def sample_rss(self):
        rss = self.rss_reader()
        if rss is not None:
            self.metrics["peak_rss_bytes"] = max(
                int(rss), self.metrics.get("peak_rss_bytes", 0)
            )

    def update(self):
        now = self.clock()
        if now < self.next_report:
            return
        self.sample_rss()
        elapsed = max(now - self.started, 1e-12)
        entries = self.metrics.get("entries_processed", 0)
        rss_text = (
            f"{self.metrics['peak_rss_bytes'] / 1024**2:.1f} MiB"
            if self.metrics.get("peak_rss_bytes") is not None else "unavailable"
        )
        requests = self.metrics.get('payload_requests', 0)
        average_span = (self.metrics.get('span_entries_total', 0) / requests
                        if requests else 0.0)
        print(
            "[h4l prepare] "
            f"entries={entries} selected={self.metrics.get('selected_entries', 0)} "
            f"spans={self.metrics.get('payload_requests', 0)} "
            f"avg_span={average_span:.1f} "
            f"rate={entries / elapsed:.1f} entries/s rss={rss_text} "
            f"payload={self.metrics.get('payload_seconds', 0.):.1f}s "
            f"payload_cpu={self.metrics.get('payload_cpu_seconds', 0.):.1f}s "
            f"convert={self.metrics.get('conversion_seconds', 0.):.1f}s "
            f"select={self.metrics.get('selection_seconds', 0.):.1f}s "
            f"features={self.metrics.get('feature_seconds', 0.):.1f}s",
            file=self.stream,
            flush=True,
        )
        while self.next_report <= now:
            self.next_report += self.interval_seconds


def limit_selected_entries(mask, limit):
    """Keep at most the first limit eligible entries in one source file."""
    result = np.asarray(mask, dtype=bool).copy()
    if limit is None:
        return result
    if type(limit) is not int or limit < 1:
        raise ResearchError("diagnostic entry limit must be a positive integer")
    selected = np.flatnonzero(result)
    result[selected[limit:]] = False
    return result


def finalize_prepare_metrics(metrics):
    """Add derived throughput and an evidence-bounded bottleneck diagnosis."""
    requests = metrics.get("payload_requests", 0)
    entries = metrics.get("span_entries_total", metrics.get("payload_entries", 0))
    metrics["average_span_length"] = entries / requests if requests else None
    wall = metrics.get("wall_seconds", 0.)
    processed = metrics.get("entries_processed", 0)
    metrics["throughput_entries_per_second"] = processed / wall if wall > 0 else None
    phases = {
        "identity": metrics.get("identity_seconds", 0.),
        "payload": metrics.get("payload_seconds", 0.),
        "conversion": metrics.get("conversion_seconds", 0.),
        "selection": metrics.get("selection_seconds", 0.),
        "features": metrics.get("feature_seconds", 0.),
        "dataframe": metrics.get("dataframe_seconds", 0.),
        "role_assignment": metrics.get("role_assignment_seconds", 0.),
        "g0": metrics.get("g0_seconds", 0.),
        "p0": metrics.get("p0_seconds", 0.),
        "write_and_digest": metrics.get("write_and_digest_seconds", 0.),
        "artifact_registration": metrics.get("artifact_registration_seconds", 0.),
        "artifact_metadata": metrics.get("artifact_metadata_seconds", 0.),
        "publication": metrics.get("publication_seconds", 0.),
    }
    accounted = sum(phases.values())
    dominant = max(phases, key=phases.get)
    average = metrics["average_span_length"]
    if dominant == "payload" and requests >= 100 and average is not None and average <= 8:
        classification = "fragmented_root_io"
    else:
        classification = {
            "payload": "root_payload_io",
            "conversion": "awkward_python_conversion",
            "selection": "event_selection",
            "features": "feature_construction",
            "write_and_digest": "artifact_serialization",
            "publication": "artifact_publication",
        }.get(dominant, f"{dominant}_overhead")
    metrics["diagnosis"] = {
        "classification": classification,
        "dominant_phase": dominant,
        "dominant_seconds": phases[dominant],
        "accounted_seconds": accounted,
        "accounted_fraction": accounted / wall if wall > 0 else None,
        "unaccounted_seconds": max(0., wall - accounted) if wall > 0 else None,
        "phase_seconds": phases,
        "phase_fractions": {
            name: seconds / wall if wall > 0 else None
            for name, seconds in phases.items()
        },
    }
    return metrics


@dataclass(frozen=True)
class ResearchDataWriteReceipt:
    population_id: str
    sha256: str
    size_bytes: int


def _is_all_mc(protocol):
    return protocol_dict(protocol).get("source_population") == "all_mc"


def _research_split(protocol):
    return "exploratory" if _is_all_mc(protocol) else "development"


def source_access_record(protocol):
    if _is_all_mc(protocol):
        return {
            "payload_access": "all_mc_entries",
            "acquisition_hash_reverified": False,
            "historical_held_out_test_preserved": False,
        }
    return {
        "payload_access": "development_entries_only",
        "acquisition_hash_reverified": False,
    }


def iter_records(frame):
    """Bounded row objects, with pandas' native scalar boxing and column order."""
    columns = list(frame.columns)
    boxed = [i for i,dtype in enumerate(frame.dtypes)
             if dtype.kind == 'O' or isinstance(dtype,pd.api.extensions.ExtensionDtype)]
    for values in frame.itertuples(index=False, name=None):
        values = list(values)
        for i in boxed:
            value = values[i]
            if value is pd.NA:
                values[i] = None
            elif isinstance(value,np.integer):
                values[i] = int(value)
            elif isinstance(value,np.floating):
                values[i] = float(value)
            elif isinstance(value,np.bool_):
                values[i] = bool(value)
        yield dict(zip(columns, values))


def _roles(groups, protocol):
    lookup = {g: role_for_group(g, protocol) for g in groups.unique()}
    return groups.map(lookup)


def population_digest(groups, dataset):
    from .artifacts import digest_json
    return digest_json({'dataset':dataset, 'physical_groups':sorted(groups)})


def development_spans(mask, max_entries=4096):
    """Ascending half-open development runs; never bridge a forbidden entry."""
    if type(max_entries) is not int or max_entries < 1:
        raise ResearchError("ROOT read limit must be a positive integer")
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 1:
        raise ResearchError("Development mask must be one-dimensional")
    boundaries = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    for start, stop in zip(boundaries[::2], boundaries[1::2]):
        for left in range(int(start), int(stop), max_entries):
            yield left, min(left + max_entries, int(stop))


def iter_development_events(tree, branches, identities, mask, max_entries=4096, *,
                            metrics=None, progress=None, root_executor=None):
    identity_branches = {branches['eventNumber'], branches['channelNumber']}
    payload = [b for b in branches.values() if b not in identity_branches]
    for start, stop in development_spans(mask, max_entries):
        began = time.perf_counter() if metrics is not None else None
        cpu_began = time.process_time() if metrics is not None else None
        executor_options = ({
            'decompression_executor': root_executor,
            'interpretation_executor': root_executor,
        } if root_executor is not None else {})
        values = tree.arrays(
            payload, entry_start=start, entry_stop=stop, library='ak',
            **executor_options,
        )
        if metrics is not None:
            metrics['payload_seconds'] = metrics.get('payload_seconds',0.) + time.perf_counter()-began
            metrics['payload_cpu_seconds'] = metrics.get('payload_cpu_seconds', 0.) + time.process_time()-cpu_began
            metrics['payload_requests'] = metrics.get('payload_requests',0)+1
            metrics['payload_entries'] = metrics.get('payload_entries',0)+stop-start
            metrics['span_entries_total'] = metrics.get('span_entries_total',0)+stop-start
            histogram = metrics.setdefault('span_length_counts',{})
            histogram[str(stop-start)] = histogram.get(str(stop-start),0)+1
        for entry in range(start, stop):
            began = time.perf_counter() if metrics is not None else None
            event = {}
            for name, branch in branches.items():
                value = identities[branch][entry] if branch in identity_branches else values[branch][entry-start]
                event[name] = value.to_list() if hasattr(value, 'to_list') else value
            if metrics is not None:
                metrics['conversion_seconds'] = metrics.get('conversion_seconds',0.) + time.perf_counter()-began
                metrics['entries_processed'] = metrics.get('entries_processed',0)+1
            if progress is not None:
                progress.update()
            yield entry, event


def role_for_group(group, protocol):
    p = protocol_dict(protocol)
    if not isinstance(group, str) or not group:
        raise ResearchError("event group identity missing")
    bucket = int.from_bytes(hashlib.sha256(f"h4l-role-v1:{group}".encode()).digest()[:8], "big") % 100
    boundary = 0
    for role in ROLES:
        boundary += round(p["roles"][role] * 100)
        if bucket < boundary:
            return role
    raise ResearchError("invalid role probabilities")


def assign_roles(frame, protocol):
    p = protocol_dict(protocol)
    result = frame.copy()
    if not (result["split"] == _research_split(p)).all():
        raise ResearchError("research source population differs from protocol")
    assigned = _roles(result.event_group_id, p)
    if "role" in result and not (result.role == assigned).all():
        raise ResearchError("role differs from frozen group assignment")
    result["role"] = assigned
    result["sampling_probability"] = assigned.map(p["roles"]) * p["development_probability"]
    result["yield_weight"] = result.physical_weight / result.sampling_probability
    _validate_identity(result, p)
    return result


def validate_role_isolation(frame, protocol):
    p = protocol_dict(protocol)
    _validate_identity(frame,p)
    if not (frame.role == _roles(frame.event_group_id, p)).all():
        raise ResearchError("role hash binding changed")


def _validate_identity(frame, p):
    if not set(IDENTITY).issubset(frame):
        raise ResearchError("research identity columns missing")
    if frame[list(IDENTITY)].isna().any().any() or frame.source_row_id.duplicated().any() or frame.event_id.duplicated().any():
        raise ResearchError("missing or repeated row identity")
    if not (frame.dataset == p["dataset"]).all() or not (frame.split == _research_split(p)).all():
        raise ResearchError("dataset/split boundary violation")
    if not set(frame.label).issubset({0, 1}) or not set(frame.role).issubset(ROLES):
        raise ResearchError("invalid role or label")
    if (frame.groupby("event_group_id")["role"].nunique() > 1).any() or (frame.groupby("event_group_id")["label"].nunique() > 1).any():
        raise ResearchError("event group crosses roles or labels")


def grouped_statistics(frame, weight="yield_weight"):
    values = frame[weight].to_numpy(float)
    if not np.isfinite(values).all():
        raise ResearchError("weights must be finite")
    grouped = frame.groupby("event_group_id", sort=True)[weight].sum().to_numpy(float)
    signed, absolute = float(values.sum()), float(np.abs(values).sum())
    variance = float(grouped @ grouped)
    return {"rows": len(frame), "event_groups": len(grouped), "positive_sum": float(values[values > 0].sum()),
            "negative_sum": float(values[values < 0].sum()), "negative_fraction": float((values < 0).mean()) if len(values) else 0.,
            "signed_yield": signed, "sum_abs_weights": absolute, "sumw2": variance,
            "N_eff_signed": signed * signed / variance if variance else None,
            "N_eff_abs": absolute * absolute / variance if variance else None,
            "rho": abs(signed) / absolute if absolute else None,
            "status": "defined" if variance and absolute else "undefined_statistics"}


def audit_g0(frame, protocol):
    p = protocol_dict(protocol)
    validate_role_isolation(frame, p)
    # Assessment is never used to adapt support or thresholds.
    allowed = frame.loc[frame.role != "assessment"]
    records = []
    for role in ROLES[:-1]:
        for label in (0, 1):
            stats = grouped_statistics(allowed.loc[(allowed.role == role) & (allowed.label == label)])
            stats.update(role=role, label=label)
            stats["passes"] = (stats["signed_yield"] > 0 and stats["N_eff_signed"] is not None
                               and stats["N_eff_signed"] >= p["g0"]["min_neff_signed"]
                               and stats["rho"] >= p["g0"]["min_rho"])
            records.append(stats)
    return {"status": "passed" if all(x["passes"] for x in records) else "insufficient_statistics",
            "records": records, "assessment_used": False, "two_dimensional_templates_validated": False,
            "physics_sources_validated": False, "scope": "software_statistics_only"}


def write_research_data(frame, path, protocol):
    p = protocol_dict(protocol)
    validate_role_isolation(frame, p)
    kind = frame.attrs.get("source_kind")
    if kind not in {"synthetic", "controlled_mc"}:
        raise ResearchError("explicit synthetic or controlled MC provenance required")
    header = {"schema_version": "h4l-events-v1", "dataset": p["dataset"], "source_kind": kind,
              "mc_only": True, "protocol_digest": hashlib.sha256(canonical(p)).hexdigest(),
              "source_evidence": frame.attrs.get("source_evidence", {})}
    population = set()
    digest = hashlib.sha256()
    size_bytes = 0

    def write_chunk(stream, chunk):
        nonlocal size_bytes
        stream.write(chunk)
        digest.update(chunk)
        size_bytes += len(chunk)

    with Path(path).open("xb") as stream:
        write_chunk(stream, canonical(header) + b"\n")
        for row in iter_records(frame):
            identity = {k: row.pop(k) for k in IDENTITY}
            population.add(tuple(identity[k] for k in ('event_group_id','label','split','dataset')))
            write_chunk(stream, canonical(identity) + b"\t" + canonical(row) + b"\n")
    return ResearchDataWriteReceipt(
        population_id=population_digest(population,p['dataset']),
        sha256=digest.hexdigest(),
        size_bytes=size_bytes,
    )


def load_research_data(path, dataset, protocol, *, allow_assessment=False, assessment_freeze=None):
    p = protocol_dict(protocol)
    if allow_assessment:
        from .artifacts import digest_json
        if (not isinstance(assessment_freeze, dict) or assessment_freeze.get("status") != "frozen"
                or not assessment_freeze.get("evidence_id")
                or assessment_freeze.get("protocol_sha256") != digest_json(p)):
            raise ResearchError("assessment requires bound frozen-analysis evidence")
    rows, identities, chunks = [], [], []
    roles, population = {}, set()
    try:
        with Path(path).open(encoding="utf-8") as stream:
            header = json.loads(next(stream))
            if (header.get("schema_version") != "h4l-events-v1" or header.get("dataset") != dataset
                    or dataset != p["dataset"] or header.get("mc_only") is not True
                    or header.get("source_kind") not in {"synthetic", "controlled_mc"}
                    or header.get("protocol_digest") != hashlib.sha256(canonical(p)).hexdigest()):
                raise ResearchError("research data provenance/protocol mismatch")
            for line in stream:
                first, payload = line.rstrip("\n").split("\t", 1)
                identity = json.loads(first)
                if (set(identity) != set(IDENTITY) or identity["split"] != _research_split(p)
                        or identity["dataset"] != dataset):
                    message = ("wrong-population or malformed research identity" if _is_all_mc(p)
                               else "non-development or malformed research identity")
                    raise ResearchError(message)
                group = identity['event_group_id']
                if group not in roles:
                    roles[group] = role_for_group(group,p)
                if identity["role"] != roles[group]:
                    raise ResearchError("role hash binding changed before payload access")
                identities.append(tuple(identity[k] for k in IDENTITY))
                population.add((group,identity['label'],identity['split'],identity['dataset']))
                if identity["role"] == "assessment" and not allow_assessment:
                    continue
                value = json.loads(payload)
                if set(value) & set(IDENTITY):
                    raise ResearchError("payload attempts identity override")
                rows.append(dict(identity, **value))
                if len(rows) >= 4096:
                    chunks.append(pd.DataFrame(rows))
                    rows.clear()
        _validate_identity(pd.DataFrame(identities, columns=IDENTITY), p)
        if rows:
            chunks.append(pd.DataFrame(rows))
        frame = pd.concat(chunks,ignore_index=True) if chunks else pd.DataFrame()
        if frame.empty:
            raise ResearchStateError("no accessible research events", status="insufficient_statistics")
        for name in (*ENGINEERED19, "m4l", "y4l", "physical_weight", "sampling_probability", "yield_weight"):
            if name not in frame or not np.isfinite(frame[name].to_numpy(float)).all():
                raise ResearchError("research numerical columns missing or nonfinite")
        lo, hi = p["mass_window"]
        if not ((frame.m4l >= lo) & (frame.m4l < hi)).all():
            raise ResearchError("research mass support changed")
        expected = frame.role.map(p["roles"]) * p["development_probability"]
        if not np.allclose(frame.sampling_probability, expected, rtol=0, atol=1e-15) or not np.allclose(frame.yield_weight, frame.physical_weight / expected, rtol=1e-12, atol=1e-12):
            raise ResearchError("sampling/yield normalization changed")
        frame.attrs.update(source_kind=header["source_kind"], source_evidence=header["source_evidence"],
                           population_id=population_digest(population,dataset))
        return frame
    except (OSError, StopIteration, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ResearchError):
            raise
        raise ResearchError("invalid research data") from exc


def export_research_data(manifest_path, profile_path, protocol, *, max_entries=4096,
                         metrics=None, diagnostic_entries_per_file=None,
                         root_threads=1, show_prepare_metrics=False):
    """Read the controlled-MC population declared by the research protocol.

    ROOT baskets may contain neighboring test bytes. Application request ranges
    alone do not establish the underlying interpretation/decompression boundary.
    Input SHA evidence is pre-existing acquisition evidence, never a test scan.
    """
    from src.dataset_binding import dataset_context
    from src.config import load_preprocess_protocol
    from src.domain.selection import SelectionConfig, select_event
    from src.domain.features import build_candidate_features
    from src.domain.angular5 import build_angular5
    from src.domain.splitting import event_split
    from src.domain.weights import physical_event_weight
    import uproot

    if type(root_threads) is not int or root_threads < 1:
        raise ResearchError('ROOT threads must be a positive integer')
    p = protocol_dict(protocol)
    context = dataset_context(p["dataset"])
    raw = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    if (raw.get("schema_version") != "h4l-root-input-v1" or raw.get("mc_only") is not True
            or raw.get("dataset") != p["dataset"] or set(raw.get("files", {})) != {"higgs", "zz"}
            or Path(profile_path).read_bytes() != context.profile_payload):
        raise ResearchError("controlled MC manifest/profile binding failure")
    sources = []
    for role, member in context.samples.items():
        item = raw["files"][role]
        source = Path(item["path"]).resolve()
        stat = source.stat()
        if (source.name != member["filename"] or source.parent.name != p["dataset"]
                or stat.st_size != member["size_bytes"] or item.get("sha256") != member["sha256"]
                or item.get("verified_size_bytes") != stat.st_size or item.get("verified_mtime_ns") != stat.st_mtime_ns):
            raise ResearchError("MC acquisition receipt or file metadata mismatch")
        sources.append((role, member, source))
    progress = PrepareProgressReporter(metrics) if metrics is not None else None
    live_progress = progress if show_prepare_metrics else None
    if metrics is not None:
        metrics.update(
            source_files_total=len(sources),
            source_files_processed=0,
            source_entries_total=sum(member["entry_count"] for _, member, _ in sources),
            eligible_entries_total=0,
            selected_entries=0,
            root_threads=root_threads,
        )
        metrics.setdefault("files", {})
    legacy = load_preprocess_protocol(Path(__file__).resolve().parents[2] / "config/preprocess_protocol_mass_window.yaml", dataset=p["dataset"])
    selection = SelectionConfig.from_mapping(dict(legacy.selection, m4l_window_gev=p["mass_window"]))
    profile = context.profile
    branches = profile["branches"]
    rows = []
    executor_context = (
        ThreadPoolExecutor(max_workers=root_threads, thread_name_prefix='h4l-root')
        if root_threads > 1 else nullcontext(None)
    )
    with executor_context as root_executor:
      for process, member, source in sources:
        # Keep the file source's executors private to uproot. ReadOnlyFile.close
        # may shut down executors supplied to uproot.open, while this bounded
        # executor intentionally spans all source files in one prepare call.
        with uproot.open(source) as root:
            tree = root[profile["tree_name"]]
            if tree.num_entries != member["entry_count"] or not set(branches.values()).issubset(tree.keys()):
                raise ResearchError("MC tree schema/count mismatch")
            began = time.perf_counter() if metrics is not None else None
            identities = tree.arrays([branches["eventNumber"], branches["channelNumber"]], library="np")
            if not np.all(identities[branches["channelNumber"]] == member["dsid"]):
                raise ResearchError("DSID differs before payload access")
            if _is_all_mc(p):
                mask = np.ones(tree.num_entries, dtype=bool)
            else:
                mask = np.fromiter((event_split(int(number),int(dsid)) != 'test'
                    for number,dsid in zip(identities[branches['eventNumber']],identities[branches['channelNumber']])),
                    dtype=bool,count=tree.num_entries)
            mask = limit_selected_entries(mask, diagnostic_entries_per_file)
            if metrics is not None:
                metrics['identity_seconds'] = metrics.get('identity_seconds',0.) + time.perf_counter()-began
                metrics['eligible_entries_total'] += int(mask.sum())
                before_entries = metrics.get('entries_processed', 0)
                before_selected = metrics.get('selected_entries', 0)
                before_spans = metrics.get('payload_requests', 0)
                before_span_entries = metrics.get('span_entries_total', 0)
                file_payload_before = metrics.get('payload_seconds', 0.)
                file_payload_cpu_before = metrics.get('payload_cpu_seconds', 0.)
            for entry, event in iter_development_events(
                    tree, branches, identities, mask, max_entries,
                    metrics=metrics, progress=live_progress,
                    root_executor=root_executor):
                event_number, channel = int(event['eventNumber']), int(event['channelNumber'])
                began = time.perf_counter() if metrics is not None else None
                result = select_event(event, selection, profile["momentum_unit"])
                if metrics is not None:
                    metrics['selection_seconds'] = metrics.get('selection_seconds',0.) + time.perf_counter()-began
                if not result.accepted:
                    continue
                c = result.candidate
                if sorted(np.abs(c.normalized.flavour).tolist()) != [11, 11, 13, 13]:
                    continue
                began = time.perf_counter() if metrics is not None else None
                features = build_candidate_features(event, c)
                try:
                    features.update(build_angular5(c))
                except ValueError as exc:
                    raise ResearchStateError("invalid angular reconstruction", status="invalid_reconstruction") from exc
                vector = c.four_lepton
                if vector.energy <= abs(vector.pz):
                    raise ResearchError("undefined four-lepton rapidity")
                weight = physical_event_weight(mc_weight=float(event["mcWeight"]), luminosity_pb=p["luminosity_pb"], **context.science["normalization"][p["dataset"]][process])
                source_id = f"{member['file_id']}:{entry}"
                features.update(event_id=source_id, source_row_id=source_id, event_group_id=f"{channel}:{event_number}",
                    dataset=p["dataset"], split=_research_split(p), label=member["label"], physical_weight=weight,
                    y4l=float(.5 * np.log((vector.energy + vector.pz) / (vector.energy - vector.pz))),
                    lep_pt=c.normalized.pt.tolist(), lep_eta=c.normalized.eta.tolist(), lep_phi=c.normalized.phi.tolist(),
                    lep_e=c.normalized.energy.tolist(), lep_charge=c.normalized.charge.tolist(), lep_type=c.normalized.flavour.tolist(),
                    pairing=[list(c.pairing.z1_indices), list(c.pairing.z2_indices)])
                rows.append(features)
                if metrics is not None:
                    metrics['feature_seconds'] = metrics.get('feature_seconds',0.) + time.perf_counter()-began
                    metrics['selected_entries'] += 1
            if metrics is not None:
                metrics['source_files_processed'] += 1
                file_metrics = {
                    'filename': source.name,
                    'size_bytes': int(source.stat().st_size),
                    'source_entries': int(tree.num_entries),
                    'eligible_entries': int(mask.sum()),
                    'processed_entries': metrics.get('entries_processed', 0) - before_entries,
                    'selected_entries': metrics.get('selected_entries', 0) - before_selected,
                    'span_count': metrics.get('payload_requests', 0) - before_spans,
                    'span_entries': metrics.get('span_entries_total', 0) - before_span_entries,
                    'payload_seconds': metrics.get('payload_seconds', 0.) - file_payload_before,
                    'payload_cpu_seconds': metrics.get('payload_cpu_seconds', 0.) - file_payload_cpu_before,
                }
                file_metrics['average_span_length'] = (
                    file_metrics['span_entries'] / file_metrics['span_count']
                    if file_metrics['span_count'] else None
                )
                file_metrics['payload_ms_per_span'] = (
                    1000. * file_metrics['payload_seconds'] / file_metrics['span_count']
                    if file_metrics['span_count'] else None
                )
                file_metrics['payload_cpu_fraction'] = (
                    file_metrics['payload_cpu_seconds'] / file_metrics['payload_seconds']
                    if file_metrics['payload_seconds'] else None
                )
                metrics['files'][process] = file_metrics
                if show_prepare_metrics:
                    print(
                        '[h4l prepare] file='
                        f"{source.name} entries={file_metrics['source_entries']} "
                        f"eligible={file_metrics['eligible_entries']} "
                        f"processed={file_metrics['processed_entries']} "
                        f"spans={file_metrics['span_count']} "
                        f"avg_span={file_metrics['average_span_length']:.1f} "
                        f"payload={file_metrics['payload_seconds']:.2f}s "
                        f"ms_per_span={file_metrics['payload_ms_per_span']:.2f} "
                        f"cpu_fraction={file_metrics['payload_cpu_fraction']:.2f}",
                        file=sys.stderr, flush=True,
                    )
    if not rows:
        raise ResearchStateError("no selected 2e2mu research events", status="insufficient_statistics")
    began = time.perf_counter() if metrics is not None else None
    frame = pd.DataFrame(rows)
    if metrics is not None:
        metrics['dataframe_seconds'] = time.perf_counter()-began
    began = time.perf_counter() if metrics is not None else None
    frame = assign_roles(frame, p)
    if metrics is not None:
        metrics['role_assignment_seconds'] = time.perf_counter()-began
        progress.sample_rss()
    frame.attrs.update(source_kind="controlled_mc", source_evidence={"dataset_snapshot": context.snapshot(),
                      "manifest": raw, **source_access_record(p)})
    return frame
