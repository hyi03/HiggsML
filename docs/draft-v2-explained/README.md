# Draft-v2 explained: completed draft001 study

Open [Chinese](index.html) or [English](index-en.html). Both editions contain
32 aligned slides explaining the current [manuscript](../../paper/draft-v2/main.tex)
and its completed controlled-MC run `h4l-draft-v2-draft001`.
Double-click either HTML file; no installation, server or internet is needed.
Keep this directory and its local assets together, in their repository location
for source links. Language switching preserves the slide number.

## Reading route

| Slides | Topic |
|---|---|
| 1–3 | Research question, physical channel and conditional ablations |
| 4–8 | Two MC members, common selection, signed weights, event groups and 60/20/20 allocation |
| 9–15 | Executed workflow, input groups, training, validation median and common freeze |
| 16–19 | Actual final-evaluation yields, signed spectra, normalized shapes and support warnings |
| 20–28 | Two-category T1 model, Asimov intervals, all widths and within-seed contrasts |
| 29–32 | Completeness, provenance, qualifications, outstanding evidence and takeaways |

The toolbar opens [width results](index-en.html#slide-23) or
[mass spectra](index-en.html#slide-17) directly. The full source mapping is shown
in each slide footer. Manuscript Tables I–IV and Figures 1–3 are referenced by
their current REVTeX numbering.

The previous unexecuted-proposal/historical-illustration presentation was replaced
as a whole. Its local snapshot is preserved at
`var/paper-evidence/draft-v2-explained-before-draft001-20261029/`.
Historical values and images are not loaded by the current site. The separate
[historical manuscript archive](../../paper/draft-v2-history/README.md) remains intact.

## Supervisor-request guide

The overview links directly to slides 16–19. Each of those slides carries a
“Supervisor request · Direct response” badge and an explanation inside the
existing slide card of how it answers the recorded request:

- Slide 16: common before/after population, frozen cuts and retained yields (Table III).
- Slide 17: simulated signal near 125 GeV, broad background and direct before/after spectra (Figure 2).
- Slide 18: separately normalized shape changes, distinguishing redistribution from yield reduction (Figure 3).
- Slide 19: low-support and signed-weight limits on interpreting the spectra.

Slide 20 connects these diagnostics to the two-category likelihood. The main
objective and W68 metric remain unchanged. These labels map the recorded request
to existing manuscript content; they do not claim supervisor approval or new
scientific validation. Both language editions contain the same guide.

## Results and scope

Five representations (ABCD, BCD, ACD, ABD and ABC) are separately trained for
seeds 42–44, giving fifteen models. All controlled 2020 MC from DSIDs 345060 and
363490 enters the common selection, including historical test events. Deterministic
physical-group assignment uses 60% training, 20% validation and 20% final evaluation.
Validation-background absolute-weight medians fix the cuts before the common freeze.
Both score categories enter T1 in one half-open mass interval [105,140) GeV.

All fifteen model intervals and the one shared inclusive-count reference are
numerically valid. Median W68 is 1.464392 for ABCD and 1.452977 for ABC; the shared
reference is 1.638845. Removing C widens all three intervals. A, B and D have
mixed-sign seed contrasts. Differences are computed within seed before taking
their median; the ACD example demonstrates why this order matters.

These nominal model-self Asimov comparisons remain `exploratory_posthoc`,
`independent=false`, `selection_aware_coverage=unvalidated` and
`primary_claim_eligible=false`. Seed spreads are not confidence intervals.
The analysis does not establish a confirmed precision improvement, a resolved
mass-peak-fit gain, an official ATLAS/CMS result, a Higgs discovery or a measurement.
No bootstrap, Toys, T2, Shapley, CDF or adversarial results are added.

## Controls and interactions

- Previous/Next, arrow keys, PageUp/PageDown, Space, Home/End and the slide-number
  input navigate the deck. Browser back/forward follows slide history.
- Contents opens a keyboard-accessible dialog; language switching keeps the slide.
- Desktop cards combine figures/key points with explanations in adjacent scrollable
  panes. Mobile uses continuous reading; tables can scroll horizontally.
- Four interactions inspect model dimensions, teach weighted-median ties using
  explicitly artificial examples, compare actual seed widths, and compute actual
  paired contrasts versus the different statistic of subtracting width medians.
- Print includes all 32 slides and their explanations. Long content can continue
  across printed pages. Fullscreen uses the browser API.
- Click either spectrum to open the original report image at full resolution.

The browser only reads bundled scripts and images. There are no fetch calls,
accounts, analytics, persistent storage, model payloads or event files.

## Sources, synchronization and checks

[Source notes](SOURCE-NOTES.md) record the selected report, aggregate checks,
file hashes and interpretation limits. `results-data.js` contains verified report
aggregates; `assets/` contains unchanged PNGs and full-precision CSV downloads.
These local generated files remain ignored and must accompany the offline site.
`content.js` is the bilingual narrative, `teaching.js` supplies deterministic
teaching helpers, and `app.js` implements navigation and interactions.

To recreate local assets from the already completed report:

```sh
conda run -n pytorch python docs/draft-v2-explained/tools/sync-results.py
node docs/draft-v2-explained/tools/check.mjs
```

Synchronization checks complete aggregate stages and their bound files. It does
not read events/checkpoints, train, score, fit or create an access claim.
It rejects a different report identity or changed existing assets.

See [verification](VERIFICATION.md) for executed checks and their limits.
