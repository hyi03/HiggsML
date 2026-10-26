# Teaching deck verification

The original 30-page deck was checked on Windows on 2026-10-26. The 32-page
revision was checked on 2026-10-27 as recorded below. These checks validate documentation,
presentation behavior, and arithmetic consistency with published aggregates.
They do not provide new scientific qualification.

## Data and arithmetic

- `tools/export_data.py --check` verified the selected snapshot hashes and
  report identity and reproduced `data.js` byte for byte.
- `node tools/check.mjs` checked 30 slides, all 80 nominal records, the complete
  15-subset median ranking, 20 per-seed Shapley values, the efficiency identity,
  equivalence with averaging all 24 permutations, 120 per-seed conditional
  interactions, and 525 per-seed paired comparisons and their medians.
- The four interval endpoints of the two illustrative T0 models meet their
  stated likelihood-ratio threshold. These models use hand-written teaching
  counts and are not a reproduction of a paper T1 fit.

## Browser checks

The deck was served from its own directory on a temporary loopback HTTP server.
All 30 slides were inspected in the in-app browser at desktop and narrow widths.
The tested viewport overrides were 1440 by 900, 1280 by 720, and 390 by 844;
application display scaling changes the corresponding CSS viewport dimensions.

- All 30 desktop slides fit their slide bodies. Narrow layouts have no
  document-level horizontal overflow; wide diagrams and tables scroll locally.
- Keyboard navigation, page entry, table of contents, browser back/forward,
  expandable explanations, and fullscreen entry/exit were exercised.
- All six interactive pages were exercised: feature/network selection, T0
  likelihood, rankings, paired comparisons, Shapley, and conditional interactions.
  Arrow keys in the likelihood slider do not change slides.
- Console inspection found no application errors during the exercised flows.
- Formula punctuation, feature colors, the complete ranking table, and narrow
  explanation wrapping were visually checked after corrections.

## Verification limits

The browser automation environment refuses `file://` navigation. Direct
double-click opening was therefore not verified in that environment. The deck
uses local ordinary scripts and CSS, inline SVG and MathML, and no module
imports, network fetches, remote fonts, or CDN dependencies.

The print action was exercised and the print stylesheet defines all 30 slides
as separate 16:9 pages. The operating-system print preview and final PDF page
count were not verified by automation. Browser print settings may affect output.

No downloads, retraining, likelihood refits, Toys, assessment access, or changes
to scientific protocols or paper selection were performed. The repository's
scientific test suite was not run for this documentation-only change.

## 32-page revision, 2026-10-27

Two introductory slides were inserted after the cover. The signal-strength
count table and the two interval examples are explicitly labelled as separate
hand-written teaching examples. Interval endpoints were not inferred from the
count table or published width-only aggregates. All original slides remain.

- The arithmetic and local-link check passed with 32 slides and the same 80
  nominal records. No result data or mathematical interaction logic changed.
- All 32 desktop slides were traversed with explanations open. The slide bodies
  had no vertical overflow and the document had no horizontal overflow.
- Both new slides were visually reviewed; a diagram caption overlap was removed.
  Both also passed narrow-screen document-width checks at a 390 by 844 viewport
  override, retaining local horizontal scrolling for the interval diagram.
- Explanations are visible and `aria-expanded=true` on initial load and reload.
  They update with each slide; manually collapsing them persists across slide
  changes until reload. Navigation remains above the explanation panel.
- The directory contains 32 links. Page entry, a directory jump, Home/End, and
  the disabled Next button on page 32 were verified in the browser.
- Script syntax and LF/local-link checks passed. The existing `file://` and
  system print-preview verification limits still apply; print CSS now includes
  all 32 slides through the existing generic slide selector.

## Shapley introduction, 33 pages, 2026-10-27

A dedicated two-group Shapley example was inserted as page 25. Its widths are
explicitly hand-written teaching values: 2.0, 1.6, 1.8, and 1.5. Averaging the
two orders gives contributions 0.35 and 0.15, which sum to the total reduction
0.50. It precedes the four-group definition and the existing numerical widget.

The 33-slide arithmetic/local-link/LF check and JavaScript syntax checks passed.
The new slide was visually checked at desktop and narrow widths without slide
body or document overflow, respectively. The 33-entry directory, the shifted
Shapley widget on page 27, the final-page Next boundary, and the default-open
explanation panel were verified in the browser. Existing scientific results
and interactive calculation logic were unchanged. File and print verification
limits above still apply.

## Bilingual edition, 2026-10-27

The English entry `index-en.html` is beside `index.html` in the same directory.
It loads translated content, SVG labels, widgets and navigation from `en/` and
shares the existing data, arithmetic and base CSS. Both editions retain 33 pages
and default-open explanations. English has separate screen/print typography.

- The extended check passed all 33 English pages, matched their figure bindings
  and six interactive-page locations to Chinese, rejected untranslated Chinese
  text in the English slide copy, and verified local resources and LF endings.
  The 80-result numerical checks remain unchanged and passed.
- All 33 English pages were traversed at desktop (1440 by 900 override) and narrow
  (390 by 844 override) widths. No desktop slide-body overflow or document-level
  horizontal overflow was found. All pages retained visible explanation panels.
- Desktop screenshots of all English pages were inspected, including formulas,
  diagrams and the complete ranking table. Wide mobile diagrams/tables scroll
  within their own containers.
- All six English interactions were exercised: 10-input AC network and empty
  baseline, merged T0 width 1.411 with a 1.01 probe, AC AUC leader / BCD seed-45
  width leader, AC-versus-ABCD paired median +1.425%, D/seed-46 Shapley −0.016000,
  and BC conditioned on AD/seed-42 interaction −0.02335.
- Switching English → Chinese → English on page 25 retained the page and
  default-open explanations. The English directory had 33 entries and a jump
  to page 3 was verified. Language switching intentionally resets widget state.
- No application console errors were found in the exercised English flows.
  The existing direct `file://` and operating-system print verification limits
  remain; this revision was previewed through the temporary loopback server.

This revision translates and packages teaching content. It does not change the
selected snapshot, protocols, numerical calculations or scientific qualification.
