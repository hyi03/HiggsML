# DropTop4 + Angular5 Source-Identity R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the approved Angular5 study with a stable raw-ROOT source identity, execute the three fresh R2 MC-only runs once, and publish the exact terminal training result.

**Architecture:** Add an opt-in raw TTree entry index at the ROOT I/O boundary, use it to build a separately sealed identity baseline that preserves every old authoritative CSV token, and make R2 enrichment join only on `(source_sample, source_entry)`. Bind each successful production receipt into the next strict configuration before implementing/executing its consumer; retain the reviewed original Angular5 mathematics and reweighting algorithm unchanged.

**Tech Stack:** Python 3.11+, NumPy, pandas, uproot/awkward, PyYAML, scikit-learn, XGBoost, pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-drop-top4-angular5-source-identity-r2-design.md`

## Global Constraints

- The failed `runs/angular5-mc-363490-2026-08-26` terminal is immutable and is never repaired, removed, completed, or reused.
- R2 is MC-only: no configuration, CLI, source inventory, manifest, artifact, plot, or report may resolve or inspect real data.
- `source_sample` is exactly `higgs_345060` or `zz_363490`; `source_entry` is the zero-based raw TTree entry index before selection.
- `(source_sample, source_entry)` is the sole R2 enrichment join identity; duplicate legacy `(runNumber,eventNumber,channelNumber)` values are retained and reported.
- The authoritative old CSV supplies every old lexical token, parsed value, label, weight, split, and row order. Identity/enrichment runs append columns only.
- Existing Angular5 formulae and ordered five-column output remain unchanged.
- Existing selection, pairing, normalization, split values, model candidates, folds, seeds, mass bins, multiplier policy, iteration cap, AUC/KS/efficiency gates, and test sealing remain unchanged.
- `source_sample` and `source_entry` are provenance and forbidden model features.
- Every production run uses its exact fresh R2 path, descriptor-bound no-clobber writes, source/output freshness checks, failure-only terminal behavior, and manifest-last publication.
- Run the focused tests after each behavior change and the full suite before each one-time production command.

---

### Task 1: Stable raw ROOT source entries

**Files:**
- Modify: `src/io.py`
- Modify: `tests/test_io.py`

**Interfaces:**
- Consumes: existing `iter_events(...)` ROOT iteration behavior.
- Produces: `iter_events(..., include_source_entry: bool = False)`; when enabled, each event contains integer `source_entry` equal to its zero-based raw TTree entry.

- [ ] **Step 1: Write failing source-entry tests**

  Add a tiny five-entry ROOT fixture and assert literal indices for multiple chunk sizes:

  ```python
  for chunk_size in (1, 2, 5):
      rows = list(iter_events(path, is_data=False, chunk_size_events=chunk_size,
                              include_source_entry=True))
      assert [row["source_entry"] for row in rows] == [0, 1, 2, 3, 4]
  ```

  Also assert `entry_stop=3` yields `[0, 1, 2]`, repeated reads agree, the default event schema omits `source_entry`, and a requested canonical ROOT branch cannot overwrite the generated identity.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_io.py -q`

  Expected: FAIL because `iter_events` does not accept `include_source_entry`.

- [ ] **Step 3: Implement the opt-in entry counter**

  Initialize one counter immediately before `tree.iterate`; attach its current integer value to each event before yield and increment once for every raw entry, independent of selection and chunk boundaries. Reject `source_entry` in `extra_canonical_branches` so a physical branch cannot spoof it.

- [ ] **Step 4: Verify GREEN**

  Run: `.venv/bin/python -m pytest tests/test_io.py tests/test_input_profiles.py -q`

  Expected: all pass.

- [ ] **Step 5: Commit**

  ```bash
  git add src/io.py tests/test_io.py
  git commit -m "feat: expose stable ROOT source entries"
  ```

### Task 2: Pure identity-bootstrap transformation

**Files:**
- Create: `src/angular5_identity.py`
- Create: `tests/test_angular5_identity.py`

**Interfaces:**
- Consumes: authoritative gzip CSV bytes and per-sample reconstructed rows containing all old fields plus `source_sample` and `source_entry`.
- Produces: `IdentityOutcome`, `build_source_identity_baseline(authoritative_gzip: bytes, reconstructed: Mapping[str, pd.DataFrame]) -> IdentityOutcome`, and immutable final gzip/evidence payloads.

- [ ] **Step 1: Write failing behavior tests**

  Use precision-sensitive literal CSV tokens and two distinct rows sharing the same legacy key. Assert:

  ```python
  assert output.columns[-2:].tolist() == ["source_sample", "source_entry"]
  assert output[["source_sample", "source_entry"]].values.tolist() == [
      ["higgs_345060", 17], ["higgs_345060", 29], ["zz_363490", 4]
  ]
  ```

  Decompress the final gzip and prove each old row prefix is byte-for-byte the authoritative prefix. Reparse the final bytes and assert exact old-column values/order. Add failures for reordered reconstructed rows, any old-field mismatch, missing/extra rows, duplicate canonical identities, invalid sample names, non-integer entries, and mutable returned evidence.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_angular5_identity.py -q`

  Expected: collection fails because `src.angular5_identity` is absent.

- [ ] **Step 3: Implement literal-preserving bootstrap**

  Parse the authoritative frame once, partition it in original order by channel, compare every old parsed field row-for-row to its reconstructed sample, then append escaped CSV tokens for the two identity columns to the original header/physical records. Parse and revalidate the exact final gzip before returning an opaque token-constructed outcome whose frame property returns a fresh parse.

- [ ] **Step 4: Verify GREEN**

  Run: `.venv/bin/python -m pytest tests/test_angular5_identity.py tests/test_angular5_enrichment.py -q`

  Expected: all pass and original enrichment regressions remain green.

- [ ] **Step 5: Commit**

  ```bash
  git add src/angular5_identity.py tests/test_angular5_identity.py
  git commit -m "feat: build authoritative MC source identities"
  ```

### Task 3: Sealed identity run, publication, and CLI

**Files:**
- Create: `config/angular5_identity_mc_dsid363490_r2.yaml`
- Create: `src/angular5_identity_run.py`
- Create: `scripts/build_angular5_identity_mc.py`
- Create: `tests/test_angular5_identity_run.py`
- Create: `tests/test_build_angular5_identity_mc_script.py`

**Interfaces:**
- Consumes: Task 1 source entries, Task 2 transformation, exact five protected input hashes from the R2 spec.
- Produces: strict config/source receipts, `build_identity_mc(sources)`, four-artifact manifest-last publication, and CLI with only `--config`/`--run-dir`.

- [ ] **Step 1: Write failing strict-boundary tests**

  Cover the exact two MC samples, copied selection/profiles/normalization, full read policy, frozen source hashes, duplicate-YAML rejection, deep immutability, descriptor-bound input snapshots, symlink/mutation/race refusal, exact output path, atomic claim, and zero data surface.

  Add real tiny ROOT integration with two distinct Higgs entries sharing one legacy key. Require both rows to survive with distinct source entries and require a row-order swap to fail semantic alignment.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_angular5_identity_run.py tests/test_build_angular5_identity_mc_script.py -q`

  Expected: collection/config failures because the R2 run boundary is absent.

- [ ] **Step 3: Implement the sealed identity command**

  Reuse reviewed descriptor/no-follow helpers without weakening them. Stream ROOT with `include_source_entry=True`, attach the exact configured sample name before selection, reconstruct old fields with the existing pipeline policy, delegate token preservation to Task 2, and publish exactly:

  ```text
  config.yaml
  processed/mc_events_source_identity.csv.gz
  artifacts/identity_validation.json
  artifacts/run_manifest.json
  ```

  Catch `BaseException` only to install the terminal and re-raise. Promote the complete manifest last after input/output revalidation.

- [ ] **Step 4: Verify GREEN and full baseline**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/test_io.py tests/test_angular5_identity.py \
    tests/test_angular5_identity_run.py tests/test_build_angular5_identity_mc_script.py -q
  .venv/bin/python -m pytest -q
  ```

  Expected: all pass; only the five known unrelated `hep_ml` warnings may remain in the full suite.

- [ ] **Step 5: Commit**

  ```bash
  git add config/angular5_identity_mc_dsid363490_r2.yaml src/angular5_identity_run.py \
    scripts/build_angular5_identity_mc.py tests/test_angular5_identity_run.py \
    tests/test_build_angular5_identity_mc_script.py
  git commit -m "feat: publish sealed Angular5 source identities"
  ```

### Task 4: Execute and freeze the identity baseline

**Files:**
- Create after actual receipt exists: `config/angular5_mc_dsid363490_r2.yaml`
- Create: `src/angular5_enrichment_r2_run.py`
- Create: `tests/test_angular5_enrichment_r2_run.py`

**Interfaces:**
- Consumes: one successful identity production run and its literal manifest/table SHA-256 values.
- Produces: audited identity artifacts and a strict R2 enrichment source/config boundary bound to those actual values.

- [ ] **Step 1: Verify production prerequisites**

  Run SHA-256 checks for the five protected sources, confirm `runs/angular5-identity-mc-363490-2026-08-26-r2` is absent/non-symlink, and confirm `git status --short` contains no tracked changes.

- [ ] **Step 2: Execute the identity run exactly once**

  ```bash
  .venv/bin/python -m scripts.build_angular5_identity_mc \
    --config config/angular5_identity_mc_dsid363490_r2.yaml \
    --run-dir runs/angular5-identity-mc-363490-2026-08-26-r2
  ```

  Audit the exact four-file allowlist, manifest-last ordering, 199,104 rows, two legacy duplicate groups/four rows, and distinct canonical identities.

- [ ] **Step 3: Write failing R2 source-binding tests**

  Capture the actual identity manifest/table hashes with `shasum -a 256`. Build the repository config using those exact literal values. Test exact schema/path/hash/output allowlists, complete identity manifest contract, row count, source receipts, no-symlink/freshness behavior, and zero real-data fields.

- [ ] **Step 4: Verify RED, implement binder, verify GREEN**

  Run before implementation: `.venv/bin/python -m pytest tests/test_angular5_enrichment_r2_run.py -q`

  Expected: collection failure for missing module.

  Implement strict `R2EnrichmentSources`, `resolve_angular5_r2_sources`, `claim_angular5_r2_output`, freshness/failure/publication helpers. Then rerun the same command and require all pass.

- [ ] **Step 5: Commit actual frozen receipts and binder**

  ```bash
  git add config/angular5_mc_dsid363490_r2.yaml src/angular5_enrichment_r2_run.py \
    tests/test_angular5_enrichment_r2_run.py
  git commit -m "feat: bind Angular5 R2 identity baseline"
  ```

### Task 5: R2 identity-based Angular5 enrichment

**Files:**
- Create: `src/angular5_enrichment_r2.py`
- Create: `scripts/enrich_angular5_mc_r2.py`
- Create: `tests/test_angular5_enrichment_r2.py`
- Create: `tests/test_enrich_angular5_mc_r2_script.py`

**Interfaces:**
- Consumes: Task 4 bound identity table, Task 1 raw entry identities, reviewed `build_angular5` formulae.
- Produces: source-identity join, exact five-angle append, five-artifact R2 publication, CLI with only `--config`/`--run-dir`.

- [ ] **Step 1: Write failing R2 join/publication tests**

  Use tiny ROOT/identity fixtures with duplicate legacy keys and literal source identities. Assert exact join on `("source_sample", "source_entry")`, retention of both duplicates, exact old/identity lexical tokens, five-angle order/ranges, and exact output allowlist. Add failures for missing/extra/duplicate source identities, entry drift, semantic mismatch, undefined geometry, mutation/swap races, output collision, `KeyboardInterrupt`, and `SystemExit`.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_angular5_enrichment_r2.py tests/test_enrich_angular5_mc_r2_script.py -q`

  Expected: collection failures because the R2 enrichment implementation is absent.

- [ ] **Step 3: Implement identity join and reviewed publication pattern**

  Snapshot CSV/ROOT through receipt-verified descriptors, calculate Angular5 for selected rows carrying canonical identity, join one-to-one by the two identity columns, preserve every input table token, append only the five angle tokens, reparse/revalidate final gzip bytes, and publish the exact five artifacts with manifest last.

- [ ] **Step 4: Verify GREEN and full suite**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/test_angular5.py tests/test_angular5_enrichment_r2_run.py \
    tests/test_angular5_enrichment_r2.py tests/test_enrich_angular5_mc_r2_script.py -q
  .venv/bin/python -m pytest -q
  ```

  Expected: all pass.

- [ ] **Step 5: Commit**

  ```bash
  git add src/angular5_enrichment_r2.py scripts/enrich_angular5_mc_r2.py \
    tests/test_angular5_enrichment_r2.py tests/test_enrich_angular5_mc_r2_script.py
  git commit -m "feat: enrich Angular5 by stable source identity"
  ```

### Task 6: Execute R2 enrichment and freeze its receipts

**Files:**
- Create after actual receipt exists: `config/mass_bin_reweighting_drop_top4_angular5_r2.yaml`

**Interfaces:**
- Consumes: reviewed Task 5 command and exact fresh R2 enrichment path.
- Produces: audited R2 enriched MC table plus a training config containing its actual manifest/table hashes.

- [ ] **Step 1: Verify prerequisites and execute exactly once**

  Confirm protected and identity-run hashes, full-suite result, clean tracked tree, and absent `runs/angular5-mc-363490-2026-08-26-r2`. Run:

  ```bash
  .venv/bin/python -m scripts.enrich_angular5_mc_r2 \
    --config config/angular5_mc_dsid363490_r2.yaml \
    --run-dir runs/angular5-mc-363490-2026-08-26-r2
  ```

- [ ] **Step 2: Audit the exact terminal artifacts**

  Verify the exact five-file allowlist, 199,104 rows, old/identity token preservation, two duplicate legacy groups/four rows, unique complete source identities, finite angle ranges, source/output receipts, and manifest-last state.

- [ ] **Step 3: Freeze the actual training source receipt**

  Use `shasum -a 256` on the R2 enrichment manifest/table and create the strict schema config with those exact values, the exact 15 ordered features, the frozen DropTop4 references, and unchanged numerical/artifact policies.

- [ ] **Step 4: Commit**

  ```bash
  git add config/mass_bin_reweighting_drop_top4_angular5_r2.yaml
  git commit -m "config: freeze Angular5 R2 training inputs"
  ```

### Task 7: Exact 15-feature R2 training wiring

**Files:**
- Modify: `src/mass_bin_reweighting.py`
- Modify: `src/mass_bin_reweighting_run.py`
- Modify: `scripts/run_mass_bin_reweighting.py`
- Modify: `tests/test_mass_bin_reweighting.py`
- Modify: `tests/test_mass_bin_reweighting_run.py`
- Modify: `tests/test_run_mass_bin_reweighting_script.py`

**Interfaces:**
- Consumes: actual Task 6 config/receipts and existing sealed reweighting algorithm.
- Produces: one exact `drop_top4_plus_angular5` profile and schema-aware loading of `mc_events_angular5.csv.gz` without changing training mathematics.

- [ ] **Step 1: Write failing profile/config/composition tests**

  Assert the literal 15-feature tuple from the spec, explicit rejection of `source_sample`, `source_entry`, all identifiers/weights/split/`m4l`/four removed proxies, exact R2 source contract, and unchanged acceptance of historical Full14/DropTop4 profiles. Tiny end-to-end tests must show exactly 15 model columns, zero test access for no selection, and exactly one test evaluation after first eligibility.

- [ ] **Step 2: Verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/test_mass_bin_reweighting.py \
    tests/test_mass_bin_reweighting_run.py tests/test_run_mass_bin_reweighting_script.py -q
  ```

  Expected: new R2 profile/config tests fail because only historical profiles/schemas are accepted.

- [ ] **Step 3: Add only the sealed R2 branches**

  Add the exact literal tuple and one strict R2 config/source path. Select the enriched table only for that schema. Keep `run_mass_bin_reweighting_study`, folds, candidates, weights, corrections, gates, plots, conditional outputs, and legacy branches unchanged.

- [ ] **Step 4: Verify GREEN and full suite**

  Run the focused command above, then `.venv/bin/python -m pytest -q`; require all pass.

- [ ] **Step 5: Commit**

  ```bash
  git add src/mass_bin_reweighting.py src/mass_bin_reweighting_run.py \
    scripts/run_mass_bin_reweighting.py tests/test_mass_bin_reweighting.py \
    tests/test_mass_bin_reweighting_run.py tests/test_run_mass_bin_reweighting_script.py
  git commit -m "feat: run sealed Angular5 R2 reweighting"
  ```

### Task 8: Execute training, audit, and publish documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/project/overview.md`
- Modify: `docs/physics/data-description.md`
- Modify: `docs/roadmap/next-stage.md`
- Create: `docs/superpowers/plans/2026-08-26-drop-top4-angular5-source-identity-r2-report.md`

**Interfaces:**
- Consumes: all reviewed implementation tasks and exact production receipts.
- Produces: the immutable R2 training terminal and evidence-backed final report/navigation.

- [ ] **Step 1: Verify the final production gate**

  Run `.venv/bin/python -m pytest -q`, verify every protected/identity/enrichment hash, confirm the exact training path is absent/non-symlink, and verify the tracked tree is clean.

- [ ] **Step 2: Execute training exactly once**

  ```bash
  .venv/bin/python -m scripts.run_mass_bin_reweighting \
    --input-run runs/angular5-mc-363490-2026-08-26-r2 \
    --reference-run runs/full-training-363490-2026-08-11-r2 \
    --config config/mass_bin_reweighting_drop_top4_angular5_r2.yaml \
    --run-dir runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26-r2
  ```

  Do not rerun, extend iterations, change features, alter bins, relax gates, or use test/data evidence to revise any choice.

- [ ] **Step 3: Audit the terminal result**

  Verify exact conditional artifact allowlist, manifest-last/failure exclusivity, source/output hashes, every full-precision iteration AUC/KS/efficiency value, first-eligible selection, and `test_opened`. If no iteration is eligible, require null selection, zero model/test artifacts, and `test_opened: false`.

- [ ] **Step 4: Write the exact report and current-status updates**

  Record root cause/raw entries, identity definitions, all production receipts, row/duplicate evidence, focused/full tests, every iteration metric, test terminal, historical comparisons, real-data exclusion, and limitations. Preserve the original design and failed run as linked historical evidence.

- [ ] **Step 5: Final verification and commit**

  Run `.venv/bin/python -m pytest -q` and `git diff --check`, then:

  ```bash
  git add README.md docs/README.md docs/project/overview.md docs/physics/data-description.md \
    docs/roadmap/next-stage.md \
    docs/superpowers/plans/2026-08-26-drop-top4-angular5-source-identity-r2-report.md
  git commit -m "docs: report Angular5 source-identity R2 result"
  ```
