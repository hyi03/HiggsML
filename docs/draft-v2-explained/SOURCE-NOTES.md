# Draft001 explanation: sources and limits

The source is the current `paper/draft-v2/main.tex`, its workflow, numerical
and spectrum inputs, and the completed report
`runs/h4l-draft-v2-draft001/report/`. This is a new three-subset analysis, not a
projection of historical test05 results.

Selected report artifact:
`9aab6d274a3e2d00d892c2d8fbf89b1e46f5b7a95d0bf0c085af90672ea36898`.

Its evaluation, freeze and prepared bindings are respectively:

- `01df03a5ea98bb098f6e3c2069fee50a17c67d06e53a1bd84003b1d6680aa324`
- `f93ef041a9d32120fcaa1af0272d1a2af00484d5e08a50cafccaf457f6a60e8d`
- `23c0e583716df4efdeb80654409aabc106661063ff765765712cab411e320953`

The synchronizer verifies report-file sizes and SHA-256 hashes, the explicit
report selection, completed upstream identities, freeze-file binding and equality
of report/evaluation summary, interval and spectrum aggregates. It recomputes all
median widths, twelve within-seed differences and their four medians. It requires
all sixteen numerical terminals and preserves the non-independent qualification.
The local projection includes consumed-file hashes and full grouped spectrum
statistics, including before/after and normalized-shape covariance.

Images are byte-for-byte copies of `mass-yields.png` and `mass-shapes.png` in the
report; no schematic distributions or mass peaks are manufactured. CSV downloads
likewise preserve original bytes. The signal/background group counts are 9,049
and 698. Display yields refer to 10 fb^-1 with evaluation weight normalization
`physical_weight / 0.2`, not MC row counts. Seven 5 GeV display bins differ from
the one mass bin used by the likelihood.

The projection preserves three-seed order 42, 43, 44. It does not interpret seed
variation as a confidence interval. The median-contrast widget calculates the
specified paired statistic from full-precision values. The weighted-median widget
uses separate hand-authored nonnegative-weight examples, explicitly labelled as
teaching arithmetic rather than measured MC results.

Scientific qualification stays `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, `primary_claim_eligible=false`. All-MC
source reuse includes historical test events. Repartitioning does not restore
independence. Template uncertainty within T1 does not calibrate all width contrasts,
threshold selection or whole-procedure coverage.

This documentation task opens only completed aggregate files. It performs no
training, scoring, fitting, bootstrap, Toy, T2, Shapley, CDF or adversarial execution,
and reads no event or checkpoint payload. Website and arithmetic checks are not
independent physics validation. The manuscript's
[evidence record](../../paper/draft-v2/DRAFT001-EVIDENCE.md) supplies further context.
