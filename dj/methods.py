"""All methods: baselines (CoT, self-consistency), the debate engine, and the judge.

A method is a function  f(q: Question, **params) -> Result.
Register it with @register("name", kinds=(...)) and run it with e.g.
    python -m dj.run --dataset gsm8k --methods "mymethod:x=3"


"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .answers import extract, extract_winner, majority_vote
from .data import Question
from .llm import chat

# ============================================================================= prompts
# Keep every prompt here, so you can copy them into your report ("Method" section).

FORMAT = {
    "math": "End your reply with a final line of the form 'Answer: <number>'.",
    "mc": "End your reply with a final line of the form 'Answer: <letter>'.",
}

COT_PROMPT = "{question}\n\nThink step by step, then give your final answer. {format}"

DEBATE_UPDATE_PROMPT = """{question}

Your previous solution was:
---
{own}
---

These are the solutions from the other agents:
{others}

Use the other agents' solutions as additional information. Check each solution carefully \
(including your own), then give your updated solution. {format}"""

JUDGE_PROMPT = """You are an impartial judge. Below is a question and two responses.
Exactly one of the responses is correct. Decide which one.
Do not let the order of the responses or their length influence you.

[Question]
{question}

[Response A]
{a}

[Response B]
{b}

Reply with JSON only, in this format:
{{"reasoning": "<short explanation>", "winner": "A" or "B"}}"""


# ============================================================================= registry

@dataclass
class Result:
    pred: str | None                      # final answer (number, letter, or "A"/"B" for judging)
    trace: dict = field(default_factory=dict)   # everything useful for error analysis


METHODS: dict[str, tuple] = {}


def register(name, kinds=("math", "mc")):
    def deco(fn):
        METHODS[name] = (fn, tuple(kinds))
        return fn
    return deco


def parse_spec(spec: str):
    """'debate:n=3,r=2,agg=judge' -> ('debate', {'n': 3, 'r': 2, 'agg': 'judge'})"""
    name, _, rest = spec.partition(":")
    params = {}
    for part in filter(None, rest.split(",")):
        k, _, v = part.partition("=")
        for cast in (int, float):
            try:
                v = cast(v)
                break
            except ValueError:
                pass
        params[k.strip()] = v
    if name not in METHODS:
        raise SystemExit(f"Unknown method '{name}'. Known: {sorted(METHODS)}")
    import inspect
    allowed = set(inspect.signature(METHODS[name][0]).parameters) - {"q"}
    bad = set(params) - allowed
    if bad:
        raise SystemExit(f"Method '{name}' has no parameter(s) {sorted(bad)}. Allowed: {sorted(allowed)}")
    return name, params


# ============================================================================= baselines

def _answer_once(q: Question, sample_id=0, temperature=0.7, tag=""):
    r = chat(COT_PROMPT.format(question=q.prompt, format=FORMAT[q.kind]),
             temperature=temperature, sample_id=sample_id, tag=tag)
    return r.text, extract(r.text, q.kind)


@register("cot")
def cot(q: Question, temperature=0.0):
    """Chain-of-thought: one answer (greedy by default)."""
    text, pred = _answer_once(q, temperature=temperature, tag=f"cot/{q.id}")
    return Result(pred, {"text": text})


@register("sc")
def self_consistency(q: Question, k=5, temperature=0.7):
    """Self-consistency: k independent CoT samples + majority vote."""
    samples = [_answer_once(q, sample_id=i, temperature=temperature, tag=f"sc/{q.id}/{i}")
               for i in range(k)]
    preds = [p for _, p in samples]
    return Result(majority_vote(preds), {"preds": preds, "texts": [t for t, _ in samples]})


# ============================================================================= debate engine

@register("debate")
def debate(q: Question, n=3, r=2, agg="vote", stop=0, temperature=0.7):
    """Multi-agent debate.
    n    : number of agents
    r    : number of debate rounds AFTER round 0 (total calls = n * (r + 1) if no early stop)
    agg  : "vote" (majority of the last round) or "judge" (LLM judge between the top-2 answers)
    stop : 1 = stop early when all agents agree
    """
    fmt = FORMAT[q.kind]
    # Round 0: every agent answers alone
    texts = [_answer_once(q, sample_id=i, temperature=temperature,
                          tag=f"debate/{q.id}/a{i}/r0")[0] for i in range(n)]
    rounds = [[{"text": t, "pred": extract(t, q.kind)} for t in texts]]

    for rnd in range(1, r + 1):
        if stop and len({a["pred"] for a in rounds[-1]}) == 1:
            break
        new = []
        for i in range(n):   # all agents read the SAME snapshot (previous round)
            others = "\n\n".join(f"Agent {j + 1}:\n---\n{texts[j]}\n---"
                                 for j in range(n) if j != i)
            prompt = DEBATE_UPDATE_PROMPT.format(question=q.prompt, own=texts[i],
                                                 others=others, format=fmt)
            new.append(chat(prompt, temperature=temperature, sample_id=i,
                            tag=f"debate/{q.id}/a{i}/r{rnd}").text)
        texts = new
        rounds.append([{"text": t, "pred": extract(t, q.kind)} for t in texts])

    final_preds = [a["pred"] for a in rounds[-1]]
    trace = {"rounds": rounds, "preds_per_round": [[a["pred"] for a in rd] for rd in rounds]}

    if agg == "judge":
        pred, jt = _judge_aggregate(q, rounds[-1])
        trace["judge"] = jt
        return Result(pred, trace)
    return Result(majority_vote(final_preds), trace)


def _judge_aggregate(q, last_round):
    counts = Counter(a["pred"] for a in last_round if a["pred"] is not None)
    if len(counts) <= 1:
        return (next(iter(counts)) if counts else None), {"used": False}
    (p1, _), (p2, _) = counts.most_common(2)
    t1 = next(a["text"] for a in last_round if a["pred"] == p1)
    t2 = next(a["text"] for a in last_round if a["pred"] == p2)
    j = judge_pair(q.prompt, t1, t2, tag=f"debate-judge/{q.id}")
    if j["winner"] is None:                       # inconsistent judge -> fall back to the vote
        return majority_vote([a["pred"] for a in last_round]), {"used": True, **j}
    return (p1 if j["winner"] == "A" else p2), {"used": True, **j}


# ============================================================================= judge

def judge_once(question, a, b, sample_id=0, temperature=0.0, tag=""):
    r = chat(JUDGE_PROMPT.format(question=question, a=a, b=b),
             temperature=temperature, sample_id=sample_id, tag=tag)
    return extract_winner(r.text), r.text


def judge_pair(question, resp_a, resp_b, k=1, temperature=None, tag=""):
    """Compare two responses, each time in BOTH orders (to cancel position bias).
    k=1 : strict - the winner counts only if both orders agree, else winner=None.
    k>1 : k samples per order (temperature 0.7); majority of all 2k votes, tie -> None.
    Returns winner in terms of the ORIGINAL order ("A" = resp_a)."""
    if temperature is None:
        temperature = 0.0 if k == 1 else 0.7
    votes, raw = [], []
    for s in range(k):
        w1, t1 = judge_once(question, resp_a, resp_b, s, temperature, f"{tag}/ab/{s}")
        w2, t2 = judge_once(question, resp_b, resp_a, s, temperature, f"{tag}/ba/{s}")
        w2 = {"A": "B", "B": "A"}.get(w2)          # map back to original order
        votes += [w1, w2]
        raw.append({"ab": w1, "ba_mapped": w2, "ab_text": t1, "ba_text": t2})
    if k == 1:
        winner = votes[0] if votes[0] is not None and votes[0] == votes[1] else None
    else:
        c = Counter(v for v in votes if v)
        winner = None
        if c and (len(c) == 1 or c["A"] != c["B"]):
            winner = c.most_common(1)[0][0]
    # position bias signal: how many single votes picked whatever was shown FIRST
    first_pos = sum(1 for d in raw if d["ab"] == "A") + sum(1 for d in raw if d["ba_mapped"] == "B")
    return {"winner": winner, "votes": votes, "picked_first_position": first_pos,
            "n_votes": 2 * k, "raw": raw}


@register("judge", kinds=("pair",))
def judge(q: Question, k=1):
    """JudgeBench: pick the correct response of the pair."""
    j = judge_pair(q.prompt, q.meta["response_A"], q.meta["response_B"], k=k, tag=f"judge/{q.id}")
    return Result(j["winner"], j)


# ============================================================================= YOUR METHOD
# Example skeleton - copy, rename and change it.
#
# @register("mydebate")
# def my_debate(q: Question, n=3, r=2):
#     ...call chat() as many times as you need...
#     return Result(pred, {"anything": "useful for analysis"})
