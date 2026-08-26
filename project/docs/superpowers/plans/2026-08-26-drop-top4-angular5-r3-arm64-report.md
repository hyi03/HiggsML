# Angular5 + DropTop4 ARM64 Training Execution Report

## Scope and frozen policy

This is the one-time, educational/technical MC-only study of the exact 15
feature profile: the frozen ten-feature DropTop4 set plus five Angular5
variables. It does not put `m4l`, identifiers, provenance fields, or weights
into the tree features. The policy was fixed before the run: weighted
development-OOF AUC must be at least `0.80`; continuum-ZZ OOF mass KS must be
at most `0.10` at loose, medium, and tight working points; and signal
efficiency must be strictly greater than achieved ZZ efficiency at every
working point.

The native Apple Silicon ARM64 environment was Python `3.12.13`, NumPy
`2.5.1`, pandas `3.0.5`, PyYAML `6.0.3`, uproot `5.7.5`, scikit-learn `1.9.0`,
XGBoost `3.3.0`, and hep_ml `0.8.0`. The earlier R2 identity terminal was kept
immutable after its exact old-column comparison failed on `mZ1`. The confirmed
cause was CPU/runtime architecture: x86_64/Rosetta recomputation differed from
the ARM authoritative table by at most `9.66e-13` for `mZ1` (`mZ2` `8.19e-13`,
`m4l` `1.83e-12`, `pt4l` `1.14e-13`, and angular/distance quantities about
`1e-15`–`1e-14`). The source identity, CSV parser, selection, and ROOT inputs
were not implicated. R3 used a distinct native-ARM64 path and no numerical
tolerance.

The production identity and enrichment records contain `199104` rows. Their
old lexical columns and row order are preserved; canonical
`(source_sample, source_entry)` identity is complete and one-to-one. The legacy
`(runNumber, eventNumber, channelNumber)` key has 2 duplicate groups covering
4 rows, which is why it is not used as the canonical identity.

## Production receipts

| Receipt | SHA-256 |
|---|---|
| Identity manifest | `74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0` |
| Identity table | `a3ffd8c53aca90dc1813d4f88f9d12113b1918a6f193b8f8ee792cdfd4621f94` |
| Enrichment manifest | `ab5e283f4b6a2038a100a2a9d4e6745cccc3ee7f400ef056bcd05d3c22f28ad5` |
| Enrichment table | `bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09` |
| Training config | `3b771cc739947d7feb4bb0f2f92a2a34b572bd0c78da8d20a4bf477964c285de` |
| Training manifest | `b6eab8e5a68f0db02fc2e5bfc671fdaa568cf71c261e36569d3a2e39a048c338` |
| Iteration CSV | `28f720e63885b7436eb2d064a42fc6d7c38ca753aa3c832b47fc0093e2ec74b4` |
| Selection JSON | `36374f9798996e68e05df06815150879a46147ed6440276a417313dc8fd03a85` |

## Final verification

After the documentation update, the native-ARM64 command
`.venv-arm64/bin/python -m pytest -q` completed with exit code `0`:

```text
878 passed, 5 warnings in 106.23s
```

The five warnings are the known scikit-learn `NearestNeighbors` feature-name
warning emitted by the real `hep_ml` synthetic OOF test. `git diff --check`
also completed with exit code `0`.

## Complete development-OOF trajectory

The following full-precision values are directly transcribed from
`artifacts/iteration_results.csv`. `ZZ efficiency` is the achieved, rather
than nominal, background efficiency. Signal efficiency is greater than the
corresponding achieved ZZ efficiency in every cell of the table, so every
signal-efficiency gate passes.

| Iteration | Candidate | Trees | Weighted OOF AUC | Loose: signal / ZZ / KS | Medium: signal / ZZ / KS | Tight: signal / ZZ / KS |
|---:|---|---:|---:|---|---|---|
| 0 | `depth4_child20` | 907 | 0.805150881259955 | 0.9068842127750482 / 0.5000423590259107 / 0.1645048771773192 | 0.6228970839564196 / 0.20000999672947067 / 0.2871440397452666 | 0.42197180089724423 / 0.10013537117391645 / 0.333771961215733 |
| 1 | `depth3_child20` | 980 | 0.7969512716122573 | 0.8957554475539414 / 0.5000295981431137 / 0.1331765017253415 | 0.6019146549882504 / 0.2000098301879539 / 0.20697354210107244 | 0.4247890408032472 / 0.10015042243409492 / 0.24956891177813523 |
| 2 | `depth4_child20` | 882 | 0.7910393793089066 | 0.8867028946806237 / 0.5000108013737884 / 0.11802005736915522 | 0.5930490279854732 / 0.20003560597030182 / 0.1779058575996429 | 0.4110499893185218 / 0.10008739949176114 / 0.21232784339918892 |
| 3 | `depth4_child20` | 731 | 0.7777583601726561 | 0.8737315744499041 / 0.5001140872438575 / 0.0897799588703656 | 0.5776810510574664 / 0.20004919509593244 / 0.12320645298202404 | 0.387330431531724 / 0.10001048689937193 / 0.12778560765808394 |
| 4 | `depth4_child20` | 835 | 0.7705509060126216 | 0.8669354838709681 / 0.5000631627106894 / 0.07725381616480781 | 0.5567854091006196 / 0.20012197600808188 / 0.10586890011029743 | 0.38100833155308705 / 0.1000043330346101 / 0.10377348918175572 |
| 5 | `depth4_child20` | 879 | 0.7665404021047497 | 0.857469023712882 / 0.5003021215787615 / 0.07381807828236636 | 0.5480199209570604 / 0.2000081292064798 / 0.090638729937013 | 0.37168874172185434 / 0.10006690724263469 / 0.08836325258185229 |

| Iteration | Eligible | Full recorded reason(s) |
|---:|---|---|
| 0 | false | `loose_zz_ks_above_limit,medium_zz_ks_above_limit,tight_zz_ks_above_limit` |
| 1 | false | `weighted_auc_below_floor,loose_zz_ks_above_limit,medium_zz_ks_above_limit,tight_zz_ks_above_limit` |
| 2 | false | `weighted_auc_below_floor,loose_zz_ks_above_limit,medium_zz_ks_above_limit,tight_zz_ks_above_limit` |
| 3 | false | `weighted_auc_below_floor,medium_zz_ks_above_limit,tight_zz_ks_above_limit` |
| 4 | false | `weighted_auc_below_floor,medium_zz_ks_above_limit,tight_zz_ks_above_limit` |
| 5 | false | `weighted_auc_below_floor` |

Iteration 0 is the only AUC-passing iteration, but it fails all three KS gates.
Iteration 5 is the only all-KS-passing iteration, but it fails the AUC floor.
No post-hoc change to features, bins, iterations, thresholds, or gates was made.

## Terminal and conditional artifact audit

The selection record is exactly `status: no_eligible_iteration`,
`selected_iteration: null`, `test_opened: false`, with
`selection_basis: development_oof_only`. There are exactly six OOF iterations
(`0` through `5`). The audited no-selection allowlist contains exactly eight
files: the config, five artifacts, and two plots. It contains no model, held-out
test metrics, test predictions, or selected-only artifacts. Held-out MC test
was not opened and real data was not read, hashed, parsed, inventoried, scored,
or plotted.

## Frozen comparison

| Frozen method / terminal point | Weighted OOF AUC | Maximum OOF ZZ KS | Status |
|---|---:|---:|---|
| Full14 | 0.8852959102354316 | 0.4579540115915921 | Historical frozen reference |
| DropTop4, no reweighting | 0.7996529199780816 | 0.34469234042569663 | Historical frozen reference |
| Full14 + reweighting, iteration 5 | 0.8523982143190011 | 0.24583464407366806 | `no_eligible_iteration` |
| DropTop4 + reweighting, iteration 5 | 0.7588712973047708 | 0.09720271279351 | `no_eligible_iteration` |
| DropTop4 KNN flatness, final candidate | 0.7566586485761435 | 0.20566162971445773 | `no_eligible_candidate` |
| Angular5 + DropTop4 + reweighting, iteration 5 | 0.7665404021047497 | 0.090638729937013 | `no_eligible_iteration` |

The Angular5 final iteration is modestly better than the frozen ten-feature
DropTop4 reweighting endpoint on both AUC and maximum KS, and it has much lower
KS than the KNN flatness endpoint. It remains ineligible because its AUC is
below `0.80`. Full14 retains substantially higher discrimination but much
stronger mass sculpting; it is a failed, immutable comparison reference, not a
candidate for repair or deployment.

## Limitations and authorization boundary

This is an educational/technical MC-only study, not an ATLAS result, Higgs
discovery, or physics measurement. It has no real-data validation, no selected
model, no held-out test result, and no systematic uncertainty, control-region,
sideband, or likelihood analysis. This report authorizes no next-stage training:
it does not permit extending this run, adding iterations, changing bins or
features, relaxing AUC >= `0.80` or any KS <= `0.10` gate, opening the held-out
test, or accessing real data. Any future work requires a new predeclared design,
configuration, and run path.
