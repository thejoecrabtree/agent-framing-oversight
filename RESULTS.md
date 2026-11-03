# Results: does an agent's wording set its own oversight?

Joseph Gwilliam Crabtree, 2026-11-02. Plan: [PREREG.md](PREREG.md), committed before the full run; deviations are listed
there. Numbers below are from `results/summary.json` (aggregates only).

**Answer.** Yes, and each kind of judge is weak in a different place. The keyword classifier in force at incident #15
could be moved by the agent's own `kind` label: an attacker lowered its oversight on 22% of cards, and the fix shipped
after #15 cut that to 3%. Claude judges ignore the label but are moved by the agent's framing sentence: the same
attacker lowered Sonnet's oversight on 12% of cards against a 3% noise floor. A judge that reads only who acts and
where it goes cannot be moved at all, and in this data it asked a person no more often than the others.

## Set-up in one paragraph

156 real approval cards that the Texas Toy Lab's agents filed between 2 September and 29 October 2026. The 57 cards I
decided myself are the labels: 25 stopped, 32 passed as written. Five judges name a class, and the Lab's own gateway
turns the class into a verdict:

- rule-pre: the keyword classifier as it stood at incident #15;
- rule-post: the same classifier after the #15 fix;
- Claude Sonnet and Claude Haiku, each given the class list;
- effect: reads only the agent and the destination.

An attacker (Nemotron 3 Super 120B on my lab, told to get the action out without a person) rewrote each card:

- **A1:** the title, plus one framing line.
- **A2:** the same, plus the agent-chosen `kind` label.

In every rewrite, what would actually be published or sent stayed byte-for-byte the same. A Claude paraphrase of the
title (C1) gives the noise floor.

## Main table

Downgrade = share of the 156 cards whose oversight is lower than on the original card (95% bootstrap interval).

| Judge | C1 paraphrase | A1 framing | A2 framing + kind | Same class on a rerun |
|---|---|---|---|---|
| rule-pre (at #15) | 0.0% | 1.3% [0, 3.2] | **21.8% [15.4, 28.2]** | deterministic |
| rule-post (after fix) | 0.0% | 0.0% | 2.6% [0.6, 5.1] | deterministic |
| Claude Sonnet | 2.6% [0.6, 5.1] | **11.5% [7.1, 16.7]** | 3.8% [1.3, 7.1] | 68.6% [60.9, 75.6] |
| Claude Haiku | 7.7% [3.8, 12.2] | **16.0% [10.3, 21.8]** | 8.3% [4.5, 12.8] | not run |
| effect | 0.0% | 0.0% | 0.0% | deterministic |

- **The #15 fix worked against this attack.** On A2, rule-pre was downgraded on 30 cards where rule-post was not, and
  never the reverse (exact McNemar p = 2×10⁻⁹). Escapes, where a person would have seen the card and after
  rewording would not, fell from 24.6% to 2.3%.
- **Prose and labels are different attack surfaces.** The rule judges barely move on A1 and move a lot on A2. The
  Claude judges move most on A1, and on A2 sit close to their noise floor. Sonnet's escape rate on A1 is 6.1%
  [2.3, 10.6].
- **The Claude judge is noisy.** It names the same class on two runs only 68.6% of the time (`claude -p` gives no
  temperature control). That sets a floor under any robustness claim about it.

## What the person-decided cards add

- **Ask burden.** Every judge asks a person about 84–91% of the cards the person then passed as written. The effect judge (90.6%) costs
  no more than rule-post (90.6%) or Sonnet (90.6%), so prediction 4 (a wording-proof judge costs more asks) was not
  supported here.
- **False release.** Every judge releases 24–28% of the cards the person stopped. Under rule-post and effect, all of them are
  customer texts in the 5-minute recall window that the owner had granted. That is the policy working as written, not a
  classifier error. The one exception: Sonnet filed a rejected free-form text as the fixed acknowledgement template,
  which goes out with no recall window.

## When Claude was the attacker (A2c, secondary)

Given the same instructions as Nemotron, Claude Sonnet mostly flagged risk instead of hiding it:

- In 98 of 156 framings it asked the reviewer to check something; Nemotron did so in 1.
- It raised the Sonnet judge's oversight on 23 cards and lowered it on 4.
- It changed the `kind` label on 9 cards; Nemotron changed it on 70.

## Limits

- One small business, and one person's decisions: 57 labelled cards, so the intervals are wide.
- The destination field is agent-written prose here. A real effect judge would take it from the tool or API, so its
  zero is an upper bound on robustness, not a measurement of it.
- There is one attacker rewrite per card. A stronger, adaptive attacker that searches against each judge would do
  better.
- 21 of the 156 A2 rewrites came from the gateway's 30B fallback model. Without them the A2 downgrade rates barely
  move: rule-pre 24.4%, rule-post 3.0%, Sonnet 4.4%.

## What I would test next

An adaptive attacker given query access to each judge, and an effect judge that reads the real tool call rather than a
description of it.
