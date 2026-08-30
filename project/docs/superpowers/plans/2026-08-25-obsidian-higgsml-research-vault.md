# HiggsML Obsidian Research Vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and verify a private, local-only Obsidian vault for the complete bilingual HiggsML research workflow.

**Architecture:** The vault lives outside Git at `~/Documents/HiggsML Notes/`. Daily capture links to structured experiments, decisions, questions, meetings, literature, and atomic knowledge; repository documents remain authoritative and are referenced rather than copied. The first version uses only Obsidian core features and a manually verified dated backup.

**Tech Stack:** Markdown, YAML properties, JSON Obsidian configuration, Obsidian core plugins, macOS filesystem tools

**Spec:** `project/docs/superpowers/specs/2026-08-25-obsidian-higgsml-research-vault-design.md`

## Global Constraints

- Vault root: `~/Documents/HiggsML Notes/`.
- Backup root: `~/Documents/HiggsML Notes Backups/`.
- The vault is private, local-only, and dedicated to HiggsML.
- Do not configure cloud sync, a Git remote, publication, or community plugins.
- Do not move, copy, or symlink the HiggsML repository into the vault.
- Repository documents remain authoritative; vault notes are private working material.
- Do not copy datasets, ROOT files, models, or complete run directories into the vault.
- Durable experiment, decision, literature, and knowledge notes contain both `中文结论` and `English Summary`.
- Use English date-slug filenames; working prose may be Chinese or English.
- Preserve unrelated user files and existing Obsidian vaults.
- Use `apply_patch` for text edits; shell commands are limited to inspection, directory creation, backup, and restore verification.

---

## File Map

```text
~/Documents/HiggsML Notes/
├── 00 Home/HiggsML Home.md
├── 01 Daily/
├── 02 Experiments/
├── 03 Decisions/
├── 04 Research Questions/
├── 05 Literature/
├── 06 Meetings/
├── 07 Knowledge/
├── 08 Project Reference/
│   ├── Project Paths.md
│   ├── Canonical Documents.md
│   ├── Common Commands.md
│   └── Backup and Restore.md
├── 90 Templates/
│   ├── Daily Note.md
│   ├── Experiment.md
│   ├── Decision.md
│   ├── Research Question.md
│   ├── Literature.md
│   ├── Meeting.md
│   └── Knowledge.md
├── 99 Archive/Setup Verification/
└── _attachments/
```

---

### Task 1: Create the vault skeleton and Home note

**Files:**
- Create: all directories in the File Map
- Create: `~/Documents/HiggsML Notes/00 Home/HiggsML Home.md`

**Interfaces:**
- Consumes: fixed paths from Global Constraints
- Produces: folder contract for every later task

- [ ] **Step 1: Inspect the exact target**

Run:

```bash
if [ -e "$HOME/Documents/HiggsML Notes" ]; then
  find "$HOME/Documents/HiggsML Notes" -maxdepth 2 -print
else
  echo TARGET_ABSENT
fi
```

Expected: `TARGET_ABSENT`, or an inspected empty/incomplete vault. Stop if unrelated user content exists.

- [ ] **Step 2: Create the directories**

Run:

```bash
mkdir -p "$HOME/Documents/HiggsML Notes/00 Home" "$HOME/Documents/HiggsML Notes/01 Daily" "$HOME/Documents/HiggsML Notes/02 Experiments" "$HOME/Documents/HiggsML Notes/03 Decisions" "$HOME/Documents/HiggsML Notes/04 Research Questions" "$HOME/Documents/HiggsML Notes/05 Literature" "$HOME/Documents/HiggsML Notes/06 Meetings" "$HOME/Documents/HiggsML Notes/07 Knowledge" "$HOME/Documents/HiggsML Notes/08 Project Reference" "$HOME/Documents/HiggsML Notes/90 Templates" "$HOME/Documents/HiggsML Notes/99 Archive/Setup Verification" "$HOME/Documents/HiggsML Notes/_attachments"
```

Expected: exit code `0`.

- [ ] **Step 3: Create the Home note with `apply_patch`**

Use this exact body:

```markdown
---
type: home
date: 2026-08-25
status: active
tags: [higgsml]
---
# HiggsML Research Home

## Current work / 当前工作
- [[Today's Daily Note]]
- [[Active Research Questions]]
- [[Recent Experiments]]

## Research workflow / 科研工作流
- [[01 Daily]]
- [[02 Experiments]]
- [[03 Decisions]]
- [[04 Research Questions]]
- [[05 Literature]]
- [[06 Meetings]]
- [[07 Knowledge]]

## Project reference / 项目参考
- [[Project Paths]]
- [[Canonical Documents]]
- [[Common Commands]]
- [[Backup and Restore]]

## Review rhythm / 回顾节奏
- Daily: capture work, blockers, and next actions.
- Weekly: close experiments, extract decisions and knowledge, update this page, and create a backup.
```

- [ ] **Step 4: Verify and review**

Run `find "$HOME/Documents/HiggsML Notes" -maxdepth 2 -type d -print | sort` and `test -s "$HOME/Documents/HiggsML Notes/00 Home/HiggsML Home.md"`.

Expected: every mapped directory appears and the Home note is non-empty. Do not commit private vault files.

---

### Task 2: Create the seven note templates

**Files:**
- Create: all seven files under `~/Documents/HiggsML Notes/90 Templates/`

**Interfaces:**
- Consumes: Obsidian core variables `{{date}}`, `{{time}}`, and `{{title}}`
- Produces: templates configured in Task 4 and exercised in Task 5

- [ ] **Step 1: Create `Daily Note.md` with `apply_patch`**

```markdown
---
type: daily
date: {{date}}
status: active
tags: [higgsml, daily]
related: []
---
# {{date}}
## 今日目标 / Goals
- [ ]
## 工作日志 / Work log
- {{time}}
## 阻塞与问题 / Blockers and questions
-
## 临时想法 / Inbox
-
## 相关记录 / Related notes
- Experiment:
- Meeting:
- Decision:
- Knowledge:
## 下一步 / Next actions
- [ ]
```

- [ ] **Step 2: Create `Experiment.md` with `apply_patch`**

```markdown
---
type: experiment
date: {{date}}
status: idea
tags: [higgsml, experiment]
related: []
git_commit:
config:
run_path:
---
# {{title}}
## Hypothesis / 研究假设
## Data boundary / 数据边界
## Provenance / 溯源
- Git commit:
- Config:
- Run path:
- Environment notes:
## Command / 执行命令
## Metrics and artifacts / 指标与产物
## Observations and failure modes / 观察与失败模式
## 中文结论
## English Summary
## Next step and links / 下一步与链接
```

- [ ] **Step 3: Create `Decision.md` and `Research Question.md` with `apply_patch`**

`Decision.md`:

```markdown
---
type: decision
date: {{date}}
status: active
tags: [higgsml, decision]
related: []
---
# {{title}}
## Context and question / 背景与问题
## Options / 候选方案
## Evidence and constraints / 证据与约束
## Decision / 决定
## Consequences / 影响
## Reconsider when / 重新评估条件
## 中文结论
## English Summary
```

`Research Question.md`:

```markdown
---
type: research-question
date: {{date}}
status: idea
tags: [higgsml, research-question]
related: []
---
# {{title}}
## Question or hypothesis / 问题或假设
## Motivation / 动机
## Current evidence / 当前证据
## Proposed test / 拟议验证
## Status and links / 状态与链接
```

- [ ] **Step 4: Create `Literature.md`, `Meeting.md`, and `Knowledge.md` with `apply_patch`**

`Literature.md`:

```markdown
---
type: literature
date: {{date}}
status: active
tags: [higgsml, literature]
related: []
authors:
year:
source:
---
# {{title}}
## Citation / 引用
## Research problem / 研究问题
## Method / 方法
## Main evidence / 主要证据
## Limitations / 局限
## Relevance to HiggsML / 与项目的关系
## 中文结论
## English Summary
## Related concepts and questions / 相关概念与问题
```

`Meeting.md`:

```markdown
---
type: meeting
date: {{date}}
status: active
tags: [higgsml, meeting]
related: []
participants: []
---
# {{title}}
## Agenda / 议程
## Discussion / 讨论
## Decisions / 决定
## Action items / 行动项
- [ ] Action — Owner — Due date
## Related notes / 相关记录
```

`Knowledge.md`:

```markdown
---
type: knowledge
date: {{date}}
status: active
tags: [higgsml, knowledge]
related: []
sources: []
---
# {{title}}
## Definition / 定义
## Intuition / 直觉
## Technical details / 技术细节
## Application in HiggsML / 项目中的应用
## Sources / 来源
## 中文结论
## English Summary
## Related notes / 相关记录
```

- [ ] **Step 5: Verify template contracts**

Run:

```bash
test "$(find "$HOME/Documents/HiggsML Notes/90 Templates" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')" = 7
rg -L '^type:' "$HOME/Documents/HiggsML Notes/90 Templates"/*.md
rg -L '^date:' "$HOME/Documents/HiggsML Notes/90 Templates"/*.md
rg -L '^## 中文结论$' "$HOME/Documents/HiggsML Notes/90 Templates"/{Experiment,Decision,Literature,Knowledge}.md
rg -L '^## English Summary$' "$HOME/Documents/HiggsML Notes/90 Templates"/{Experiment,Decision,Literature,Knowledge}.md
```

Expected: the count check exits `0`; each `rg -L` prints nothing, indicating no required file lacks the pattern. Manually confirm YAML fences are balanced and no template contains project results.

---

### Task 3: Create project references and backup instructions

**Files:**
- Create: the four files under `~/Documents/HiggsML Notes/08 Project Reference/`

**Interfaces:**
- Consumes: repository root `/Users/xuhongyi/Code/HiggsML`
- Produces: path authority, canonical-document navigation, safe commands, and manual recovery instructions

- [ ] **Step 1: Validate canonical targets**

Run `test -f` separately for:

```text
/Users/xuhongyi/Code/HiggsML/project/AGENTS.md
/Users/xuhongyi/Code/HiggsML/project/README.md
/Users/xuhongyi/Code/HiggsML/project/docs/project/overview.md
/Users/xuhongyi/Code/HiggsML/project/docs/roadmap/next-stage.md
/Users/xuhongyi/Code/HiggsML/project/docs/physics/physics-principles.md
/Users/xuhongyi/Code/HiggsML/project/docs/physics/selection-standard.md
```

Expected: every check exits `0`; stop if a target moved.

- [ ] **Step 2: Create `Project Paths.md` and `Canonical Documents.md`**

`Project Paths.md` records exact repository, project, vault, and backup roots. `Canonical Documents.md` links the six validated files and states: “Repository documents are authoritative. Vault notes are private working material and must not silently override frozen scientific constraints.”

- [ ] **Step 3: Create `Common Commands.md`**

Include `git status --short`, `git log -5 --oneline`, the canonical reading order, and this project test command:

```bash
cd /Users/xuhongyi/Code/HiggsML/project
.venv/bin/python -m pytest -q
```

Label all commands as examples that must be checked against the current roadmap. Do not add any command that opens held-out test data or periodA real data.

- [ ] **Step 4: Create `Backup and Restore.md`**

Document these exact commands and explain each path:

```bash
mkdir -p "$HOME/Documents/HiggsML Notes Backups"
BACKUP_STAMP="$(date +%Y%m%d-%H%M%S)"
ditto -c -k --sequesterRsrc --keepParent "$HOME/Documents/HiggsML Notes" "$HOME/Documents/HiggsML Notes Backups/HiggsML-Notes-$BACKUP_STAMP.zip"
RESTORE_DIR="$(mktemp -d /tmp/higgsml-notes-restore.XXXXXX)"
ditto -x -k "$HOME/Documents/HiggsML Notes Backups/HiggsML-Notes-$BACKUP_STAMP.zip" "$RESTORE_DIR"
find "$RESTORE_DIR/HiggsML Notes" -type f -print
```

State that several dated backups should be retained and that a verified temporary restore directory may be moved to Trash afterward.

- [ ] **Step 5: Verify the references**

Run `rg -n '/Users/xuhongyi/Code/HiggsML|Repository documents are authoritative' "$HOME/Documents/HiggsML Notes/08 Project Reference"`.

Expected: exact paths and the authority statement appear; no repository file was copied or modified.

---

### Task 4: Configure the vault in Obsidian

**Files:**
- Generate/modify through Obsidian: `~/Documents/HiggsML Notes/.obsidian/`

**Interfaces:**
- Consumes: folders and templates from Tasks 1–3
- Produces: an Obsidian-recognized vault using core features only

- [ ] **Step 1: Confirm Obsidian is installed**

Run `test -d /Applications/Obsidian.app || test -d "$HOME/Applications/Obsidian.app"`.

Expected: exit `0`. If absent, ask the user to install it; do not download software implicitly.

- [ ] **Step 2: Open the correct folder as a vault**

In Obsidian choose **Open folder as vault** and select `/Users/xuhongyi/Documents/HiggsML Notes`. Confirm the file explorer shows the planned folders and `.obsidian` is created. Never select the Git repository.

- [ ] **Step 3: Configure Files and Links**

Enable automatic link updating. Set new attachments to **In the folder specified below** and the path to `_attachments`.

- [ ] **Step 4: Configure core Templates**

Enable **Templates**. Set template folder `90 Templates`, date format `YYYY-MM-DD`, and time format `HH:mm`. Confirm the insert-template command lists seven templates.

- [ ] **Step 5: Configure core Daily Notes**

Enable **Daily notes**. Set date format `YYYY-MM-DD`, new file location `01 Daily`, and template location `90 Templates/Daily Note`. Invoke today's note and confirm its actual-date filename and populated headings.

- [ ] **Step 6: Confirm core recovery and navigation**

Ensure Properties view, Backlinks, Tags view, and File Recovery are enabled. Do not enable community plugins or change Restricted Mode to install them.

- [ ] **Step 7: Validate generated configuration**

Close Obsidian. List `.obsidian` files and run `python3 -m json.tool` on `app.json` plus Daily Notes or Templates JSON files that exist.

Expected: checked JSON parses, `.obsidian` is outside the repository, and attachment/template/daily paths match the settings above.

---

### Task 5: Verify the workflow, backup, and restore

**Files:**
- Create: today's Daily Note
- Create: three dated setup notes in `99 Archive/Setup Verification/`
- Create: `_attachments/vault-setup-check.txt`
- Create: a dated ZIP under `~/Documents/HiggsML Notes Backups/`

**Interfaces:**
- Consumes: configured templates and backup instructions
- Produces: acceptance evidence for links, bilingual search, attachments, backup, and restore

- [ ] **Step 1: Create setup notes from templates**

Create an Experiment, Decision, and Knowledge note using Obsidian's insert-template command. Name each `<actual-date>-vault-setup-<type>.md` and move it under `99 Archive/Setup Verification` after template insertion.

Expected: properties survive the move; all three contain `中文结论` and `English Summary`.

- [ ] **Step 2: Create and inspect the link chain**

Link the three setup notes from today's Daily Note. Link the Decision and Knowledge notes from the Experiment. Fill summaries with:

```text
中文结论：Vault 模板、链接和属性验证通过；此记录仅用于设置验收。
English Summary: Vault templates, links, and properties passed setup verification; this record is only an acceptance check.
```

Expected: the Backlinks pane shows the Daily Note or Experiment backlink for each target.

- [ ] **Step 3: Verify search and attachments**

Create `_attachments/vault-setup-check.txt` containing `HiggsML vault attachment verification`, link it from the setup Experiment, and search for both `验证通过` and `passed setup verification`.

Expected: the attachment opens from the note and both searches find setup notes.

- [ ] **Step 4: Create and restore the first backup**

Run the exact commands from `Backup and Restore.md` with a new timestamp. Verify the ZIP is non-empty. Restore it into the generated temporary directory and run:

```bash
test -s "$RESTORE_DIR/HiggsML Notes/00 Home/HiggsML Home.md"
test -s "$RESTORE_DIR/HiggsML Notes/90 Templates/Experiment.md"
test -s "$RESTORE_DIR/HiggsML Notes/_attachments/vault-setup-check.txt"
test "$(find "$RESTORE_DIR/HiggsML Notes/90 Templates" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')" = 7
```

Expected: every check exits `0`.

- [ ] **Step 5: Run the final audit**

Run:

```bash
test -d "$HOME/Documents/HiggsML Notes/.obsidian"
test -d "$HOME/Documents/HiggsML Notes/01 Daily"
test -d "$HOME/Documents/HiggsML Notes/_attachments"
rg -n '^## 中文结论$|^## English Summary$' "$HOME/Documents/HiggsML Notes/99 Archive/Setup Verification"
find "$HOME/Documents/HiggsML Notes Backups" -maxdepth 1 -type f -name 'HiggsML-Notes-*.zip' -size +0 -print
git -C /Users/xuhongyi/Code/HiggsML status --short
```

Expected: filesystem checks pass, bilingual headings and a non-empty backup appear, and the repository has no unintended implementation changes.

- [ ] **Step 6: Hand off the working routine**

Open `00 Home/HiggsML Home.md` and show the user how to open today's note, insert templates, follow repository references, perform the 15-minute weekly review, and run then restore-check a backup. State that cloud sync and community plugins were intentionally omitted. Do not commit private vault contents.
