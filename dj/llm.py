"""The ONE place that calls the API.

Every method must call `chat()` and nothing else. That gives you, for free:
  * a disk cache  -> re-running an experiment costs $0 and gives identical results
  * a call log    -> logs/calls.jsonl has every call (for your "code and logs" submission)
  * cost tracking -> `meter()` adds up the tokens of all calls made inside it
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict

from . import config

# ----------------------------------------------------------------------------- usage / cost

@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0          # all prompt tokens (hit + miss)
    input_cache_hit: int = 0       # DeepSeek server-side prefix cache hits (cheaper)
    output_tokens: int = 0         # includes reasoning tokens if thinking is on
    cost_usd: float = 0.0          # cost as if every call were paid (fair for comparing methods)
    spent_usd: float = 0.0         # money actually spent now (0 for calls served from our disk cache)

    def add(self, other: "Usage") -> None:
        for k in asdict(self):
            setattr(self, k, getattr(self, k) + getattr(other, k))


def price(input_tokens: int, cache_hit: int, output_tokens: int) -> float:
    p = config.PRICE_PER_M
    miss = input_tokens - cache_hit
    return (miss * p["input_cache_miss"] + cache_hit * p["input_cache_hit"]
            + output_tokens * p["output"]) / 1e6


# A stack of active meters per thread. Every call is added to all active meters,
# so you can nest them (e.g. one per question inside one per run).
_local = threading.local()
_global_lock = threading.Lock()
RUN_TOTAL = Usage()        # everything in this Python process


@contextmanager
def meter():
    """with meter() as u: ... -> u is a Usage with the totals of the calls made inside."""
    u = Usage()
    stack = getattr(_local, "stack", None)
    if stack is None:
        stack = _local.stack = []
    stack.append(u)
    try:
        yield u
    finally:
        stack.pop()


def _record(u: Usage) -> None:
    for m in getattr(_local, "stack", []):
        m.add(u)
    with _global_lock:
        RUN_TOTAL.add(u)


# ----------------------------------------------------------------------------- cache + log

class _Cache:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, v TEXT)")
        self.db.commit()

    def get(self, k):
        with self.lock:
            row = self.db.execute("SELECT v FROM c WHERE k=?", (k,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, k, v):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO c VALUES (?,?)", (k, json.dumps(v)))
            self.db.commit()


_cache = None
_log_lock = threading.Lock()


def _get_cache():
    global _cache
    if _cache is None:
        _cache = _Cache(config.CACHE_PATH + (".mock" if config.MOCK else ""))
    return _cache


def _log(entry: dict) -> None:
    path = config.CALL_LOG_PATH + (".mock" if config.MOCK else "")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _log_lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------- client

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI  # imported lazily so mock mode needs no packages
        key = os.getenv(config.API_KEY_ENV)
        if not key:
            raise SystemExit(f"Set your API key first:  export {config.API_KEY_ENV}=sk-...")
        _client = OpenAI(api_key=key, base_url=config.BASE_URL, timeout=config.REQUEST_TIMEOUT)
    return _client


@dataclass
class Reply:
    text: str
    reasoning: str = ""          # DeepSeek "thinking" text, if the model returns it
    usage: Usage = field(default_factory=Usage)
    cached: bool = False
    finish_reason: str = ""      # "stop" | "length" | "content_filter" | ... ("" = unknown)
    truncated: bool = False      # True iff the API stopped because max_tokens was reached

    def __post_init__(self):
        # `truncated` is always derived from finish_reason so the two cannot disagree.
        if self.finish_reason == "length":
            self.truncated = True


def _is_truncated(finish_reason: str, output_tokens) -> bool:
    """Did the model stop because it hit the max_tokens limit?

    The API finish_reason is authoritative. Replies cached before truncation tracking
    existed have no finish_reason, so fall back to "output tokens reached the limit".
    """
    if finish_reason:
        return finish_reason == "length"
    return output_tokens is not None and output_tokens >= config.DEFAULT_MAX_TOKENS


def chat(messages, *, temperature: float = config.DEFAULT_TEMPERATURE,
         max_tokens: int = config.DEFAULT_MAX_TOKENS, sample_id: int = 0,
         tag: str = "", extra_body: dict | None = None,
         model: str | None = None) -> Reply:
    """Send one chat request.

    messages   : list of {"role": ..., "content": ...}, or a plain string (= one user message)
    sample_id  : use different values to get *different* samples of the same prompt
                 (otherwise the cache would return the same answer k times)
    tag        : free text saved in the log, e.g. "debate/agent2/round1"
    extra_body : extra DeepSeek parameters, e.g. to switch thinking mode on/off
                 (see the DeepSeek API docs for the exact field name)
    """
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    model = model or config.MODEL
    key_src = json.dumps([model, messages, temperature, max_tokens, sample_id, extra_body],
                         sort_keys=True, ensure_ascii=False)
    key = hashlib.sha256(key_src.encode()).hexdigest()

    cache = _get_cache()
    hit = cache.get(key)
    if hit is not None:
        u = Usage(calls=1, input_tokens=hit["in"], input_cache_hit=hit["in_hit"],
                  output_tokens=hit["out"], cost_usd=price(hit["in"], hit["in_hit"], hit["out"]),
                  spent_usd=0.0)
        _record(u)
        fr = hit.get("finish_reason", "")
        return Reply(hit["text"], hit.get("reasoning", ""), u, cached=True,
                     finish_reason=fr, truncated=_is_truncated(fr, hit["out"]))

    t0 = time.time()
    if config.MOCK:
        text, reasoning, n_in, n_hit, n_out, finish_reason = _mock_reply(
            messages, sample_id, max_tokens)
    else:
        text, reasoning, n_in, n_hit, n_out, finish_reason = _api_call(
            model, messages, temperature, max_tokens, extra_body)
    truncated = _is_truncated(finish_reason, n_out)
    cost = price(n_in, n_hit, n_out)
    u = Usage(calls=1, input_tokens=n_in, input_cache_hit=n_hit, output_tokens=n_out,
              cost_usd=cost, spent_usd=cost)
    _record(u)
    cache.put(key, {"text": text, "reasoning": reasoning, "in": n_in, "in_hit": n_hit,
                    "out": n_out, "finish_reason": finish_reason})
    _log({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": tag, "model": model,
          "temperature": temperature, "sample_id": sample_id, "messages": messages,
          "reply": text, "reasoning": reasoning, "input_tokens": n_in, "input_cache_hit": n_hit,
          "output_tokens": n_out, "cost_usd": round(cost, 6),
          "finish_reason": finish_reason, "truncated": truncated, "max_tokens": max_tokens,
          "seconds": round(time.time() - t0, 2)})
    return Reply(text, reasoning, u, cached=False, finish_reason=finish_reason,
                 truncated=truncated)


def _api_call(model, messages, temperature, max_tokens, extra_body):
    client = _get_client()
    delay = 2.0
    for attempt in range(config.MAX_RETRIES):
        try:
            kw = dict(model=model, messages=messages, temperature=temperature,
                      max_tokens=max_tokens)
            if extra_body:
                kw["extra_body"] = extra_body
            r = client.chat.completions.create(**kw)
            choice = r.choices[0]
            msg = choice.message
            us = r.usage
            n_in = us.prompt_tokens
            n_hit = getattr(us, "prompt_cache_hit_tokens", 0) or 0
            finish_reason = getattr(choice, "finish_reason", "") or ""
            return (msg.content or "", getattr(msg, "reasoning_content", "") or "",
                    n_in, n_hit, us.completion_tokens, finish_reason)
        except Exception as e:  # rate limits, timeouts, server errors
            if attempt == config.MAX_RETRIES - 1:
                raise
            print(f"[chat] {type(e).__name__}: {e} -> retry in {delay:.0f}s")
            time.sleep(delay + random.random())
            delay *= 2


# ----------------------------------------------------------------------------- mock model

def _mock_reply(messages, sample_id, max_tokens=config.DEFAULT_MAX_TOKENS):
    """A fake model for offline testing. Answers are random but deterministic.

    Returns (text, reasoning, n_in, n_hit, n_out, finish_reason).
    A configurable share of calls (config.MOCK_TRUNCATION_RATE) simulates the failure
    mode observed in the paid runs: the model "thinks" until max_tokens and returns an
    empty content, so finish_reason == "length" and there is no parsable answer.
    """
    prompt = "\n".join(m["content"] for m in messages)
    rng = random.Random(hashlib.md5(f"{prompt}|{sample_id}".encode()).hexdigest())
    n_in = len(prompt.split()) * 4 // 3
    if rng.random() < config.MOCK_TRUNCATION_RATE:
        return ("", "mock reasoning that runs into the max_tokens limit",
                n_in, 0, max_tokens, "length")
    if '"winner"' in prompt:                                   # judge prompt
        text = json.dumps({"reasoning": "mock judge", "winner": rng.choice("AB")})
    elif re.search(r"\(J\)|\(D\)", prompt):                    # multiple choice
        letters = re.findall(r"\(([A-J])\)", prompt) or list("ABCD")
        text = f"Some reasoning. Answer: {rng.choice(sorted(set(letters))[:4])}"
    else:                                                      # math
        text = f"Some reasoning. Answer: {rng.choice([18, 18, 18, 20, 3])}"
    return (text, "", n_in, 0, len(text.split()) * 4 // 3 + 150, "stop")
