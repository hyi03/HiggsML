# F4 / F11 / F12: evidence-version and qualification alignment

## Record scope and subsequent changes

Historical date: 2026-09-23. Baseline:
`5275fc586ec25d41e84459e665c168dba6a31671`; changes were uncommitted at the time.
This record was translated into English and relocated on 2026-10-06 from
`docs/changes/evidence-alignment-20260923.md`. Original text remains in Git history
before migration (HEAD `e1448f3eb1b841b371d82b3ccfc1bc4f7f2bf160`). The request
came from section 3 and F4/F11/F12 of the research-quality solution confirmation,
historically `docs/4-Reviews/research-quality-audit-2026-09-23-review-confirm.md`
(an ignored local review, not a distributed evidence source).

This is test01 restoration and software-verification history, not the current
paper's selected numerical source. The paper later selected test05; use the
[paper evidence index](../../paper/result-evidence.md), [build instructions](../../paper/README.md)
and [current results](../results-and-limitations.md).
The historical sync_manuscript.py command below no longer exists. Old Chinese/
English manuscript synchronization and snapshot-required builds describe the
then-existing workflow; ordinary current compilation uses committed assets.
Local runs/var/paper-evidence files and old host paths are not bundled with Git;
their original checks were not repeated during migration. Preserve historical
bindings without claiming the archived inputs are available on this machine.

## Changes and source selection

- Automatic P0/T1 moved to v2 contract_checked. Independent references became
  null; T1 stopped counting schema checks as numerical experiments. Source audit,
  independent numerical validation, physical applicability and confirmation
  eligibility each remained false.
- prepare, G0, G1/check, training wrappers, T1 and sample-efficiency consumers
  accepted v2. Old v1 remained software-compatibility input only. New audits no
  longer inferred physics_sources_validated from nonempty references. Independent
  evidence, history and assessment gates still separately constrained qualification.
- Old run bytes were unchanged. New exports recorded conservative interpretations
  alongside original report/audit qualification fields, without rewriting v1 history.
- The exporter accepted --report or --evidence-manifest and followed manifest/freeze
  to Asimov, registration, named preparation and available evaluation. Path remapping
  did not change IDs; bytes, manifest identities, protocol-content digests and
  main lineage had to match. Where old access was not a report upstream, the source
  manifest explicitly pinned access ID and checked freeze/specification bindings.
- Stage B, invalid_or_consumed_output, failed/complete bootstrap and both access
  independence states retained their actual status. Bootstrap ranges no longer
  had to be empty, nor access independence false. Output required a fresh directory.
- Chinese/English manuscripts shared a pinned snapshot. English coverage-table/
  prose conflict, Chinese model-self completeness and historical implementation
  architecture were corrected. Chinese tables and English figures used the same
  selection file; builds rejected mixed results.

The user located original test01 under `var/runs-test-01/`, while then-current
runs/ held incomplete work. Exact hash matching identified **h4l-off-test01-old1**;
the other h4l-off-test01 differed. Sizes/SHA-256/manifest hashes matched for all
14 original aggregate source files. All 75 referenced training manifest IDs
matched, with execution revision
`a4ecb8f3799729a01bb05aa00f1f5ef7c11b854a`. That revision's code had two Dropout
and three LayerNorm layers. The original version/source/qualification matrix was
maintained in the paper evidence index; that index now describes the later selection.

## Verification record

Actual environment: Windows AMD64, Python 3.12.13, existing pytorch interpreter
`C:/Users/whchen/anaconda3/envs/pytorch/python.exe`. The AGENTS example
`D:/apps/anaconda3/Scripts/conda.exe` did not exist on that host; no environment
or dependency change was made.

| Level | Historical execution and boundary |
|---|---|
| Initial full software suite | python -m pytest -q --basetemp D:/t/h4l-f41112-all: 577 passed, 5 skipped, 509 warnings, 902.18 s; later exporter fixes mean this was not the final suite |
| Wrapper regression | Old check/run initially rejected v2; reproduced failure then fixed; complete script tests: 59 passed, 1 skipped |
| Exporter/T1 focused regression | 11 passed, 6 deselected, 2 warnings: v2/legacy model equality, qualification guards, Stage B, complete/failed bootstrap, relocation, missing/tampered sources, protocol mismatch and snapshot drift |
| Final full software suite | python -m pytest -q --basetemp D:/t/h4l-f41112-final: **596 passed, 5 skipped, 511 warnings, 922.92 s**; no failures. pyhf/jsonschema.RefResolver deprecation; skips not counted as passes. Log: runs/f4-f11-f12-final-suite.log |
| Original archival bytes | 14/14 aggregate files/manifests checked; var/paper-evidence/test01-restoration-20260923.json |
| Fresh aggregate exports | Selected test01: 15 files; test03 Stage B: 12 files, 36 units not_run. Algebra checked for 80 nominal, 4 Shapley, 24 interactions and 105 pairs |
| Manuscript consistency | python paper/scripts/sync_manuscript.py --check passed; English macros from the same pinned snapshot |
| PDF | python paper/scripts/build.py --evidence-manifest paper/evidence/test01-source.json passed, then passed again after date update. No undefined references, overfull boxes or stuck floats. 13 pages; final pages 9--10 and earlier page 8 rendered without clipping/overlap; isolated source paragraph page overflow removed. Extracted text had no ?? or replacement characters |
| Static checks | git diff --check and pip check passed; 32 modified/new text files had no CRLF; generated evidence remained ignored |
| Independent numerical/scientific qualification | No new independent numerical validation, formal MC bootstrap/Toy/assessment/T2 or physical-applicability audit; software/aggregate recalculation did not grant qualification |

Pre-existing review documents were untracked user files and retained. Original
Chinese evidence-index text was archived at
`paper/evidence/history/result-evidence-20260921.md`; old aggregate bytes remained
unchanged. Independent code review identified wrapper v2 compatibility,
provenance timestamp refresh, unpublished bootstrap-failure state and protocol
content-digest issues; focused regressions addressed them.

## Historical reproduction and rerun boundaries

These archival commands require the old source tree, interpreter and local archive;
they are not current setup instructions:

```powershell
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' paper/scripts/collect_evidence.py --evidence-manifest paper/evidence/test01-source.json --output var/paper-evidence/test01-fresh-check
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' paper/scripts/sync_manuscript.py --check
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' paper/scripts/build.py --evidence-manifest paper/evidence/test01-source.json
```

Export/prose revision did not require preparation, training or inference reruns.
A new execution adopting v2 audit contracts required affected audit/freeze/downstream
qualification in a new root; old artifacts were not upgraded in place.
Independent-validation and qualification gaps remained subject to scientific
gates; passing tests/source restoration did not remove them.
At the time, build inputs were local archives, not a permanent external publication.
A clean checkout needed selected snapshot/provenance or mapped original archives;
recompiling was not full scientific reproduction. Later committed paper assets
changed ordinary compilation requirements, not these historical checks.
