# DropTop4 KNN Flatness Training Execution Report

## Scope and frozen constraints

This was one immutable, MC-only study of `hep_ml.UGradientBoostingClassifier`
with `KnnFlatnessLossFunction`. It used exactly the ten ordered DropTop4 tree
features, five development folds, coefficients `0.0`, `0.5`, `1.0`, `2.0`, and
`3.0`, and the frozen model/loss configuration in
`config/decorrelation_training_drop_top4.yaml`. `m4l` was supplied only to the
flatness loss and was not a tree feature.

Eligibility was frozen before execution: weighted development-OOF AUC had to
be at least `0.80`; continuum-ZZ mass KS had to be at most `0.10` at loose,
medium, and tight working points; and signal efficiency had to be strictly
above background efficiency at all three working points. The held-out MC test
could open once only after an eligible OOF selection. No real-data input was
read, hashed, scored, plotted, or inventoried.

The single production path was
`runs/decorrelation-drop-top4-363490-2026-08-24`. It was absent before the run
and was never reused or retried.

## Verification

Pre-production verification completed with:

```text
focused new tests: 23 passed
full suite: 738 passed, 5 warnings in 99.66s
python byte-compilation: exit 0
git diff --check: exit 0
fresh output-path check: exit 0
```

After production, the exact focused command from the plan completed with:

```text
43 passed, 5 warnings in 49.81s
exit code: 0
```

The fresh final full-suite command completed after the report and project
documentation updates with:

```text
738 passed, 5 warnings in 114.73s
exit code: 0
```

All five warnings were the known upstream scikit-learn warning that feature
names were present when querying a `NearestNeighbors` instance fitted without
feature names. The real `hep_ml` synthetic integration test emitted the same
warning once per fold and passed.

The production process published a manifest-last terminal run with
`status: complete`. The desktop interaction was interrupted after the process
finished, so its original shell session and numeric exit status were no longer
retrievable. Success was independently established without rerunning: the
process was absent, the terminal manifest was present and newer than every
other artifact, all seven declared output hashes matched, all five source
hashes matched, and the recursive file set exactly matched the no-selection
allowlist plus the terminal manifest.

Post-run structural verification printed:

```text
terminal_status: no_eligible_candidate
test_opened: False
manifest_status: complete
manifest_last: True
output_hashes_verified: 7
source_hashes_verified: 5
oof_rows: 159395
forbidden_paths_absent: True
```

## Source hashes

Only the explicitly approved MC sources and frozen configuration were bound:

| Source | SHA-256 |
|---|---|
| Study config | `725ebbbe5b7ee347596dc047a1878b80a7d18be8c20721877556fd125697eda7` |
| Task 4A config | `0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320` |
| Task 4A manifest | `10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8` |
| Task 4A MC table | `1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e` |
| Task 4A summary | `454335d828976ca9de2befc8964f63f3cc9fb3f22f9c0a91af9b63ff7cd16fc5` |

The explicit source audit output for the two protected production inputs was:

```text
10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8  runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json
1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e  runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz
```

## Candidate OOF results

| Candidate | Coefficient | Weighted OOF AUC | Maximum OOF ZZ KS | OOF ZZ score-mass correlation | Eligible | Reasons |
|---|---:|---:|---:|---:|---|---|
| `lambda_0p0` | 0.0 | 0.7631932798301158 | 0.25914767204496136 | -0.3426856292434955 | false | AUC; loose, medium, tight KS |
| `lambda_0p5` | 0.5 | 0.7629246387278324 | 0.24575963130127432 | -0.32159336991894577 | false | AUC; loose, medium, tight KS |
| `lambda_1p0` | 1.0 | 0.7613989193141701 | 0.23087967228895234 | -0.30153309176261606 | false | AUC; loose, medium, tight KS |
| `lambda_2p0` | 2.0 | 0.7591766292389683 | 0.2262391834359853 | -0.2737350617437902 | false | AUC; medium, tight KS |
| `lambda_3p0` | 3.0 | 0.7566586485761435 | 0.20566162971445773 | -0.2507441970494172 | false | AUC; medium, tight KS |

The complete working-point values were:

| Candidate | Working point | Threshold | Target background efficiency | Achieved background efficiency | Signal efficiency | OOF ZZ mass KS |
|---|---|---:|---:|---:|---:|---:|
| `lambda_0p0` | loose | 0.4643354054208464 | 0.5 | 0.5001012321268915 | 0.8508531830805386 | 0.1252793013619376 |
| `lambda_0p0` | medium | 0.5443884988856972 | 0.2 | 0.20007909079933534 | 0.5483537171544542 | 0.2105377091489123 |
| `lambda_0p0` | tight | 0.5832908984585553 | 0.1 | 0.10002130308822696 | 0.3751335184789576 | 0.25914767204496136 |
| `lambda_0p5` | loose | 0.4650062434071121 | 0.5 | 0.5001210956838767 | 0.8487102114932707 | 0.114543779558341 |
| `lambda_0p5` | medium | 0.5421826073660037 | 0.2 | 0.20006181512980373 | 0.549481948301645 | 0.20959683761724796 |
| `lambda_0p5` | tight | 0.5813736286200413 | 0.1 | 0.1000405104810212 | 0.37217608417004916 | 0.24575963130127432 |
| `lambda_1p0` | loose | 0.46496333617529784 | 0.5 | 0.5000212395132607 | 0.8467207861568042 | 0.1017449429243314 |
| `lambda_1p0` | medium | 0.5398553599300749 | 0.2 | 0.20004861311232555 | 0.5500894573809015 | 0.19387568559479806 |
| `lambda_1p0` | tight | 0.5783266787668706 | 0.1 | 0.10000299857212037 | 0.3743524353770562 | 0.23087967228895234 |
| `lambda_2p0` | loose | 0.4658315324516353 | 0.5 | 0.500028399724351 | 0.8413867229224524 | 0.09185553345459496 |
| `lambda_2p0` | medium | 0.5374804345774605 | 0.2 | 0.20005278889524863 | 0.5494552446058535 | 0.17554071738468285 |
| `lambda_2p0` | tight | 0.5759063491460166 | 0.1 | 0.1001423713943935 | 0.3720559175389874 | 0.2262391834359853 |
| `lambda_3p0` | loose | 0.4666851134552224 | 0.5 | 0.5000150244229581 | 0.8369872890408032 | 0.08816291650526226 |
| `lambda_3p0` | medium | 0.5356597379261665 | 0.2 | 0.20001270758012754 | 0.5433000427259133 | 0.16074233941960342 |
| `lambda_3p0` | tight | 0.5731556196307044 | 0.1 | 0.1001093580069326 | 0.36903839991454823 | 0.20566162971445773 |

## Terminal decision

The exact selection record was:

```json
{
  "auc_floor": 0.8,
  "ks_limit": 0.1,
  "schema_version": "1.0",
  "selected_candidate": null,
  "status": "no_eligible_candidate",
  "test_opened": false
}
```

Increasing the flatness coefficient monotonically reduced the maximum KS from
`0.25914767204496136` to `0.20566162971445773`, but it also reduced AUC from
`0.7631932798301158` to `0.7566586485761435`. No candidate reached the AUC
floor, and no candidate passed all three KS limits. The frozen gates were not
changed after seeing these values.

## Conditional test evidence

Held-out test was not opened because no OOF candidate passed every frozen gate.
Consequently there is no selected final model, selected-only OOF table, test
score table, test metric file, or selected mass-sculpting plot. This absence
matches the predeclared no-selection artifact contract.

## Artifact inventory

| Artifact | Rows | Bytes | SHA-256 |
|---|---:|---:|---|
| `config.yaml` | — | 1552 | `725ebbbe5b7ee347596dc047a1878b80a7d18be8c20721877556fd125697eda7` |
| `artifacts/candidate_results.csv` | 5 | 1069 | `f9f927b0033c6467f7a00fe85d4ec5097fd73e62d184f9c87e7d11cd13208cef` |
| `artifacts/selection.json` | — | 160 | `15981104e6f2f0cd2784252b11d58fd0934cadd7b4cbf610968f40be67d816e2` |
| `artifacts/working_point_metrics.csv` | 15 | 1685 | `30dd0d2f5c2888f711601e5ffb9b548789e36d4ee061454d2b014d8903f70a18` |
| `plots/candidate_tradeoff.png` | — | 56768 | `097c1ea41a2030c9360249f24e22464056044a217065f0beb4c6b903fb5be5c0` |
| `plots/working_point_ks.png` | — | 57025 | `80da252455af30faec9c6a2dca80b5f3db82f6542b3c0941fc89444a77ec457c` |
| `predictions/oof_scores.csv.gz` | 159395 | 9315286 | `c251d9b527849475e13adbaa77c1c663a4838845a54cc36a95ace398f3dc70bf` |

`artifacts/study_manifest.json` was published after these seven outputs and is
intentionally not self-listed in its output map.

## Remaining limitations

- This is an educational/technical MC-only method study, not an ATLAS result,
  Higgs discovery claim, or physics measurement.
- The chosen DropTop4 feature set begins below the required AUC floor under
  this native flatness implementation; stronger regularization improves KS
  only modestly and worsens AUC.
- The result does not authorize post-hoc coefficients, relaxed gates, test
  opening, real-data access, or reuse of this immutable run path.
- Any next experiment needs a new predeclared design and run path. A materially
  different decorrelation approach (for example an adversarial objective or a
  template/sideband statistical strategy) is more informative than extending
  this coefficient scan.
