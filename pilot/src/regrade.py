"""POST HOC, EXPLORATORY (added 2026-11-08 after REPORT.md's first version). Re-scores the existing judge calls with
graded rewards, with no new calls. Writes results/regrade.json (aggregates and card IDs only).
  python3 src/regrade.py
Rewards, per training card (K = 4 samples, 3 calls each; 6 baseline calls on the card as filed):
  mean-below: a sample is kept if its mean single-call score is below the mean of the card's 6 baseline calls.
  best-of-K:  the card's lowest-mean sample is kept if it is below the baseline mean (at most one per card).
  relative:   the card's lowest-mean sample is kept if strictly lower than the card's other samples (no baseline);
              this is what pure best-of-K expert iteration would train on.
Noise floor: the same rule applied to re-judgings of the unchanged card, simulated from each card's own 6 baseline
calls (draw a 6-call baseline and K 3-call pseudo-samples with replacement)."""
import json
import os
from collections import defaultdict

import numpy as np

from common import D, ROOT, SPLIT, load

B = 10_000
rng = np.random.default_rng(20261108)


def boot(vals):
    v = np.array(vals, float)
    bs = v[rng.integers(0, len(v), (B, len(v)))].mean(1)
    return [round(100 * float(np.percentile(bs, 2.5)), 1), round(100 * float(np.percentile(bs, 97.5)), 1)]


def pct(x):
    return round(100 * float(x), 1)


def main():
    base = {r["key"]: r for r in load(D("judged-baseline.jsonl"))}
    smp = {r["key"]: r for r in load(D("judged-samples.jsonl"))}
    sec = {r["key"]: r for r in load(D("judged-second.jsonl"))}
    mis = {r["key"]: r["misleading"] for r in load(D("graded.jsonl"))}
    cards = sorted(base)
    bmean = {c: np.mean(base[c]["scores"]) for c in cards}
    bmeanA = {c: np.mean(base[c]["scores"][:3]) for c in cards}
    bmeanB = {c: np.mean(base[c]["scores"][3:]) for c in cards}
    by = defaultdict(list)
    for k, r in smp.items():
        by[k.split("#")[0]].append((k, float(np.mean(r["scores"]))))
    out = {}

    # mean-below, per sample
    per = {c: np.mean([m < bmean[c] for _, m in by[c]]) for c in cards}
    up = {c: np.mean([m > bmean[c] for _, m in by[c]]) for c in cards}
    out["mean_below"] = {"samples": int(sum(m < bmean[c] for c in cards for _, m in by[c])), "rate": pct(np.mean(list(per.values()))),
                         "ci_card": boot(list(per.values())), "raise_rate": pct(np.mean(list(up.values())))}

    # best-of-K
    best = {c: min(by[c], key=lambda x: (x[1], x[0])) for c in cards}
    kept_best = {c: best[c][1] < bmean[c] for c in cards}
    out["best_of_K"] = {"cards_kept": int(sum(kept_best.values())), "ci_card": boot([float(v) for v in kept_best.values()]),
                        "kept_cards": sorted(c for c in cards if kept_best[c]),
                        "mean_drop_when_kept": round(float(np.mean([bmean[c] - best[c][1] for c in cards if kept_best[c]])), 2)
                        if any(kept_best.values()) else None}
    # replication of best-of-K against independent halves of the baseline
    kA = {c: best[c][1] < bmeanA[c] for c in cards}
    kB = {c: best[c][1] < bmeanB[c] for c in cards}
    out["best_of_K"]["vs_baseline_half_A"] = int(sum(kA.values()))
    out["best_of_K"]["vs_baseline_half_B"] = int(sum(kB.values()))
    out["best_of_K"]["kept_vs_both_halves"] = int(sum(kA[c] and kB[c] for c in cards))
    # where the best sample also got a second majority, does it stay below?
    rep = [(c, float(np.mean(sec[best[c][0]]["scores"])) < bmean[c]) for c in cards if kept_best[c] and best[c][0] in sec]
    out["best_of_K"]["second_scoring_available"] = len(rep)
    out["best_of_K"]["second_scoring_still_below"] = int(sum(v for _, v in rep))

    # noise floor (parametric bootstrap from each card's own 6 calls)
    def null_rate(K, nsim=2000):
        rates_best, rates_sample = [], []
        for c in cards:
            s = np.array(base[c]["scores"], float)
            bl = rng.choice(s, (nsim, 6)).mean(1)
            ps = rng.choice(s, (nsim, K, 3)).mean(2)
            rates_best.append(np.mean(ps.min(1) < bl))
            rates_sample.append(np.mean(ps < bl[:, None]))
        return pct(np.mean(rates_sample)), pct(np.mean(rates_best))
    ns, nb = null_rate(4)
    out["noise_floor_K4"] = {"mean_below_per_sample": ns, "best_of_K_cards": nb}
    out["noise_floor_by_K_best_of_K_cards"] = {K: null_rate(K)[1] for K in (8, 16, 32)}
    out["cards_with_any_baseline_variation"] = sum(len(set(base[c]["scores"])) > 1 for c in cards)

    # relative best-of-K: what selection keeps, compared within card (misleading = Haiku grader, unvalidated)
    rel, pairs = [], []
    for c in cards:
        s = sorted(by[c], key=lambda x: x[1])
        if s[0][1] < s[1][1]:
            others = [mis[k] for k, _ in s[1:] if mis.get(k) is not None]
            if mis.get(s[0][0]) is not None and others:
                rel.append(c)
                pairs.append((float(mis[s[0][0]]), float(np.mean(others))))
    if pairs:
        d = np.array([a - b for a, b in pairs])
        bs = d[rng.integers(0, len(d), (B, len(d)))].mean(1)
        out["relative"] = {"cards_with_a_strictly_lowest_sample": len(rel),
                           "misleading_lowest": pct(np.mean([a for a, _ in pairs])),
                           "misleading_others_same_card": pct(np.mean([b for _, b in pairs])),
                           "diff_pp": pct(d.mean()), "diff_ci": [pct(np.percentile(bs, 2.5)), pct(np.percentile(bs, 97.5))]}
    json.dump(out, open(os.path.join(ROOT, "results/regrade.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
