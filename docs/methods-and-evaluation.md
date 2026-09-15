# Methods and evaluation

## Active off-only study

The active paper objective is to quantify the contribution, complementarity and training-seed stability of A/B/C/D kinematic groups when the classifier omits explicit `m4l`. The likelihood still uses the registered mass window and mass coordinate. The 15 nonempty combinations use seeds 42–46 and their existing checkpoints; five deterministic `M0off` identities supply the same-family empty set. No model is retrained for this analysis.

The six result areas are all off-only: paired W68; complete subset ranking/stability; exact Shapley and 24 conditional interactions; validation-checkpoint AUC versus W68; BC/AC versus ABCD as exploration-selected comparisons pending frozen validation; and all 105 direct subset pairs. AUC is descriptive, not an inference or coverage qualification. Older physical-CDF M5/M4, explicit-mass controls, MELA and sample-efficiency workflows remain compatible background/extension studies and are not required off-family candidates.

The versioned [definition](../config/protocols/feature_attribution_mass_off_v1.json) is not a completed scientific registration. A new immutable registration run binds the actual core protocol, prepared population and 75 audited model/calibration artifacts. The candidate family has its own 80-identity G1 and freeze; freezing does not grant assessment access. Automatic P0/T1 materials remain software evidence, with independent qualification pending. Actual uncertainty/coverage stages and native ARM64 are separate evidence levels.

This document defines how the [research questions](research-design.md) are translated into models and statistical comparisons. Input definitions and weights are maintained in [Data and processing](data-and-processing.md); commands and persisted interfaces are in [Implementation and reproduction](implementation-and-reproduction.md). Exact numerical rules belong to the [versioned protocol](../config/protocols/h4l_protocol.json), whose default scope is synthetic software validation rather than full-MC scientific qualification.

## Representations and common mass information

Let m denote `m4l`, z the standard decay coordinates, and r additional observables. A useful explanatory decomposition is

\[
\log\frac{p_s(m,z,r)}{p_b(m,z,r)}=
\log\frac{p_s(m)}{p_b(m)}+
\log\frac{p_s(z\mid m)}{p_b(z\mid m)}+
\log\frac{p_s(r\mid m,z)}{p_b(r\mid m,z)}.
\]

This chain rule does not assume independent feature groups and is not a unique causal decomposition. Legacy mass-conditioned MLP representations receive the same explicit mass condition. The active raw off-only attribution family omits that input. The separate grouped-M3 control removes it only to form independently retrained on/off pairs. BCE training with mass does not guarantee a conditional likelihood ratio, while removing the explicit column does not remove mass information encoded by correlated kinematics; absolute training weights define a surrogate measure.

`decay7` describes two dilepton masses and Angular5; engineered19 also exposes laboratory quantities and derived geometry. L1 checks whether adding `pt4l` and reliably reconstructed `y4l` partly reproduces the engineered representation's gain. This does not by itself identify production information: learning convenience, acceptance, and mass use remain alternatives. A future four-momentum study must preserve the beam direction and longitudinal production information rather than remove it by an arbitrary boost and then attribute the loss to other features.

## Classifier and checkpoint selection

The controlled learner is

```text
input -> Linear(64) -> LayerNorm -> SiLU -> Dropout(0.1)
      -> Linear(64) -> LayerNorm -> SiLU -> Dropout(0.1)
      -> Linear(32) -> LayerNorm -> SiLU -> Linear(1)
```

Use CPU float32, AdamW, learning rate `1e-3`, weight decay `1e-4`, batch size 1024, and the declared absolute-weight normalization. Ordinary models run for at most 200 epochs, with validation absolute-weight AUC early stopping, patience 20, and minimum improvement `1e-4`. This keeps the learner and training budget comparable; it is not a search for the best architecture or a guarantee of optimal mu precision. Assessment interval width cannot select the checkpoint.

For adversarial training, an auxiliary network predicts eleven train-background mass-quantile bins from the classifier logit. Gradient reversal makes the classifier minimize

\[
L_{\rm cls}-\lambda L_{\rm adv},
\]

while the adversary minimizes its own classification loss. A stronger penalty can reduce mass dependence at the cost of discrimination or stability. The adversary targets the absolute-weight background, which differs from a signed physical-background estimate.

M6 and M3-fixed200 use a distinct one-based checkpoint rule:

| Epochs | Effective strength |
|---|---|
| 1--5 | Zero warm-up |
| 6--15 | Target lambda times `(epoch - 5) / 10` |
| 16--200 | Full target strength |

Select epoch 200 after complete training; M3-fixed200 keeps lambda zero throughout with matched initialization, data order, and duration. Do not restore an early high-AUC model before the constraint became active. Incomplete training, nonfinite loss, or unusable bins produce failure. A traceable common training prefix may be reused, but both final artifacts still require complete histories. Fixed duration prevents a particular selection error; it does not prove convergence.

## Training diagnostics

Store ordered inputs, scaler, architecture, seed, numeric tensors, checkpoint-rule ID, selected epoch, target/effective lambda, AUC, and diagnostic provenance. The extended history records classification BCE, background adversary CE, effective lambda, validation AUC, and mass-dependence metrics per epoch.

Classification BCE is accumulated from pre-update batches with train class-normalized absolute weights and divided by train row count. Adversary CE uses the background normalized absolute-weight sum. The legacy combined `loss` is the arithmetic mean of batch losses, not pure classification loss under gradient reversal; absent adversary loss remains null.

Mass bins come from train. Each epoch recomputes a 50% background working point using the train absolute-weight median in evaluation mode, then measures validation mass KS and bin acceptance. Diagnostics do not select checkpoints, consume training dropout randomness, or access assessment. Plot warm-up, ramp, selected epoch, and the same-seed fixed200 control. Missing historical loss components are not reconstructed from total loss. Epoch curves are not training-sample-size learning curves.

## Conditional calibration

Mass sculpting occurs when a score selection favours a mass region and changes the background mass spectrum. Removing `m4l` from the input is insufficient because kinematics can encode it. The goal is a controlled comparison with the same mass information, not removal of all mass sensitivity.

For classifier score t, fit on independent calibration background

\[
u=F_b(t\mid m).
\]

An exact, continuous, strictly monotone conditional CDF preserves fixed-mass ranking and allows recovery of t from `(m,u)`. Finite histograms, ties, plateaus, interpolation, and subsequent binning do not guarantee this invertibility. A global AUC decrease therefore does not directly imply lost mu precision; a correctly specified correlated joint model can also be unbiased.

| Transformation | Target and reason | Limitation |
|---|---|---|
| raw | Retain the score and estimate category thresholds | Mass dependence remains and must be represented in templates |
| physical | Estimate a normalized nonnegative distribution from signed bin yields | Signed cumulative sums are not a probability CDF |
| absolute | Calibrate the nonnegative absolute-weight measure used in learning/diagnostics | This is not the physical background CDF |

The software physical-CDF default uses a fixed score grid, variance-weighted nonnegative total-preserving constrained estimation, and records corrections and objective values. It never silently clips negative bins. Total signed background must be positive. The current solver rejects unsupported same-group cross-bin correlations. Initial mass slices are 5 GeV, with protocol-defined adjacent merging and linear interpolation between slice centres. Tails, ties, support, and failure rules are frozen; out-of-window inputs fail.

The same background mapping applies to signal and background. It is frozen before templates or evaluation. M4 and M5 reuse M2 and M3; M5-abs is a necessary Q3 bridge using the same M3 score but another target measure. All final fits remain signed. Absolute calibration is a gated extension and must validate the matching passed G1 before payload access.

Report absolute-weight acceptance/KS separately from physical fitted yields and physical-background shape estimates. Use the registered absolute acceptance denominator where required; cancellation can make signed acceptance ratios unstable. A bridge comparison alone does not remove capacity, optimization, or binning differences. Finite calibration fluctuations are handled as described below, not automatically added as nuisance parameters.

## Matrix-element baseline

M1 uses a kinematic-only matrix-element score at fixed mass; M1c gives it the same calibration opportunity as M4/M5. A validated external implementation is required. Match available information, post-processing, event population, categories, mass grid, and error model. If a backend additionally uses production variables, PDFs, mass-peak information, or detector convolution, record that and provide matched controls before claiming equal inputs.

The optional adapter reconstructs canonical massless leptons from decay7 and `m4l`, excluding original `pt4l`, `y4l`, individual lepton masses, and global azimuth. Internal round trips and fake-module tests establish software consistency only. Independent momenta, angular conventions, and probability references remain necessary. Backend process choices do not establish the MC sample's process composition. Exact APIs and validation bindings appear in the [MELA contract](implementation-and-reproduction.md#mela-backend-contract).

## Common templates and likelihood

Use score categories c and mass bins j:

\[
\mathcal L(\mu,\theta)=\prod_{c,j}\mathrm{Pois}
\left(n_{cj}\mid\mu s_{cj}(\theta)+\sum_k b_{kcj}(\theta)\right)
\prod_a\pi_a(\theta_a).
\]

The initial design uses 1 GeV mass bins and two background equal-yield score categories. Thresholds come only from calibration. Every accepted event belongs to one category; do not first discard low-score events. Raw and CDF can define different categories, but the primary comparison retains equal category count and total acceptance where statistically valid. Do not split ties using labels or event identity to manufacture information.

All participants share mass boundaries and the registered deterministic merge rule. Check nominal and required varied templates together; do not optimize a grid separately for each model. M0 sums the same sample over score categories. M0c diagnoses within-mass-bin refinement: even `t=f(m)` can split a finite mass bin. Compare registered coarse/fine common grids and report M0c versus M0 separately before assigning improvements to additional kinematics.

Templates retain signed yields, positive/negative sums, group occupancy, variance, covariance, effective counts, and cancellation. Nonpositive physical rates cannot be repaired with epsilon or absolute weights. No observed events is not proof of a structural zero. Distinguish structural zeros, zero variance, and insufficient statistics; omit all-process structural-zero observation bins only under the common support rule.

T1 uses the validated per-process/per-bin pyhf `shapesys` approximation. For positive yield y and standard deviation sigma,

\[
\tau=(y/\sigma)^2,\qquad E[n_{\rm auxiliary}]=\tau\gamma,
\]

with nonnegative multiplicative gamma. The evidence binds `pyhf_version=0.7.6`, `modifier=shapesys`, `correlation=independent_process_bins`, `auxiliary=poisson_tau_gamma`, protocol, and reference ID. Group correlations that contradict this assumption are rejected even if a validation marker exists. Saving sumw2 is not itself validation.

`staterror` and `histosys` have different statistical meanings and cannot silently replace this model. Strong cancellation or low support triggers common merging; persistent problems become `insufficient_statistics` or `template_stat_model_unvalidated`. A more detailed positive/negative generative model requires separate design and validation.

## Uncertainty layers and resampling

| Layer | Randomness or model | Meaning |
|---|---|---|
| T0 | Fixed map and nominal templates | Idealized fixed-template comparison |
| T1 | T0 plus validated finite-template MC model | Precision of that fixed analysis |
| T2-procedure | Outer calibration group resampling and a new frozen map per replica; T1 within each | Repeated-calibration procedure variability |
| S | Artificial yield/shape perturbations | Sensitivity to specified stress scenarios |
| P | Sourced generator/theory/detector changes | Robustness only to those validated variations |

The main fixed-network MC bootstrap resamples calibration/template physical groups in paired replicas. It does not include retraining or assessment-parent uncertainty. T2 instead isolates recalibration: resample calibration groups, fit CDF or raw thresholds, freeze the replica map, apply that same map to template and common pseudo-events, reconstruct bins, and fit T1. Never alter template categories while leaving observations under the original map.

T2 normally fixes models and template/assessment parent events. Any broader resampling scope must be explicit. Declare whether auxiliary observations are fixed or regenerated. Do not add outer calibration spread again inside T1 or call calibration-only resampling unconditional uncertainty for the entire analysis. Using CDF uniformity as a predictive background model would require a different uncertainty treatment; the default uses independent templates.

## Primary and supporting metrics

At `mu_true=1`, 10 fb^-1, and the same bound T1 expectation and interval construction,

\[
W_{68}=\mu_{\rm upper}-\mu_{\rm lower},\qquad
R_s=1-\frac{W_{68}(M5,s)}{W_{68}(M4,s)}.
\]

Report all five paired `R_s` and their median. Failed seeds and undefined denominators cannot be dropped while retaining a five-seed primary-comparison claim. W68 directly measures expected signal-strength resolution; 95% widths, Toy width distributions, bias, coverage, and failures qualify that interpretation.

AUC means absolute-weight AUC at the selected validation checkpoint. It is neither an assessment measurement nor a newly measured CDF AUC inherited from the raw network. Include fixed-mass-slice AUC and local support; the empty-set global AUC is not automatically 0.5 when mass is available. Report the pull denominator convention when using asymmetric intervals.

For every nonempty A/B/C/D subset, the raw feature-combination family trains a paired model with explicit `m4l` and a model with `m4l` removed. The pair shares the event population, seed, learner, common template grid, and T1 model-self Asimov contract at `mu=1`, but each model is trained and checkpointed independently. Candidate keys are `M3:<seed>:groups=<subset>` and `M3:<seed>:groups=<subset>:m4l=off`.

Fixed-mass diagnostics use the registered 5 GeV calibration edges on validation events with absolute physical weights. Slices missing either class retain `insufficient_class_support`; they make the affected pair incomplete rather than being deleted or assigned a neutral AUC. The on/off effect is reported as `AUC_on-AUC_off`, `W68_on-W68_off`, and `1-W68_on/W68_off`. A seed-level comparison requires all 15 pairs, every registered slice, and a valid M0c reference; the five-seed summary requires seeds 42--46 with no failure deletion. The legacy mass-on export uses M0c. The separately registered off-only export uses M0off and never substitutes M0c or M0.

## Pseudo-experiments, boundaries, and assessment

Separate model-self closure, frozen assessment-parent mismatch, and externally sourced variation tests. Generate counts from a valid nonnegative model, not by using signed events as Poisson probabilities. Methods share physical pseudo-events or equivalent joint-cell sampling, not merely equal random seeds.

The pilot uses seed 42 and 500 Toys for each registered generating scenario at `mu=0,1,2`. This budget does not multiply automatically across every T2 replica; outer/inner budgets are separately registered. At 500 independent conditional Toys, binomial standard errors are approximately 2.09 percentage points for 68% coverage and 0.97 points for 95%. Approximate 95% half-widths are 4.1 and 1.9 points, not minimum detectable differences. Report binomial intervals and paired coverage-difference uncertainty.

More Toys reduce conditional sampling error, not missing parent-template information or unsupported tails. Failed replicas remain in planned denominators; do not draw replacements until the result looks acceptable.

Physical profile-likelihood intervals use `mu >= 0` and chi-square(1) critical values. Missing upper bounds and optimization failures remain failures. Toys currently check coverage; they do not calibrate critical values. Interval calibration requires separate registration and independent validation. Boundary bias must not automatically be called model mismatch.

An optional `signed_mu_diagnostic` at injected zero fits the same counts with fixed nominal templates and nuisance values. Even with a T1 primary interval it is labelled `T0_fixed_template_diagnostic`. Search intersects `[-20,20]` with positive `b + mu*s` support, using the 0.99999999 interior factor at the negative physical boundary. Nonpositive background or absent sensitivity gives `signed_domain_unavailable`; a boundary optimum gives `search_bound_reached` and is not included in valid-estimate means. It is not a T1 signed profile, is not automatically enabled by the default protocol, and is not run for modeled stress.

Before assessment, freeze candidates, models, mappings, templates, likelihood, protocol, and budgets. A durable claim precedes payload decoding. Re-preparing the same groups does not bypass it. Explicit repeats must use the same frozen analysis and allowed budget, without retuning.

## Feature attribution

Train every nonempty subset of `N={A,B,C,D}` afresh within the same experiment family. For each seed use `v_s(S)=-W68(S,s)` and

\[
\phi_G=\sum_{S\subseteq N\setminus\{G\}}
\frac{|S|!(4-|S|-1)!}{4!}[v(S\cup\{G\})-v(S)].
\]

The legacy mass-conditioned raw family's empty set is M0c. The new raw off-only family's empty set is constant M0off, with structural-zero category evidence and a same-grid likelihood-equivalence check. Report M0c/M0 separately. Compute Shapley per seed, check `sum(phi)=v(N)-v(empty)`, then summarize; medians of individual contributions need not obey the identity. Contributions have interval-width units, not percentages of physical information.

A CDF family must run its own mass-only empty set through the same calibration. At exact mass, a mass-only score is a conditional point mass; strict continuous-CDF assumptions fail. Follow ties/plateau/structural-zero rules without manufacturing two occupied categories. If an empty set or subset is invalid, exact Shapley for that family is unavailable; do not insert zero or substitute a different procedure. This need not block M5/M4.

Second differences, `v(S+i+j)-v(S+i)-v(S+j)+v(S)`, measure complementarity in the chosen metric, not mutual information or causal synergy. Pair group resampling across combinations and propagate the declared upstream randomness; resampling only the final contribution table is insufficient. Raw and decorrelated families cannot be pooled.

## Stress tests and sourced variations

The pilot registers artificial plus/minus 10% normalization, mass, score, and mass-score correlation perturbations. A mass coordinate can be `x=(m-122.5)/17.5`; score/correlation stress uses the bound common `M3:42` reference rather than a different pseudo-truth for each model. Shape normalization is separate from yield variation.

Compare omitted perturbations with modeled ones. Modeled stress uses fixed endpoints through normsys/histosys and nuisance limits `[-1,+1]`, with the declared normal and shapesys Poisson auxiliary generation. T1 refuses unvalidated changes to relative template-MC variance. Neither a modifier nor an arbitrary 10% perturbation proves experimental systematic coverage.

Sourced studies require process/version/settings, weights or variation samples, correlations, and independent provenance for generators, showers, PDFs, background composition, lepton scale/resolution, or efficiency. Lepton variations must redo selection, pairing, features, matrix elements, and scores, including migration into and out of selection. Modifying only the accepted nineteen-feature table misses acceptance migration.

Freeze models/CDF for robustness evaluation. Adaptive recalibration is a separate strategy. Cross-release identity, event overlap, and process equivalence must be established before combination. Reliable gain claims require the registered primary comparison, valid normalization and T1 model, uncertainty, acceptable bias/coverage, and evidence for every asserted systematic scope. See [Results and limitations](results-and-limitations.md).

## Off-only estimands and uncertainty

For every seed compute all 16 coalition values `v(S)=-W68(S)` under fixed T1 model-self Asimov at mu=1, then four exact Shapley contributions and 24 conditional second differences. Summarize each estimand over the five seeds by its median. Medians of individual contributions need not obey the per-seed efficiency identity. Seed intervals enumerate all 3125 ordered joint seed vectors, with linear 16/84 and 2.5/97.5 percentiles. They are training-seed stability conditional on the current MC, not total confidence intervals.

Display nonempty subsets by median W68, subset size, then alphabetic order. Statistical ties use unrounded equality and average ranks; first-place counts include shared minima. Every one of 105 canonical nonempty subset pairs keeps five differences and ratios: `W_left-W_right` (negative favours left) and `1-W_left/W_right` (positive favours left). Intervals are per pair, without simultaneous-coverage claims. BC and AC remain the exploration-selected compact comparisons and are not retrospectively preregistered. Missing/failed seeds or mixed cohorts make complete summaries unavailable; values are never imputed.

Event-MC bootstrap uses 200 common physical-group draws for calibration and template roles separately, seed 42001, fixed networks and frozen nominal mass grid. Raw thresholds are refit, M0off stays constant, and the full inference/attribution chain is rebuilt. All 200 complete replicas are required for formal percentile intervals; failures keep their identities, mappings and budgets. Do not add event-MC and training-seed intervals.

T1 Toys use mu=0,1,2 and 500 marginal Toys per candidate per expectation. Joint physical cells must have nonnegative process rates and compatible marginals. If the model-self joint construction fails, retain marginal closure and mark pairing unavailable; never claim pairing from equal seeds. Report successful-fit conditional coverage and its Wilson interval, planned-denominator success-and-coverage with its Wilson interval, and failure rates. No generic pilot pass threshold is introduced.

T2 uses T1 at mu=1, 20 common calibration-group outer draws and 100 joint inner Toys per outer draw. A replica mapping transforms both template and pseudo-event classification on the fixed grid. Preserve outer mapping records, multiplicities and failed inner budgets; 20 outer replicas are the independent procedure units, not 2000 unconditional experiments. Independent assessment requires a separate reviewed access/evidence receipt and durable cell claim before payload decoding.
