# H4l research documentation

## Active off-only study

The active paper objective is to quantify the contribution, complementarity and training-seed stability of A/B/C/D kinematic groups when the classifier omits explicit `m4l`. The likelihood still uses the registered mass coordinate. The retained local run `h4l-off-test01` reuses the 75 trained off-models for 15 nonempty subsets and seeds 42–46, plus five deterministic `M0off` identities. No model was retrained by the attribution analysis.

Its nominal T1 Asimov result is complete for all five seeds. BC has the smallest median `W68` (1.51162), followed closely by AC (1.51524); their median improvements relative to `M0off` are 9.14% and 8.92%. Both beat ABCD in all five same-seed comparisons, by median relative improvements of 1.30% and 1.42%. Exact Shapley medians rank the groups `B ≈ C >> A > D`, with D negative in every seed. Validation AUC and `W68` do not share the same ordering.

These are exploratory controlled-MC results. The final report is `incomplete` and `primary_claim_eligible=false`: the access review is a non-independent single-researcher self-review, event-MC bootstrap has only 161/200 valid replicas, three model-self units are blocked by consumed budgets, and independent-allocation sensitivity is pending. Use [Results and limitations](results-and-limitations.md#h4l-off-test01-controlled-mc-result) for the numerical result and its evidence boundary.

HiggsML studies whether kinematic representations and mass-conditioned discrimination improve the expected precision of signal-strength inference in controlled `H -> ZZ* -> 4l` Monte Carlo (MC) samples. The registered feature-combination batch also retrains every nonempty A/B/C/D subset with explicit `m4l` switched on and off. A related study asks whether a compact representation can retain precision with fewer training events.

This is an MC-only educational and technical workflow. Its outputs are not an ATLAS/CMS result, a Higgs discovery, or a physics measurement. The default protocol defines synthetic software rules, not full-MC qualification. Available evidence and remaining validation are recorded in [Results and limitations](results-and-limitations.md).

## Research reading path

| Document | Questions answered |
|---|---|
| [Research design](research-design.md) | What is the physical motivation? Which hypotheses, comparisons, and controls answer the question? |
| [Data and processing](data-and-processing.md) | Why these MC samples and selections? How are events reconstructed, weighted, and separated? |
| [Methods and evaluation](methods-and-evaluation.md) | Why these representations, models, calibrations, and metrics? How are uncertainty and coverage evaluated? |
| [Sample efficiency](sample-efficiency.md) | How is a compact candidate discovered, frozen, evaluated across sizes, and independently confirmed? |
| [Implementation and reproduction](implementation-and-reproduction.md) | Which tools implement the methods? How are commands, contracts, artifacts, and resources used? |
| [Results and limitations](results-and-limitations.md) | What evidence exists, what does it support, and what remains unverified? |

The analysis follows this sequence. Arrows describe dependencies, not evidence that every stage is complete.

```text
Question and registered design
  -> controlled MC audit and event reconstruction
  -> independent training / validation / calibration / template roles
  -> models, mappings, common templates, and statistical gates
  -> frozen analysis and budgeted assessment
  -> paired inference, diagnostics, and qualified conclusions
```

For execution, start with [environment and installation](implementation-and-reproduction.md#environment-and-installation), then the [main workflow](implementation-and-reproduction.md#main-workflow). For the subordinate study, read [sample-efficiency execution](sample-efficiency.md#execution-and-artifact-contracts). Detailed fields are consolidated in the [artifact contract](implementation-and-reproduction.md#artifact-and-lineage-contract).

## Sources of truth

- [H4l protocol](../config/protocols/h4l_protocol.json): versioned scientific parameters, roles, thresholds, and budgets.
- [Feature-combination batch](../config/protocols/feature_combinations_seed42.json): five-seed A/B/C/D matrix, explicit-`m4l` on/off variants, and bound comparison-family IDs.
- [Sample-efficiency overlay](../config/protocols/sample_efficiency_v1.json): registration template; null values require explicit registration.
- [Dataset contracts](../config/datasets/): controlled member identities, locations, sizes, and hashes.
- [Off-only definition](../config/protocols/feature_attribution_mass_off.json): estimands and candidate-family contract; actual runs bind this definition to concrete artifacts.
- [Manuscript](../paper/manuscript.md): separate paper text supported by these method and reproduction documents.
- [Historical synthetic performance record](performance-synthetic-results.json): immutable numerical evidence interpreted in the results document.

Scientific explanations, execution contracts, and evidence status have one maintained location each. Quoted protocol values explain the bound version; they do not permit tuning a frozen analysis. Old artifacts retain their original protocol snapshots and lineage. All seven maintained Markdown documents live directly in this directory.
