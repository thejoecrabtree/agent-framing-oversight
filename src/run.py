"""Run the study: build the conditions, run the LLM judges, then every judge on every condition.
  python3 src/run.py [--limit N] [--workers 6]
Everything is cached, so it can be stopped and restarted."""
import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

import llm

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = lambda *p: os.path.join(ROOT, "data", *p)
LLM_JUDGES = {"llm-sonnet": "sonnet", "llm-haiku": "haiku"}


def load(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def save(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_conditions(items, pool):
    para = list(pool.map(llm.paraphrase, items))
    a1 = list(pool.map(lambda it: llm.attack(it, False), items))
    a2 = list(pool.map(lambda it: llm.attack(it, True), items))
    a2c = list(pool.map(lambda it: llm.attack(it, True, model="sonnet"), items))
    save(D("cond/C0.jsonl"), items)
    save(D("cond/C1.jsonl"), [{**it, "title": p["title"], "refused": p["refused"]} for it, p in zip(items, para)])
    for name, rs in (("A1", a1), ("A2", a2), ("A2c", a2c)):
        save(D(f"cond/{name}.jsonl"), [{**it, "title": r["title"], "kind": r["kind"],
                                         "body": (r["framing"] + "\n\n" if r["framing"] else "") + it["body"],
                                         "framing": r["framing"], "refused": r["refused"], "attacker": r["attacker"]}
                                        for it, r in zip(items, rs)])


def run_llm_judges(cond, pool, runs=1):
    rows = load(D(f"cond/{cond}.jsonl"))
    os.makedirs(D("llm", cond), exist_ok=True)
    for name, model in LLM_JUDGES.items():
        for run in range(runs):
            # the attacker's framing line is already in the body, so the judge reads the card as filed
            classes = list(pool.map(lambda it: llm.judge(it, model, run), rows))
            suffix = "" if run == 0 else f"-run{run}"
            json.dump(dict(zip([r["id"] for r in rows], classes)), open(D("llm", cond, f"{name}{suffix}.json"), "w"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    items = load(D("items.jsonl"))[: a.limit or None]
    with ThreadPoolExecutor(a.workers) as pool:
        build_conditions(items, pool)
        for cond in ("C0", "C1", "A1", "A2", "A2c"):
            run_llm_judges(cond, pool, runs=2 if cond == "C0" else 1)
            files = [D("llm", cond, f"{n}.json") for n in LLM_JUDGES]
            out = subprocess.run(["node", os.path.join(ROOT, "src/judges.mjs"), D(f"cond/{cond}.jsonl"), *files],
                                 capture_output=True, text=True, check=True).stdout
            os.makedirs(D("verdicts"), exist_ok=True)
            open(D("verdicts", f"{cond}.jsonl"), "w").write(out)
            print(cond, "done")


if __name__ == "__main__":
    main()
