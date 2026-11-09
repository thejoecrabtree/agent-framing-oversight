"""Fix the train / held-out split before anything is scored.
Related scenarios = connected components of cards from the same agent whose titles or bodies share at least half their
word tokens (Jaccard >= 0.5 on lower-case tokens of 3+ letters): resubmissions after "changes", repeated campaign
posts, near-identical customer replies. Whole groups go to one side. Groups are shuffled with SEED and added to the
training side until it holds at least TARGET cards. Writes split.json (card IDs and group numbers only, no text)."""
import json
import random
import re

from common import SPLIT, items

SEED, TARGET, THRESH = 20261108, 100, 0.5


def groups(rows):
    tok = lambda s: set(re.findall(r"[a-z0-9]{3,}", s.lower()))
    jac = lambda a, b: len(a & b) / max(1, len(a | b))
    T, B = [tok(r["title"]) for r in rows], [tok(r["body"]) for r in rows]
    par = list(range(len(rows)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if rows[i]["agent"] == rows[j]["agent"] and (jac(T[i], T[j]) >= THRESH or jac(B[i], B[j]) >= THRESH):
                par[find(i)] = find(j)
    roots = sorted({find(i) for i in range(len(rows))}, key=lambda r: rows[r]["id"])
    num = {r: k for k, r in enumerate(roots)}
    return [num[find(i)] for i in range(len(rows))]


def main():
    rows = items()
    g = groups(rows)
    ids = sorted(set(g))
    random.Random(SEED).shuffle(ids)
    train, n = set(), 0
    for gid in ids:
        if n >= TARGET:
            break
        train.add(gid)
        n += g.count(gid)
    out = {"seed": SEED, "target_train": TARGET, "jaccard": THRESH,
           "cards": {r["id"]: {"group": gi, "side": "train" if gi in train else "heldout"} for r, gi in zip(rows, g)}}
    json.dump(out, open(SPLIT, "w"), indent=1, sort_keys=True)
    side = [v["side"] for v in out["cards"].values()]
    print(f"{len(set(g))} groups; train {side.count('train')} cards in {len(train)} groups; "
          f"held-out {side.count('heldout')} cards in {len(set(g)) - len(train)} groups")


if __name__ == "__main__":
    main()
