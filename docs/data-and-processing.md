# Data and processing

## Data background and selection rationale

The study binds [atlas2020_4lep](../config/datasets/atlas2020_4lep.json), its [ROOT profile](../config/profiles/open_data_2020.yaml), and the [H4l protocol](../config/protocols/h4l_protocol.json). The controlled pair is signal DSID 345060 (`ggH125_ZZ4lep`) and background DSID 363490 (`llll`). URLs, sizes, and SHA-256 values are maintained only in the dataset contract.

| Choice | Reason | Qualification |
|---|---|---|
| Fixed two-member MC collection | Auditable acquisition, labels, and comparisons | Not all Higgs modes or experimental backgrounds |
| 2020 release | Bound by the active profile and workflow | No established superiority over later releases |
| `2e2mu` | Manageable pilot with reduced same-flavour pairing ambiguity | `4e`/`4mu` need additional pairing/interference checks |
| `105 <= m4l < 140` GeV | On-shell signal region and continuum context | Registered endpoints, not an assessment-optimized window |
| 10 fb^-1 normalization | Common expected-yield scale | Simulated normalization, not a measurement |

[atlas2025_exactly4lep](../config/datasets/atlas2025_exactly4lep.json) is a separate release/collection. It is not automatically interchangeable, independent, or a generator variation. Do not mix releases or share feedback without a validated new contract.

P0 must establish processes, generator/version, perturbative order, PDF, shower, filters, detector chain, normalization, and negative-weight origin. Do not call DSID 363490 pure qqZZ without evidence. Check whether cross sections include branching fractions, k-factors, or efficiencies to avoid double counting. Document FSR conventions and unavailable physical definitions.

## Input identity and access

ROOT preparation requires a `h4l-root-input-v1` manifest with the dataset, `mc_only: true`, exactly the bound `higgs` and `zz` members, and the sealed profile. Check source identity, parent path, size, recorded acquisition hash, verified size/mtime, tree, entry count, branches, and channel DSID. Labels come from the contract, not technical features or file-name heuristics.

Preparation reuses acquisition evidence; it does not independently rehash the entire ROOT input. Synthetic fixtures require `source_kind=synthetic` and do not establish controlled-MC validity.

Identity is inspected first to preserve the pre-existing development/test split. Application payload requests use ordered, half-open development spans, bounded by `root_max_entries`, without bridging forbidden entries.

**ROOT interpretation limitation:** request ranges do not independently prove that uproot never interprets neighbouring held-out values inside a mixed basket. A historical synthetic probe observed basket-wide numerical views before final slicing. Full bound-source access validation must examine actual branch interpretations; this does not authorize whole-basket decoding followed by filtering. See [performance evidence](results-and-limitations.md#historical-performance-evidence).

`--diagnostic-entries-per-file N` uses the first N eligible entries per file for a bounded diagnostic workload. It is not scientific selection. The resulting diagnostic artifact cannot feed training or G1.

## Reconstruction and selection

The [selection configuration](../config/protocols/h4l_selection_v1.yaml) supplies base cuts; the research protocol overrides its mass window. Branch names and units come from the profile. Reconstructed masses and momenta use GeV.

| Step | Rule | Failure handling |
|---|---|---|
| Trigger | `trigE` or `trigM` | Reject event |
| Flavour / identification | At least four electrons or muons, then tight ID | Remove failing leptons; reject if insufficient |
| Track / calorimeter isolation | Each isolation divided by `lep_pt` below 0.3 | Remove failing leptons |
| Transverse impact | Electron `abs(d0sig) < 5`, muon `< 3` | Remove failing leptons |
| Longitudinal impact | `abs(z0 / cosh(eta)) < 0.5 mm` | Remove failing leptons |
| Multiplicity | Exactly four good leptons | Reject event |
| Trigger matching | At least one matched good lepton | Reject event |
| Ordered pT | 20, 15, 10, 7 GeV thresholds | Reject event |
| Acceptance | Electron `abs(eta) < 2.47`, muon `< 2.7` | Reject event |
| Charge / pairing | Zero total charge and valid same-flavour opposite-sign (SFOS) pairs | Reject event |
| Pair masses | Every SFOS mass above 5 GeV; `50 < mZ1 < 106`, `12 < mZ2 < 115` GeV | Reject event |
| Research population | Protocol half-open mass window and sorted absolute flavours `[11,11,13,13]` | Reject event |

Z1 is the SFOS pair closest to the nominal Z mass; Z2 uses the remaining leptons. Tie-breaking follows [reconstruction](../src/higgsml/physics/reconstruction.py). These cuts define the population; their exact values are fixed choices, not a claim of universal optimality.

Malformed arrays, nonfinite inputs, invalid Angular5, undefined rapidity (`E <= abs(pz)`), inconsistent bindings, duplicate source identity, and groups spanning roles/labels cause failure rather than silent event removal. An empty selected population terminates as `insufficient_statistics`.

## Features and information content

Selected events retain lepton `pt`, `eta`, `phi`, energy, charge, flavour, pairing indices, `m4l`, and `y4l` for replay and matrix-element export. These fields cannot be guessed from an old feature-only table.

| Group | Features | Count |
|---|---|---:|
| A | `lep1_pt` through `lep4_pt`, `lep1_eta` through `lep4_eta` | 8 |
| B | `mZ1`, `mZ2`, `deltaR_Z1`, `deltaR_Z2` | 4 |
| C | `pt4l`, `deltaPhi_ZZ` | 2 |
| D: Angular5 | `cos_theta_star`, `cos_theta_1`, `cos_theta_2`, `phi_decay_planes`, `phi_production_plane` | 5 |

Leptons are pT-ordered; angles use radians, pseudorapidities/cosines are dimensionless, and masses/momenta use GeV. `m4l` is outside engineered19. It is a common condition in the primary and feature-attribution families; the registered grouped-M3 control independently retrains each nonempty subset with this explicit input present or absent. Registered B subdivisions are `B_mass` and `B_geometry`.

| Representation | Actual classifier dimension |
|---|---:|
| mass-only | 1 |
| decay7: two Z masses and Angular5, plus mass | 8 |
| engineered19 plus mass | 20 |
| A/B/C/D subset, explicit `m4l` on | Selected count plus 1 |
| Nonempty A/B/C/D subset, explicit `m4l` off control | Selected count |
| lab-extension: decay7, `pt4l`, `y4l`, mass | 10 |

Order is fixed by the [representation registry](../src/higgsml/modeling/representations.py). The off variant is registered only for a nonempty grouped `engineered19`/M3 model; an empty off model and off variants of mass-only, decay7, lab-extension, or adversarial candidates are rejected. Identity, source, label, role, and weight fields must not enter the classifier.

For approximately massless leptons,

\[
m_{ij}^2=2p_{Ti}p_{Tj}[\cosh(\Delta\eta)-\cos(\Delta\phi)].
\]

Groups are not independent degrees of freedom. Derived features can help a finite learner without adding event information. Freeze a dictionary of definitions, units, frames, ordering, mass dependence, reconstructibility from the baseline, extra production/acceptance information, cross-dataset consistency, and degeneracy handling.

## Identity, weights, and roles

`event_id = source_row_id = <file_id>:<entry>`; `event_group_id = <channelNumber>:<eventNumber>`. A physical group remains intact across roles, variants, folds, and resampling and cannot have conflicting labels.

\[
w_i=L_{\rm pb}\,\sigma_{\rm pb}\,k\,\epsilon_{\rm filter}
\frac{\mathrm{mcWeight}_i}{\mathrm{sumOfWeights}},\qquad
p_{\rm sample}=p_{\rm dev}r,\qquad
w_{\rm yield}=w_i/p_{\rm sample}.
\]

Normalization comes from the science contract and protocol. Preserve the physical sign. The development probability is 0.8; `r` is the conditional role fraction. Variance scales with the squared sampling correction. Do not force role totals to agree and thereby conceal sampling fluctuations.

Roles use the first eight big-endian bytes of `SHA256("h4l-role-v1:" + event_group_id)`, modulo 100:

| Role | Fraction | Permitted use |
|---|---:|---|
| train | 40% | Network, scaler, class normalization, adversary bins |
| validation | 10% | Early stopping, checkpoint AUC, diagnostics |
| calibration | 20% | CDF and category thresholds |
| template | 20% | Yields, common grid, finite-MC statistics |
| assessment | 10% | Budgeted frozen evaluation |

Independent calibration/template resources cost training events. This allocation is registered, not proven optimal. Five network seeds are not independent MC samples; historical folds do not replace these roles. Identity validation may precede payload access, but assessment payload requires bound frozen-analysis evidence. Pooling roles for a final fit destroys the original isolation. Historical feedback requires a separate audit.

## Support and numerical preprocessing

For a group with total contribution `W_g`, use grouped variance `sum_g W_g^2` and preserve cross-bin covariance. Retain bootstrap multiplicity and occupancy even when signed contributions cancel. Record group counts, signed/absolute sums, positive/negative sums, negative fraction, and

\[
N_{\rm eff,signed}=\frac{(\sum w)^2}{\mathrm{sumw2}},\quad
N_{\rm eff,abs}=\frac{(\sum |w|)^2}{\mathrm{sumw2}},\quad
\rho=\frac{|\sum w|}{\sum |w|}.
\]

Undefined denominators produce explicit states. G0 checks permitted non-assessment role/label populations against positive-yield, effective-count, and cancellation thresholds. These statistics do not prove likelihood validity. Controlled-MC training also requires independent P0 evidence for processes, units, four-vectors, pairing, weights, and selection.

Fit feature means and population standard deviations (`ddof=0`) on train only. Zero scales become one. Validation/prediction reuse the stored transform. This improves optimization without leaking validation statistics.

Optimizer weights are `abs(physical_weight)` divided by the train class-specific mean absolute weight. Validation AUC uses absolute physical weights; yields remain signed. M6 and its control fit eleven adversary bins from train-background absolute-weight quantiles, separately from calibration and likelihood bins.

There is no undocumented imputation, winsorization, class oversampling, or outcome-driven selection. Physics rejection, role access, diagnostic truncation, numerical transformation, and binding failure are distinct operations.

## Prepared-event contract

`h4l-events-v1` starts with a header binding dataset, source kind, MC status, protocol digest, and source evidence. Each following line separates the identity envelope from feature payload with a tab. Payload cannot override identity. Writing accumulates hash and byte count.

Readers revalidate receipts, header/schema, exact identity keys, split, role hash, uniqueness, group isolation, finite features, half-open mass support, weight consistency, and population ID. Payload is decoded only when the role contract permits it. See the [full artifact contract](implementation-and-reproduction.md#artifact-and-lineage-contract).
