"""Evaluation harness: run methods on a dataset, save one record per question, then build
the results table and plot.

Example:
  python -m dj.run --dataset gsm8k --n 100 --methods cot "sc:k=5" "debate:n=3,r=2"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from . import config, data, flips, llm, report
from .answers import is_correct
from . import methods
from .methods import METHODS, parse_spec


METRICS_VERSION = 2   # bump when how a record is scored / classified changes


def safe_name(spec: str) -> str:
    return re.sub(r"[^A-Za-z0-9=._-]+", "_", spec)


class TruncationCounter:
    """Counts, per question, how many model calls were cut off by the max_tokens limit.

    Methods call `chat` imported into `dj.methods`, so patching `dj.llm.chat` is not
    enough - we must swap the name in the methods module too. This only *observes* the
    calls a method makes; it never changes what the method computes.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.per_qid: dict[str, int] = {}
        self.calls_per_qid: dict[str, int] = {}
        self._orig = None

    def __enter__(self):
        self._orig = llm.chat
        counter = self

        def wrapped(messages, **kw):
            reply = counter._orig(messages, **kw)
            qid = _qid_from_tag(kw.get("tag", ""))
            if qid is not None:
                with counter.lock:
                    counter.calls_per_qid[qid] = counter.calls_per_qid.get(qid, 0) + 1
                    if reply.truncated:
                        counter.per_qid[qid] = counter.per_qid.get(qid, 0) + 1
            return reply

        wrapped.__module__ = "dj.methods"   # cosmetic: keep tracebacks readable
        llm.chat = wrapped
        methods.chat = wrapped              # <- this is what methods actually call
        return self

    def __exit__(self, *exc):
        llm.chat = self._orig
        methods.chat = self._orig

    def get(self, qid):
        return self.per_qid.get(qid, 0), self.calls_per_qid.get(qid, 0)


def _qid_from_tag(tag: str):
    """'debate/gsm8k-513/a0/r0' -> 'gsm8k-513'. Tags are always '<method>/<qid>/...'."""
    parts = tag.split("/")
    return parts[1] if len(parts) > 1 and parts[1] else None


def classify(error, pred, truncated, correct):
    """One label per question, used for the outcome breakdown in the report.

    technical_error : the method raised an exception (API error, bad response, ...)
    truncated       : at least one model call hit max_tokens and no usable answer came out
    correct         : an answer was produced and matches gold
    wrong           : an answer was produced but does not match gold
    no_answer       : nothing parsable and no truncation (the model just did not answer)
    """
    if error:
        return "technical_error"
    if pred is None:
        return "truncated" if truncated else "no_answer"
    return "correct" if correct else "wrong"


def run_method(spec, questions, out_dir, workers, budget):
    name, params = parse_spec(spec)
    fn, kinds = METHODS[name]
    qs = [q for q in questions if q.kind in kinds]
    if not qs:
        print(f"  skip {spec}: does not apply to {questions[0].kind} questions")
        return
    path = os.path.join(out_dir, "records", safe_name(spec) + ".jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    records, stopped = {}, False

    def one(q):
        if llm.RUN_TOTAL.spent_usd > budget:
            return q, None, None, "budget"
        try:
            with llm.meter() as u:
                res = fn(q, **params)
            return q, res, u, None
        except Exception as e:      # keep going; the error is saved in the record
            return q, None, None, f"{type(e).__name__}: {e}"

    t0 = time.time()
    counter = TruncationCounter()
    with counter, ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, q) for q in qs]
        for i, f in enumerate(as_completed(futs), 1):
            q, res, u, err = f.result()
            if err == "budget":
                stopped = True
                continue
            pred = res.pred if res else None
            correct = bool(res and is_correct(pred, q.gold, q.kind))
            truncated_calls, calls_made = counter.get(q.id)
            rec = {"method": spec, "qid": q.id, "dataset": q.dataset, "gold": q.gold,
                   "pred": pred,
                   "correct": correct,
                   "error": err, "usage": asdict(u) if u else None,
                   # ---- outcome breakdown (v2 metrics), see classify() ----
                   "outcome": classify(err, pred, truncated_calls > 0, correct),
                   "truncated_calls": truncated_calls,
                   "calls_made": calls_made,
                   "metrics_version": METRICS_VERSION,
                   "trace": res.trace if res else None}
            records[q.id] = rec
            if i % 10 == 0 or i == len(qs):
                acc = sum(r["correct"] for r in records.values()) / max(1, len(records))
                print(f"  {spec}: {i}/{len(qs)}  acc so far {acc:.3f}  "
                      f"spent this run ${llm.RUN_TOTAL.spent_usd:.3f}", flush=True)

    with open(path, "w", encoding="utf-8") as f:     # keep the dataset order
        for q in qs:
            if q.id in records:
                f.write(json.dumps(records[q.id], ensure_ascii=False) + "\n")
    errors = sum(1 for r in records.values() if r["error"])
    n_trunc = sum(1 for r in records.values() if r.get("truncated_calls"))
    print(f"  done {spec} in {time.time() - t0:.0f}s -> {path}"
          + (f"  ({errors} errors, counted as wrong)" if errors else "")
          + (f"  ({n_trunc} questions hit max_tokens={config.DEFAULT_MAX_TOKENS})" if n_trunc else ""))
    if stopped:
        print(f"!! Budget of ${budget:.2f} reached: {spec} is INCOMPLETE. Stopping.")
        sys.exit(1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dataset", required=True, help="gsm8k | mmlu_pro | judgebench | sample_math | sample_mc | sample_pair")
    ap.add_argument("--n", type=int, default=100, help="number of questions (same subset for all methods)")
    ap.add_argument("--seed", type=int, default=0, help="which subset of questions")
    ap.add_argument("--methods", nargs="+", required=True, help='e.g. cot "sc:k=5" "debate:n=3,r=2"')
    ap.add_argument("--ref", default=None, help="baseline for paired tests (default: first method)")
    ap.add_argument("--out", default=None, help="output folder (default results/<dataset>)")
    ap.add_argument("--workers", type=int, default=8, help="questions run in parallel")
    ap.add_argument("--budget", type=float, default=config.DEFAULT_RUN_BUDGET_USD,
                    help="stop if this run spends more than this many US$")
    ap.add_argument("--category", default=None, help="MMLU-Pro category filter, e.g. physics")
    ap.add_argument("--split", default=None, help="JudgeBench split: gpt or claude")
    a = ap.parse_args(argv)

    kw = {}
    if a.category:
        kw["category"] = a.category
    if a.split:
        kw["split"] = a.split
    out = a.out or os.path.join(config.ROOT, "results", a.dataset)
    os.makedirs(out, exist_ok=True)

    questions = data.load(a.dataset, n=a.n, seed=a.seed, **kw)
    print(f"{a.dataset}: {len(questions)} questions | model {config.MODEL}"
          f"{' | MOCK MODE' if config.MOCK else ''} | budget ${a.budget:.2f}")
    with open(os.path.join(out, "run_config.json"), "w") as f:
        json.dump({**vars(a), "model": config.MODEL, "prices_per_M": config.PRICE_PER_M,
                   "max_tokens": config.DEFAULT_MAX_TOKENS,
                   "metrics_version": METRICS_VERSION,
                   "mock": config.MOCK,
                   "question_ids": [q.id for q in questions]}, f, indent=2)

    for spec in a.methods:
        parse_spec(spec)          # fail fast on typos before spending money
    for spec in a.methods:
        run_method(spec, questions, out, a.workers, a.budget)

    print(f"\nThis run: {llm.RUN_TOTAL.calls} calls, real money spent ${llm.RUN_TOTAL.spent_usd:.4f}")
    # table + plot include EVERY method saved in this folder (also from earlier runs)
    report.main([out, "--ref", a.ref or a.methods[0]])
    if any(m.split(":")[0] == "debate" for m in a.methods):
        flips.main([out])


if __name__ == "__main__":
    main()
