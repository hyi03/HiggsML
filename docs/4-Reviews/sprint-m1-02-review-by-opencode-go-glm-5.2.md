# Sprint M1-02 / FR-001 Document Review Report

- **Reviewer:** opencode-go / glm-5.2
- **Review date:** 2026-09-01
- **Review type:** Document review (revised set; no documents or code were modified; xgboost inspected read-only as characterization evidence only)
- **Primary target:** `neural/docs/sprint-m1-02.md`
- **Required linked targets reviewed:**
  - `neural/docs/preprocess-protocol-v1.md` (new self-contained normative spec, this revision)
  - `neural/docs/FR-001-adversarial-mlp-refactor.md` (v1.2, "已确认，实施中")
  - `neural_adversarial_mlp_refactor_design.md` (root, authoritative)
  - `AGENTS.md` (repository root)
  - `neural/AGENTS.md`
- **Read-only evidence inspected (xgboost source/configs + neural state):**
  - `xgboost/src/input_profiles.py`, `selection.py`, `split.py`, `weights.py`, `reconstruction.py`, `pairing.py`, `features.py`, `angular5.py`, `angular5_identity.py`, `angular5_enrichment.py`, `io.py`, `pipeline.py`
  - `xgboost/config/angular5_mc_dsid363490_r3_arm64.yaml`
  - `neural/src/cli/preprocess.py` (help-only stub), `neural/config/` (only `.gitkeep`), `neural/tests/`
- **Authority status:** The r3-ARM64 golden artifacts are external/absent on this device. Per the owner-approved policy and the Sprint's own rule, this absence is an un-met conditional verification gate (`authoritative_gate_not_run`), not evidence of equivalence, and is treated accordingly below.

---

## 1. Executive Summary

The revised document set is **decision-complete for M1-02 implementation**. Every operative scientific constant and convention required to build the behavior-equivalent MC-only preprocessor is now written into `neural/docs/preprocess-protocol-v1.md` — per-sample ROOT profiles and unit conversion (§2.3), full selection with stage order and boundary inclusivity (§3), normalization and both weight formulas (§5.1), canonical identity and the legacy-duplicate fact (§5.2), the stable split algorithm (§5.3), Base14/Angular5 construction, frames, signs and degenerate behavior (§4), deterministic row/column order (§6), canonical CSV/gzip serialization (§6.3), the pinned golden authority chain (§7.1), the equivalence predicate (§7.2), all three JSON schemas (§8), and the CLI/exit-code/test contract (§9).

The two prior Critical gaps are closed and cross-confirmed by on-disk evidence: (1) the per-column golden authority is pinned as `xgboost/runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/mc_events_angular5.csv.gz`, SHA-256 `bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09`, identically in `sprint-m1-02.md` §6, `FR-001` R2, and protocol §7.1; (2) the equivalence predicate is predeclared as structural fields exact and floats elementwise `isclose(rtol=1e-12, atol=1e-12, equal_nan=False)` on the locked native `osx-arm64` environment (protocol §7.2, sprint §6, FR-001 R2). I independently re-derived the protocol's values from `xgboost/src` and the frozen r3 config: profiles, selection constants/boundaries, ZZ normalization override (`1.2564 / 1.0 / 1.0 / 7538705.808`, `L=10000.0`), split hash (`blake2b(digest_size=8)` big-endian `% 10` on `"{channel}:{event}"`), Base14/Angular5 math and cosine tolerance `1e-12`, `.17g` serialization, and the r3 identity-chain SHA-256s — all match the legacy implementation. The fixed counts (419,943/554,279 reads; 187,128/11,976 selected; 119,676/39,719/39,709 splits; dev 159,395) are internally consistent and match the frozen evidence.

Remaining findings are refinements, not blockers: three Medium (a stale run-config sentence in the design, an ambiguous manifest-outputs sentence, and an undocumented `beta=0` identity-boost edge case in the boost formula) and four Low (a cutflow-stage wording slip, a cutflow stage-by-stage comparison the protocol should state explicitly, sprint-vs-protocol run-config wording, and the protocol header status wording). Two Info items note facts that can only be confirmed by the authority gate itself. No finding requires reading real data; the MC-only boundary is clean and unchanged.

**Findings count:** 0 Critical · 0 High · 3 Medium · 4 Low · 3 Info.

---

## 2. Review Findings

| # | Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|---|
| 1 | Medium | Internal consistency | `neural_adversarial_mlp_refactor_design.md` §6.1 (L156); `preprocess-protocol-v1.md` §2.2 (L51) | The root design says run config carries "ROOT 路径、输出路径、chunk size 和资源参数" (output path included), but the protocol — the newer, M1-02-normative doc — explicitly forbids an output path in run config ("输出路径只通过必填 `--run-dir` 提供"). The two authoritative docs disagree on where the output path lives. | Design §6.1 L156: "运行配置只允许指定 ROOT 路径、输出路径、chunk size 和资源参数". Protocol §2.2 L51: "输出路径只通过必填 `--run-dir` 提供". Protocol §2.2 whitelist (schema_version/samples/resources) contains no output field. | Amend design §6.1 to drop "输出路径" from the run-config contents (or add a supersession note pointing to protocol §2.2). The protocol's rule is correct and must govern; the design sentence should not contradict it. |
| 2 | Medium | Specification / clarity | `preprocess-protocol-v1.md` §8.3 (L419–420) | The manifest outputs sentence is ambiguous about whether `mc_summary.json` is listed: "Manifest 必须列出 `config.yaml`、MC 表、cutflow、summary 自身以外的全部已发布输出" parses either as "list config.yaml/MC table/cutflow plus every output except the summary" (excluding the summary from the manifest, which would be odd) or as a slip for "manifest 自身" (list everything except the manifest, matching the no-self-reference rule). An implementer cannot tell whether `mc_summary.json` belongs in `outputs`. | §8.3: "Manifest 必须列出 `config.yaml`、MC 表、cutflow、summary 自身以外的全部已发布输出；最终 manifest 的文件哈希由上层目录审计，不自引用。" The intended set should be all published outputs (config.yaml, MC table, cutflow, mc_summary.json) except manifest.json. | Reword to "列出全部已发布输出（`config.yaml`、MC 表、cutflow、`mc_summary.json`），但排除 manifest 自身（不自引用）", or enumerate the outputs explicitly. |
| 3 | Medium | Specification / edge case | `preprocess-protocol-v1.md` §4.3 (L205–212) | The Lorentz-boost spec omits the `beta = 0` identity-boost special case present in the legacy implementation. The protocol's formula divides by `\|beta\|²`, which is undefined at `beta = 0`; the protocol's failure list covers `\|beta\| >= 1`, zero energy, non-finite components, and zero-norm normalization, but not `\|beta\| = 0`. This is reachable when a Z or the 4-lepton system is at rest in the lab, and a literal transcription would diverge from legacy (which returns the vector unchanged). | `xgboost/src/angular5.py` L105–106: `if beta2 == 0.0: return FourVector(vector.energy, vector.px, vector.py, vector.pz)` before the gamma/formula path. Protocol §4.3 gives only the general formula and the `\|beta\| >= 1` failure. | Add "当 `\|beta\| = 0` 时不作变换（identity boost），向量原样返回" to §4.3 so new and legacy behavior agree on the degenerate rest-frame case. |
| 4 | Low | Wording / consistency | `preprocess-protocol-v1.md` §3.1 (L139–140) | "前八个质量阶段均要求存活轻子数至少为四" is self-contradictory: counting the cutflow list, the first seven quality stages (trigger … longitudinal_impact_parameter) require ≥ 4 survivors and the 8th (`exactly_four_good_leptons`) requires exactly 4. Taken literally, the sentence asks the 8th stage to satisfy both. | Protocol §3.1 L139–140 vs the 19-key order in the same section; `xgboost/src/selection.py` L31–51 confirms `exactly_four_good_leptons` follows the seven ≥-4 stages and is itself `len(indices) != 4 → fail` (L626–627). | Reword to "`exactly_four_good_leptons` 之前的各质量阶段均要求存活轻子数至少为四；`exactly_four_good_leptons` 要求恰好四个"（或写 "前七个质量阶段"）。 |
| 5 | Low | Verification specificity | `preprocess-protocol-v1.md` §7.2 (L343–349) | The exact-comparison list names "sample/read/selected/split counts" and the fixed-counts table, and §7.1 binds the baseline cutflow.json, but the protocol never explicitly requires stage-by-stage cutflow counts to equal the bound legacy `cutflow.json` for both samples. The sprint (§5.3) says "比较 … cutflow", but the protocol's golden predicate is the document that must make it precise. | Protocol §7.1 binds `xgboost/runs/full-baseline-363490-2026-08-11-r2/artifacts/cutflow.json` via manifest `10e0c293…`; §7.2's Exact list (L343–345) enumerates counts but not per-stage cutflow equality. | Add to §7.2: "Exact：两个样本的逐级 cutflow count 必须与 §7.1 绑定 manifest 对应同 run 的 `cutflow.json` 逐级一致"（及效率/加权产额按 §8.1 格式）。 |
| 6 | Low | Consistency | `sprint-m1-02.md` §3 (L42–43); `preprocess-protocol-v1.md` §2.2 (L37–51) | The Sprint's run-config description ("只能包含两个 ROOT 路径和 `chunk_size_events`") omits the `schema_version: "1.0"` key and the `samples:`/`resources:` nesting that the protocol §2.2 whitelist requires. Descriptive rather than normative, but the two docs should say the same thing. | Sprint §3 L42–43 vs protocol §2.2's exact whitelist YAML and the "拒绝重复 YAML key 和任何额外键" rule. | Align the Sprint sentence with the protocol whitelist, e.g. "只能包含 `schema_version`、两个样本的 `path` 和 `chunk_size_events` 这几种内容". |
| 7 | Low | Status wording | `preprocess-protocol-v1.md` header (L3–4); `sprint-m1-02.md` §10 (L167) | The protocol header declares "文档状态: 已批准，等待实现验证" while the Sprint §10 states the protocol "等待双模型文档复审和确认". The owner's 2026-09-01 approval covers the golden/equivalence policy, not necessarily final sign-off of the full protocol text; the two status labels should not conflict. | Protocol L3–4 ("已批准") vs Sprint §10 L167 ("等待双模型文档复审和确认"). | Clarify what "已批准" refers to (owner-approved golden/equivalence policy) or align the status wording across the two docs. |
| 8 | Info | Verification-dependent | `preprocess-protocol-v1.md` §5.2 (L270–273), §7.1 (L332–336) | The specific legacy duplicate source-entries (Higgs `102001` at entries `173348/345900`, `1136001` at `340911/342358`) and the cutflow-lineage manifest SHA-256 `10e0c293…` are data/artifact-dependent and cannot be verified on this device (r3 artifacts external/absent). They are not contradicted by any on-device evidence, but they are confirmed only when the authority gate runs. | r3 identity/enrichment table and `full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json` are not present on this device; §7.2 correctly mandates `authoritative_gate_not_run` when absent. | At gate execution, verify the two duplicate groups/4 rows and the `10e0c293…` manifest SHA against the bound artifacts before comparing per-column values. This is gate-internal verification, not a spec change. |
| 9 | Info | Positive / Golden & predicate transcription | `sprint-m1-02.md` §6; `FR-001` R2; `preprocess-protocol-v1.md` §7 | The owner-approved policy (structural exact; floats `rtol=1e-12, atol=1e-12`; gate only on locked native `osx-arm64`) is transcribed identically across all three documents, and the pinned authority chain SHA-256s (`74ebc01e…` identity manifest, `a3ffd8c5…` identity table, `ab5e283f…` enrichment manifest, `bc31f4e6…` authoritative table) match the on-disk r3 config and prior frozen-run evidence. Fixed counts are internally consistent (419,943+554,279=974,222 reads; 187,128+11,976=199,104 selected; 112,502+7,174=119,676 train; 37,290+2,429=39,719 val; 37,336+2,373=39,709 test; dev 159,395). | `xgboost/config/angular5_mc_dsid363490_r3_arm64.yaml` L8–12, L17, L23–40; protocol §7.2 table; sprint §6 L120–123; FR-001 R2 L58–63. | None; preserve verbatim. |
| 10 | Info | Positive / Safety inheritance | `preprocess-protocol-v1.md` §1, §2, §9; `sprint-m1-02.md` §4, §6, §9; `neural/AGENTS.md` | Scientific-safety boundaries are fully preserved and now closed-form: MC-only (only Higgs 345060 / ZZ 363490), no real-data read/hash/artifact, fail-closed on hash/schema/non-finite/DSID 700600 with exit code 3, no `xgboost/src` runtime import, immutable runs, no frozen-artifact modification, and synthetic micro-ROOT fixtures generated in-test only (no committed ROOT or MC-derived fixtures; literal expected values allowed as test constants). Forbidden features (`m4l`, identifiers, weights) stay out of the v1 classifier (fixed 15 features). | Protocol §1 (L17–20), §2.1 (L31–33), §9 (L437–439); sprint §6 (L124), §9 (L154–156); matches root `AGENTS.md` and `neural/AGENTS.md` without relaxing any rule. | None; maintain verbatim in the YAML transcription and tests. |

---

## 3. Decision-Completeness Assessment by Topic

Assessment basis: `sprint-m1-02.md` plus its normative references (protocol, FR-001, design, AGENTS), with xgboost inspected read-only to confirm the protocol's transcription is faithful.

| Topic | Verdict | Where the decision now lives |
|---|---|---|
| ROOT schema & per-sample profiles | **Complete** | Protocol §2.1 (files, DSID, label, SHA-256, entry counts) + §2.3 (tree, unit, full branch map per profile; MeV→GeV scaling; `channelNumber == DSID` check; `zz.root`/700600 rejection). Matches `input_profiles.py` verbatim. |
| Selection constants, stage order, boundaries | **Complete** | Protocol §3.1 (19-key order) + §3.2 (all thresholds, strict/inclusive bounds, `105 <= m4l < 160`, sorted-lepton pt thresholds `>= 20/15/10/7`, fixed Z2). Matches `selection.py` and the r3 config. |
| Normalization & weights | **Complete** | Protocol §5.1: `L=10000.0`, Higgs event-branch constants with `rtol=1e-12, atol=0` in-sample check; ZZ override `1.2564/1.0/1.0/7538705.808`; physical-weight formula; per-sample pre-merge `abs/mean` `train_weight` with all-ones fallback. Matches `weights.py`/`pipeline.py`. |
| Canonical identity | **Complete** | Protocol §5.2: `(source_sample, source_entry)`, strings `higgs_345060`/`zz_363490`, zero-based pre-selection per-file entry index, chunk-continuous, globally unique; legacy-key duplicates 2 groups/4 rows documented. Matches `angular5_identity.py`/`io.py`. |
| Stable split | **Complete** | Protocol §5.3: `blake2b(f"{channel}:{event}", digest_size=8)` big-endian `% 10`, buckets `<6`/`6–7`/`8–9`. Matches `split.py` exactly, including channelNumber in the payload. Five-fold dev hash correctly deferred to a later Sprint. |
| Base14/Angular5 conventions | **Complete** | Protocol §4.1–§4.4: partitions, Z-mass 91.1876 tie-break, Δφ/ΔR, `deltaPhi_ZZ` absolute, pt-descending stable lepton order, boost, cosine tolerance `1e-12`, signed-angle wrap `[-π, π)`, negative-lepton orientation, degenerate → fail-closed. Matches `pairing.py`/`features.py`/`angular5.py`. One edge case omitted (finding 3). |
| Row order & column mapping | **Complete** | Protocol §6.1 (29 columns, exact order) + §6.2 (Higgs then ZZ, ascending `source_entry`) + §7.2 (compare 29 same-named columns, excluding the five old normalization columns). |
| Canonical serialization | **Complete** | Protocol §6.3: UTF-8 no BOM, LF, header one line, floats `.17g`, `-0`→`0`, integers base-10, enum whitelist, `canonical_content_sha256` over decompressed bytes, `gzip.compress(..., compresslevel=9, mtime=0)` + gzip SHA-256. |
| Golden authority | **Complete** | Protocol §7.1 pins the four-artifact chain with SHA-256s (corroborated by the r3 config and prior evidence); sprint §6 and FR-001 R2 pin the authoritative table identically. Cutflow lineage bound via baseline manifest `10e0c293…` (gate-verifiable, finding 8). |
| Equivalence predicate | **Complete** | Protocol §7.2: exact for structure/integers/enums/order/counts/duplicates; floats `isclose(rtol=1e-12, atol=1e-12, equal_nan=False)`; known `9.66e-13` mZ1 cross-arch diff covered; gate only on locked `osx-arm64`; absent artifact → `authoritative_gate_not_run`. |
| Artifact schemas | **Complete** | Protocol §8.1–§8.3: `cutflow.json`, `mc_summary.json`, `manifest.json` field lists + schema_version `"1.0"` + `allow_nan=false`; manifest published last, no self-reference, inputs re-verified at publish. One wording fix needed (finding 2). |
| CLI, exit codes, tests, fixtures | **Complete** | Protocol §9: exact CLI contract, exit codes 0/2/3/4/70 (5 reserved for later training gates, consistent with `neural/AGENTS.md`), test coverage list, synthetic micro-ROOT fixture policy, full-gate conditionality. |

**Overall: all prioritized topics are decision-complete in the neural document set.** The remaining items are three Medium and four Low refinements; none requires an implementer to guess a scientific constant, read legacy source for a value, or touch real data.

---

## 4. Points That Would Still Require Judgment (Bound to Refinements Above)

1. **Boost `beta = 0` (rest-frame) handling** — the formula is undefined at `|beta|=0`; legacy returns the vector unchanged (finding 3). An implementer must choose the identity-boost behavior until the protocol states it.
2. **Whether `mc_summary.json` appears in the manifest `outputs` array** — ambiguous wording in §8.3 (finding 2).
3. **Per-stage cutflow equality with legacy** — implied by the sprint and lineage binding but not stated as an exact predicate (finding 5).
4. **Design §6.1 "输出路径" in run config vs protocol §2.2** — which document governs (finding 1; protocol should).
5. Cutflow-stage wording (finding 4), run-config description (finding 6), and status label (finding 7) — cosmetic but should be harmonized.

**Real-data exposure: none.** Every input named in the neural contract is bound MC (Higgs 345060, ZZ 363490) with SHA-256; real-data paths and the historical `zz.root`/700600 are explicitly rejected fail-closed (exit 3). The MC-only boundary is clean and must be preserved exactly.

---

## 5. Resolution of the Prior Review's Gaps

- **Prior Critical 1 (golden authority unpinned):** RESOLVED — pinned in sprint §6, FR-001 R2, protocol §7.1; corroborated by the on-disk r3 config and frozen-run evidence.
- **Prior Critical 2 (equivalence predicate undefined):** RESOLVED — exact structural + `isclose(1e-12, 1e-12, equal_nan=False)`, gate on locked native `osx-arm64` (protocol §7.2, sprint §6, FR-001 R2), with the known `9.66e-13` cross-arch diff pre-registered as covered.
- **Prior 9 High (ROOT schema, profiles, selection, normalization, identity, split, Base14/Angular5, row/column mapping, canonical serialization, protocol content):** ALL RESOLVED in protocol §§2–6, verified faithful against `xgboost/src` and the frozen r3 config.
- **Prior 4 Medium (artifact schemas, fixture provenance, ZZ file naming, golden platform):** ALL RESOLVED (protocol §§8–9, §2.1, §7.2).
- **Prior 3 Low (golden strengthening, verification command, §10 placeholder):** ALL RESOLVED (protocol §7.2 counts table, sprint §7 `preprocess_run.local.yaml` reference, populated §10).

---

## 6. AGENTS.md Compliance Check

- **Root `AGENTS.md`:** No scientific-safety rule relaxed. No `m4l`/identifiers/provenance/weights as features; no real data; no frozen-run modification; educational framing preserved; "do not commit generated data" respected by the synthetic-fixture policy (protocol §9).
- **`neural/AGENTS.md`:** Consistent — MC-only, protocol owns science / run config owns paths, fail-closed exit codes map to the 0/2/3/4/70 table, no authority claim without the locked `osx-arm64` run (protocol §7.2, sprint §7).
- **`xgboost/AGENTS.md`:** Treated as read-only characterization/golden evidence only; no runtime import. The historical `zz.root`/700600 guidance there is explicitly rejected as a neural input (protocol §2.1), so the neural docs do not inherit the stale file binding.

---

## 7. Implementation-Gate Verdict

**Gate: PASS — decision-complete for M1-02 implementation.**

The revised document set is sufficient for an independent implementer to build the behavior-equivalent MC-only preprocessor without guessing a scientific constant, reading legacy source for a value, or opening real data. Proceed to implementation on this basis, with the following handling of the open refinements:

- **Fix before or early during implementation (recommended, not blocking):** the three Medium items — design §6.1 run-config output-path sentence (finding 1), the manifest-outputs wording in protocol §8.3 (finding 2), and the `beta=0` identity-boost edge case in protocol §4.3 (finding 3) — so the YAML transcription cannot diverge from legacy on these points.
- **Track the four Low wording/verification items** (findings 4–7) as small protocol/sprint harmonization edits.
- **Conditional authority gate (unchanged, per owner approval):** the full-data, per-column golden comparison runs only on the locked native `osx-arm64` environment with the two bound ROOT files and the r3-ARM64 artifacts present. On this device the r3 artifacts are external/absent; the gate is therefore recorded as `authoritative_gate_not_run` and full column-wise equivalence must **not** be claimed until it passes. Synthetic micro-ROOT and Windows results do not substitute for the gate.
- **Verification before Sprint completion:** `conda run -n pytorch python -m pip check` and `conda run -n pytorch python -m pytest -q`, plus the M1-02 micro-ROOT/determinism/fail-closed tests, on the `pytorch` environment per `neural/AGENTS.md`.

Only the target report file was written; no source or target documents were modified.
