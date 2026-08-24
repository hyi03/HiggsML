# HiggsML Obsidian Research Vault Design

**Date:** 2026-08-25  
**Status:** Approved in chat; pending written-spec review

## 1. Purpose and scope

Create a private Obsidian vault dedicated to the HiggsML project. The vault is a
personal research workspace for daily progress, experiments, research decisions,
open questions, meetings, literature, and reusable physics or machine-learning
knowledge.

The vault is separate from the Git repository and is stored locally at
`~/Documents/HiggsML Notes/`. Repository documentation remains the authoritative
source for accepted project state, scientific constraints, implementation plans,
and shared results. The vault may contain preliminary reasoning and private notes,
but it must not become a competing source of truth.

The first version is local-only. It does not use iCloud, Obsidian Sync, or a Git
remote.

## 2. Design principles

The system combines three complementary views without duplicating content:

1. **Chronological capture:** daily notes record what happened and when.
2. **Research workflow:** experiments, decisions, meetings, and research questions
   preserve structured evidence and outcomes.
3. **Knowledge network:** literature and atomic concept notes preserve reusable
   knowledge through backlinks.

Daily notes link to structured notes. Structured notes link to decisions and
knowledge. Information is promoted by linking and refinement rather than copied
into several locations.

## 3. Vault structure

```text
HiggsML Notes/
├── 00 Home/
├── 01 Daily/
├── 02 Experiments/
├── 03 Decisions/
├── 04 Research Questions/
├── 05 Literature/
├── 06 Meetings/
├── 07 Knowledge/
├── 08 Project Reference/
├── 90 Templates/
├── 99 Archive/
└── _attachments/
```

- `00 Home` contains the landing page, active-work index, and navigation.
- `01 Daily` contains one note per working day.
- `02 Experiments` contains reproducible training, ablation, and validation records.
- `03 Decisions` records important methodological or implementation decisions.
- `04 Research Questions` tracks hypotheses and unresolved questions.
- `05 Literature` contains paper notes and citations.
- `06 Meetings` contains supervisor and project meeting notes.
- `07 Knowledge` contains atomic physics and machine-learning concept notes.
- `08 Project Reference` contains repository paths, canonical-document links, and
  frequently used commands.
- `90 Templates` contains the note templates.
- `99 Archive` contains inactive or superseded personal notes.
- `_attachments` contains small images and other attachments used by notes.

## 4. Note templates

### 4.1 Daily note

The daily template contains:

- today's goals;
- chronological work log;
- blockers and unresolved questions;
- temporary ideas;
- links to experiments, meetings, decisions, and knowledge notes;
- next actions.

The daily note is optimized for fast capture. It does not need a bilingual summary.

### 4.2 Experiment

The experiment template contains:

- research hypothesis;
- data boundary and dataset identity;
- Git commit;
- configuration path and run path;
- exact command;
- environment or dependency notes when relevant;
- metrics and plots;
- observations and failure modes;
- Chinese conclusion;
- English summary;
- next experiment or decision links.

An experiment note must distinguish an intended run from a completed run. Results
must not be written as established until the command has finished and the relevant
artifacts have been checked.

### 4.3 Research decision

The decision template contains:

- question or decision context;
- candidate options;
- evidence and constraints;
- selected decision;
- consequences;
- conditions that would justify reconsideration;
- Chinese conclusion;
- English summary.

### 4.4 Research question

The research-question template contains:

- question or hypothesis;
- motivation;
- current evidence;
- proposed test;
- status;
- linked experiments, literature, decisions, and knowledge notes.

### 4.5 Literature note

The literature template contains:

- complete citation and source link;
- research problem;
- method;
- main evidence;
- limitations;
- relevance to HiggsML;
- Chinese conclusion;
- English summary;
- linked concepts and research questions.

### 4.6 Meeting note

The meeting template contains:

- date and participants;
- agenda;
- discussion notes;
- decisions;
- action items, owners, and deadlines;
- links to affected experiments, questions, and decisions.

### 4.7 Knowledge note

The knowledge template contains:

- concept definition;
- intuition;
- equations or technical details when useful;
- application in HiggsML;
- sources;
- Chinese conclusion;
- English summary;
- related knowledge, literature, and experiment links.

Knowledge notes should be atomic enough to describe one concept clearly, but they
should not be split merely to increase graph size.

## 5. Language and naming

The vault is bilingual without requiring paragraph-by-paragraph translation.

- Working text may be written in Chinese or English.
- Durable experiment, decision, literature, and knowledge notes include both a
  `中文结论` section and an `English Summary` section.
- Code, commands, configuration keys, metric names, paths, and established paper
  terminology remain in English.
- File names use dates and filesystem-friendly English slugs, for example
  `2026-08-25-adversarial-decorrelation-baseline.md`.
- Note titles inside the document may include both Chinese and English names.

## 6. Metadata

Structured notes use a small common property set:

```yaml
type: experiment
date: 2026-08-25
status: active
tags:
  - higgsml
related: []
git_commit:
config:
run_path:
```

Only relevant properties appear on each note type. For example, literature notes do
not need `git_commit`, and knowledge notes do not need `run_path`. Status values are
kept small and explicit: `idea`, `active`, `blocked`, `complete`, or `archived`.

## 7. Information flow and maintenance

The normal flow is:

```text
Daily capture
    -> experiment, meeting, or research-question note
    -> decision and reusable knowledge
    -> Home index and topic links
```

A weekly review should take about 15 minutes:

1. resolve or move temporary ideas from daily notes;
2. complete conclusions for finished experiments;
3. create decision notes for consequential choices;
4. extract only genuinely reusable knowledge;
5. update active work on the Home page;
6. archive stale personal tasks and superseded notes.

## 8. Repository integration and scientific provenance

`08 Project Reference` records the local repository root and links to canonical
files such as `project/AGENTS.md`, `project/README.md`, the project overview, the
roadmap, physics standards, and current design documents.

The vault does not copy repository documentation and does not symlink the repository
into the vault. This prevents accidental edits and conflicting versions.

Experiment notes record an immutable Git commit when possible, plus the exact
configuration and run paths. Paths to ignored run artifacts are treated as local
references that may later disappear; the note must therefore preserve the essential
metrics, outcome, and provenance needed to understand the result.

Small, interpretation-critical figures may be copied to `_attachments`. Large ROOT
files, processed tables, model files, and complete run directories remain outside
the vault. Their paths may be recorded, but the vault must not duplicate them.

If the repository moves, the `Project Paths` reference note is updated. Other notes
should link through the project reference notes where practical rather than repeat
the repository root throughout the vault.

## 9. Obsidian configuration

The initial version uses core Obsidian features only:

- Daily Notes;
- Templates;
- Properties;
- Backlinks;
- Tags;
- File Recovery.

Daily Notes writes into `01 Daily` and uses the daily template. Templates are read
from `90 Templates`. New attachments are stored in `_attachments`.

Community plugins such as Dataview and Templater are intentionally excluded from
the initial version. They may be evaluated after the manual workflow has been used
long enough to identify a concrete automation need.

## 10. Failure handling and backup

- Obsidian File Recovery provides short-term recovery from accidental edits.
- The whole vault is copied or compressed to a separate local backup location once
  per week, retaining multiple dated versions.
- Time Machine, if enabled, should include the vault and its backup location.
- Backup success is not inferred from file creation: at least one archive must be
  opened or restored into a temporary directory and checked.
- A broken repository link does not invalidate the note; the repository root in the
  project reference is corrected and affected links are rechecked.
- Missing run artifacts are noted explicitly rather than silently removed from an
  experiment record.

## 11. Acceptance criteria

The setup is complete when:

1. Obsidian opens `~/Documents/HiggsML Notes/` as a vault.
2. All specified folders and templates exist.
3. Daily Notes and Templates point to the correct folders.
4. Attachments are stored in `_attachments`.
5. Each template creates a readable note with valid properties.
6. A daily note can link to an experiment, decision, and knowledge note, and the
   backlinks are visible.
7. Project reference links and common commands match the current HiggsML checkout.
8. Search finds both Chinese and English summaries.
9. A small test attachment renders correctly.
10. A dated backup can be restored and opened independently.

## 12. Non-goals

The initial implementation does not:

- move or reorganize the HiggsML repository;
- replace canonical repository documentation;
- copy large datasets or run artifacts into Obsidian;
- install community plugins;
- configure cloud synchronization;
- publish the private vault;
- automate note generation from training runs.
