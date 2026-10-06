# H4l full-entry history and completion-state hardening

## Record scope and subsequent changes

Historical date: 2026-09-24. The task changed source/configuration/documentation/
tests following research review, without modifying runs/ or starting formal MC,
training, bootstrap, Toy, assessment or T2. This record was translated into English
and relocated on 2026-10-06 from `docs/changes/h4l-entry-hardening-20260924.md`.
The original remains in Git history before migration (HEAD
`e1448f3eb1b841b371d82b3ccfc1bc4f7f2bf160`).

The initial required archived root and median default below were subsequently
changed: commit `5b4beb0` removed the required archived-root preflight dependency;
commit `03ea1b4` made joint-support-v1 the full wrapper's default. The current
history configuration declares only runs/ and cannot prove unused status in
other directories/machines. See [current history/completion instructions](../implementation-and-reproduction.md#cross-root-history-and-completion-states)
and [history configuration](../../config/h4l_history_roots.json).
Historical outcomes, population and test counts below were not recomputed by
migration. Host-specific logs/evidence are not bundled with Git and their old
checks were not revalidated. Completion remains distinct from scientific eligibility.

## Implemented behavior at the time

1. **Cross-root access history.** The then-existing config declared runs/ and
   required var/runs-test-01/. Scans read four historical ledger types, not event/
   assessment values. Missing archives, malformed records, out-of-bounds paths
   and symlinks/junctions failed closed. Model-self did not consume assessment
   access. The first root's atomic population reservation coordinated new access
   across all declared roots. Old archived records were not moved or rewritten.
2. **Honest local review.** New h4l-off-self-review-access-v2 checked actual history
   before publication, recording roots, configuration path/hash and no matches.
   It claimed no access found within those roots, not global independence. History
   blocked a new unused review. Old v1 remained readable but could not bypass live
   checks. Same-freeze recovery still required its existing bound receipt.
3. **Read-only preflight and bounded execution.** h4l_all.py --plan-only emitted
   method/identity/history/planned commands without run creation or children.
   Missing prepared identity stayed pending; execution rechecked after prepare
   and before training. The initial default was median-v1; joint support needed
   explicit selection consistent with registration. --stage-b-only stopped after
   validating the bound plan and Stage B report.
4. **Verifiable completion.** Preflight/access/support blocking returned 5;
   normal children with incomplete evidence returned 6. Full completion checked
   all 36 units, terminal hashes, plan/freeze/unit identity and report consistency;
   bound report-resume-* could be selected. Plan/Markdown reports required valid
   receipts. Published numerical failures could be execution terminals, with
   execution/scientific status separately reported and qualification exploratory.

Weights, scale factors, T0/T1 algorithms, threshold selection and formal replica/
Toy budgets were not changed by this task. Software completion did not replace
F2 results, low-count/selection-aware coverage or physical applicability.

## Historical read-only checks on real directories

```powershell
python scripts/h4l_all.py --run-name test03 --threshold-method median-v1 --plan-only
```

Reported exit 5, access_status=blocked_used_population. Prepared population was
`1059f531f6da7dd2aaae9ef4956c6f2a6465fbf1f5e1254bb0ee81b08fd42e00`, matching
archived history with a different/unknown freeze. Claims showed access/budget
occupation, not completion of all numerical tasks.
Joint-support-v1 preflight on test03 also returned 5 because test03 registered
median-v1. The method could not change in place: a new Stage B was needed, and
a new directory did not erase population access.

The new-run plan example was:

```powershell
python scripts/h4l_all.py --run-name planned-joint-001 --threshold-method joint-support-v1 --plan-only
```

Without prepared identity this could return only pending_prepare_identity, not
assessment eligibility. Reusing prepared/training for a new-method Stage B used
the reproduction guide's h4l_off_run.py --source-run-name ... --run-name ...
--threshold-method joint-support-v1 --stage-b route, without retraining.
These are recorded historical checks/examples; migration did not execute them.

## Verification record

- Focused history/self-review/preflight/completion/routing/marginal regressions:
  **60 passed**. After report-receipt additions the relevant group had **23 passed**.
  Groups overlapped and were not additive.
- Reproduced failures before fixes: cross-root occupation, altered report terminal,
  embedded/terminal mismatch, plan-only Stage B and missing Markdown report.
- Full suite: **621 passed, 5 skipped, 511 warnings**, exit 0, 1115.27 seconds
  (18 minutes 35 seconds). pyhf/jsonschema.RefResolver deprecation; skipped items
  were not passes. Command: python -m pytest -q --basetemp D:/t/h4l-entry-full
  -p no:cacheprovider, with write guard and repository src/ loaded via PYTHONPATH.
- Real preflights read only metadata/history. All Python checks had runs/ write
  rejection, temporary roots under D:/t/, and logs under ignored
  var/h4l-entry-hardening-20260923/.
- Against the 252-file starting hash baseline, pre-existing files outside the
  task were unchanged. git diff --check passed; task text used LF.

Evidence was Windows/Python 3.12 software/synthetic-contract validation. It did
not include formal MC numerical validation, independent physical-reference checks,
cross-platform compatibility or complete one-command scientific execution.
