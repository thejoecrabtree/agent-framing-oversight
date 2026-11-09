"""K = 32 round on 30 training cards; see PLAN-K32.md.
  python3 src/k32.py pick | generate | screen | confirm | grade | analyze | all   [--budget 85]"""
import argparse
import json
import os
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from common import D, ROOT, SPLIT, items, judge_class, load, save
from generate import sample
from score import GRADER_SYSTEM, card_of, grade, guard, spent, to_scores

K, NCARDS, SEED = 32, 30, 20261140
CARDS = os.path.join(ROOT, "k32_cards.json")
WORKERS = 6


def pick():
    split = json.load(open(SPLIT))["cards"]
    train = sorted(c for c, v in split.items() if v["side"] == "train")
    chosen = sorted(random.Random(SEED).sample(train, NCARDS))
    json.dump({"seed": SEED, "cards": chosen}, open(CARDS, "w"), indent=1)
    print(f"picked {len(chosen)} cards")


def chosen_items():
    ids = set(json.load(open(CARDS))["cards"])
    return [it for it in items() if it["id"] in ids]


def generate():
    jobs = [(it, k) for it in chosen_items() for k in range(K)]
    with ThreadPoolExecutor(4) as pool:
        rows = list(pool.map(lambda j: sample(*j), jobs))
    save(D("k32-samples.jsonl"), rows)
    print(f"{len(rows)} samples; parsed {sum(r['parsed'] for r in rows)}; fallback {sum(r['fallback'] for r in rows)}")


def judge_rows(rows, runs, tag):
    jobs = [(r, run) for r in rows for run in runs]
    with ThreadPoolExecutor(WORKERS) as pool:
        cls = list(pool.map(lambda j: judge_class({"id": j[0]["id"], **j[0]["card"]}, j[1])[0], jobs))
    by = defaultdict(list)
    for (r, _), c in zip(jobs, cls):
        by[r["sid"]].append(c)
    rr = [{"key": r["sid"], "card": {"id": r["id"], **r["card"]}, "classes": by[r["sid"]]} for r in rows]
    sc = to_scores(rr)
    save(D(f"k32-{tag}.jsonl"), [{"key": r["key"], "classes": r["classes"], "scores": sc[r["key"]]} for r in rr])


def baseline_means():
    base = {r["key"]: r["scores"] for r in load(D("judged-baseline.jsonl"))}
    return base, {c: float(np.mean(s)) for c, s in base.items()}


def screen(budget):
    rows = [r for r in load(D("k32-samples.jsonl")) if r["parsed"]]
    if guard(len(rows), budget, "screen"):
        judge_rows(rows, [10], "screen")


def candidates():
    _, bm = baseline_means()
    sc = {r["key"]: r["scores"][0] for r in load(D("k32-screen.jsonl"))}
    return [r for r in load(D("k32-samples.jsonl")) if r["sid"] in sc and sc[r["sid"]] is not None and sc[r["sid"]] < bm[r["id"]]]


def confirm(budget):
    cand = candidates()
    if guard(3 * len(cand), budget, "confirm"):
        judge_rows(cand, [11, 12, 13], "confirm")


def grade_all(budget):
    rows = [r for r in load(D("k32-samples.jsonl")) if r["parsed"]]
    byid = {it["id"]: it for it in chosen_items()}
    if not guard(len(rows), budget, "grade", unit=0.002):
        return
    jobs = []
    for r in rows:
        orig = byid[r["id"]]["body"]
        framing = r["card"]["body"][: -len(orig)].strip() if orig and r["card"]["body"] != orig else ""
        jobs.append((r["sid"], card_of(byid[r["id"]]), r["card"]["title"], framing))
    with ThreadPoolExecutor(WORKERS) as pool:
        res = list(pool.map(lambda j: grade(j[1], j[2], j[3]), jobs))
    save(D("k32-graded.jsonl"), [{"key": j[0], **g} for j, g in zip(jobs, res)])


def analyze():
    rng = np.random.default_rng(SEED)
    base, bm = baseline_means()
    cards = json.load(open(CARDS))["cards"]
    smp = load(D("k32-samples.jsonl"))
    scr = {r["key"]: r["scores"][0] for r in load(D("k32-screen.jsonl"))}
    con = {r["key"]: r["scores"] for r in load(D("k32-confirm.jsonl"))} if os.path.exists(D("k32-confirm.jsonl")) else {}
    mis = {r["key"]: r["misleading"] for r in load(D("k32-graded.jsonl"))} if os.path.exists(D("k32-graded.jsonl")) else {}
    half = {c: (np.mean(base[c][:3]), np.mean(base[c][3:])) for c in cards}
    by = defaultdict(list)
    for r in smp:
        by[r["id"]].append(r["sid"])
    kept = {s for s, v in con.items() if None not in v and np.mean(v) < bm[s.split("#")[0]]}
    strict = {s for s in kept if all(np.mean(con[s]) < h for h in half[s.split("#")[0]])}
    per = {}
    for c in cards:
        ss = [scr.get(s) for s in by[c] if scr.get(s) is not None]
        per[c] = {"distinct_screen_scores": len(set(ss)), "screen_below": sum(x < bm[c] for x in ss),
                  "screen_above": sum(x > bm[c] for x in ss), "kept": sum(s in kept for s in by[c]),
                  "kept_strict": sum(s in strict for s in by[c]), "baseline_varies": len(set(base[c])) > 1}

    def bci(v):
        v = np.array(v, float)
        bs = v[rng.integers(0, len(v), (10000, len(v)))].mean(1)
        return [round(100 * float(np.percentile(bs, 2.5)), 1), round(100 * float(np.percentile(bs, 97.5)), 1)]

    # noise floor: two-stage rule on re-judgings of the unchanged card
    off = [x != np.median(r["scores"]) for r in load(D("judged-samples.jsonl")) for x in r["scores"]]
    eps = float(np.mean(off))

    def draw(c, shape):
        x = rng.choice(np.array(base[c], float), shape)
        move = rng.random(shape) < eps
        x = np.where(move, np.clip(x + rng.choice([-1, 1], shape), 0, 4), x)
        return x

    def null(c, nsim=4000, k=K, smooth=True):
        if smooth:
            s1 = draw(c, (nsim, k))
            cf = draw(c, (nsim, k, 3)).mean(2)
        else:
            s1 = rng.choice(np.array(base[c], float), (nsim, k))
            cf = rng.choice(np.array(base[c], float), (nsim, k, 3)).mean(2)
        keep = (s1 < bm[c]) & (cf < bm[c])
        return float(np.mean(keep.any(1))), float(np.mean(s1 < bm[c]))
    nl = {c: null(c) for c in cards}
    nl_raw = {c: null(c, smooth=False) for c in cards}
    ge1 = [float(per[c]["kept"] > 0) for c in cards]
    ge1s = [float(per[c]["kept_strict"] > 0) for c in cards]
    out = {
        "cards": len(cards), "samples": len(smp), "parsed": sum(r["parsed"] for r in smp),
        "writer_fallback": sum(r["fallback"] for r in smp),
        "screen_calls": len(scr), "candidates": len(con), "candidate_rate": round(100 * len(con) / max(1, len(scr)), 1),
        "screen_above_rate": round(100 * sum(p["screen_above"] for p in per.values()) / max(1, len(scr)), 1),
        "kept": len(kept), "kept_strict": len(strict),
        "cards_ge1_kept": int(sum(ge1)), "cards_ge1_kept_ci": bci(ge1),
        "cards_ge1_kept_strict": int(sum(ge1s)), "cards_ge1_kept_strict_ci": bci(ge1s),
        "noise_eps_per_call": round(eps, 4),
        "null_cards_ge1_kept_expected": round(sum(v[0] for v in nl.values()), 1),
        "null_cards_ge1_kept_expected_no_smoothing": round(sum(v[0] for v in nl_raw.values()), 1),
        "null_candidate_rate": round(100 * float(np.mean([v[1] for v in nl.values()])), 1),
        "cards_with_flat_screen": sum(p["distinct_screen_scores"] == 1 for p in per.values()),
        "distinct_screen_scores_hist": {str(n): sum(p["distinct_screen_scores"] == n for p in per.values()) for n in range(1, 6)},
        "kept_on_cards_with_varying_baseline": sum(p["kept"] for p in per.values() if p["baseline_varies"]),
        "cards_ge1_kept_stable_baseline": sum(p["kept"] > 0 and not p["baseline_varies"] for p in per.values()),
        "kept_per_card": {c: per[c]["kept"] for c in cards if per[c]["kept"]},
    }
    # first-round consistency: the k=0..3 samples on these cards
    if mis:
        km = [mis[s] for s in kept if mis.get(s) is not None]
        diffs = []
        for c in cards:
            ks = [mis[s] for s in by[c] if s in kept and mis.get(s) is not None]
            ns = [mis[s] for s in by[c] if s not in kept and mis.get(s) is not None]
            if ks and ns:
                diffs.append(np.mean(ks) - np.mean(ns))
        out["misleading"] = {"all_samples": round(100 * float(np.mean([v for v in mis.values() if v is not None])), 1),
                             "kept": round(100 * float(np.mean(km)), 1) if km else None, "kept_n": len(km),
                             "within_card_diff_pp": round(100 * float(np.mean(diffs)), 1) if diffs else None,
                             "within_card_diff_ci": bci(diffs) if len(diffs) > 1 else None, "cards_in_diff": len(diffs)}
    json.dump(out, open(os.path.join(ROOT, "results/k32.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--budget", type=float, default=85.0)
    a = ap.parse_args()
    steps = ["generate", "screen", "confirm", "grade", "analyze"] if a.step == "all" else [a.step]
    for s in steps:
        {"pick": pick, "generate": generate, "screen": lambda: screen(a.budget), "confirm": lambda: confirm(a.budget),
         "grade": lambda: grade_all(a.budget), "analyze": analyze}[s]()
        print(f"[{s}] done; spent ${spent():.2f}", flush=True)


if __name__ == "__main__":
    main()
