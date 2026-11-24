# Bilingual paper explanation: 33 slides

Open [English](index-en.html) or [Chinese](index.html) in a modern Chrome or Edge
browser. All resources are local: reading requires no server, Python, account or
internet access. Keep the entire `paper-explained` folder together. Links to the
manuscript and original figures additionally require the repository's relative
directory layout.

The language link in the top toolbar preserves the current slide number. Both
editions have the same 33-slide sequence, scientific results, teaching examples
and six interactive pages. Detailed explanations are expanded by default.

## Controls

- Use Left/Right, PageUp/PageDown, or Previous/Next. Home/End reach the endpoints.
- Enter a slide number, use Contents, or open a `#slide-25` address. Browser
  back/forward follows slide history. Keyboard shortcuts do not override controls.
- Details toggles the explanation below the slide and navigation. Its state
  persists while navigating; a reload restores the expanded default.
- Fullscreen uses the browser API. Print applies the shared stylesheet to all
  33 slides, with one 16:9 page per slide and explanations omitted. For PDF output,
  disable browser headers/footers and use the CSS page size.
- Interactive selections persist within the current document only. Switching
  languages keeps the slide, but resets widget selections and explanation state.

## Learning route

Slide 1 introduces the question; 2–3 connect μ, intervals, widths and comparison;
4 shows the workflow; 5–8 cover MC and processing; 9–11 explain inputs; 12–15
explain networks; 16–18 define categories; 19–22 explain likelihood and width;
23–24 compare subsets; 25–27 introduce and calculate Shapley values; 28 covers
conditional interactions; 29–32 discuss validation; 33 reviews the full chain.

Interactive pages are 12, 21, 23, 24, 27 and 28. The counts and intervals on
2–3 are independent hand-written examples. Slide 21 is an illustrative T0 model,
not a paper T1 refit. Slide 25 is a two-group teaching example, followed by the
actual four-group calculation. Network diagrams show architecture, not weights.

## Evidence and scientific status

Both editions share the same `data.js` and `math.js`; there is only one published
aggregate projection and one implementation of all numerical calculations.
Source: [main.tex](../../paper/latex/main.tex), the 2026-10-12 manuscript and its
committed figures/tables, bound by
[selected-snapshot.json](../../paper/selected-snapshot.json).

- Report ID: `baede583dc2ef36330af1184d266833f3e64a3179fc8d5ce8bff1b6867307cb5`.
- Results SHA-256: `f9cf1470480f8c8fab971077c7947361ffb5cd47f44502dafedd977687a3794f`.
- Provenance SHA-256: `009b8713e9c47b6d1d66932da424a3b779b0585ace25bd97860d445d5d4684da`.

Those hashes and the report identity were checked on 2026-10-26. Restored
aggregate availability does not constitute independent scientific validation.
Qualification remains `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, `primary_claim_eligible=false`; core scope
is `synthetic_software_defaults_not_physics_validation`.

This is an MC-only educational/technical workflow, not an ATLAS/CMS result,
Higgs discovery or physics measurement. Generator/detector configurations and
the applicability of signed-MC approximations retain their stated limitations.
Five seeds share the MC. Fixed-network MC percentile ranges are not total
confidence intervals, and complete selection-aware coverage remains unvalidated.

## Maintenance and checks

Chinese copy and UI are in the root JavaScript files; their English counterparts
are in `en/`. English reuses the root CSS with typography overrides. The HTML
entries use ordinary scripts, not modules or runtime translation/network services.
Keep slide numbering and teaching/example qualifications aligned when editing.

```powershell
node docs/paper-explained/tools/check.mjs
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python docs/paper-explained/tools/export_data.py --check
```

The first command checks arithmetic, bilingual slide correspondence, local
resources and LF endings. The second checks the selected aggregate projection.
Neither launches training, scientific refits, Toys or assessment access.
See [VERIFICATION.md](VERIFICATION.md) for browser checks and their limits.
