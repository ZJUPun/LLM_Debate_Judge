"""Debate flip analysis (read-only, no API calls).

Run:  python -m dj.flips results/mmlu_pro

For each debate method in the folder, count how individual agents change their answer
between consecutive rounds, and whether the majority answer changes between round 0 and
the last round.

Definitions (per agent, per consecutive round pair r -> r+1):
  flip            : the agent's answer changed.
  W->R            : a wrong answer was corrected (debate "fixes" an error).
  R->W            : a right answer was abandoned for a wrong one (debate "spreads" an error).
  W->W / R->R     : the answer changed but the correctness stayed the same (sideways).
  switch-to-peer  : the new answer was one a peer held in the previous round (social
                    influence), rather than a novel answer.

Truncation vs genuine flips:
  `None` means "no parsable answer", usually a call that hit max_tokens. A transition to or
  from `None` is a truncation artifact, NOT a genuine W/R flip, so it is counted separately
  as a no-answer transition (`none->R`, `none->W`, `R->none`, `W->none`). Genuine flips
  require BOTH answers to be non-None.

Rates:
  W->R rate = W->R flips / wrong (non-None) answers available to correct.
  R->W rate = R->W flips / right (non-None) answers available to corrupt.

Outputs (next to table.md):
  flips.md               summary table
  flips.json             the same numbers as structured data
  flips_by_round.png     genuine W->R vs R->W per round transition
  flips_examples.jsonl   one line per genuine W->R / R->W flip, for error analysis
"""
from __future__ import annotations

import argparse
import json
import os

from .answers import is_correct, majority_vote
from .report import load_records

DATASET_KIND = {
    "gsm8k": "math", "sample_math": "math",
    "mmlu_pro": "mc", "sample_mc": "mc",
    "judgebench": "pair", "sample_pair": "pair",
}
GENUINE_FLIPS = ("W->R", "R->W", "W->W", "R->R")
NOANSWER_FLIPS = ("none->R", "none->W", "R->none", "W->none")
ALL_FLIPS = GENUINE_FLIPS + NOANSWER_FLIPS


def _kind_of(rec) -> str:
    return DATASET_KIND.get(rec.get("dataset", ""), "mc")


def _per_question(rec):
    """Flip stats for one debate record, or None if the trace is unusable."""
    trace = rec.get("trace") or {}
    rounds = trace.get("rounds")
    if not isinstance(rounds, list) or len(rounds) < 2:
        return None
    gold, qkind = rec.get("gold"), _kind_of(rec)
    n_agents = len(rounds[0]) if rounds else 0
    if n_agents == 0:
        return None
    preds = [[a.get("pred") for a in rd] for rd in rounds]

    votes = [majority_vote(p) for p in preds]
    events = []
    per_transition = {}
    wrong_opp = right_opp = 0
    no_answer = {t: 0 for t in NOANSWER_FLIPS}

    for r in range(len(preds) - 1):
        cur, nxt = preds[r], preds[r + 1]
        counts = {t: 0 for t in ALL_FLIPS}
        for i in range(n_agents):
            prev, new = cur[i], nxt[i]
            # opportunities: only genuine (non-None) answers at the start of a transition
            # are eligible to be corrected/corrupted.
            if prev is not None:
                if is_correct(prev, gold, qkind):
                    right_opp += 1
                else:
                    wrong_opp += 1
            if prev == new:
                continue
            # no-answer (truncation) transition: one side is None -> not a genuine flip.
            if prev is None or new is None:
                if new is None:
                    ftype = "R->none" if is_correct(prev, gold, qkind) else "W->none"
                else:
                    ftype = "none->R" if is_correct(new, gold, qkind) else "none->W"
                no_answer[ftype] += 1
                counts[ftype] += 1
                continue
            # genuine flip: both answers non-None.
            pc, nc = is_correct(prev, gold, qkind), is_correct(new, gold, qkind)
            if pc == nc:
                ftype = "W->W" if not nc else "R->R"
            else:
                ftype = "W->R" if nc else "R->W"
            peers = [cur[j] for j in range(n_agents) if j != i]
            counts[ftype] += 1
            events.append({
                "qid": rec.get("qid"), "method": rec.get("method"),
                "transition": f"r{r}->r{r + 1}", "agent": i,
                "prev": prev, "new": new, "gold": gold, "flip": ftype,
                "switch_to_peer": new in peers, "peers_prev_round": peers,
                "prev_text": (rounds[r][i].get("text") or "")[:400],
                "new_text": (rounds[r + 1][i].get("text") or "")[:400],
            })
        per_transition[f"r{r}->r{r + 1}"] = counts

    fixed = empty = broken = corrected = corrupted = 0
    for i in range(n_agents):
        traj = [p[i] for p in preds]
        if all(t is None for t in traj):
            empty += 1                          # never produced an answer (truncation)
        elif all(t == traj[0] for t in traj):
            fixed += 1                          # never changed a REAL answer
        # broken = always a genuine (non-None) wrong answer; None is truncation, not "wrong".
        if all(t is not None and not is_correct(t, gold, qkind) for t in traj):
            broken += 1
        # corrected/corrupted only make sense for trajectories that start and end with a
        # genuine (non-None) answer.
        if traj[0] is not None and traj[-1] is not None:
            sc, ec = is_correct(traj[0], gold, qkind), is_correct(traj[-1], gold, qkind)
            if sc != ec:
                if ec:
                    corrected += 1
                else:
                    corrupted += 1

    return {
        "qid": rec.get("qid"), "n_agents": n_agents, "n_rounds": len(rounds),
        "round0_vote": votes[0], "final_vote": votes[-1],
        "round0_correct": is_correct(votes[0], gold, qkind),
        "final_correct": is_correct(votes[-1], gold, qkind),
        "events": events, "per_transition": per_transition,
        "wrong_opp": wrong_opp, "right_opp": right_opp, "no_answer": no_answer,
        "fixed": fixed, "empty": empty, "broken": broken,
        "corrected": corrected, "corrupted": corrupted,
    }


def _aggregate(recs):
    """Aggregate per-question flip stats for one method into one summary dict."""
    per_q = [d for d in (_per_question(r) for r in recs) if d is not None]
    n = len(per_q)
    if n == 0:
        return None

    flips = {t: 0 for t in GENUINE_FLIPS}
    switch = {"W->R": 0, "R->W": 0}
    no_answer = {t: 0 for t in NOANSWER_FLIPS}
    per_transition = {}
    wrong_opp = right_opp = 0
    round0_correct = final_correct = 0
    agg = {"n": 0, "W->R": 0, "R->W": 0}
    traj = {"fixed": 0, "empty": 0, "broken": 0, "corrected": 0, "corrupted": 0}
    examples = []

    for d in per_q:
        round0_correct += d["round0_correct"]
        final_correct += d["final_correct"]
        if d["round0_vote"] != d["final_vote"]:
            agg["n"] += 1
            if d["final_correct"] and not d["round0_correct"]:
                agg["W->R"] += 1
            elif d["round0_correct"] and not d["final_correct"]:
                agg["R->W"] += 1
        wrong_opp += d["wrong_opp"]
        right_opp += d["right_opp"]
        for t in GENUINE_FLIPS:
            flips[t] += sum(1 for e in d["events"] if e["flip"] == t)
        for t in NOANSWER_FLIPS:
            no_answer[t] += d["no_answer"][t]
        for e in d["events"]:
            if e["flip"] in ("W->R", "R->W"):
                if e["switch_to_peer"]:
                    switch[e["flip"]] += 1
                examples.append(e)
        for label, counts in d["per_transition"].items():
            per_transition.setdefault(label, {t: 0 for t in ALL_FLIPS})
            for t in ALL_FLIPS:
                per_transition[label][t] += counts[t]
        for k in traj:
            traj[k] += d[k]

    return {
        "n_questions": n,
        "n_agents": per_q[0]["n_agents"],
        "n_rounds": max(d["n_rounds"] for d in per_q),
        "round0_acc": round0_correct / n,
        "final_acc": final_correct / n,
        "aggregate_flips": agg,
        "genuine_flips": {
            **flips, "total": sum(flips.values()),
            "wrong_opportunities": wrong_opp,
            "right_opportunities": right_opp,
            "W->R_rate": flips["W->R"] / wrong_opp if wrong_opp else 0.0,
            "R->W_rate": flips["R->W"] / right_opp if right_opp else 0.0,
            "W->R_switch_to_peer": switch["W->R"],
            "R->W_switch_to_peer": switch["R->W"],
            "W->R_switch_rate": switch["W->R"] / flips["W->R"] if flips["W->R"] else 0.0,
            "R->W_switch_rate": switch["R->W"] / flips["R->W"] if flips["R->W"] else 0.0,
        },
        "no_answer_transitions": {**no_answer, "total": sum(no_answer.values())},
        "per_transition": per_transition,
        "trajectories": traj,
        "examples": examples,
    }


# ----------------------------------------------------------------------------- rendering

def _pct(x):
    return f"{100 * x:.1f}"


def _render_md(by_method):
    lines = [
        "# Debate flips",
        "",
        "**Genuine flip** = one agent changes its (non-empty) answer between two consecutive "
        "rounds. **W->R** = a wrong answer was corrected (debate fixes); **R->W** = a right "
        "answer was abandoned for a wrong one (debate spreads). **W->W / R->R** = sideways "
        "(answer changed, correctness unchanged). **switch-to-peer** = the new answer was one "
        "a peer held in the previous round. Rates are over the genuine (non-empty) answers "
        "eligible to change.",
        "",
        "A transition to/from `none` (no parsable answer) is a **truncation artifact**, not a "
        "genuine flip: it is reported separately under \"No-answer transitions\" and excluded "
        "from the W->R / R->W rates.",
        "",
        "## Per method",
        "",
        "| Method | n | Round-0 acc | Final acc | Agg. flips (n / W->R / R->W) | Genuine W->R (rate) | Genuine R->W (rate) | W->R switch | R->W switch | No-answer trans. | Trajectories (fixed / empty / broken / corrected / corrupted) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m, s in by_method.items():
        g = s["genuine_flips"]
        t = s["trajectories"]
        lines.append(
            f"| {m} | {s['n_questions']} | {_pct(s['round0_acc'])} | {_pct(s['final_acc'])} | "
            f"{s['aggregate_flips']['n']} / {s['aggregate_flips']['W->R']} / {s['aggregate_flips']['R->W']} | "
            f"{g['W->R']} ({_pct(g['W->R_rate'])}) | {g['R->W']} ({_pct(g['R->W_rate'])}) | "
            f"{_pct(g['W->R_switch_rate'])} | {_pct(g['R->W_switch_rate'])} | "
            f"{s['no_answer_transitions']['total']} | "
            f"{t['fixed']} / {t['empty']} / {t['broken']} / {t['corrected']} / {t['corrupted']} |")

    all_labels = []
    for s in by_method.values():
        for label in s["per_transition"]:
            if label not in all_labels:
                all_labels.append(label)
    lines += ["", "## Genuine flips per round (W->R / R->W)", ""]
    header = "| Method |" + "".join(f" {lab} |" for lab in all_labels)
    lines += [header, "|" + "---|" * (len(all_labels) + 1)]
    for m, s in by_method.items():
        cells = []
        for lab in all_labels:
            c = s["per_transition"].get(lab, {})
            cells.append(f"{c.get('W->R', 0)} / {c.get('R->W', 0)}")
        lines.append(f"| {m} |" + "".join(f" {c} |" for c in cells))

    lines += [
        "",
        "Trajectory legend (per agent): **fixed** = never changed a real answer; **empty** = "
        "never produced an answer (truncated every round); **broken** = always a genuine wrong "
        "answer (never `none`); **corrected** = genuine wrong -> right; **corrupted** = genuine "
        "right -> wrong.",
    ]
    return "\n".join(lines) + "\n"


def _plot(by_method, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed: no flips_by_round.png)")
        return
    # shared x-axis: union of transition labels, so methods with different round counts
    # (e.g. r=2 next to r=4) line up on the same rounds.
    labels = []
    for s in by_method.values():
        for lab in s["per_transition"]:
            if lab not in labels:
                labels.append(lab)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for m, s in by_method.items():
        wr = [s["per_transition"].get(lab, {}).get("W->R", 0) for lab in labels]
        rw = [s["per_transition"].get(lab, {}).get("R->W", 0) for lab in labels]
        x = list(range(len(labels)))
        ax.plot(x, wr, "o-", label=f"{m} W->R")
        ax.plot(x, rw, "s--", label=f"{m} R->W")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Round transition")
    ax.set_ylabel("Number of genuine flips")
    ax.set_title("Genuine flips by round (W->R vs R->W)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = os.path.join(out_dir, "flips_by_round.png")
    fig.savefig(path, dpi=150)
    print(f"Saved {path}")


# ----------------------------------------------------------------------------- entry point

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir")
    ap.add_argument("--methods", nargs="*", default=None,
                    help="only these methods (default: every debate method)")
    a = ap.parse_args(argv)

    by_method = load_records(a.out_dir)
    debate = {m: recs for m, recs in by_method.items() if m.startswith("debate")}
    if a.methods:
        debate = {m: debate[m] for m in a.methods if m in debate}
    if not debate:
        print("No debate records found in", a.out_dir)
        return

    summaries = {m: _aggregate(recs) for m, recs in debate.items()}
    summaries = {m: s for m, s in summaries.items() if s is not None}
    if not summaries:
        print("No debate records with a usable trace found in", a.out_dir)
        return

    md = _render_md(summaries)
    with open(os.path.join(a.out_dir, "flips.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(a.out_dir, "flips.json"), "w", encoding="utf-8") as f:
        json.dump({m: {k: v for k, v in s.items() if k != "examples"}
                   for m, s in summaries.items()}, f, indent=2)

    examples = []
    for m, s in summaries.items():
        examples.extend(s["examples"])
    with open(os.path.join(a.out_dir, "flips_examples.jsonl"), "w", encoding="utf-8") as f:
        for e in examples:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(md)
    _plot(summaries, a.out_dir)
    print(f"Wrote flips.md, flips.json, flips_examples.jsonl "
          f"({len(examples)} genuine W->R/R->W examples) in {a.out_dir}")


if __name__ == "__main__":
    main()
