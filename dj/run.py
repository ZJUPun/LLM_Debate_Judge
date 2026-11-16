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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from . import config, data, llm, report
from .answers import is_correct
from .methods import METHODS, parse_spec


def safe_name(spec: str) -> str:
    return re.sub(r"[^A-Za-z0-9=._-]+", "_", spec)


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
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, q) for q in qs]
        for i, f in enumerate(as_completed(futs), 1):
            q, res, u, err = f.result()
            if err == "budget":
                stopped = True
                continue
            rec = {"method": spec, "qid": q.id, "dataset": q.dataset, "gold": q.gold,
                   "pred": res.pred if res else None,
                   "correct": bool(res and is_correct(res.pred, q.gold, q.kind)),
                   "error": err, "usage": asdict(u) if u else None,
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
    print(f"  done {spec} in {time.time() - t0:.0f}s -> {path}"
          + (f"  ({errors} errors, counted as wrong)" if errors else ""))
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
                   "question_ids": [q.id for q in questions]}, f, indent=2)

    for spec in a.methods:
        parse_spec(spec)          # fail fast on typos before spending money
    for spec in a.methods:
        run_method(spec, questions, out, a.workers, a.budget)

    print(f"\nThis run: {llm.RUN_TOTAL.calls} calls, real money spent ${llm.RUN_TOTAL.spent_usd:.4f}")
    # table + plot include EVERY method saved in this folder (also from earlier runs)
    report.main([out, "--ref", a.ref or a.methods[0]])


if __name__ == "__main__":
    main()
