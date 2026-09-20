"""Durable claims and terminal artifacts for within-seed v3 evaluation cells."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import time
from typing import Any, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from higgsml._manifest import canonical_json_bytes
from higgsml.artifacts import LoadedRun, ResearchRun, digest_json, read_json, read_run
from higgsml.errors import ResearchError, ResearchStateError


CLAIM_SCHEMA = "h4l-mass-off-marginal-block-claim-v1"
TERMINAL_SCHEMA = "h4l-mass-off-marginal-block-evaluation-v1"
STAGE = "marginal-block-evaluation"
VALID_SCIENTIFIC_STATUSES = frozenset({"valid"})
TERMINAL_SCIENTIFIC_STATUSES = VALID_SCIENTIFIC_STATUSES | {
    "insufficient_statistics",
    "unsupported_assessment_support",
    "template_stat_model_unvalidated",
    "inference_incomplete",
}
CELL_STAGES = frozenset({"model-self", "assessment", "t2"})
ASSESSMENT_ACCESS_STAGES = frozenset({"assessment", "t2"})
Resolution = Literal[
    "run", "retry_failed", "skip_terminal", "blocked_consumed_budget", "recover_publication"
]


@dataclass(frozen=True)
class SeedEvaluationBinding:
    population_id: str
    freeze_artifact_id: str
    specification_id: str
    evaluation_plan_id: str
    pairing_contract: str
    stage: str
    mu: float | int | None
    training_seed: int
    candidate_ids: tuple[str, ...]
    access_receipt: dict[str, Any]
    budget: dict[str, Any]
    rng: dict[str, Any]

    def value(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_ids"] = list(self.candidate_ids)
        value["mu"] = _canonical_mu(self.mu)
        _validate_binding(value)
        return value

    @property
    def cell_id(self) -> str:
        return digest_json(self.value())

    @property
    def ledger_key(self) -> str:
        """Stable budget slot; changing a receipt or plan cannot create a new slot."""
        value = self.value()
        return digest_json({key: value[key] for key in (
            "population_id", "freeze_artifact_id", "stage", "mu", "training_seed",
        )})


def _fail(message: str) -> None:
    raise ResearchError(message)


def _canonical_mu(value: float | int | None) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail("invalid seed evaluation mu")
    result = float(value)
    return 0.0 if result == 0 else result


def _schema(name: str) -> dict[str, Any]:
    return read_json(Path(__file__).resolve().parents[3] / "config" / "schemas" / name)


def _validate_schema(value: Any, name: str, label: str) -> None:
    try:
        Draft202012Validator(_schema(name)).validate(value)
    except ValidationError as error:
        raise ResearchError(f"invalid {label} schema: {error.message}") from error


def _validate_binding(value: Any) -> None:
    if type(value) is not dict:
        _fail("invalid seed evaluation binding")
    strings = (
        "population_id", "freeze_artifact_id", "specification_id",
        "evaluation_plan_id", "pairing_contract", "stage",
    )
    if any(type(value.get(key)) is not str or not value[key] for key in strings):
        _fail("invalid seed evaluation binding identity")
    candidates = value.get("candidate_ids")
    if (
        value.get("stage") not in CELL_STAGES
        or type(value.get("training_seed")) is not int
        or value["training_seed"] not in range(42, 47)
        or type(candidates) is not list
        or len(candidates) != 16
        or len(set(candidates)) != 16
        or any(type(item) is not str or not item for item in candidates)
        or type(value.get("access_receipt")) is not dict
        or not value["access_receipt"]
        or type(value.get("budget")) is not dict
        or not value["budget"]
        or type(value.get("rng")) is not dict
        or not value["rng"]
        or (value.get("mu") is not None and type(value["mu"]) is not float)
    ):
        _fail("invalid seed evaluation binding contract")
    allowed_mu = {
        "model-self": {0.0, 1.0, 2.0},
        "assessment": {0.0, 1.0, 2.0},
        "t2": {1.0},
    }
    if value["mu"] not in allowed_mu[value["stage"]]:
        _fail("invalid seed evaluation stage/mu identity")
    from higgsml.inference.marginal_coupling import canonical_seed_blocks, pairing_contract
    if value["pairing_contract"] != pairing_contract()["contract_digest"]:
        _fail("v3 pairing contract mismatch")
    expected_candidates = next(
        block.candidate_keys for block in canonical_seed_blocks()
        if block.seed == value["training_seed"]
    )
    if tuple(candidates) != expected_candidates:
        _fail("invalid seed evaluation candidate block")
    budget = value["budget"]
    if value["stage"] == "t2":
        required = (budget.get("planned_outer"), budget.get("planned_inner_per_outer"))
        if any(type(item) is not int or item < 1 for item in required):
            _fail("invalid claimed T2 budget")
    elif type(budget.get("planned_toys_per_candidate")) is not int or budget["planned_toys_per_candidate"] < 1:
        _fail("invalid claimed Toy budget")


def _inside(path: str | Path, root: str | Path, label: str) -> tuple[Path, Path]:
    root_path = Path(root).resolve(strict=True)
    requested = Path(path).absolute()
    try:
        requested.relative_to(root_path)
    except ValueError as error:
        raise ResearchError(f"{label} is outside its allowed root") from error
    if requested == root_path:
        _fail(f"{label} cannot be its allowed root")
    return requested, root_path


def _claims_directory(claims_root: str | Path) -> tuple[Path, Path]:
    root = Path(claims_root).resolve(strict=True)
    directory = root / ".h4l-mass-off-v3-claims"
    if directory.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(directory)):
        _fail("unsafe seed evaluation claim directory")
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != root:
        _fail("invalid seed evaluation claim directory")
    return directory, root


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    # Once O_EXCL succeeds the durable slot is consumed. A partial record after
    # an I/O failure must remain visibly blocked; deleting it would restore budget.
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _population_marker(directory: Path, binding: SeedEvaluationBinding) -> Path:
    from higgsml.inference.population_history import claim_population
    claim_population(directory.parent,binding.population_id,binding.freeze_artifact_id)
    path = directory / f"population-{digest_json(binding.population_id)}.json"
    value = {
        "schema_version": "h4l-mass-off-population-access-history-v1",
        "population_id": binding.population_id,
        "freeze_artifact_id": binding.freeze_artifact_id,
    }
    value["history_id"] = digest_json(value)
    try:
        _atomic_write(path, value)
    except FileExistsError:
        existing = read_json(path)
        if path.is_symlink() or existing != value:
            raise ResearchStateError(
                "population previously used under another freeze",
                status="assessment_already_started",
            )
    return path


def _check_v1_population_history(claims_root: Path, binding: SeedEvaluationBinding) -> None:
    for dirname in ('.research-claims','.h4l-mass-off-v2-claims','.h4l-mass-off-v3-claims','.h4l-population-access'):
        legacy = claims_root / dirname
        if not legacy.exists():
            continue
        if legacy.is_symlink() or not legacy.is_dir():
            _fail('unsafe historical claim directory')
        for path in legacy.glob('*.json'):
            if path.is_symlink():
                _fail('unsafe historical claim receipt')
            claim = read_json(path)
            prior = claim.get('binding',claim)
            if prior.get('stage') == 'model-self':
                continue
            if (prior.get('population_id') == binding.population_id
                    and prior.get('freeze_artifact_id') not in (None,binding.freeze_artifact_id)):
                raise ResearchStateError('population previously used under another freeze',
                                         status='assessment_already_started')


def _claim_value(output_dir: Path, binding: SeedEvaluationBinding) -> dict[str, Any]:
    value = {
        "schema_version": CLAIM_SCHEMA,
        "ledger_key": binding.ledger_key,
        "cell_id": binding.cell_id,
        "binding": binding.value(),
        "initial_output": str(output_dir),
    }
    value["claim_id"] = digest_json(value)
    return value


def _claim_path(claims_root: str | Path, binding: SeedEvaluationBinding) -> Path:
    root = Path(claims_root).resolve(strict=True)
    directory = root / ".h4l-mass-off-v3-claims"
    if directory.exists() and (
        directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != root
    ):
        _fail("invalid seed evaluation claim directory")
    return directory / f"cell-{binding.ledger_key}.json"


def _recomputations_directory(claims_root: str | Path) -> Path:
    root = Path(claims_root).resolve(strict=True)
    directory = root / ".h4l-mass-off-v3-recomputations"
    if directory.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(directory)):
        _fail("unsafe seed evaluation recomputation directory")
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != root:
        _fail("invalid seed evaluation recomputation directory")
    return directory


def record_seed_evaluation_recomputation(
    *, claims_root: str | Path, output_dir: str | Path, binding: SeedEvaluationBinding,
) -> dict[str, Any]:
    """Durably record an explicit retry without deleting the original budget claim."""
    _, claim = _read_claim(claims_root, binding)
    directory = _recomputations_directory(claims_root)
    prefix = f"cell-{binding.ledger_key}-attempt-"
    indices = []
    for path in directory.glob(prefix + "*.json"):
        try:
            indices.append(int(path.stem.removeprefix(prefix)))
        except ValueError:
            _fail("invalid seed evaluation recomputation receipt name")
    attempt = max(indices, default=0) + 1
    value = {
        "schema_version": "h4l-mass-off-marginal-block-recomputation-v1",
        "ledger_key": binding.ledger_key,
        "cell_id": binding.cell_id,
        "claim_id": claim["claim_id"],
        "attempt": attempt,
        "reason": "explicit_partial_recompute_after_unpublished_failure",
        "output": str(Path(output_dir).absolute()),
    }
    value["recomputation_id"] = digest_json(value)
    _validate_schema(value, "h4l_mass_off_marginal_block_recomputation.schema.json",
                     "seed evaluation recomputation")
    try:
        _atomic_write(directory / f"{prefix}{attempt}.json", value)
    except FileExistsError as error:
        raise ResearchStateError(
            "concurrent seed evaluation recomputation attempt",
            status="assessment_already_started",
        ) from error
    return value


def _validate_recomputation(
    value: Any, *, claims_root: str | Path, binding: SeedEvaluationBinding,
    claim: dict[str, Any],
) -> None:
    _validate_schema(value, "h4l_mass_off_marginal_block_recomputation.schema.json",
                     "seed evaluation recomputation")
    if type(value) is not dict:
        _fail("invalid seed evaluation recomputation binding")
    identity = dict(value)
    recomputation_id = identity.pop("recomputation_id", None)
    attempt = value.get("attempt")
    expected = {
        "schema_version": "h4l-mass-off-marginal-block-recomputation-v1",
        "ledger_key": binding.ledger_key,
        "cell_id": binding.cell_id,
        "claim_id": claim["claim_id"],
        "reason": "explicit_partial_recompute_after_unpublished_failure",
        "output": claim["initial_output"],
    }
    if (type(attempt) is not int or attempt < 1 or recomputation_id != digest_json(identity)
            or any(value.get(key) != item for key, item in expected.items())):
        _fail("seed evaluation recomputation binding mismatch")
    path = (_recomputations_directory(claims_root)
            / f"cell-{binding.ledger_key}-attempt-{attempt}.json")
    if path.is_symlink() or not path.is_file() or read_json(path) != value:
        _fail("missing seed evaluation recomputation receipt")


def claim_seed_evaluation(
    *, claims_root: str | Path, output_dir: str | Path, binding: SeedEvaluationBinding
) -> dict[str, Any]:
    """Atomically consume a cell budget after safe metadata checks and before decode."""
    binding.value()
    lineage_root = Path(claims_root).resolve(strict=True)
    output = Path(output_dir).absolute()
    value = _claim_value(output, binding)
    _validate_schema(value, "h4l_mass_off_marginal_block_claim.schema.json", "seed evaluation claim")
    if binding.stage in ASSESSMENT_ACCESS_STAGES:
        _check_v1_population_history(lineage_root, binding)
    directory, _ = _claims_directory(lineage_root)
    if binding.stage in ASSESSMENT_ACCESS_STAGES:
        _population_marker(directory, binding)
    path = directory / f"cell-{binding.ledger_key}.json"
    try:
        _atomic_write(path, value)
    except FileExistsError as error:
        raise ResearchStateError(
            "seed evaluation cell budget already consumed",
            status="assessment_already_started",
        ) from error
    return {"claim_id": value["claim_id"], "cell_id": binding.cell_id,
            "ledger_key": binding.ledger_key, "path": str(path)}


def _read_claim(claims_root: str | Path, binding: SeedEvaluationBinding) -> tuple[Path, dict[str, Any]]:
    path = _claim_path(claims_root, binding)
    if path.is_symlink() or not path.is_file():
        _fail("missing seed evaluation claim")
    value = read_json(path)
    _validate_schema(value, "h4l_mass_off_marginal_block_claim.schema.json", "seed evaluation claim")
    expected = dict(value)
    claim_id = expected.pop("claim_id", None)
    if (
        claim_id != digest_json(expected)
        or value.get("ledger_key") != binding.ledger_key
        or value.get("cell_id") != binding.cell_id
        or value.get("binding") != binding.value()
    ):
        _fail("seed evaluation claim binding mismatch")
    return path, value


def _validate_terminal(value: Any, binding: SeedEvaluationBinding, claim: dict[str, Any]) -> None:
    _validate_schema(value, "h4l_mass_off_marginal_block_evaluation.schema.json", "seed evaluation terminal")
    from higgsml.inference.marginal_coupling import METADATA
    if any(value.get(key)!=expected for key,expected in METADATA.items()):
        _fail('v3 conditional coupling metadata mismatch')
    if value.get('marginal_support') != value.get('joint_support'):
        _fail('v3 marginal support alias mismatch')
    identity = dict(value)
    terminal_id = identity.pop("terminal_id", None)
    if (
        terminal_id != digest_json(identity)
        or value["cell_id"] != binding.cell_id
        or value["claim_id"] != claim["claim_id"]
        or value["binding"] != binding.value()
        or value["scientific_status"] not in TERMINAL_SCIENTIFIC_STATUSES
    ):
        _fail("seed evaluation terminal binding mismatch")
    optional_bindings = {
        "stage": binding.stage, "training_seed": binding.training_seed,
        "pairing_scope": "within_seed", "cross_seed_pairing": "none",
    }
    if any(key in value and value[key] != expected for key, expected in optional_bindings.items()):
        _fail("seed evaluation terminal repeated binding mismatch")
    planned = value["planned_toys_per_candidate"]
    budget = binding.value()["budget"]
    if binding.stage == "t2":
        outer, inner = budget["planned_outer"], budget["planned_inner_per_outer"]
        if (
            planned != outer * inner
            or value.get("planned_outer") != outer
            or value.get("planned_inner_per_outer") != inner
        ):
            _fail("terminal T2 budget differs from claim")
    elif planned != budget["planned_toys_per_candidate"]:
        _fail("terminal Toy budget differs from claim")
    if value["generated_physical_toys"] > planned:
        _fail("generated physical Toy count exceeds budget")
    seen = set()
    for row in value["candidate_results"]:
        attempted, completed, valid = row["attempted_fits"], row["completed_fits"], row["valid_fits"]
        if not (0 <= valid <= completed <= attempted <= planned):
            _fail("invalid candidate fit budget accounting")
        seen.add(row["candidate_id"])
    if seen != set(binding.candidate_ids):
        _fail("terminal candidate identity mismatch")
    if value["scientific_status"] == "valid":
        support = value["joint_support"]
        support_valid = (
            support.get("status") == "valid" or support.get("qualification") == "valid"
        )
        complete = value["generated_physical_toys"] == planned and all(
            row["attempted_fits"] == planned
            and row["completed_fits"] == planned
            and row["valid_fits"] == planned
            for row in value["candidate_results"]
        )
        if value["qualification"].get("status") != "valid" or not support_valid or not complete:
            _fail("scientifically valid terminal is incomplete")


def publish_seed_evaluation_terminal(
    *, output_dir: str | Path, allowed_root: str | Path, claims_root: str | Path,
    dataset: str, protocol: dict[str, Any], binding: SeedEvaluationBinding,
    terminal: dict[str, Any], upstreams: tuple[LoadedRun, ...] = (),
    recomputation: dict[str, Any] | None = None,
) -> LoadedRun:
    """Publish an execution-complete result, including a scientific failure terminal."""
    output, root = _inside(output_dir, allowed_root, "seed evaluation output")
    _, claim = _read_claim(claims_root, binding)
    if recomputation is not None:
        _validate_recomputation(recomputation, claims_root=claims_root, binding=binding,
                                claim=claim)
    value = {
        "schema_version": TERMINAL_SCHEMA,
        "cell_id": binding.cell_id,
        "claim_id": claim["claim_id"],
        "binding": binding.value(),
        **terminal,
    }
    if recomputation is not None:
        value["recomputation"] = recomputation
    value["terminal_id"] = digest_json(value)
    _validate_terminal(value, binding, claim)
    with ResearchRun(
        output, allowed_root=root, stage=STAGE, dataset=dataset, protocol=protocol,
        upstreams=list(upstreams), context={"cell_id": binding.cell_id, "claim_id": claim["claim_id"]},
    ) as run:
        run.write_json("seed-evaluation.json", value)
    return read_seed_evaluation_terminal(
        output_dir=output, claims_root=claims_root, dataset=dataset,
        protocol=protocol, binding=binding,
    )[0]


def read_seed_evaluation_terminal(
    *, output_dir: str | Path, claims_root: str | Path, dataset: str,
    protocol: dict[str, Any], binding: SeedEvaluationBinding,
    require_scientific_valid: bool = False,
) -> tuple[LoadedRun, dict[str, Any]]:
    """Read a complete terminal; consumers must opt into the scientific-valid gate."""
    _, claim = _read_claim(claims_root, binding)
    run = read_run(output_dir, dataset=dataset, protocol=protocol, stages=(STAGE,))
    if set(run.manifest["files"]) != {"protocol.json", "seed-evaluation.json"}:
        _fail("seed evaluation artifact file surface mismatch")
    if run.manifest.get("context") != {"cell_id": binding.cell_id, "claim_id": claim["claim_id"]}:
        _fail("seed evaluation manifest context mismatch")
    value = run.read_json("seed-evaluation.json")
    _validate_terminal(value, binding, claim)
    if value.get("recomputation") is not None:
        _validate_recomputation(value["recomputation"], claims_root=claims_root, binding=binding,
                                claim=claim)
    if require_scientific_valid and value["scientific_status"] not in VALID_SCIENTIFIC_STATUSES:
        raise ResearchStateError(
            "seed evaluation terminal is not scientifically valid",
            status=value["scientific_status"],
        )
    return run, value


def _failed_staging(output: Path) -> list[Path]:
    return sorted(output.parent.glob(f".{output.name}.*.failed"))


def resolve_seed_evaluation(
    *, output_dir: str | Path, claims_root: str | Path, dataset: str,
    protocol: dict[str, Any], binding: SeedEvaluationBinding, retry_failed: bool = False,
) -> Resolution:
    """Resolve a cell; explicit retry applies only when no terminal can be recovered."""
    output = Path(output_dir).absolute()
    path = _claim_path(claims_root, binding)
    claimed = os.path.lexists(path)
    if os.path.lexists(output):
        if not claimed:
            _fail("seed evaluation output has no legal claim")
        try:
            read_seed_evaluation_terminal(
                output_dir=output, claims_root=claims_root, dataset=dataset,
                protocol=protocol, binding=binding,
            )
        except ResearchError:
            return "blocked_consumed_budget"
        return "skip_terminal"
    if not claimed:
        return "run"
    valid = 0
    for staging in _failed_staging(output):
        try:
            read_seed_evaluation_terminal(
                output_dir=staging, claims_root=claims_root, dataset=dataset,
                protocol=protocol, binding=binding,
            )
            valid += 1
        except ResearchError:
            continue
    if valid == 1:
        return "recover_publication"
    return "retry_failed" if retry_failed else "blocked_consumed_budget"


def recover_seed_evaluation_publication(
    *, output_dir: str | Path, allowed_root: str | Path, claims_root: str | Path,
    dataset: str, protocol: dict[str, Any], binding: SeedEvaluationBinding,
) -> LoadedRun:
    """Publish one fully verified failed staging directory without recomputation."""
    output, _ = _inside(output_dir, allowed_root, "seed evaluation output")
    if resolve_seed_evaluation(
        output_dir=output, claims_root=claims_root, dataset=dataset,
        protocol=protocol, binding=binding,
    ) != "recover_publication":
        _fail("seed evaluation staging is not provably recoverable")
    staging = next(
        path for path in _failed_staging(output)
        if _staging_valid(path, claims_root, dataset, protocol, binding)
    )
    for attempt, delay in enumerate((0.1, 0.2, 0.4, 0.8, None), start=1):
        if os.path.lexists(output):
            _fail("seed evaluation output already exists")
        try:
            staging.rename(output)
            break
        except OSError as error:
            if delay is None or not staging.is_dir():
                raise ResearchError(f"cannot recover seed evaluation publication after {attempt} attempts") from error
            time.sleep(delay)
    return read_seed_evaluation_terminal(
        output_dir=output, claims_root=claims_root, dataset=dataset,
        protocol=protocol, binding=binding,
    )[0]


def _staging_valid(path, claims_root, dataset, protocol, binding) -> bool:
    try:
        read_seed_evaluation_terminal(
            output_dir=path, claims_root=claims_root, dataset=dataset,
            protocol=protocol, binding=binding,
        )
        return True
    except ResearchError:
        return False
