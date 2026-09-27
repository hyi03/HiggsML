# H4l research documentation

Updated against the repository code and selected paper evidence on **2026-09-27**.
These seven top-level Markdown documents describe the maintained MC-only workflow,
its current exploratory result, and separately registered extensions.

## Active off-only study

The paper studies the contribution, complementarity, and training-seed stability of
A/B/C/D kinematic groups when classifiers omit explicit `m4l`. It compares all
15 nonempty subsets for seeds 42–46, reusing 75 independently trained networks,
and adds five deterministic `M0off` identities. Its `joint-support-v1` likelihood
uses one mass bin over 105–140 GeV and two score categories for nonempty subsets;
the reference is an inclusive count. This is not a comparison against a resolved
Higgs mass-spectrum fit, and omission of a mass column does not remove implicit
mass information.

The selected result is `runs/h4l-off-test05/evaluation/report`, pinned by
[the paper selection](../paper/selected-snapshot.json). It has 80/80 nominal
candidate results, 36/36 valid evaluation units, and 200/200 valid event-MC
bootstrap replicas. BC and AC have nominal median `W68` values 1.511617 and
1.515244, versus 1.535930 for ABCD and 1.663723 for `M0off`. The MC 95% paired
width-difference ranges for BC/AC versus ABCD include zero. The access review is
non-independent, selection-aware coverage is unvalidated, and
`primary_claim_eligible=false`. Numerical completion does not establish a
calibrated precision gain. Full tables and qualifications are in
[Results and limitations](results-and-limitations.md#h4l-off-test05-controlled-mc-result).

HiggsML is an educational and technical study of controlled `H -> ZZ* -> 4l` MC.
Its outputs are not an ATLAS/CMS result, a Higgs discovery, or a physics measurement.
The core protocol remains `synthetic_software_defaults_not_physics_validation`.
Historical test01 results and synthetic benchmarks retain their original meaning;
they are not the current paper's numerical source.

## Research reading path

| Document | Questions answered |
|---|---|
| [Research design](research-design.md) | What does the current paper test, and how do the optional studies differ? |
| [Data and processing](data-and-processing.md) | Which controlled samples, selections, features, weights, and roles define the population? |
| [Methods and evaluation](methods-and-evaluation.md) | How do training, threshold selection, templates, attribution, bootstrap, and Toys work? |
| [Sample efficiency](sample-efficiency.md) | How would a separate mass-conditioned compact-candidate study be registered and confirmed? |
| [Implementation and reproduction](implementation-and-reproduction.md) | Which commands, dependencies, artifacts, access checks, and recovery rules implement the workflow? |
| [Results and limitations](results-and-limitations.md) | Which numerical results exist, what do they support, and what remains unvalidated? |

```text
Controlled MC and preserved historical split
  -> training / validation / calibration / template roles
  -> audited off checkpoints and joint calibration/template threshold selection
  -> common templates, G1 and J0/J1 support gates
  -> frozen analysis and bound evaluation plan
  -> event-MC bootstrap, model-self / assessment Toys, T2
  -> immutable exploratory report and pinned manuscript assets
```

Start execution with [environment and installation](implementation-and-reproduction.md#environment-and-installation)
and the [main workflow](implementation-and-reproduction.md#main-workflow). To reuse
trained models, use [off-only attribution execution](implementation-and-reproduction.md#off-only-attribution-execution).
To compile the paper without local runs, use [manuscript reproduction](implementation-and-reproduction.md#manuscript-reproduction).

## Sources of truth

- [Core H4l protocol](../config/protocols/h4l_protocol.json): base scientific parameters, roles, training and inference budgets.
- [Joint-support method](../config/protocols/h4l_off_joint_support_v1.json): the separately bound threshold selector and explicit single mass bin used by test05.
- [Off-only definition](../config/protocols/feature_attribution_mass_off.json): candidate family, estimands and budgets; execution requires a bound registration artifact.
- [Feature-combination batch](../config/protocols/feature_combinations_seed42.json): five-seed training matrix and explicit-mass on/off controls; the filename does not restrict it to seed 42.
- [Dataset contracts](../config/datasets/): controlled member identities, locations, sizes and hashes.
- [Sample-efficiency overlay](../config/protocols/sample_efficiency_v1.json): incomplete registration template, with null choices requiring explicit registration.
- [Manuscript](../paper/latex/main.tex), [paper evidence index](../paper/result-evidence.md) and [selected snapshot](../paper/selected-snapshot.json): current paper claims, bindings and numerical sources.
- [Historical synthetic performance record](performance-synthetic-results.json): immutable measurements, interpreted in the results document; preserved byte-for-byte.

Code defines implemented behavior; versioned contracts and each run's snapshots
define the executed analysis; published artifacts establish numerical results.
A prose update does not retune a frozen analysis, change old identities, or promote
software checks to independent scientific validation. Local `runs/` and `var/`
are ignored and must be preserved separately to regenerate evidence. The paper's
committed figures and TeX tables suffice for an ordinary manuscript build.
