"""Shared plumbing for the pilot. Reuses the study's code read-only: the judge prompt, class list, card rendering and
reply parser come from approval-judge-study/src/llm.py unchanged. Only the cache location differs (this repo's
data/cache), so nothing is written into the study repo."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request

STUDY = os.environ.get("STUDY_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(STUDY, "src"))
import llm  # noqa: E402  (the study's module: JUDGE_SYSTEM, class_list, card_text, parse)
import relay  # noqa: E402  (the study's lab-gateway credentials reader; the key is never printed)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = lambda *p: os.path.join(ROOT, "data", *p)
CACHE = D("cache")
EMPTY = tempfile.mkdtemp(prefix="pilot-")
SPLIT = os.path.join(ROOT, "split.json")


def load(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def save(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def items():
    return load(os.path.join(STUDY, "data/items.jsonl"))


def _path(tag, payload):
    key = hashlib.sha256(json.dumps([tag, payload]).encode()).hexdigest()
    return os.path.join(CACHE, key[:2], key + ".json")


# ---------- Claude judge: same command line as the study's llm.call, plus the reported cost ----------

def claude(model, system, prompt, run=0):
    """One cached `claude -p` call. Returns (text, cost_usd) or (None, 0) on a transport failure."""
    path = _path("claude", [model, system, prompt, run])
    if os.path.exists(path):
        j = json.load(open(path))
        return j["text"], 0.0
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--tools", "", "--no-session-persistence",
           "--strict-mcp-config", "--system-prompt", system]
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=EMPTY, timeout=180)
        out = json.loads(p.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None, 0.0
    if out.get("is_error"):
        raise RuntimeError(str(out.get("result"))[:200] or "claude -p failed")
    cost = float(out.get("total_cost_usd") or 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"model": model, "run": run, "text": out.get("result", ""), "usage": out.get("usage"),
               "cost": cost}, open(path, "w"))
    return out.get("result", ""), cost


def judge_class(card, run):
    """The study's Sonnet judge, unchanged prompt. `card` has agent, kind, channel, standing, title, body
    (any framing line already placed above the body, as the study did for its attacked conditions)."""
    text, cost = claude("sonnet", llm.JUDGE_SYSTEM + llm.class_list(), llm.card_text(card), run)
    cls = (llm.parse(text) or {}).get("class", "")
    return (cls if cls in llm.CONSTITUTION["classes"] else ""), cost


# ---------- Lab writer model ----------

WRITER = "thinking-humans-lightning-30b"     # Nemotron 3.5 Lightning 30B-A3B on the lab
_SLOTS = threading.BoundedSemaphore(4)       # the fast model is documented at 4-parallel; never the 120B


def lab_chat(system, prompt, seed, temperature=1.0, top_p=0.95, max_tokens=600):
    """Cached chat completion on the lab gateway. Returns (text, served_model) or (None, '')."""
    path = _path("lab", [WRITER, system, prompt, seed, temperature, top_p])
    if os.path.exists(path):
        j = json.load(open(path))
        return j["text"], j["model"]
    url, key = relay._env()
    body = json.dumps({"model": WRITER, "max_tokens": max_tokens, "temperature": temperature, "top_p": top_p,
                       "seed": seed, "chat_template_kwargs": {"enable_thinking": False},
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body,
                                 headers={"content-type": "application/json", "authorization": "Bearer " + key})
    try:
        with _SLOTS, urllib.request.urlopen(req, timeout=300) as r:
            j = json.load(r)
    except Exception:
        return None, ""
    text, served = j["choices"][0]["message"].get("content") or "", j.get("model", WRITER)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"model": served, "seed": seed, "text": text}, open(path, "w"))
    return text, served
