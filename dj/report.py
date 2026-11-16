"""Build the results table + accuracy-vs-cost plot from saved records (no API calls).

  python -m dj.report results/gsm8k [--ref cot] [--methods cot sc:k=5 ...]
"""
from __future__ import annotations

import argparse
import glob
import json
import os

from .stats import mcnemar_exact, paired_bootstrap_diff, wilson_ci


def load_records(out_dir):
    by_method = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "records", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            recs = [json.loads(l) for l in f if l.strip()]
        if recs:
            by_method[recs[0]["method"]] = recs
    return by_method


def summarize(recs):
    n = len(recs)
    k = sum(r["correct"] for r in recs)
    lo, hi = wilson_ci(k, n)
    u = [r["usage"] or {} for r in recs]
    tot = lambda key: sum(x.get(key, 0) for x in u)
    return {"n": n, "acc": k / n if n else 0, "ci_lo": lo, "ci_hi": hi,
            "calls_per_q": tot("calls") / n, "in_tok_per_q": tot("input_tokens") / n,
            "out_tok_per_q": tot("output_tokens") / n, "cost_per_q": tot("cost_usd") / n,
            "cost_total": tot("cost_usd"), "errors": sum(1 for r in recs if r["error"]),
            "no_answer": sum(1 for r in recs if r["pred"] is None)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--ref", default=None)
    ap.add_argument("--methods", nargs="*", default=None)
    a = ap.parse_args(argv)

    by_method = load_records(a.out_dir)
    if a.methods:
        by_method = {m: by_method[m] for m in a.methods if m in by_method}
    if not by_method:
        print("No records found.")
        return
    ref = a.ref if a.ref in by_method else next(iter(by_method))
    ref_map = {r["qid"]: r["correct"] for r in by_method[ref]}

    rows = []
    for m, recs in by_method.items():
        s = summarize(recs)
        shared = [r for r in recs if r["qid"] in ref_map]
        x = [r["correct"] for r in shared]
        y = [ref_map[r["qid"]] for r in shared]
        if m == ref:
            s.update(diff=None, diff_lo=None, diff_hi=None, p=None, wins=None, losses=None)
        else:
            d, dlo, dhi = paired_bootstrap_diff(x, y)
            w, l, p = mcnemar_exact(x, y)
            s.update(diff=d, diff_lo=dlo, diff_hi=dhi, p=p, wins=w, losses=l)
        rows.append((m, s))
    rows.sort(key=lambda t: t[1]["cost_per_q"])

    pct = lambda v: f"{100 * v:.1f}"
    lines = [f"Reference for paired tests: **{ref}**  (diff = method - reference, same questions)\n",
             "| Method | n | Accuracy % | 95% CI | Calls/q | Tokens/q (in+out) | Cost/q ($) | "
             "Total cost ($) | Diff vs ref (pp) [95% CI] | Wins/Losses | McNemar p |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, s in rows:
        diff = "-" if s["diff"] is None else f"{pct(s['diff'])} [{pct(s['diff_lo'])}, {pct(s['diff_hi'])}]"
        wl = "-" if s["wins"] is None else f"{s['wins']}/{s['losses']}"
        p = "-" if s["p"] is None else f"{s['p']:.3f}"
        lines.append(f"| {m} | {s['n']} | {pct(s['acc'])} | [{pct(s['ci_lo'])}, {pct(s['ci_hi'])}] | "
                     f"{s['calls_per_q']:.1f} | {s['in_tok_per_q'] + s['out_tok_per_q']:.0f} | "
                     f"{s['cost_per_q']:.5f} | {s['cost_total']:.3f} | {diff} | {wl} | {p} |")
    notes = [f"- {m}: {s['errors']} errors, {s['no_answer']} without a parsable answer (counted wrong)"
             for m, s in rows if s["errors"] or s["no_answer"]]
    table = "\n".join(lines + ([""] + notes if notes else []))

    with open(os.path.join(a.out_dir, "table.md"), "w") as f:
        f.write(table + "\n")
    with open(os.path.join(a.out_dir, "table.json"), "w") as f:
        json.dump({m: s for m, s in rows}, f, indent=2)
    print("\n" + table)
    _plot(rows, a.out_dir)


def _plot(rows, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed: no plot)")
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, (m, s) in enumerate(rows):
        x, y = s["cost_per_q"] * 1000, 100 * s["acc"]
        ax.errorbar(x, y, yerr=[[y - 100 * s["ci_lo"]], [100 * s["ci_hi"] - y]],
                    fmt="o", capsize=4)
        ax.annotate(m, (x, y), textcoords="offset points", xytext=(6, 6 if i % 2 else -12),
                    fontsize=8)
    # connect self-consistency points, if any, to show the "same-cost" baseline curve
    sc = sorted([(s["cost_per_q"] * 1000, 100 * s["acc"]) for m, s in rows if m.startswith("sc")])
    if len(sc) > 1:
        ax.plot(*zip(*sc), "--", color="gray", lw=1, label="self-consistency curve")
        ax.legend(fontsize=8)
    ax.set_xlabel("Cost per question (US$ x 1000)")
    ax.set_ylabel("Accuracy (%)  with 95% CI")
    ax.set_title(f"Accuracy vs. cost - {os.path.basename(os.path.normpath(out_dir))}")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = os.path.join(out_dir, "accuracy_vs_cost.png")
    fig.savefig(path, dpi=150)
    print(f"\nSaved {os.path.join(out_dir, 'table.md')} and {path}")


if __name__ == "__main__":
    main()
