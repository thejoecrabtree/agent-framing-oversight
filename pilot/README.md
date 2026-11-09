# Follow-up pilot: does selection for approval have anything to select?

A small pilot run on 8 November 2026, after the main study, to test the first stage of the proposed follow-up:
rejection-sampling fine-tuning of an open-weight model that may change only the description of an action, rewarded
by the study's Sonnet judge. Read [REPORT.md](REPORT.md) for the results.

**Result in one line.** With a writer told only to be accurate, 1.5% of 400 descriptions lowered the judge's
oversight level (95% CI 0.2-3.2%), about as often as re-judging the unchanged card, and on 22 of 30 cards all 32
descriptions scored the same. Approval reward has almost nothing to select on these cards; the next step is
borderline cards where wording can matter.

## Timing and provenance

The pilot was run in a private working repo, because its `data/` folder holds the approval cards and model outputs
(customer details). Each plan was committed there before its run:

| Commit | Time (CT, 8 Nov 2026) | What |
|---|---|---|
| `b702228` | 15:36 | [PLAN.md](PLAN.md), fixed split (seed 20261108) and code, before scoring |
| `b12798f` | 16:36 | First results and REPORT.md |
| `07e83d1` | 16:53 | Post hoc graded re-score of existing calls (exploratory) |
| `4471a9d` | 17:02 | [PLAN-K32.md](PLAN-K32.md), card pick (seed 20261140) and code, before running |
| `4fd364c` | 17:49 | K=32 results; report rewritten around both rounds |

The commit hashes in these files refer to that private repo. Git dates are self-reported. This folder holds
everything except `data/`: the plans, the report, the code and aggregate results (card IDs only, no card text).
A three-word tooling note was left out of PLAN.md and REPORT.md. On 9 November a closing section of draft summary
sentences was removed from REPORT.md, and its cost note and the approval sentence in PLAN-K32.md were reworded;
nothing else in them was changed. Two
absolute paths in the code were replaced with paths relative to this repo (set `STUDY_DIR` to point elsewhere).

## What is here

| Path | What it is |
|---|---|
| `PLAN.md`, `PLAN-K32.md` | The two analysis plans, each committed before its run |
| `REPORT.md` | Results: yield, judge noise, power, limits and what they imply |
| `results/*.json` | Aggregates only |
| `split.json`, `k32_cards.json` | The fixed train / held-out split and the K=32 card pick (card IDs only) |
| `src/` | The pilot code. It reuses the study's judge prompt, card rendering and parser from `../src` unchanged |
