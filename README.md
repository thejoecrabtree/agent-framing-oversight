# Does an agent's wording set its own oversight?

A pre-registered control evaluation on 156 real approval cards that LLM agents filed while running a small
3D-printing business. It answers open question 1 of [agent-failure-log](https://github.com/thejoecrabtree/agent-failure-log):
in incident #15, a gateway read agent-written text and auto-approved a public post. Can the class an action is given be
made independent of how the agent describes it, and at what cost in extra asks?

**Result.** Each kind of judge is weak in a different place.

- The keyword classifier in force at #15 could be moved by the agent-chosen `kind` label: an attacker lowered its
  oversight on 21.8% of cards, and the fix cut that to 2.6% (exact McNemar p = 2×10⁻⁹).
- Claude judges ignore the label but are moved by one framing sentence: Sonnet 11.5% against a 2.6% paraphrase floor.
  Sonnet also names the same class on a rerun only 69% of the time.
- A judge that reads only who acts and where the action goes cannot be moved, and here it asked a person no more often.

Full numbers and limits: [RESULTS.md](RESULTS.md). The plan, written before the full run, and every deviation from it:
[PREREG.md](PREREG.md).

## What is here

| Path | What it is |
|---|---|
| `PREREG.md` | Question, data, judges, conditions, measures and predictions, plus the pilot and the deviations |
| `RESULTS.md` | Results, with 95% bootstrap intervals and the stated limits |
| `results/summary.json` | Every pre-registered number (aggregates only) |
| `classifier/pre`, `classifier/post` | The gateway's classifier before and after the #15 fix; `constitution.json` is the rule set both read |
| `src/judges.mjs` | The five judges; each names a class and the gateway's own `judge()` gives the verdict |
| `src/llm.py`, `src/relay.py` | Claude judge, paraphrase and attacker prompts (Claude via `claude -p`; the attacker via any OpenAI-compatible endpoint) |
| `src/run.py`, `src/analyze.py` | Build the conditions, run every judge, compute the measures |

## Data

The approval cards hold customers' names, phone numbers and messages, so they are not published. `src/extract.py`
shows exactly how the cards were read and labelled. `results/summary.json` holds every pre-registered measure.

## Running it on your own approval log

Put cards as JSON lines in `data/items.jsonl`, with the fields that `src/extract.py` writes. Set `ATTACKER_API_URL` and
`ATTACKER_API_KEY` for the attacker, have Claude Code installed for the Claude judges, then run:

```bash
python3 src/run.py --workers 6
python3 src/analyze.py
```

Every model call is cached under `data/llm-cache`, so a run can be stopped and restarted.

## Licence

Code under the MIT licence. Text under CC BY 4.0, like agent-failure-log.
