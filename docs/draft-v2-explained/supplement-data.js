/* Committed-record transcription only; original aggregates were not verified locally.
 * Recorded hashes identify sources; they are not a claim of local hash verification. */
globalThis.DraftSupplement = Object.freeze({
  "source_kind": "committed_record_transcription",
  "local_aggregate_verification": false,
  "source_files": [
    "paper/draft-v2/DRAFT001-EVIDENCE.md",
    "paper/draft-v2/project-report-B-cn.tex"
  ],
  "report_path": "runs/h4l-draft-v2-validation001/report/",
  "report_artifact_id": "0e95510075beff91cbcd68bba53109b63d459c70faea6223fdcf9181eba4c195",
  "nominal_report_artifact_id": "9aab6d274a3e2d00d892c2d8fbf89b1e46f5b7a95d0bf0c085af90672ea36898",
  "recorded_aggregate_sha256": {
    "summary.json": "414e31e427969e6b4a423c0400704ac7097f784cbf9333d3a029d13351711837",
    "bootstrap-summary.csv": "1080d9ca991eed9a843e0844e4cf9fd08a8b6a9d5ec2b3c8f2b3f4aa650f06d6",
    "coverage.csv": "65d15b129ee237bbc1e43bd5b32dd1a567b87c23f664786fc85b5bd0cb7a0594"
  },
  "bootstrap_replicas": 200,
  "terminal_units": 248,
  "model_self_cells": 48,
  "toys_per_cell": 500,
  "toys_total": 24000,
  "injections": [
    0,
    1,
    2
  ],
  "refitted_threshold_ranges": {
    "C": [
      0.0101,
      0.0711
    ],
    "D": [
      -0.0384,
      0.0055
    ]
  },
  "other_ranges_include_zero": [
    "A",
    "B"
  ],
  "coverage_mu1_percent": [
    60.4,
    67.2
  ],
  "precision": {
    "contrast_decimals": 4,
    "coverage_percent_decimals": 1
  },
  "qualification": {
    "status": "exploratory_posthoc",
    "independent": false,
    "selection_aware_coverage": "unvalidated",
    "primary_claim_eligible": false
  }
});
