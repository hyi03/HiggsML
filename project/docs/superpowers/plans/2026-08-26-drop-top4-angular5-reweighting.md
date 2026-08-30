# DropTop4 + Angular5 Reweighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and execute the approved immutable MC-only Angular5 enrichment and DropTop4-plus-Angular5 iterative mass-bin reweighting study.

**Architecture:** Add a pure angular-mathematics module, then a dedicated fail-closed MC enrichment boundary that re-runs the frozen selection and appends exactly five columns to the authoritative frozen MC table. Extend the existing sealed mass-bin reweighting workflow with one exact 15-feature profile and one schema-specific source contract, reusing the unchanged model-selection, OOF, reweighting, plotting, and conditional test-opening logic.

**Tech Stack:** Python 3.11+, NumPy, pandas, uproot/awkward, PyYAML, scikit-learn, XGBoost, pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-drop-top4-angular5-reweighting-design.md`

## Global Constraints

- MC only: neither command accepts, resolves, hashes, reads, inventories, scores, or plots real data.
- Frozen input hashes, selection, pairing, split, normalization, model candidates, five folds, seeds, mass bins, damping, multiplier bounds, iteration cap, and eligibility gates are exact.
- The new ordered model profile is exactly the ten DropTop4 inputs followed by the five approved Angular5 inputs.
- `m4l`, mass proxies, identifiers, labels, provenance, split, and weights never enter the model matrix.
- A selected event with undefined angles fails closed; it is never dropped, imputed, or assigned a constant.
- Held-out MC test remains sealed unless the first eligible development-OOF iteration exists.
- Both fresh production paths are no-clobber and publish their complete manifest last.

---

### Task 1: Pure Angular5 mathematics

**Files:**
- Create: `src/angular5.py`
- Create: `tests/test_angular5.py`

**Interfaces:**
- Consumes: `src.pairing.FourVector`, `src.reconstruction.FourLeptonCandidate`.
- Produces: `ANGULAR5_FEATURES: tuple[str, ...]`, `lorentz_boost(vector, beta) -> FourVector`, and `build_angular5(candidate) -> dict[str, float]`.

- [ ] **Step 1: Write failing analytic boost and angle tests**

  Add literal, hand-derived cases that verify a rest-frame boost, an inverse common longitudinal boost, range bounds, `+pi -> -pi`, charge orientation, input-permutation stability, and rejection of non-finite vectors, `|beta| >= 1`, invalid charges, zero axes, and degenerate planes. Each test calls the public functions and names the concrete mutation it catches.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_angular5.py -q`

  Expected: collection fails because `src.angular5` does not exist.

- [ ] **Step 3: Implement the minimal vector operations and five formulas**

  Use the Lorentz transform

  ```python
  p_prime = p + (((gamma - 1.0) * dot(beta, p) / beta2) - gamma * energy) * beta
  e_prime = gamma * (energy - dot(beta, p))
  ```

  with finite checks and `beta2 < 1`. Select the negative lepton in each reconstructed Z pair, boost the required vectors into the X/Z rest frames, normalize axes with a single checked helper, compute signed angles with `atan2`, clip cosines only within a fixed tolerance, and normalize angles to `[-pi, pi)`.

- [ ] **Step 4: Verify GREEN and focused regressions**

  Run: `.venv/bin/python -m pytest tests/test_angular5.py tests/test_pairing.py tests/test_reconstruction.py tests/test_features.py -q`

  Expected: all pass.

- [ ] **Step 5: Commit**

  ```bash
  git add src/angular5.py tests/test_angular5.py
  git commit -m "feat: implement canonical Angular5 observables"
  ```

### Task 2: Exact MC enrichment configuration and source binding

**Files:**
- Create: `config/angular5_mc_dsid363490.yaml`
- Create: `src/angular5_enrichment_run.py`
- Create: `tests/test_angular5_enrichment_run.py`

**Interfaces:**
- Consumes: frozen `config/dsid363490.yaml`, Task 4A manifest/table, and the Higgs/ZZ ROOT files.
- Produces: `Angular5EnrichmentConfig`, `Angular5Sources`, `load_angular5_enrichment_config`, `resolve_angular5_sources`, `claim_angular5_output`, and source-freshness validation.

- [ ] **Step 1: Write failing strict-schema and source-receipt tests**

  Cover the exact two MC sample keys, exact profiles and normalization, absence of data keys/paths, fixed entry-stop/chunk policy, exact selection mapping, fixed hashes, regular-file/no-symlink checks, protected-path refusal, fresh output claiming, and mutation between bind and publication.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_angular5_enrichment_run.py -q`

  Expected: collection fails because the module/config is absent.

- [ ] **Step 3: Implement strict config parsing and immutable source receipts**

  Bind exact path, device/inode, size, and SHA-256 for:

  ```text
  config/angular5_mc_dsid363490.yaml
  config/dsid363490.yaml
  runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json
  runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz
  data/raw/higgs.root
  data/raw/zz_363490.root
  ```

  Reject any schema extension, real-data source, symlink, non-regular file, hash mismatch, or output collision before parsing ROOT/table contents.

- [ ] **Step 4: Verify GREEN**

  Run: `.venv/bin/python -m pytest tests/test_angular5_enrichment_run.py -q`

  Expected: all pass.

- [ ] **Step 5: Commit**

  ```bash
  git add config/angular5_mc_dsid363490.yaml src/angular5_enrichment_run.py tests/test_angular5_enrichment_run.py
  git commit -m "feat: bind sealed Angular5 MC enrichment inputs"
  ```

### Task 3: MC enrichment behavior and manifest-last publication

**Files:**
- Create: `src/angular5_enrichment.py`
- Create: `scripts/enrich_angular5_mc.py`
- Create: `tests/test_angular5_enrichment.py`
- Create: `tests/test_enrich_angular5_mc_script.py`

**Interfaces:**
- Consumes: Task 1 `build_angular5`, Task 2 bound sources, existing selection/input-profile/pairing code.
- Produces: `enrich_angular5_mc(sources) -> EnrichmentOutcome`, five approved artifacts, and CLI `python -m scripts.enrich_angular5_mc --config ... --run-dir ...`.

- [ ] **Step 1: Write failing identity/enrichment tests**

  Exercise tiny real in-memory/ROOT fixtures for both input profiles. Assert identical authoritative row order/count, unique `(runNumber,eventNumber,channelNumber)` keys, exact old-column parsed values, exact five-column append order, finite declared ranges, and failures for missing/extra/duplicate/mismatched rows or undefined geometry.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_angular5_enrichment.py tests/test_enrich_angular5_mc_script.py -q`

  Expected: collection fails because the enrichment API/CLI is absent.

- [ ] **Step 3: Implement streaming MC-only enrichment**

  Re-run the unchanged selection through existing profile and selection APIs; build existing features plus Angular5 for each accepted event; validate channels; join angles to the frozen table by the exact key; compare authoritative values without replacing them; and return the authoritative frame with only five appended columns.

- [ ] **Step 4: Implement conditional terminal publication**

  Publish only:

  ```text
  config.yaml
  processed/mc_events_angular5.csv.gz
  artifacts/identity_validation.json
  artifacts/angular5_summary.json
  artifacts/run_manifest.json
  ```

  Use descriptor-bound atomic writes, failure-only terminal behavior, source revalidation, and manifest-last promotion. The CLI has only `--config` and `--run-dir`.

- [ ] **Step 5: Verify GREEN and safety cases**

  Run: `.venv/bin/python -m pytest tests/test_angular5.py tests/test_angular5_enrichment.py tests/test_angular5_enrichment_run.py tests/test_enrich_angular5_mc_script.py -q`

  Expected: all pass, including race/mutation and no-data-surface cases.

- [ ] **Step 6: Commit**

  ```bash
  git add src/angular5_enrichment.py scripts/enrich_angular5_mc.py tests/test_angular5_enrichment.py tests/test_enrich_angular5_mc_script.py
  git commit -m "feat: publish immutable Angular5 MC enrichment"
  ```

### Task 4: Exact 15-feature reweighting profile

**Files:**
- Create: `config/mass_bin_reweighting_drop_top4_angular5.yaml`
- Modify: `src/mass_bin_reweighting.py`
- Modify: `src/mass_bin_reweighting_run.py`
- Modify: `tests/test_mass_bin_reweighting.py`
- Modify: `tests/test_mass_bin_reweighting_run.py`

**Interfaces:**
- Consumes: successful enrichment manifest/table and existing reweighting implementation.
- Produces: approved `drop_top4_plus_angular5` tuple and schema-specific source/policy binding.

- [ ] **Step 1: Write failing feature-policy and config tests**

  Assert the exact ordered tuple, rejection of missing/extra/reordered/rebound features, unchanged legacy Full14/DropTop4 acceptance, exact enrichment paths/hashes, unchanged numerical policy, and correct conditional artifact allowlists.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_mass_bin_reweighting.py tests/test_mass_bin_reweighting_run.py -q`

  Expected: new profile/config tests fail because only two profiles are approved.

- [ ] **Step 3: Extend only the sealed profile/config branches**

  Add the literal tuple

  ```python
  (
      "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
      "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
      "cos_theta_star", "cos_theta_1", "cos_theta_2",
      "phi_decay_planes", "phi_production_plane",
  )
  ```

  and one strict schema branch that binds the enrichment receipt and frozen DropTop4 reweighting reference. Do not create a general runtime feature API.

- [ ] **Step 4: Verify GREEN and legacy regression coverage**

  Run: `.venv/bin/python -m pytest tests/test_mass_bin_reweighting.py tests/test_mass_bin_reweighting_run.py tests/test_run_mass_bin_reweighting_script.py -q`

  Expected: all pass.

- [ ] **Step 5: Commit**

  ```bash
  git add config/mass_bin_reweighting_drop_top4_angular5.yaml src/mass_bin_reweighting.py src/mass_bin_reweighting_run.py tests/test_mass_bin_reweighting.py tests/test_mass_bin_reweighting_run.py
  git commit -m "feat: seal DropTop4 plus Angular5 reweighting profile"
  ```

### Task 5: End-to-end training wiring and conditional test opening

**Files:**
- Modify: `scripts/run_mass_bin_reweighting.py`
- Modify: `src/full_training_policy.py` only if frame validation currently rejects the appended feature columns.
- Modify: `tests/test_run_mass_bin_reweighting_script.py`

**Interfaces:**
- Consumes: schema-validated Angular5 table/profile from Task 4.
- Produces: unchanged iteration `0..5` evidence and first-eligible conditional test/model artifacts.

- [ ] **Step 1: Write failing tiny end-to-end tests**

  Verify the script loads `mc_events_angular5.csv.gz`, passes exactly 15 columns to every fold/model, opens test zero times for no-selection and exactly once after first eligibility, and produces internally agreeing CSV/JSON/plot/manifest evidence.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/test_run_mass_bin_reweighting_script.py -q`

  Expected: Angular5 path/profile composition fails.

- [ ] **Step 3: Add the minimal schema-aware table resolution**

  Preserve the existing `run_mass_bin_reweighting_study` algorithm. Only select the enriched table/source contract when the exact Angular5 config schema is loaded; legacy inputs remain byte-for-byte behavior-compatible.

- [ ] **Step 4: Verify GREEN**

  Run: `.venv/bin/python -m pytest tests/test_run_mass_bin_reweighting_script.py tests/test_mass_bin_reweighting.py tests/test_mass_bin_reweighting_run.py -q`

  Expected: all pass.

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/run_mass_bin_reweighting.py src/full_training_policy.py tests/test_run_mass_bin_reweighting_script.py
  git commit -m "feat: run sealed Angular5 reweighting study"
  ```

### Task 6: Full verification, one-time production execution, and documentation

**Files:**
- Modify after actual results: `README.md`
- Modify after actual results: `docs/project/overview.md`
- Modify after actual results: `docs/physics/data-description.md`
- Modify after actual results: `docs/roadmap/next-stage.md`
- Create after actual results: `docs/superpowers/plans/2026-08-26-drop-top4-angular5-reweighting-report.md`

**Interfaces:**
- Consumes: all implementation tasks and protected local inputs.
- Produces: immutable production runs plus an exact execution report.

- [ ] **Step 1: Run focused and complete tests**

  Run: `.venv/bin/python -m pytest -q`

  Expected: all pass with no warnings/errors that invalidate execution.

- [ ] **Step 2: Verify protected inputs and fresh paths**

  Run SHA-256 checks for the approved config, Task 4A manifest/table, Higgs ROOT, ZZ ROOT, and DropTop4 reference. Confirm both exact output directories are absent and regular parent directories are not symlinks.

- [ ] **Step 3: Execute enrichment exactly once**

  ```bash
  .venv/bin/python -m scripts.enrich_angular5_mc \
    --config config/angular5_mc_dsid363490.yaml \
    --run-dir runs/angular5-mc-363490-2026-08-26
  ```

  Audit only the five approved artifacts, hashes, row counts, identity evidence, ranges, and manifest ordering.

- [ ] **Step 4: Freeze the enrichment receipt into the already-approved training config**

  Replace only the predeclared enrichment manifest/table receipt fields with the just-produced exact SHA-256 values; run the config/source tests again. This is binding execution evidence, not changing a scientific decision.

- [ ] **Step 5: Execute training exactly once**

  ```bash
  .venv/bin/python -m scripts.run_mass_bin_reweighting \
    --input-run runs/angular5-mc-363490-2026-08-26 \
    --reference-run runs/full-training-363490-2026-08-11-r2 \
    --config config/mass_bin_reweighting_drop_top4_angular5.yaml \
    --run-dir runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26
  ```

  Do not rerun or adjust any decision after seeing the result.

- [ ] **Step 6: Audit and document exact terminal evidence**

  Record full-precision iteration AUC/KS/efficiencies, status, selected iteration, `test_opened`, source/output hashes, identity evidence, test counts, comparison references, and limitations. Update navigation/status docs without altering historical evidence.

- [ ] **Step 7: Run final verification and commit**

  Run: `.venv/bin/python -m pytest -q`

  ```bash
  git add README.md docs/project/overview.md docs/physics/data-description.md docs/roadmap/next-stage.md docs/superpowers/plans/2026-08-26-drop-top4-angular5-reweighting-report.md
  git commit -m "docs: report Angular5 reweighting result"
  ```
