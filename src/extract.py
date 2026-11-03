"""Build data/items.jsonl from the approvals snapshot: one card per line, with its label and who decided it.
The output holds customer text and stays in data/ (git-ignored)."""
import glob
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
DECISIONS = ("approved", "rejected", "changes")


def decider(card):
    events = [e for e in card.get("history") or [] if e.get("event") in DECISIONS]
    return events[-1].get("by", "") if events else ""


def person(by, card):
    """A person's decision: recorded as Joseph's and not made by Autopilot. approvectl records Autopilot's defaults and
    releases as "by joseph" with decidedVia "autopilot" (incident #15's post among them), so those are excluded."""
    return by == "joseph" and card.get("decidedVia") != "autopilot" and card.get("status") in DECISIONS


def main():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data/raw/approvals/*.json"))):
        a = json.load(open(f))
        by = decider(a)
        out.append({
            "id": a["id"], "agent": a.get("agent", ""), "kind": a.get("kind", ""), "title": a.get("title", ""),
            "body": a.get("body", ""), "channel": a.get("channel", ""), "standing": a.get("standing") or "",
            "createdAt": a.get("createdAt", ""), "status": a.get("status", ""), "decidedBy": by,
            "decidedVia": a.get("decidedVia") or "",
            "personDecided": person(by, a),
            "personStopped": person(by, a) and a.get("status") in ("rejected", "changes"),
            "personPassed": person(by, a) and a.get("status") == "approved",
        })
    with open(os.path.join(ROOT, "data/items.jsonl"), "w") as fh:
        for it in out:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    pd = [i for i in out if i["personDecided"]]
    print(f"{len(out)} cards; {len(pd)} person-decided "
          f"({sum(i['personStopped'] for i in pd)} stopped, {sum(i['personPassed'] for i in pd)} passed; "
          f"{sum(1 for i in pd if i['decidedVia'] == 'UNSOURCED')} unsourced)")


if __name__ == "__main__":
    main()
