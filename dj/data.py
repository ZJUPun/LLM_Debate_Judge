"""Dataset loaders. Every loader returns a list of Question with the SAME fixed subset
for a given (n, seed), so every method is tested on exactly the same questions
(needed for paired tests)."""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field

from . import config

LETTERS = "ABCDEFGHIJ"


@dataclass
class Question:
    id: str
    dataset: str
    kind: str            # "math" (number answer), "mc" (letter answer), "pair" (judge: A or B)
    prompt: str          # the question text as shown to the model
    gold: str            # answer key
    meta: dict = field(default_factory=dict)   # e.g. category, the two responses for "pair"


def _subset(rows, n, seed):
    idx = list(range(len(rows)))
    if n and n < len(idx):
        idx = sorted(random.Random(seed).sample(idx, n))
    return idx


def _hf(name, *args, **kw):
    from datasets import load_dataset
    return load_dataset(name, *args, **kw)


# ----------------------------------------------------------------------------- GSM8K

def load_gsm8k(n=100, seed=0):
    ds = _hf("openai/gsm8k", "main", split="test")
    out = []
    for i in _subset(ds, n, seed):
        r = ds[i]
        gold = r["answer"].split("####")[-1].strip().replace(",", "")
        out.append(Question(f"gsm8k-{i}", "gsm8k", "math", r["question"], gold))
    return out


# ----------------------------------------------------------------------------- MMLU-Pro

def format_mc(question, options):
    opts = "\n".join(f"({LETTERS[j]}) {o}" for j, o in enumerate(options))
    return f"{question}\n\n{opts}"


def load_mmlu_pro(n=100, seed=0, category=None):
    ds = _hf("TIGER-Lab/MMLU-Pro", split="test")
    if category:
        ds = ds.filter(lambda r: r["category"] == category)
    out = []
    for i in _subset(ds, n, seed):
        r = ds[i]
        out.append(Question(f"mmlupro-{r['question_id']}", "mmlu_pro", "mc",
                            format_mc(r["question"], r["options"]), r["answer"],
                            {"category": r["category"], "n_options": len(r["options"])}))
    return out


# ----------------------------------------------------------------------------- JudgeBench

def load_judgebench(n=100, seed=0, split="gpt"):
    """Pairs of responses where exactly one is correct. gold = the better response (A or B).
    split="gpt" (responses from GPT-4o) or "claude"."""
    ds = _hf("ScalerLab/JudgeBench", split=split)
    keep = [i for i in range(len(ds)) if ds[i]["label"] in ("A>B", "B>A")]
    out = []
    for j in _subset(keep, n, seed):
        r = ds[keep[j]]
        out.append(Question(f"judgebench-{r['pair_id']}", "judgebench", "pair", r["question"],
                            r["label"][0],
                            {"response_A": r["response_A"], "response_B": r["response_B"],
                             "source": r.get("source", "")}))
    return out


# ----------------------------------------------------------------------------- toy samples

def load_sample(name):
    """Tiny hand-written sets in data/samples/ for offline testing (DJ_MOCK=1)."""
    path = os.path.join(config.SAMPLE_DATA_DIR, f"{name}.jsonl")
    with open(path, encoding="utf-8") as f:
        return [Question(**json.loads(line)) for line in f if line.strip()]


LOADERS = {"gsm8k": load_gsm8k, "mmlu_pro": load_mmlu_pro, "judgebench": load_judgebench}


def load(name, n=100, seed=0, **kw):
    if name.startswith("sample_"):
        return load_sample(name)
    if name not in LOADERS:
        raise SystemExit(f"Unknown dataset {name}. Choose from {list(LOADERS)} or sample_*")
    return LOADERS[name](n=n, seed=seed, **kw)
