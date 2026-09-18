# Review: h4l-off-marginal-coupling-v3 spec

Review target: `docs/changes/h4l-off-marginal-coupling-v3/spec.md`  
Review type: document review  
Reviewer: GPT-5.5

## Summary

The v3 direction is well motivated and mostly consistent with the repository's current evidence boundary: it introduces a new versioned contract, preserves v1/v2 history, avoids joint-cell Poisson intensities, and labels CRN dependence as artificial rather than physical-event pairing. I found four actionable issues to resolve before approval or implementation planning.

Evidence reviewed:

- `docs/changes/h4l-off-marginal-coupling-v3/spec.md`
- `AGENTS.md`
- `README.md`
- `docs/README.md`
- `docs/methods-and-evaluation.md`
- `docs/implementation-and-reproduction.md`
- `docs/results-and-limitations.md`
- `config/protocols/h4l_protocol.json`
- `config/schemas/h4l_joint_support_workflow_v1.schema.json`
- `src/higgsml/cli_attribution.py`
- `scripts/h4l_off_run.py`
- `src/higgsml/inference/joint_support.py`
- `src/higgsml/inference/seed_workflow.py`
- `src/higgsml/inference/seed_blocks.py`
- `runs/h4l-off-test01-v2/support-j0/joint-support-summary.json`

The inspected v2 J0 artifact supports the spec's stated failure diagnosis: status is `failed`, `assessment_payload_read=false`, all five seeds fail with `negative_process_rate`, cell counts are 2238-2522, each seed has 62 projected marginal rates, projection mismatch count is 0, and maximum projection error is about `1.51e-13`.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Correctness | `docs/changes/h4l-off-marginal-coupling-v3/spec.md:100-103`, `docs/changes/h4l-off-marginal-coupling-v3/spec.md:125-133` | The spec does not define how `Lambda[p,b]` is canonically selected after candidate-total equality is checked within tolerance. This can make v3 Toys non-reproducible across implementations or parallel workers, and can slightly change marginal rates depending on whether the implementation uses the first candidate, an average, a direct parent total, or a compensated sum. | The spec defines `Lambda[c,p,b]` and says candidate totals must agree at tolerance, then later samples `N[p,b] ~ Poisson(Lambda[p,b])` without defining that scalar. The risk section recognizes summation-order sensitivity, but acceptance criteria only require bitwise output tests, not a canonical total rule. | Add a normative rule such as: after deterministic accumulation and tolerance validation, `Lambda[p,b]` is computed from a named canonical source, for example the direct parent process/bin total or a fixed reference candidate, with exact serialization into the stream/coupling receipt. Include a test where candidates differ only by allowed floating-point summation noise and prove the selected `Lambda[p,b]` is stable. |
| High | Correctness | `docs/changes/h4l-off-marginal-coupling-v3/spec.md:100-103`, `runs/h4l-off-test01-v2/support-j0/joint-support-summary.json` | The fallback from audited `process` to `label_legacy` is underspecified for signal injection. If the parent lacks an audited process field, v3 still needs an explicit, bound mapping from legacy labels to signal/background before multiplying only signal by `mu`; otherwise an implementation can apply `mu` to the wrong process or allow signal/background cancellation under a relabeling mistake. | The spec says signal rates are multiplied by `mu` and process identity uses `process` when available, otherwise `label_legacy`. The inspected v2 J0 artifact records `process_identity_source="label_legacy"` and process IDs `"0"`/`"1"`, so this is not hypothetical for the current evidence path. | Require a version-bound process role map for every process identity, including `label_legacy`, and make missing or ambiguous signal/background classification a binding error. Add an acceptance test that a legacy-label parent with swapped or missing role mapping is rejected before rate construction. |
| Medium | Clarity | `docs/changes/h4l-off-marginal-coupling-v3/spec.md:130-133`, `docs/changes/h4l-off-marginal-coupling-v3/spec.md:173-176`, `config/schemas/h4l_joint_support_workflow_v1.schema.json:4`, `src/higgsml/inference/joint_support.py:189-226` | The symbol `q` is overloaded between the v3 category split probability `q[c,p,b]` and the existing J1 Bernoulli-thinning policy `q`. This is easy to misimplement because J1 currently accepts a scalar thinning `q`, while the new coupling defines per-candidate/per-process/per-bin category probabilities. | The spec defines `q[c,p,b] = lambda[c,p,b,1] / Lambda[p,b]`, then says J1 retains registered `q`. The current workflow schema requires `policy.q`, and `run_j1(..., q: float, ...)` uses it for group thinning. | Rename one side in the spec. For example, call the coupling probability `theta[c,p,b]` and reserve `q_thin` for J1 group thinning. Update acceptance criteria to check both quantities are recorded distinctly in v3 artifacts and receipts. |
| Medium | Consistency | `docs/changes/h4l-off-marginal-coupling-v3/spec.md:60-61`, `docs/changes/h4l-off-marginal-coupling-v3/spec.md:209-211`, `docs/implementation-and-reproduction.md:347-349`, `docs/results-and-limitations.md:176`, `src/higgsml/cli_attribution.py:16`, `scripts/h4l_off_run.py:48` | The spec changes the one-command/default route to v3, but the proof criteria do not require updating user-facing docs or asserting CLI default/compatibility behavior. This is a high-risk contract migration because current docs and CLIs state or implement `v1` as the default and only allow `v1|v2`. | Current reproduction docs say "v1 remains the default"; results docs say v2 preserves v1 as default; both `cli_attribution.py` and `h4l_off_run.py` currently use `choices=['v1','v2'], default='v1'`. The spec mentions adding `v3`, but acceptance criteria only say v1/v2 golden tests continue to pass. | Add migration acceptance criteria covering documentation updates, `--evaluation-version v1|v2|v3` behavior for every listed entry point, explicit default behavior for `h4l_all.py`, and a regression that an omitted version routes to v3 only after the approved migration point while explicit v1/v2 remain unchanged. |

## Non-Blocking Notes

- The spec correctly avoids reclassifying the failed v2 J0 artifact as v3 evidence and requires fresh v3 claims and run roots.
- The evidence boundary language is strong: controlled-MC engineering checks, software tests, and assessment/T2 authorization remain separate.
- The artificial covariance risk is explicitly acknowledged; implementation should preserve that language in reports and CSV/data-dictionary fields, not just in prose.

