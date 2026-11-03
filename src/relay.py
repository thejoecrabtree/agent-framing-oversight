"""The attacker model, through any OpenAI-compatible endpoint: set ATTACKER_API_URL and ATTACKER_API_KEY.
The study used Nemotron 3 Super 120B served on a private lab (model alias `th-reason`)."""
import json
import os
import threading
import urllib.request

# at most two requests at once: the study's lab froze a GPU node under agent load once
_SLOTS = threading.BoundedSemaphore(2)


def chat(model, system, prompt, max_tokens=4000, temperature=0.0):
    url, key = os.environ["ATTACKER_API_URL"].rstrip("/"), os.environ["ATTACKER_API_KEY"]
    body = json.dumps({"model": model, "max_tokens": max_tokens, "temperature": temperature,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body,
                                 headers={"content-type": "application/json", "authorization": "Bearer " + key})
    with _SLOTS, urllib.request.urlopen(req, timeout=300) as r:
        j = json.load(r)
    return j["choices"][0]["message"].get("content") or "", j.get("model", model)
