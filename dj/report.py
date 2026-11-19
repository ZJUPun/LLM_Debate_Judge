"""Build the results table + accuracy-vs-cost plot from saved records (no API calls).

  python -m dj.report results/gsm8k [--ref cot] [--methods cot sc:k=5 ...]
"""
from __future__ import annotations

import argparse
import glob
import json
import os

from .stats import mcnemar_exact, paired_bootstrap_diff, wilson_ci

# One label per question, see dj.run.classify()
OUTCOME_KEYS = ("correct", "wrong", "no_answer", "truncated", "technical_error")

from . import config

MAX_TOKENS_SHOWN = config.DEFAULT_MAX_TOKENS


def load_records(out_dir):
    by_method = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "records", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            recs = [json.loads(l) for l in f if l.strip()]
        if recs:
            by_method[recs[0]["method"]] = recs
    return by_method


def outcome_of(r):
    """Outcome label of one record. Old records (metrics_version < 2) have no 'outcome'
    field; they are re-classified here without modifying the saved files."""
    if r.get("outcome"):
        return r["outcome"]
    if r.get("error"):
        return "technical_error"
    if r.get("correct"):
        return "correct"
    if r.get("pred") is None:
        return "truncated" if r.get("truncated_calls") else "no_answer"
    return "wrong"


def summarize(recs):
    n = len(recs)
    k = sum(r["correct"] for r in recs)
    lo, hi = wilson_ci(k, n)
    u = [r["usage"] or {} for r in recs]
    tot = lambda key: sum(x.get(key, 0) for x in u)

    # --- outcome breakdown ---------------------------------------------------------
    outcomes = {key: 0 for key in OUTCOME_KEYS}
    for r in recs:
        label = outcome_of(r)
        if label == "correct" and not r["correct"]:
            label = "wrong"          # never let the breakdown disagree with 'correct'
        outcomes[label] += 1
    answered = sum(1 for r in recs if r["pred"] is not None)         # a parsable answer exists
    k_ans = sum(r["correct"] for r in recs if r["pred"] is not None)
    lo_ans, hi_ans = wilson_ci(k_ans, answered)

    truncated_q = sum(1 for r in recs if r.get("truncated_calls"))
    truncated_calls = sum(r.get("truncated_calls", 0) for r in recs)
    calls_made = sum(r.get("calls_made", 0) for r in recs)

    return {"n": n,
            # accuracy over ALL questions (unchanged definition; non-answers count as wrong)
            "acc": k / n if n else 0, "ci_lo": lo, "ci_hi": hi,
            # accuracy among questions where the method produced a parsable answer
            "answered": answered,
            "acc_answered": k_ans / answered if answered else 0,
            "acc_answered_ci_lo": lo_ans, "acc_answered_ci_hi": hi_ans,
            "no_answer_rate": (n - answered) / n if n else 0,
            # outcome breakdown (counts + shares of n), one label per question
            **{f"n_{key}": outcomes[key] for key in OUTCOME_KEYS},
            **{f"pct_{key}": (outcomes[key] / n if n else 0) for key in OUTCOME_KEYS},
            # how much the experiment's max_tokens limit actually bit
            "truncated_questions": truncated_q,
            "truncated_questions_pct": (truncated_q / n if n else 0),
            "truncated_calls": truncated_calls,
            "calls_made": calls_made,
            "truncated_calls_pct": (truncated_calls / calls_made if calls_made else 0),
            # cost / usage
            "calls_per_q": tot("calls") / n, "in_tok_per_q": tot("input_tokens") / n,
            "out_tok_per_q": tot("output_tokens") / n, "cost_per_q": tot("cost_usd") / n,
            "cost_total": tot("cost_usd"),
            "errors": outcomes["technical_error"], "no_answer": n - answered}


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
    lines = [f"Reference for paired tests: **{ref}**  (diff = method - reference, same questions)",
             "",
             f"**Accuracy (all)** = correct / n, a non-answer counts as wrong (unchanged definition).",
             f"**Accuracy (answered)** = correct / questions where the method produced a parsable "
             f"answer. **No answer %** = share of questions with no parsable answer, split into "
             f"*wrong*, *no answer* (model answered nothing usable), *truncated* (hit "
             f"max_tokens) and *error* (technical failure).",
             "",
             "| Method | n | Accuracy (all) % | 95% CI | Accuracy (answered) % | No answer % "
             "(wrong / no-ans / trunc / error) | Calls/q | Tokens/q (in+out) | Cost/q ($) | "
             "Total cost ($) | Diff vs ref (pp) [95% CI] | Wins/Losses | McNemar p |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, s in rows:
        diff = "-" if s["diff"] is None else f"{pct(s['diff'])} [{pct(s['diff_lo'])}, {pct(s['diff_hi'])}]"
        wl = "-" if s["wins"] is None else f"{s['wins']}/{s['losses']}"
        p = "-" if s["p"] is None else f"{s['p']:.3f}"
        breakdown = (f"{s['n_wrong']} / {s['n_no_answer']} / {s['n_truncated']} / "
                     f"{s['n_technical_error']}")
        lines.append(
            f"| {m} | {s['n']} | {pct(s['acc'])} | [{pct(s['ci_lo'])}, {pct(s['ci_hi'])}] | "
            f"{pct(s['acc_answered'])} [{pct(s['acc_answered_ci_lo'])}, {pct(s['acc_answered_ci_hi'])}] | "
            f"{pct(s['no_answer_rate'])} ({breakdown}) | "
            f"{s['calls_per_q']:.1f} | {s['in_tok_per_q'] + s['out_tok_per_q']:.0f} | "
            f"{s['cost_per_q']:.5f} | {s['cost_total']:.3f} | {diff} | {wl} | {p} |")
    notes = [f"- {m}: {s['errors']} errors, {s['no_answer']} without a parsable answer (counted wrong)"
             for m, s in rows if s["errors"] or s["no_answer"]]

    # ---- truncation impact block: how much did max_tokens=2048 bite per method? ----
    trunc_lines = []
    if any(s["truncated_questions"] or s["truncated_calls"] for m, s in rows):
        trunc_lines = ["",
                       f"**Impact of the experiment limit (max_tokens = {MAX_TOKENS_SHOWN})**",
                       "",
                       "| Method | Questions with a truncated call | Calls truncated | Truncated calls % |",
                       "|---|---|---|---|"]
        for m, s in rows:
            if not (s["truncated_questions"] or s["truncated_calls"]):
                continue
            trunc_lines.append(
                f"| {m} | {s['truncated_questions']}/{s['n']} "
                f"({pct(s['truncated_questions_pct'])}) | "
                f"{s['truncated_calls']}/{s['calls_made']} | "
                f"{pct(s['truncated_calls_pct'])} |")
        trunc_lines += ["",
                        "A truncated question is one where at least one model call inside the "
                        "method stopped with `finish_reason == \"length\"`. "
                        "Per-call truncation is derived from call usage: records written before "
                        "truncation tracking existed (metrics_version < 2) have no per-call "
                        "`finish_reason`, so their counts may be 0/absent."]

    table = "\n".join(lines + ([""] + notes if notes else []) + trunc_lines)

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
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharex=True)

    def draw(ax, acc_key, lo_key, hi_key, title):
        for i, (m, s) in enumerate(rows):
            x, y = s["cost_per_q"] * 1000, 100 * s[acc_key]
            ax.errorbar(x, y, yerr=[[y - 100 * s[lo_key]], [100 * s[hi_key] - y]],
                        fmt="o", capsize=4)
            ax.annotate(m, (x, y), textcoords="offset points",
                        xytext=(6, 6 if i % 2 else -12), fontsize=8)
        # connect self-consistency points to show the "same-cost" baseline curve
        sc = sorted([(s["cost_per_q"] * 1000, 100 * s[acc_key])
                     for m, s in rows if m.startswith("sc")])
        if len(sc) > 1:
            ax.plot(*zip(*sc), "--", color="gray", lw=1, label="self-consistency curve")
            ax.legend(fontsize=8)
        ax.set_xlabel("Cost per question (US$ x 1000)")
        ax.set_ylabel("Accuracy (%)  with 95% CI")
        ax.set_title(title)
        ax.grid(alpha=0.3)

    draw(axes[0], "acc", "ci_lo", "ci_hi", "All questions (non-answers = wrong)")
    draw(axes[1], "acc_answered", "acc_answered_ci_lo", "acc_answered_ci_hi",
         "Answered questions only")
    fig.suptitle(f"Accuracy vs. cost - {os.path.basename(os.path.normpath(out_dir))}")
    fig.tight_layout()
    path = os.path.join(out_dir, "accuracy_vs_cost.png")
    fig.savefig(path, dpi=150)
    print(f"\nSaved {os.path.join(out_dir, 'table.md')} and {path}")


if __name__ == "__main__":
    main()
