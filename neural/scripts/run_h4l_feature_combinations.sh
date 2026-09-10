#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: run_h4l_feature_combinations.sh [options]

Options:
  --seed N                 Seed 42-46 (default: 42)
  --config PATH            Batch configuration JSON
  --prepared-run PATH      Override prepared run from the configuration
  --gate-run PATH          Override G1 gate run from the configuration
  --t1-validation PATH     Override independent T1 validation JSON
  --output-root PATH       Override output root under neural/runs
  --python-command PATH    Python executable (default: python)
  --plan-only              Print commands without creating a run
  -h, --help               Show this help
EOF
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd -P)
cd "$PROJECT_ROOT"

SEED=42
CONFIG_PATH="config/research_feature_combinations_seed42.json"
PREPARED_OVERRIDE=""
GATE_OVERRIDE=""
T1_OVERRIDE=""
OUTPUT_OVERRIDE=""
PYTHON_COMMAND=python
PLAN_ONLY=0

while (($#)); do
    case "$1" in
        --seed) SEED=${2:?missing value for --seed}; shift 2 ;;
        --config) CONFIG_PATH=${2:?missing value for --config}; shift 2 ;;
        --prepared-run) PREPARED_OVERRIDE=${2:?missing value for --prepared-run}; shift 2 ;;
        --gate-run) GATE_OVERRIDE=${2:?missing value for --gate-run}; shift 2 ;;
        --t1-validation) T1_OVERRIDE=${2:?missing value for --t1-validation}; shift 2 ;;
        --output-root) OUTPUT_OVERRIDE=${2:?missing value for --output-root}; shift 2 ;;
        --python-command) PYTHON_COMMAND=${2:?missing value for --python-command}; shift 2 ;;
        --plan-only) PLAN_ONLY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! "$SEED" =~ ^(42|43|44|45|46)$ ]]; then
    echo "Seed must be one of 42, 43, 44, 45, or 46: $SEED" >&2
    exit 2
fi

resolve_path() {
    local value=$1
    if [[ "$value" = /* ]]; then
        realpath -m -- "$value"
    else
        realpath -m -- "$PROJECT_ROOT/$value"
    fi
}

CONFIG_FILE=$(resolve_path "$CONFIG_PATH")
[[ -f "$CONFIG_FILE" ]] || { echo "Batch configuration does not exist: $CONFIG_FILE" >&2; exit 3; }

CONFIG_JSON=$("$PYTHON_COMMAND" - "$CONFIG_FILE" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    config = json.load(handle)
expected = ["A", "B", "C", "D", "AB", "AC", "AD", "BC", "BD", "CD",
            "ABC", "ABD", "ACD", "BCD", "ABCD"]
if (config.get("schema_version") != "h4l-feature-combination-batch-v1"
        or config.get("dataset") != "atlas2020_4lep"
        or config.get("default_seed") != 42
        or config.get("family_id") != "engineered19_raw_T1"
        or config.get("empty_baseline_candidate") != "M0c"
        or config.get("combination_candidate") != "M3"
        or config.get("calibration_transform") != "raw"
        or config.get("inference_layer") != "T1"
        or config.get("injection_mu") != 1.0
        or config.get("feature_combinations") != expected):
    raise SystemExit("Batch configuration differs from the registered single-seed feature-combination contract.")
for key in ("protocol", "prepared_run", "g1_gate_run", "t1_validation", "output_root"):
    print(config[key])
PY
)
mapfile -t CONFIG_VALUES <<< "$CONFIG_JSON"
PROTOCOL_REL=${CONFIG_VALUES[0]}
PREPARED_REL=${CONFIG_VALUES[1]}
GATE_REL=${CONFIG_VALUES[2]}
T1_REL=${CONFIG_VALUES[3]}
OUTPUT_TEMPLATE=${CONFIG_VALUES[4]}

PROTOCOL=$(resolve_path "$PROTOCOL_REL")
PREPARED=$(resolve_path "${PREPARED_OVERRIDE:-$PREPARED_REL}")
GATE=$(resolve_path "${GATE_OVERRIDE:-$GATE_REL}")
T1_VALIDATION=$(resolve_path "${T1_OVERRIDE:-$T1_REL}")
OUTPUT_TEMPLATE=${OUTPUT_OVERRIDE:-$OUTPUT_TEMPLATE}
OUTPUT_TEMPLATE=${OUTPUT_TEMPLATE//\{seed\}/$SEED}
BATCH_ROOT=$(resolve_path "$OUTPUT_TEMPLATE")
RUNS_ROOT=$(resolve_path "runs")

case "$BATCH_ROOT/" in
    "$RUNS_ROOT"/*/) ;;
    *) echo "OutputRoot must be a child of the neural/runs directory: $BATCH_ROOT" >&2; exit 4 ;;
esac
[[ -f "$PROTOCOL" ]] || { echo "Research protocol does not exist: $PROTOCOL" >&2; exit 3; }

if (( ! PLAN_ONLY )); then
    for required in "$PREPARED" "$GATE" "$T1_VALIDATION"; do
        [[ -e "$required" ]] || { echo "Required bound input does not exist: $required" >&2; exit 3; }
    done
    [[ ! -e "$BATCH_ROOT" ]] || { echo "OutputRoot already exists and cannot be reused: $BATCH_ROOT" >&2; exit 4; }
fi

invoke_research() {
    local -a args=("$@")
    printf '%q ' "$PYTHON_COMMAND" -m src.cli.research "${args[@]}"
    printf '\n'
    if (( ! PLAN_ONLY )); then
        "$PYTHON_COMMAND" -m src.cli.research "${args[@]}"
    fi
}

COMMON=(--dataset atlas2020_4lep --protocol "$PROTOCOL")
CALIBRATION_RUNS=()

BASELINE_TRAIN="$BATCH_ROOT/train/empty"
BASELINE_CALIBRATION="$BATCH_ROOT/calibrate/empty"
invoke_research train "${COMMON[@]}" --input-run "$PREPARED" --gate-run "$GATE" \
    --candidate M0c --seed "$SEED" --run-dir "$BASELINE_TRAIN"
invoke_research calibrate "${COMMON[@]}" --input-run "$PREPARED" --model-run "$BASELINE_TRAIN" \
    --transform raw --seed "$SEED" --run-dir "$BASELINE_CALIBRATION"
CALIBRATION_RUNS+=("$BASELINE_CALIBRATION")

for groups in A B C D AB AC AD BC BD CD ABC ABD ACD BCD ABCD; do
    TRAIN_RUN="$BATCH_ROOT/train/groups-$groups"
    CALIBRATION_RUN="$BATCH_ROOT/calibrate/groups-$groups"
    invoke_research train "${COMMON[@]}" --input-run "$PREPARED" --gate-run "$GATE" \
        --candidate M3 --groups "$groups" --seed "$SEED" --run-dir "$TRAIN_RUN"
    invoke_research calibrate "${COMMON[@]}" --input-run "$PREPARED" --model-run "$TRAIN_RUN" \
        --transform raw --seed "$SEED" --run-dir "$CALIBRATION_RUN"
    CALIBRATION_RUNS+=("$CALIBRATION_RUN")
done

TEMPLATE_RUN="$BATCH_ROOT/templates"
TEMPLATE_ARGS=(templates "${COMMON[@]}" --input-run "$PREPARED" --t1-validation "$T1_VALIDATION" \
    --seed "$SEED" --run-dir "$TEMPLATE_RUN")
for calibration_run in "${CALIBRATION_RUNS[@]}"; do
    TEMPLATE_ARGS+=(--calibration-run "$calibration_run")
done
invoke_research "${TEMPLATE_ARGS[@]}"

INFERENCE_RUN="$BATCH_ROOT/inference"
invoke_research infer "${COMMON[@]}" --template-run "$TEMPLATE_RUN" --layer T1 --mu 1 \
    --seed "$SEED" --run-dir "$INFERENCE_RUN"

REPORT_RUN="$BATCH_ROOT/report"
invoke_research report "${COMMON[@]}" --result-run "$INFERENCE_RUN" --seed "$SEED" \
    --run-dir "$REPORT_RUN"

if (( PLAN_ONLY )); then
    echo "Plan complete: 15 nonempty combinations plus the M0c empty baseline; no run was created."
    exit 0
fi

"$PYTHON_COMMAND" - "$REPORT_RUN/report.json" "$SEED" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    report = json.load(handle)
seed = int(sys.argv[2])
comparisons = report.get("feature_combination_comparisons", [])
if (len(comparisons) != 1 or comparisons[0].get("status") != "valid"
        or comparisons[0].get("seed") != seed):
    raise SystemExit("The batch completed, but the complete 15-combination comparison is unavailable.")
PY
echo "Completed seed $SEED: 15 combination models, M0c baseline, common T1 inference and exact Shapley comparison."
echo "Report: $REPORT_RUN/report.md"
