# H4l research documentation

HiggsML studies whether kinematic representations and mass-conditioned discrimination improve the expected precision of signal-strength inference in controlled `H -> ZZ* -> 4l` Monte Carlo (MC) samples. A related study asks whether a compact representation can retain that precision with fewer training events.

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
- [Sample-efficiency overlay](../config/protocols/sample_efficiency_v1.json): registration template; null values require explicit registration.
- [Dataset contracts](../config/datasets/): controlled member identities, locations, sizes, and hashes.
- [Manuscript](../paper/manuscript.md): separate paper text supported by these method and reproduction documents.
- [Historical synthetic performance record](performance-synthetic-results.json): immutable numerical evidence interpreted in the results document.

Scientific explanations, execution contracts, and evidence status have one maintained location each. Quoted protocol values explain the bound version; they do not permit tuning a frozen analysis. Old artifacts retain their original protocol snapshots and lineage. All seven maintained Markdown documents live directly in this directory.
