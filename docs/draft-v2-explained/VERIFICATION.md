# Current-site verification — 29 October 2026

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
