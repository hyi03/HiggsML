# Baseline verification — 2026-09-14

- Checkout: 879560b, isolated branch codex/m4l-off-feature-attribution; no source edits.
- Python: 3.12.13, C:/Users/whchen/anaconda3/envs/pytorch/python.exe.
- PYTHONPATH: D:/code/HiggsML-m4l-off/src; imported higgsml.__file__ verified inside this worktree.
- conda run -n pytorch python -m pytest -q: 448 passed, 3 failed, 5 skipped, 304 warnings; 657.32 seconds. Complete log: sprint-m4-01-baseline-tests.txt.
- Same-environment python -m pip check: No broken requirements found.
- Failures: test_loss_components_use_declared_denominators_and_curves (classification_loss missing); test_reader_rejects_resigned_out_of_overlay_seed_and_missing_history (history_contract missing); test_enabled_controls_publish_and_replay_capacity_stage_chain (FileNotFoundError writing a long Windows temporary path).
- These failures predate implementation. Causes above describe observed errors, not completed root-cause fixes. No protocol resource was re-signed and no source was altered to make the baseline pass.
- Read-only source audit: sprint-m4-01-reuse-audit.json records all 75 model/calibration checks and allowed-file SHA-256, size and mtime_ns. All 75 checked payload contracts passed. Historical access and independent qualification remain pending; no event or assessment payload was read.
- Old external reviewer output is historical only; updated review-start requires fresh gpt-5.6-sol and gpt-5.5 passes.
