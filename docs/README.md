# H4l research documentation

## Active off-only study

The active paper objective is to quantify the contribution, complementarity and training-seed stability of A/B/C/D kinematic groups when the classifier omits explicit `m4l`. The likelihood still uses the registered mass window and mass coordinate. The 15 nonempty combinations use seeds 42–46 and their existing checkpoints; five deterministic `M0off` identities supply the same-family empty set. No model is retrained for this analysis.

The six result areas are all off-only: paired W68; complete subset ranking/stability; exact Shapley and 24 conditional interactions; validation-checkpoint AUC versus W68; BC/AC versus ABCD as exploration-selected comparisons pending frozen validation; and all 105 direct subset pairs. AUC is descriptive, not an inference or coverage qualification. Older physical-CDF M5/M4, explicit-mass controls, MELA and sample-efficiency workflows remain compatible background/extension studies and are not required off-family candidates.

The default [definition](../config/protocols/feature_attribution_mass_off.json) is not a completed scientific registration. A new immutable registration run binds the actual core protocol, prepared population and 75 audited model/calibration artifacts. The candidate family has its own 80-identity G1 and freeze; freezing does not grant assessment access. Automatic P0/T1 materials remain software evidence, with independent qualification pending. Actual uncertainty and coverage stages are separate evidence levels; no operating system or CPU architecture is an authority requirement.

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
- [Manuscript](../paper/manuscript.md): separate paper text supported by these method and reproduction documents.
- [Historical synthetic performance record](performance-synthetic-results.json): immutable numerical evidence interpreted in the results document.

Scientific explanations, execution contracts, and evidence status have one maintained location each. Quoted protocol values explain the bound version; they do not permit tuning a frozen analysis. Old artifacts retain their original protocol snapshots and lineage. All seven maintained Markdown documents live directly in this directory.
