"""Aggregates for the report: yield, judge noise, power. Writes results/summary.json (aggregates and card IDs only).
  python3 src/analyze.py"""
import json
import os
from collections import defaultdict

import numpy as np
from scipy import optimize, special, stats

from common import D, ROOT, SPLIT, load

B = 10_000
rng = np.random.default_rng(20261108)


def med(xs):
    v = [x for x in xs if x is not None]
    return float(np.median(v)) if v else None


def boot(card_vals, groups=None, fn=np.mean):
    """95% bootstrap CI. card_vals: dict card -> value. If groups given (card -> group), resample groups."""
    if groups is None:
        v = np.array(list(card_vals.values()), float)
        idx = rng.integers(0, len(v), (B, len(v)))
        bs = np.array([fn(v[i]) for i in idx])
    else:
        by = defaultdict(list)
        for c, x in card_vals.items():
            by[groups[c]].append(x)
        gl = list(by.values())
        bs = []
        for _ in range(B):
            pick = rng.integers(0, len(gl), len(gl))
            bs.append(fn(np.concatenate([gl[i] for i in pick])))
        bs = np.array(bs)
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def pct(x):
    return round(100 * x, 1)


def betabin_fit(k, n):
    """MLE of Beta(a, b) for counts k out of n per card."""
    k, n = np.asarray(k), np.asarray(n)

    def nll(t):
        a, b = np.exp(t)
        return -np.sum(special.betaln(k + a, n - k + b) - special.betaln(a, b))
    r = optimize.minimize(nll, [0.0, 0.0], method="Nelder-Mead")
    return tuple(np.exp(r.x))


def main():
    split = json.load(open(SPLIT))["cards"]
    grp = {c: v["group"] for c, v in split.items()}
    base = {r["key"]: r for r in load(D("judged-baseline.jsonl"))}
    smp = {r["key"]: r for r in load(D("judged-samples.jsonl"))}
    sec = {r["key"]: r for r in load(D("judged-second.jsonl"))} if os.path.exists(D("judged-second.jsonl")) else {}
    graded = {r["key"]: r for r in load(D("graded.jsonl"))} if os.path.exists(D("graded.jsonl")) else {}
    samples = load(D("samples.jsonl"))
    cards = sorted(base)
    out = {"n_cards": len(cards), "n_samples": len(samples), "parsed": sum(s["parsed"] for s in samples),
           "writer_fallback": sum(s["fallback"] for s in samples)}

    bA = {c: med(base[c]["scores"][:3]) for c in cards}
    bB = {c: med(base[c]["scores"][3:6]) for c in cards}
    sm = {k: med(r["scores"][:3]) for k, r in smp.items()}
    card_of = {s["sid"]: s["id"] for s in samples}
    invalid = sum(x is None for r in list(base.values()) + list(smp.values()) + list(sec.values()) for x in r["scores"])
    out["invalid_calls"] = invalid

    # ---------- Q1 yield ----------
    def rates(ref, cmp=lambda s, b: s < b):
        per = defaultdict(list)
        for k, v in sm.items():
            c = card_of[k]
            per[c].append(1.0 if (v is not None and ref[c] is not None and cmp(v, ref[c])) else 0.0)
        return {c: float(np.mean(v)) for c, v in per.items()}, {c: int(sum(v)) for c, v in per.items()}

    rA, kA = rates(bA)
    rB, _ = rates(bB)
    both = {c: min(bA[c], bB[c]) for c in cards}
    rBoth, _ = rates(both)
    rUp, _ = rates(bA, lambda s, b: s > b)
    lowerable = [c for c in cards if bA[c] and bA[c] > 0]
    q1 = {
        "keep_vs_A": {"rate": pct(np.mean(list(rA.values()))), "ci_card": [pct(x) for x in boot(rA)],
                      "ci_group": [pct(x) for x in boot(rA, grp)]},
        "keep_vs_B": {"rate": pct(np.mean(list(rB.values()))), "ci_card": [pct(x) for x in boot(rB)]},
        "keep_vs_both": {"rate": pct(np.mean(list(rBoth.values()))), "ci_card": [pct(x) for x in boot(rBoth)]},
        "raise_vs_A": {"rate": pct(np.mean(list(rUp.values()))), "ci_card": [pct(x) for x in boot(rUp)]},
        "baseline_A_score_dist": {str(s): sum(1 for c in cards if bA[c] == s) for s in sorted({v for v in bA.values() if v is not None})},
        "n_lowerable_cards": len(lowerable),
        "keep_rate_among_lowerable": pct(np.mean([rA[c] for c in lowerable])),
        "ci_lowerable": [pct(x) for x in boot({c: rA[c] for c in lowerable})],
    }
    any_kept = {c: 1.0 if kA[c] > 0 else 0.0 for c in cards}
    q1["cards_with_ge1_kept"] = {"n": int(sum(any_kept.values())), "ci_card": [round(100 * x) for x in boot(any_kept, fn=np.mean)]}
    q1["kept_per_card_hist"] = {str(i): sum(1 for c in cards if kA[c] == i) for i in range(5)}
    q1["kept_by_card"] = {c: kA[c] for c in cards}
    a, b = betabin_fit([kA[c] for c in cards], [4] * len(cards))
    q1["betabin"] = {"a": a, "b": b, "mean": a / (a + b), "icc_rho": 1 / (a + b + 1)}
    q1["expected_cards_ge1_kept"] = {K: round(100 * (1 - np.exp(special.betaln(a, b + K) - special.betaln(a, b))), 1)
                                     for K in (4, 8, 16, 32)}
    # kept by agent (card IDs are fine; agent names are the Lab's own agent roles)
    out["q1"] = q1

    # ---------- Q2 noise ----------
    def triple_stats(rows, sl):
        all3 = maj = sc3 = 0
        n = 0
        for r in rows:
            cl = [c for c in r["classes"][sl] if c]
            if len(cl) < 3:
                continue
            n += 1
            all3 += len(set(cl)) == 1
            maj += max(cl.count(x) for x in cl) >= 2
            s = r["scores"][sl]
            sc3 += len(set(s)) == 1
        return {"n": n, "all3_same_class": pct(all3 / n), "class_majority_exists": pct(maj / n),
                "all3_same_score": pct(sc3 / n)}

    q2 = {"baseline_triples": triple_stats(list(base.values()) * 1, slice(0, 3)),
          "baseline_triples_B": triple_stats(list(base.values()), slice(3, 6)),
          "sample_triples": triple_stats(list(smp.values()), slice(0, 3))}
    # single-call self-consistency: mean pairwise class match over the 6 baseline calls
    pair = {}
    for c in cards:
        cl = base[c]["classes"]
        m = [cl[i] == cl[j] for i in range(6) for j in range(i + 1, 6) if cl[i] and cl[j]]
        pair[c] = float(np.mean(m))
    q2["single_call_class_match_baseline"] = {"rate": pct(np.mean(list(pair.values()))), "ci_card": [pct(x) for x in boot(pair)]}
    sp = {}
    for k, r in smp.items():
        cl = r["classes"][:3]
        m = [cl[i] == cl[j] for i in range(3) for j in range(i + 1, 3) if cl[i] and cl[j]]
        if m:
            sp[k] = float(np.mean(m))
    q2["single_call_class_match_samples"] = pct(np.mean(list(sp.values())))
    # majority flips
    flipA = {c: float(bA[c] != bB[c]) for c in cards}
    q2["baseline_majority_score_flip"] = {"rate": pct(np.mean(list(flipA.values()))), "ci_card": [pct(x) for x in boot(flipA)]}
    single_flip = {c: float(np.mean([base[c]["scores"][i] != base[c]["scores"][j] for i in range(6) for j in range(i + 1, 6)
                                     if base[c]["scores"][i] is not None and base[c]["scores"][j] is not None])) for c in cards}
    q2["baseline_single_call_score_flip"] = {"rate": pct(np.mean(list(single_flip.values()))), "ci_card": [pct(x) for x in boot(single_flip)]}
    if sec:
        m1 = {k: sm[k] for k in sec}
        m2 = {k: med(sec[k]["scores"]) for k in sec}
        c_ = {k: card_of[k] for k in sec}
        q2["sample_majority_score_flip"] = {"n": len(sec), "rate": pct(np.mean([m1[k] != m2[k] for k in sec])),
                                            "ci_card": [pct(x) for x in boot({c_[k]: float(m1[k] != m2[k]) for k in sec})]}
        keep1 = {k: m1[k] < bA[c_[k]] for k in sec}
        keep2_sameBase = {k: m2[k] < bA[c_[k]] for k in sec}
        keep2_indep = {k: m2[k] < bB[c_[k]] for k in sec}
        # single-call reward replication: (sample call 0 vs baseline call 0) vs (sample call 3 vs baseline call 3)
        s1 = {k: smp[k]["scores"][0] is not None and base[c_[k]]["scores"][0] is not None and smp[k]["scores"][0] < base[c_[k]]["scores"][0] for k in sec}
        s2 = {k: sec[k]["scores"][0] is not None and base[c_[k]]["scores"][3] is not None and sec[k]["scores"][0] < base[c_[k]]["scores"][3] for k in sec}

        def agree(x, y):
            v = {c_[k]: float(x[k] == y[k]) for k in sec}
            xs, ys = np.array([x[k] for k in sec], int), np.array([y[k] for k in sec], int)
            po = np.mean(xs == ys)
            pe = xs.mean() * ys.mean() + (1 - xs.mean()) * (1 - ys.mean())
            return {"agree": pct(po), "ci_card": [pct(z) for z in boot(v)], "kappa": round(float((po - pe) / (1 - pe)) if pe < 1 else 1.0, 2),
                    "pos_rate_1": pct(xs.mean()), "pos_rate_2": pct(ys.mean()),
                    "pos_both": int(np.sum(xs & ys)), "pos_either": int(np.sum(xs | ys))}
        q2["keep_flip_same_baseline_maj3"] = agree(keep1, keep2_sameBase)
        q2["keep_flip_independent_maj3"] = agree(keep1, keep2_indep)
        q2["keep_flip_independent_single_call"] = agree(s1, s2)
    out["q2"] = q2

    # ---------- misleading (exploratory) ----------
    if graded:
        mis = {k: r["misleading"] for k, r in graded.items()}
        orig = [mis.get(f"{c}#orig") for c in cards]
        smis = {k: mis.get(k) for k in sm}
        keptset = {k for k, v in sm.items() if v is not None and bA[card_of[k]] is not None and v < bA[card_of[k]]}
        per_card_mis = defaultdict(list)
        for k, v in smis.items():
            if v is not None:
                per_card_mis[card_of[k]].append(float(v))
        pcm = {c: float(np.mean(v)) for c, v in per_card_mis.items()}
        kept_m = [smis[k] for k in keptset if smis[k] is not None]
        nkept_m = [smis[k] for k in sm if k not in keptset and smis[k] is not None]
        out["misleading"] = {
            "grader_unparsed": sum(v is None for v in mis.values()),
            "original_titles": pct(np.mean([o for o in orig if o is not None])),
            "samples": pct(np.mean(list(pcm.values()))), "samples_ci_card": [pct(x) for x in boot(pcm)],
            "kept": {"n": len(kept_m), "rate": pct(np.mean(kept_m)) if kept_m else None},
            "not_kept": {"n": len(nkept_m), "rate": pct(np.mean(nkept_m))},
            "kept_vs_not_fisher_p": float(stats.fisher_exact([[sum(kept_m), len(kept_m) - sum(kept_m)],
                                                               [sum(nkept_m), len(nkept_m) - sum(nkept_m)]])[1]) if kept_m else None,
        }
        mk = defaultdict(int)
        for k in sm:
            if smis[k] is not None:
                mk[card_of[k]] += int(smis[k])
        ma, mb = betabin_fit([mk[c] for c in cards], [4] * len(cards))
        out["misleading"]["betabin"] = {"a": ma, "b": mb, "mean": ma / (ma + mb)}

    # ---------- Q3 power ----------
    held_sizes = defaultdict(int)
    for c, v in split.items():
        if v["side"] == "heldout":
            held_sizes[v["group"]] += 1
    sizes = list(held_sizes.values())
    frac_lowerable = len(lowerable) / len(cards)
    # rate model among lowerable cards only (non-lowerable cards cannot be kept)
    la, lb = betabin_fit([kA[c] for c in lowerable], [4] * len(lowerable))

    def sim_power(delta, K, mult, kind, nsim=1500):
        """Paired held-out comparison; delta = absolute change in the overall rate. Test over groups."""
        gs = sizes * mult
        n = sum(gs)
        hits = 0
        for _ in range(nsim):
            if kind == "approval":
                low = rng.random(n) < frac_lowerable
                p0 = np.where(low, rng.beta(la, lb, n), 0.0)
                # spread the effect over lowerable cards so the overall mean rises by delta
                p1 = np.where(low, np.clip(p0 + delta / frac_lowerable, 0, 1), 0.0)
            else:
                p0 = rng.beta(ma, mb, n)
                p1 = np.clip(p0 + delta, 0, 1)
            d = (rng.binomial(K, p1) - rng.binomial(K, p0)) / K
            gm = np.add.reduceat(d, np.cumsum([0] + gs[:-1])) / np.array(gs)
            if gm.std(ddof=1) == 0:
                hits += gm.mean() != 0
                continue
            t = gm.mean() / (gm.std(ddof=1) / np.sqrt(len(gm)))
            hits += abs(t) > stats.t.ppf(0.975, len(gm) - 1)
        return hits / nsim

    def mde(K, mult, kind):
        lo, hi = 0.0, 0.5
        for _ in range(12):
            mid = (lo + hi) / 2
            if sim_power(mid, K, mult, kind) >= 0.8:
                hi = mid
            else:
                lo = mid
        return round(100 * hi, 1)

    q3 = {"heldout_cards": sum(sizes), "heldout_groups": len(sizes), "frac_lowerable": round(frac_lowerable, 3),
          "lowerable_betabin": {"a": la, "b": lb, "mean": la / (la + lb)}, "mde_pp_approval": {}, "mde_pp_misleading": {}}
    for mult in (1, 2, 4):
        for K in (4, 8, 16, 32):
            q3["mde_pp_approval"][f"cards x{mult}, K={K}"] = mde(K, mult, "approval")
            if graded:
                q3["mde_pp_misleading"][f"cards x{mult}, K={K}"] = mde(K, mult, "misleading")
    out["q3"] = q3

    # ---------- cost ----------
    import glob
    from common import CACHE
    costs = [json.load(open(f)) for f in glob.glob(f"{CACHE}/*/*.json")]
    out["cost"] = {"claude_calls": sum(1 for j in costs if "cost" in j),
                   "sonnet_calls": sum(1 for j in costs if j.get("model") == "sonnet"),
                   "haiku_calls": sum(1 for j in costs if j.get("model") == "haiku"),
                   "usd_api_equivalent": round(sum(j.get("cost", 0) for j in costs), 2),
                   "lab_calls": sum(1 for j in costs if "seed" in j)}
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "results/summary.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "q1"}, indent=1))
    print(json.dumps({k: v for k, v in out["q1"].items() if k != "kept_by_card"}, indent=1))


if __name__ == "__main__":
    main()
