#!/bin/bash
# Submit from the repository root after activating the Python 3.12 environment.
# Site partition/account settings must be supplied to sbatch by the user.
#SBATCH --job-name=h4l-evaluation
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=180G
#SBATCH --hint=nomultithread
#SBATCH --time=12:00:00
#SBATCH --output=h4l-%j.out

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Submit from the repository root}"
export PYTHONUNBUFFERED=1
srun --cpu-bind=cores python scripts/h4l_off_run.py \
  --source-run-name "${H4L_SOURCE_RUN:-test01}" \
  --run-name "${H4L_OFF_RUN:-study-001}" \
  --evaluation --HPC "$@"
