# Basic report synchronization — 8 November 2026

Both editions now follow the seven-chapter basic report in
`paper/draft-v2/project-report-cn.tex`. The selected source is the new report
`a7e610a163e5d155705014201b7ee330323e3bf69309e0e89b2496edba5d4317`.
Historical interval/supplement results are no longer the slide narrative or an
input to current basic results. They are summarized only in provenance, with
an explicit statement that they do not validate this same-name new run.

## Executed checks

```sh
/Users/xulei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node docs/draft-v2-explained/tools/check.mjs
```

Passed: 40 slides in each language; aligned IDs and complete translations;
fifteen displayed metric rows and twelve contrast rows match the updated report;
yield/error cells and region fractions match; current report bindings and three
publication PDF hashes match BASIC-20261108-EVIDENCE.md; consumed source hashes
match; all local resources and semantic links resolve; four supervisor badges;
weighted-median report example, ties and invalid-input checks; offline script
restrictions and LF endings. The page has no mandatory results-data.js or
supplement-data.js dependency. The older synchronizer remains historically pinned
and was not executed. No paper sources or evidence records were modified by this
synchronization.

Installed Chrome through Playwright opened both actual file URLs at 1440×1000
and 390×844: 160 visible slide states passed, with no JavaScript errors, missing
resources, document horizontal overflow or remote HTTP/HTTPS requests.
A PDF navigation cancellation (ERR_ABORTED) during rapid slide changes was
recorded; this was not a missing resource. Four interaction families, semantic
navigation, contents, language switching and print visibility of all 40 slides
passed. The report weighted-median example is the default (t=0.80, 60%).

The temporary script was `/tmp/higgsml-basic-20261108-qa.cjs`; screenshots include
`/tmp/higgsml-basic-20261108-cover.png`, `...-spectrum.png` and `...-coverage.png`
(the latter now displays the C-group interpretation). They were visually inspected, together with `/tmp/higgsml-basic-deletion.png`
(the three-panel deletion plot) and `/tmp/higgsml-basic-mobile-table.png`
(the scrollable fifteen-model table).
Native print pagination, fullscreen, other browsers and original scientific
aggregate integrity are not established by these checks.

## Scientific scope

Only repository report/evidence text and publication PDF bytes were consumed.
No original run aggregates, events, ROOT files or checkpoints were accessed or
hashed. No training, scoring, fitting, bootstrap or Toys were run. No scientific
qualification was promoted. Display precision and reported paired summaries are
preserved; the browser does not reconstruct unrounded metrics from rounded yields.
All earlier verification sections below are historical and do not identify the
current selected basic-report artifact.

---

# Offline startup fix verification — 7 November 2026

The initial 40-slide revision still loaded ignored `results-data.js` as a mandatory
script. That file was absent, so `content.js` raised `DraftResults is not defined`
and `app.js` could not populate the deck. Earlier source-only checks did not test
complete startup. The fix uses the tracked manuscript display transcription and
original committed PDF spectra, with no ignored startup dependencies.

## Executed source and runtime checks

On macOS with the bundled Node runtime:

```sh
/Users/xulei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node docs/draft-v2-explained/tools/check.mjs
```

Passed: source checks, both complete 40-slide editions evaluated from the actual
page scripts, complete translations, semantic destinations, four supervisor labels,
all referenced local resources, transcription cells compared with committed TeX,
recorded report identities and original PDF byte hashes. Display source hashes
also match. `--source-only` remains available; full-precision aggregate checks
are now explicitly opt-in with `--aggregates`, not a prerequisite for opening.

## Browser acceptance

The computer-use connector timed out on connection. The installed Playwright
package drove installed Google Chrome 157.0.8103.39 headlessly, directly at the requested
`file:///Users/xulei/code/HiggsML/docs/draft-v2-explained/index.html` and its English
edition. No server or dependency installation was used.

The temporary script `/tmp/higgsml-offline-qa.cjs` passed 40 slides × two languages
× desktop/mobile (1440×1000 and 390×844), 160 states total. No JavaScript/console
errors, failed resource requests or remote HTTP/HTTPS requests were observed.
No document horizontal overflow was detected. It exercised semantic toolbar links,
contents, same-slide language switching, model dimensions, weighted-median ties,
seed widths, and the B-removal paired contrast versus difference of medians.
Print media exposed all 40 slides. Native print dialogs and fullscreen were not
validated.

Screenshots at `/tmp/higgsml-offline-cover.png`,
`/tmp/higgsml-offline-spectrum.png` and `/tmp/higgsml-offline-coverage.png`
were visually inspected, together with `/tmp/higgsml-offline-shapes.png` and
`/tmp/higgsml-offline-mobile.png` (normalized-shape spectrum and mobile counting
example). Both original PDF figures display all four panels. The original PDF spectrum needs time for Chrome's native
viewer to paint; the accepted screenshot waits for this and uses `view=Fit` so
all four spectrum panels and axes fit inside the slide. Browsers without embedded
PDF support can use the permanent original-PDF link.

## Scientific limits

Browser acceptance establishes presentation behavior only. The site now explicitly
uses manuscript display precision. Full-precision original aggregates, covariance,
event/checkpoint payloads and scientific runs remain untouched and unverified.
No training, scoring, fitting, bootstrap, Toys or T2 was performed. No scientific
qualification was promoted. The earlier records below are retained as history
and their missing-bundle acceptance prerequisite is superseded by this fix.

---

# Earlier source-only revision — 7 November 2026

The site now declares 40 aligned slides for physics graduate students, including
five teaching additions and three supplemental-diagnostic additions. The earlier
32-slide verification below is historical and does not validate this revision.

## Executed checks

On macOS, using the bundled Node.js runtime (ordinary `node` is absent from PATH):

```sh
/Users/xulei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node docs/draft-v2-explained/tools/check.mjs --source-only
```

Source-only checks passed: 40 bilingual slide declarations with unique IDs;
eight added slides evaluated in Chinese and English with substantive notes and
no untranslated Chinese in English; supplemental values, report bindings and
recorded hashes matched committed evidence records. Semantic links were checked
against slide IDs, including reordered-slide tests; four supervisor annotations
and four existing interaction targets remain. Model dimensions, weighted-median
ties, zero weights and invalid inputs were exercised. Script syntax, local
source links, offline API restrictions and LF checks passed.

The checks evaluate added self-contained slides only. They do not fabricate
nominal data to claim that the complete deck rendered. Source-only success is
explicitly labelled as limited validation.

## Unavailable checks and acceptance prerequisite

This checkout has no nominal `results-data.js`, `assets/`, source runs or local
aggregate snapshots. Running the full checker without `--source-only` reports
BLOCKED and exits nonzero. Full nominal arithmetic, asset-hash consistency,
complete 40-slide runtime and both-language browser acceptance were not run.
The site requires its pinned nominal bundle to function completely. Restore
that bundle or synchronize from the original completed nominal report, then run:

```sh
node docs/draft-v2-explained/tools/check.mjs
```

After that passes, check both languages at desktop/mobile sizes: all 40 slides,
semantic and numeric links, browser back/forward, contents, language switching,
four interactions, decoded spectra, table scrolling, errors and print visibility.
No browser rendering, screenshots, native printing or fullscreen validation is
claimed for this revision.

Supplemental provenance checks compare **committed records**, not original
validation001 aggregate bytes. Original aggregate hashes were not verified
locally. The nominal sync tool and numerical bindings were unchanged.
No repository-wide scientific test suite, event access, training, scoring,
likelihood fitting, bootstrap, Toys or T2 was run. These are documentation and
source-consistency checks, not scientific validation.

---

# Historical 32-slide verification — 29 October 2026

The site now explains the completed draft001 manuscript, replacing the previous
proposal and historical-illustration deck. The earlier site is preserved at
`var/paper-evidence/draft-v2-explained-before-draft001-20261029/`.
No event or checkpoint payload was read in this documentation task.

## Aggregate and manuscript consistency

Executed:

```sh
conda run -n pytorch python docs/draft-v2-explained/tools/sync-results.py
node docs/draft-v2-explained/tools/check.mjs
```

The synchronizer consumed only completed report, evaluation and freeze aggregates,
plus prepared-manifest metadata. The selected report ID is
`9aab6d274a3e2d00d892c2d8fbf89b1e46f5b7a95d0bf0c085af90672ea36898`.
File sizes and SHA-256 hashes, upstream identities and equal evaluation/report
aggregates were checked. All 15 widths, one reference, 12 paired differences and
four median differences match the bound results; manuscript TeX numeric cells
match at display precision. Both PNGs and all five CSV downloads preserve the
report bytes. Full precision remains in `results-data.js` and the CSV files.

The Node checks passed for 32 aligned Chinese/English slides, substantive aligned
explanations, no untranslated Chinese in the English content, model dimensions,
weighted-median ties/zero weights/invalid inputs, shared-reference identity,
paired-median arithmetic, group counts, signed negative bins, normalized fractions,
covariance dimensions, local assets/links, script syntax, offline runtime and LF.
The ACD example explicitly checks a negative median paired contrast and positive
difference of width medians. No failed-seed deletion or artificial reference
seed spread is introduced.

## Browser checks

Browser plugin availability: **absent** (no Browser plugin/skill listed).
The regular Playwright fallback used installed Google Chrome 156.0.8078.48 on
macOS, with an isolated headless context. The bundled Playwright default browser
revision was absent, so the existing Chrome executable was selected; no browser,
package or dependency installation was performed.

Entry routes were the actual offline files:
`file:///Users/xulei/code/HiggsML/docs/draft-v2-explained/index.html`
and `index-en.html`. Desktop viewport: 1440×1000; mobile: 390×844.

| Check | Result |
|---|---|
| Correct URL/title, meaningful first screen | Pass in both languages |
| All 32 slides at desktop and mobile sizes | Pass: 128 visible slide states total |
| Missing content, runtime errors or error overlays | None observed |
| JavaScript errors and warning/error console messages | None |
| Remote HTTP/HTTPS requests | None |
| Card/page horizontal overflow | None; tables retain their own horizontal scrolling |
| Model-input widget | BCD displays 11 inputs in both languages |
| Weighted-median widget | Ties show 83.3%; unequal weights show 100.0% |
| Width widget | Seed 42 shows ABCD 1.472197 and shared reference 1.638845 |
| Contrast widget | B shows −0.002909 versus +0.003117; C shows +0.046283 |
| Contents and slide-number jump | Correct target slide and closed dialog |
| Keyboard navigation | ArrowRight moves spectrum slide 17 to 18 |
| Language switching | Preserves slide 23 |
| Both spectrum images | Decoded with positive intrinsic size |
| Print CSS | All 32 slides visible, toolbar hidden, pane overflow visible |
| Print button | Dispatches window.print; native print dialog mocked |

Screenshots of the Chinese cover, English width table, both language spectrum
pages, paired-median interaction and mobile pages were saved outside the repository
at `/tmp/higgsml-draft001-*.png`. Desktop and mobile captures were visually
inspected: readable tables, full uncropped spectrum panels, aligned body/explanation
panes and natural mobile reading order. The current width view is explicitly
labelled in the output so it remains identified when controls are hidden in print.

Key commands were `node docs/draft-v2-explained/tools/check.mjs` and a temporary
Playwright smoke script at `/tmp/higgsml-draft001-site-qa.cjs` using
`chromium.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'})`.
The temporary script exercised navigation, widgets, responsive states and print
media. These scripts/screenshots are local QA evidence, not scientific artifacts.

## Limits

Native fullscreen behavior, native print-dialog interaction, printed pagination
and other browsers/devices were not validated. Print checks cover CSS visibility
and the button dispatch, not a publication-quality PDF export.
No full repository regression suite was rerun for this static documentation change.
No training, scoring, likelihood fitting, coverage study, bootstrap, Toys or T2
was performed. Presentation/source consistency does not establish independent
physics validation or promote the fixed exploratory qualification.

## Supervisor-request annotations — 2026-10-29

Added bilingual direct-response labels to slides 16–19 and a page-specific
explanation of the recorded supervisor request within each existing explanation
pane. The overview links to all four pages and distinguishes the spectrum
request from the unchanged W68 objective. Numerical inputs and figures are unchanged.

The Node consistency check passed. Installed Chrome through Playwright checked
32 slides × two languages × desktop/mobile (1440×1000, 390×844): 128 states,
no page errors or document horizontal overflow. Both editions expose exactly four
request badges. Clicking the overview's spectrum link opened slide 17 with its
response visible. Desktop screenshots were captured for both languages. These
checks cover website presentation and consistency, not scientific validation or
supervisor acceptance. No event access, training, scoring or inference was run.
