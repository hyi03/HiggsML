# Actual MC Stage A/B replay — 2026-09-14

Output root: D:/code/HiggsML-m4l-off/runs/m4l-off-002. Source models: D:/code/HiggsML/runs/h4l-train-T2/batch/all-seeds. Source prepared population: D:/code/HiggsML/runs/h4l-prepare/prepare. No source artifact was modified and no assessment payload was decoded.

| Stage | Status | Artifact ID |
|---|---|---|
| register | complete | 65445ac6080355dc12a90179b7b0db8c1b200f090bb1706642e94cab8b77147c |
| nominal | complete | 948e4edbed55ff891298c70177cadeea2e4cf7d60910a7a2f4e1e0babe5b9c1a |
| freeze | complete | 0f8cc5f7d161fc419f8489e4d9bb498c7746f45393e726313618f1a42571d00b |
| asimov | complete | b028903ab4bf8039ea3502c0c3b0da33cbbfcadf332036df56e6555517061485 |
| report-B | complete | 6df02e260da347978617643d5caae7cda2f36a57103f27a59ce722a817da679a |

Verified: 75 reusable training/calibration artifacts plus five bound deterministic M0off models; all 80 on one nominal grid; G1 and active-bin likelihood equivalence; all five per-seed Shapley tables; four contributions, 24 conditional interactions, 105 paired comparisons, 75 checkpoint AUC observations, 3125 joint seed-vector resamples. CSV rows: metrics 80, attribution 4, interactions 24, pairwise 105. Off-only Markdown contains no m4l=on, M4/M5 or on/off result text. Publication rechecked original model/calibration SHA-256, sizes and mtime_ns.

This is an exploratory fixed-T1 model-self Asimov replay using automatic software-contract P0/T1 materials. Independent physical/numerical qualification and historical-use review remain pending. C event-MC bootstrap, D model-self/assessment Toys, E T2 and native ARM64 are not_run. The exploratory freeze grants no assessment access. This replay is not evidence for coverage or a physics measurement.

The earlier m4l-off-001 registration/nominal runs remain immutable development evidence from before the final registration-definition binding; they are not inputs to this replay.

## Post-review replay

The final implementation reused the immutable m4l-off-002 registration/nominal/freeze and wrote fresh outputs:

| Stage | Output | Artifact ID |
|---|---|---|
| Asimov | runs/m4l-off-003/asimov | faddb4e6d0a9a7d3be8d2245df06e99a9f8e73b6751ed141260f5b53d5947fad |
| Stage B report | runs/m4l-off-003/report-B | cccde13076eb75681dfad5449eb78436f3bbf079b3ff1810942ff552b5a70ac9 |

The report now generates evaluation-plan.json from actual manifests, stores its canonical digest and exposes expanded export-field semantics. `sprint-m4-01-bound-plan-preflight.json` confirms all five manifest identities resolved, 80 candidates, eight registered evaluation cells, no default stress and no assessment payload opened. Plan preflight is metadata-only, not C–E validation. The same scientific evidence limits above apply.
