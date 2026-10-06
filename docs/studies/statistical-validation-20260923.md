# Low-count interval probe and subsequent signed-MC validation design

## Record scope

Historical date: 2026-09-23. Code HEAD:
`5275fc586ec25d41e84459e665c168dba6a31671`, with pre-existing uncommitted changes.
This record was translated into English and relocated on 2026-10-06 from
`docs/changes/priority3-statistical-validation-20260923.md`. The original is in Git
history before migration (HEAD `e1448f3eb1b841b371d82b3ccfc1bc4f7f2bf160`).
The request came from section 5 of the research-quality solution confirmation,
historically `docs/4-Reviews/research-quality-audit-2026-09-23-review-confirm.md`,
and the user's instruction to start priority 3. That ignored review is not a
distributed source of evidence.

**Layer A's bounded T0 coverage probe was completed. Layers B (signed-MC
applicability) and C (selection-procedure coverage) were designed but not executed.
Production intervals were not changed and independent scientific qualification
was not promoted.** References to F2 progress describe the original task, not
the current selected result. See [current results](../results-and-limitations.md)
and [current methods](../methods-and-evaluation.md).

All evidence paths below are historical, repository-relative locations under
the ignored `var/priority3-lowcount-20260923-001/`. These artifacts were not found
in the migration workspace, are not bundled with Git and were not recomputed.
Their absence limits current reproducibility; this document preserves the
reported results, failures and bindings without independently revalidating them.

The key reported result used the public rounded totals `s=2.7683`, `b=2.4979`:
in a single-bin fixed-known-template synthetic T0 scenario at mu=1, nominal 68%
chi-square(1) intervals covered **60.776%**. This came from summing integer-outcome
probabilities, not random Toy error. It motivated further reliability work; it
did not quantify undercoverage of F2 T1, BC/AC or signed-MC results.

## 1. Execution boundaries and existing work

- Preserve the then-uncommitted F4/F11/F12 changes. The
  [alignment record](../history/evidence-alignment-20260923.md) had restored old
  test01 sources and conservative automatic P0/T1 semantics; the earlier review's
  missing-source finding was not reassessed as a current fact.
- No src/, production scripts, protocols, tests or existing runs changed.
  Research scripts, frozen configuration, failures and outputs used only the
  new local evidence directory.
- No ROOT, event payload, new assessment or formal replica data were opened;
  no live F2 results informed design, and F2 progress was not assessed.
- No training, formal bootstrap/Toy/T2 or random draws. One process with
  OMP/OpenBLAS/MKL threads fixed to 1; no performance benchmark.
- Code discovery first used the existing graph. Uncommitted changes had shifted
  indexed snippets, so current files were read to verify actual bytes rather
  than relying on Git HEAD alone.
- The original task hashed 248 existing source/configuration/document files,
  not event inputs; the receipt was `baseline.json` in the evidence root.

The disposable probe script was not a production interval tool. Its mathematical
reference was independent of higgsml inference code but authored in the same
study and shared NumPy/SciPy foundations. It was not external researcher review,
independent physics certification or complete qualification-gate evidence.

## 2. Layer A's frozen question and numerical method

Question: with an expected count near five and nonnegative mu, how does coverage
at fixed chi-square(1) thresholds vary with true mu and category sparsity?
Each bin followed independent `N_i ~ Poisson(mu*s_i+b_i)`, with fixed known
nonnegative s/b. Every scenario retained the same total yields.

| Scenario | Signal fractions | Background fractions | Purpose |
|---|---|---|---|
| one_bin | 1 | 1 | Single-bin low-count reference |
| two_equal | 0.5 / 0.5 | 0.5 / 0.5 | Information-preserving bin-split identity |
| two_separating | 0.8 / 0.2 | 0.2 / 0.8 | Synthetic discriminating categories |
| two_sparse | 0.95 / 0.05 | 0.05 / 0.95 | Sparse, strongly separated stress case |

The latter three were not measured BC/AC/ABCD distributions. Rounded review
yields were not claimed byte-identical to any actual template.
`probe.json` fixed mu=0--4 in steps of 0.05 (81 points), fit domain [0,20],
68%/95% confidence levels and Poisson tail budget 1e-12. Configuration/script
were copied and hashed into preflight before main calculation, without
result-driven parameter changes. No scientific pass tolerance was inferred
from observed coverage; it remained undefined.

The independent reference used explicit Poisson log likelihood. Single-bin MLE
was analytic; two-bin MLE used likelihood concavity and bisection of the monotone
score, including boundary optima. It compared:

1. Asymptotic LR acceptance: `q_mu <= chi2.ppf(CL,1)`.
2. Neyman LR-ordering reference: at each injected mu, accumulate original
   outcome probabilities in increasing q order to CL; accept all outcomes tied
   at the critical value. This finite-grid Feldman--Cousins-style construction
   did not randomize acceptance.

Maximum injected mu determined each bin's enumeration cap. The sum of bin tails
bounded omitted probability; truncated probabilities were not renormalized.
Coverage was saved as [enumerated accepted probability, that probability + tail
bound]. Floating-point checks used identities/independent calculation and were
not included in the probability tail bound.
Target coverage of the Neyman set on the registered grid was a construction
property/consistency check, not external validation. No continuous-mu confidence
belt endpoints, Neyman widths, Asimov replacement or precision ranking were computed.

Production returned `interval_unbounded` when the upper crossing was not found
by 20. CSV distinguished acceptance-set coverage from successful-return-and-coverage,
and recorded upper-search failure probability. The search cap was not treated
as a proven finite endpoint.

## 3. Reported coverage results

`run-001/coverage.csv` contained 1,296 rows, with `run-001/summary.json`.
At mu=1:

| Synthetic scenario | Asymptotic 68% | Neyman 68% acceptance | Asymptotic 95% | Neyman 95% acceptance |
|---|---:|---:|---:|---:|
| one_bin | 60.776% | 73.344% | 94.845% | 97.564% |
| two_equal | 60.776% | 73.344% | 94.845% | 97.564% |
| two_separating | 66.440% | 70.406% | 92.870% | 96.672% |
| two_sparse | 61.580% | 68.265% | 91.375% | 95.795% |

Minimum asymptotic coverage on the registered grid:

| Scenario | 68% minimum and mu | 95% minimum and mu |
|---|---|---|
| one_bin / two_equal | 59.655%, mu=2.30 | 92.288%, mu=1.40 |
| two_separating | 58.185%, mu=0.30 | 92.133%, mu=0.95 |
| two_sparse | 35.779%, mu=0.25 | 86.752%, mu=0.80 |

These are finite-grid minima, not continuous-domain global minima. The sparse
case was deliberately synthetic and cannot describe the worst current candidate.
The scenarios enumerated 48, 1,089, 1,053 and 966 outcome states respectively.
Maximum omitted tail bound was about 8.99e-13. Maximum enumerated probability
of no finite asymptotic interval due to upper cap 20 was about 4.68e-11, negligible
relative to these coverage deficits but recorded separately.
Single-bin 68% coverage at mu=0 was about 89.146%; boundary conservatism did not
compensate for mu>0 undercoverage. Equal splitting matched single-bin coverage:
two categories alone do not add information. Discrimination and sparse counts
jointly determine discrete coverage.

Figures were `plot-v2/coverage.png` and `plot-v2/coverage.svg`. The original plot's
lower y limit 0.4 clipped the sparse minimum; visual inspection led to a separate
plot-v2 with lower limit 0.3. Neither numbers nor original artifacts were overwritten.

## 4. Numerical checks and retained failures

Historical environment: Windows, Python 3.12.13, NumPy 2.5.1, SciPy 1.18.0,
pyhf 0.7.6, Matplotlib 3.11.1, using the existing
`C:/Users/whchen/anaconda3/envs/pytorch/python.exe`; no dependency changes.
Seven check types covered:

- Analytic single-bin MLE and zero-observation LR identity.
- Outcome-by-outcome equality of single-bin and proportional two-bin LR.
- Independent scalar optimizer versus score bisection: maximum MLE difference
  about 2.24e-7.
- Poisson recurrence without SciPy PMF: maximum probability difference 2.23e-16.
- Production T0 versus reference statuses/endpoints.
- Enumerated single-bin/equal-split coverage: maximum difference 3.00e-15.
- Analytic single-bin acceptance plus independent probability recurrence at
  mu=0,1,2: coverage difference about 1.00e-15.

**Production comparison did not fully pass.** Initial preflight checked 39
observation cases at two confidence levels (78 intervals). Status/endpoints
passed the frozen 5e-5 endpoint tolerance for 78/78, but 32/78 interval-associated
MLEs exceeded 1e-4, involving 16/39 distinct fits. Maximum MLE difference was
0.00129806 and maximum endpoint difference 3.53e-7.
The first execution failed. Only the research checker's reporting flow changed
to preserve strict MLE failures while completing independent-reference checks;
tolerances were not relaxed. `verification-final/verification.json` explicitly
recorded `status=partial`, `production_strict_bridge_status=failed`, not all_passed.

A separate-process, single-variable diagnostic set pyhf `tolerance=1e-10` for
the same 39 cases. Maximum MLE difference fell to 9.23e-6 with zero tolerance
violations. This supported default optimizer stopping precision as the main
cause, not reliability of every fit. Production code and coverage construction
were unchanged, and the first failure remained. Evidence was
`optimizer-diagnostic.json`.
The decision was to retain the identity-checked mathematical T0 reference,
without automatically changing production optimization. High-precision MLE/pull
work should register numerical tolerances/failure handling and revalidate T1
nuisance cases. No full repository suite ran for this production-unchanged probe;
its numerical checks did not replace F4/F11/F12 regression or scientific qualification.

## 5. Layer B: signed-MC applicability design, not executed

Goal: with known nonnegative true yields, test whether current T1 adequately
describes repeated finite signed-MC generation. Initially fix thresholds to
isolate the statistical model. An analytic equal-magnitude signed benchmark for
one process/bin specifies true y>0, population effective count K and cancellation
ratio rho:

```text
lambda_plus  = K * (1+rho) / (2*rho^2)
lambda_minus = K * (1-rho) / (2*rho^2)
a = y*rho/K
N_plus  ~ Poisson(lambda_plus)
N_minus ~ Poisson(lambda_minus)
Y_hat = a*(N_plus-N_minus)
V_hat = a^2*(N_plus+N_minus)
```

Independence of these counts gives `E[Y_hat]=y`, `Var[Y_hat]=y^2/K`. This is an
explicit synthetic generative assumption, not a claim that real negative weights
are independent Poisson counts. At fixed y/K, varying rho preserves the first
two moments while changing distribution shape, probing y/V-only approximations.
Suggested development grid: `K in {20,100}`, `rho in {1,0.5,0.2}`, generating
signal/background separately. K/rho are population parameters, not guaranteed
realized support. K=20 probes the boundary; failures stay in the denominator
without replacement draws.

| Path | Outer generation/fixed components | Primary observation | Auxiliary meaning |
|---|---|---|---|
| T1 internal closure | Fixed template and tau | Poisson from that template | Regenerated model Poisson auxiliary; tests the model itself |
| MC regeneration applicability | Regenerate positive/negative MC independently, deriving Y/V/tau | Poisson from known mu*s_true+b_true | Compress observed MC into the fit's nominal auxiliary; no unexplained extra Poisson draw |

Data-dependent tau is the second path's research question, not automatically a
true independent auxiliary count. Alternative auxiliary generation requires a
separate estimand to avoid counting finite-MC variation twice.
Later cases include long-tailed weights, within-group positive/negative correlation
and cross-bin correlation. Generate physical-group weight vectors and use net
group moments/covariances, rather than independent within-group resampling.
Report T1's cross-bin-covariance rejection as a scope limitation; do not delete
covariance to make it run.
Retain support/optimizer/upper-search failures, conditional coverage and
planned-denominator success-and-coverage. Report bias, defined pulls/distributions,
widths and binomial intervals; Gaussian pulls are not required at boundaries.
No final Layer B budget or pass tolerance was specified, and Layer A did not
select favorable signed scenarios. First resolve auxiliary semantics,
independent reference and numerical contract; then use small development repeats
for feasibility/cost, and determine independent-validation budget from precision.
Development draws must not enter final validation.

## 6. Layer C: selector-procedure coverage design, not executed

Goal: performance when calibration/template are regenerated and joint thresholds
reselected each time. Ordinary F2 Toys fixed thresholds and existing T2 fixed
template, so neither implements this study.
Begin with known score densities, such as distinct signal/background Beta laws.
Initially make signed marking independent of score so net densities and category
truths integrate analytically; score-dependent marking is a later case.
Generate both roles independently, with identities/streams separate from formal
H4l runs. Each outer repeat:

1. Generate calibration/template physical groups with the frozen generator.
2. Apply the version-bound selector and retain all cuts and the selected cut.
3. Analytically integrate true category rates at that cut and generate independent
   observations.
4. Fit fixed-template T0 reference and T1 under validation; record support,
   selection, fitting and coverage.
5. Estimate full-procedure coverage using outer repeats as independent units.
   Multiple inner observations require group-level uncertainty, not independent
   outer counts.

Separate calibration/method development and final validation namespaces/streams.
Fixed-network evidence excludes retraining; full-learning validation needs new
training resources and repeated training. Initial validation covers only the
synthetic generator's domain. H4l applicability additionally needs process/weight
provenance, representative distributions and independent resources. Selection-aware
coverage stays unvalidated; Neyman T0 success cannot promote it.

## 7. Next decisions and relationship to F2

| Known fact at the time | Decision | Subsequent requirement |
|---|---|---|
| Low-count T0 asymptotic undercoverage | Continue priority 3 regardless of F2 success | Independent finite-MC nuisance reference |
| Neyman grid reference reaches target | Preserve as reference; no production integration | Continuous inversion, width definition, nuisance and independent validation |
| Default MLE differs slightly from strict reference | Retain issue; no F2 change | Validate tighter precision under a new numerical contract |
| F2 results not read in this task | Preserve frozen analysis/budgets | After publication inspect support, conditional coverage and failures for B/C priorities/cost |
| Scientific coverage tolerance undefined | No formal pass declaration | Freeze intended-use, failure/conservatism and acceptance rules before validation |

Future reliable-precision comparison should freeze expected or median observed
width of a validated interval. A discrete confidence belt cannot supply an
undefined width at noninteger Asimov observations. This probe did not replace
W68/Shapley/ranking or reinterpret their numbers.

## 8. Historical recomputation and preservation

The ignored directory held one-off scripts, not a long-term production tool.
Formal design/review would precede promotion. Historical scripts refused overwrite
and used fresh output paths. These are archival commands; unavailable scripts or
changed production bytes must not be silently substituted:

```powershell
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' var/priority3-lowcount-20260923-001/probe.py --config var/priority3-lowcount-20260923-001/probe.json --output var/priority3-lowcount-20260923-001/run-002
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' var/priority3-lowcount-20260923-001/verify.py --config var/priority3-lowcount-20260923-001/probe.json --output var/priority3-lowcount-20260923-001/verification-002 --results var/priority3-lowcount-20260923-001/run-002
```

Verification required production likelihood bytes to match the original baseline;
changes require a new study directory/baseline. Final partial status preserves
strict MLE failure; normal process exit only meant the report was saved.

| Binding | SHA-256 |
|---|---|
| Configuration | `35dd6fc9695a94e99a8082fce60ec3d1e0f84665cce321874560e09b9dba6240` |
| Probe script | `01f1a7cc8c4f66b8119d63404eb245b50fb1211a7dfb29b648d54ca9ee5573b9` |
| Production likelihood file | `6b45ebd39e54b334e90b7f830cd19b2c48cdf6286f2112205a6469bd284a29b1` |

Initial failure, final checks, optimizer diagnostic, figure revision and file
bindings remained separate; they were not combined as one fully passed run.
References: [Feldman and Cousins (1998)](https://doi.org/10.1103/PhysRevD.57.3873)
and [Glusenkamp (2020)](https://doi.org/10.1088/1748-0221/15/01/P01035).
No new full-text literature review was claimed; citations do not validate applicability.
