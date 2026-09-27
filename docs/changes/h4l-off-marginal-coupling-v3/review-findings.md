---
change_id: h4l-off-marginal-coupling-v3
status: verified
source: Fresh-context read-only correctness and risk subagent reviews
updated_at: 2026-09-18
---

# Implementation review findings

Reviewers: GPT-5.6 Terra (high, correctness) and GPT-5.5 (high, risk).
Both reviewed the tracked diff and untracked v3 implementation, schemas and
tests. Neither ran tests or scientific evaluation. Full verification was still
in progress, so this records review completion, not final acceptance.

| ID | Severity | Reviewer | Finding | Location |
|---|---|---|---|---|
| C1 | Medium | GPT-5.6 Terra | T2 preflight overwrote every scientific failure with insufficient_statistics | likelihood.py, preflight terminal |
| C2 | Medium | GPT-5.6 Terra | Null theta lacked an explicit zero-total marker | marginal_coupling.py, coupling receipt |
| R1 | Medium | GPT-5.5 | Full v3 wrapper could begin work without the required access receipt | h4l_off_run.py, versioned execution |
| R2 | Medium | GPT-5.5 | Default-version documentation contradicted the existing wrapper default | README.md and reproduction guide |
| R3 | Medium | GPT-5.5 | Marginal blocks schema retained joint-contract and wrong block-prefix constants | marginal blocks schema |
| R4 | Medium | GPT-5.5 | Terminal schema lacked explicit marginal support, receipts and mandatory CRN metadata | marginal evaluation schema |
| R5 | Low | GPT-5.5 | Plan-only message always named v2 | h4l_off_run.py |
| S1 | High | Implementation self-review; GPT-5.5 recheck | Separate version ledgers allowed concurrent cross-version population reservations | population_history.py and v1/v2/v3 claim/freeze paths |
| R6 | Medium | GPT-5.5 follow-up | An invalid legacy claim directory could consume the shared reservation before directory validation | workflow.py, legacy assessment claim |

Both reviewers rechecked their findings. The correctness reviewer reported all
findings resolved and no obvious correctness regression. The risk reviewer
reported all functional/schema findings resolved and requested one remaining
wording correction distinguishing explicit-v2 commands from the default-v2
wrapper; that wording was subsequently corrected.

The shared population reservation now uses exclusive atomic creation across
v1/v2/v3. A forced concurrent reservation regression proves that only one
version can reserve a population. Legacy directory validation and creation
precede reservation; the invalid-directory regression proves that rejection
does not consume the population. The risk reviewer rechecked both fixes and
confirmed resolution. These checks are software evidence only.
