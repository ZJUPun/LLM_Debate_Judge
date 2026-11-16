# debate-judge-baseline

A small framework for the final project **LLM Debate and LLM Judge**: multi-agent debate,
an LLM judge, CoT and self-consistency baselines, and an evaluation harness that measures
accuracy, 95% confidence intervals, paired tests and API cost. It uses only the OpenAI
Python SDK with the DeepSeek base URL.

## Setup
Recommended to set up a venv first

python -m venv .venv         (Do this once only!)        #create the environment 
source .venv/bin/activate 
pip -r install requirements.txt


```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY=sk-...          # never commit your key
export DJ_USER=alice                    # your name: your call log goes to logs/calls_alice.jsonl
```

**Before you spend money:** check the prices in `dj/config.py` (`PRICE_PER_M`) against
<https://api-docs.deepseek.com/quick_start/pricing>, and check that the model name
`deepseek-flash` is accepted by the API. If the API rejects the name, set
`export DEEPSEEK_MODEL=<the exact model id>` and ask your instructor which id they mean.

## 1. Free test (no key, no internet, fake model)

```bash
bash scripts/test_offline.sh
```

## 2. Pilot (a few cents), then the baselines

```bash
N=20 bash scripts/run_baseline.sh       # pilot: look at Cost/q in the tables
bash scripts/run_baseline.sh            # full: N=100 questions per dataset
python -m dj.spend                      # team spending so far
```

Each run writes to `results/<dataset>/`:

| File | What it is |
|---|---|
| `records/<method>.jsonl` | one line per question: answer, correct?, tokens, cost, full trace (every round of the debate, every judge vote) |
| `table.md` | the results table: accuracy, 95% CI, calls, tokens, cost, paired diff vs. the reference method, McNemar p |
| `accuracy_vs_cost.png` | the accuracy-vs-cost plot for the report |
| `run_config.json` | settings + the exact question ids |

Rebuild a table without any API call: `python -m dj.report results/gsm8k --ref "sc:k=9"`.
Re-running any experiment is free: every call is cached in `cache/llm_cache.sqlite`.

## Methods and how to call them

```bash
python -m dj.run --dataset gsm8k --n 100 --methods cot "sc:k=9" "debate:n=3,r=2"
```

| Spec | Meaning | Calls per question |
|---|---|---|
| `cot` | one chain-of-thought answer (temperature 0) | 1 |
| `sc:k=9` | self-consistency: 9 samples, majority vote | k |
| `debate:n=3,r=2` | 3 agents, round 0 + 2 debate rounds, majority vote | n·(r+1) |
| `debate:n=3,r=2,agg=judge` | ...then the LLM judge picks between the top-2 answers | +2 if they disagree |
| `debate:n=3,r=3,stop=1` | stop early when all agents agree | variable |
| `judge` | (JudgeBench) judge both orders; counts only if both agree | 2 |
| `judge:k=3` | 3 samples per order, majority of the 6 votes | 2k |

Datasets: `gsm8k` (math), `mmlu_pro` (10-option multiple choice; `--category physics`),
`judgebench` (`--split gpt|claude`). `--seed` selects a different fixed subset.
`--budget 5` stops a run that spends more than $5.

## Fair comparisons (same cost)

Debate prompts grow every round (each agent reads the others), so 9 debate calls cost
**more tokens** than 9 self-consistency calls. Compare on **Cost/q**, not on calls. The
plot draws the self-consistency curve (k = 3, 6, 9...): a method is better only if it is
above that curve at the same cost. Add more `sc:k=...` points if you need a closer match.

Note: debate round 0 uses the same cached samples as `sc` (sample ids 0..n-1). This is fine
and makes the paired comparison tighter; the cost columns still count every call in full.

## Add your own method

Open `dj/methods.py`, copy the skeleton at the bottom:

```python
@register("mymethod")
def my_method(q: Question, n=3, r=2):
    reply = chat("...", sample_id=0, tag=f"mymethod/{q.id}")   # ALWAYS use chat()
    ...
    return Result(pred, {"anything": "for error analysis"})
```

then run `python -m dj.run --dataset gsm8k --methods "sc:k=9" "mymethod:n=3"`.
Never call the API directly: `chat()` is what counts your tokens and cost.

## Files

```
dj/config.py    model, prices, paths, budget
dj/llm.py       chat(): cache, log, cost meter, retries, mock model
dj/data.py      GSM8K, MMLU-Pro, JudgeBench loaders (fixed subsets)
dj/answers.py   answer extraction, correctness, majority vote
dj/methods.py   prompts, CoT, self-consistency, debate engine, judge  <- add methods here
dj/stats.py     Wilson CI, McNemar exact test, paired bootstrap
dj/run.py       the harness (CLI)
dj/report.py    table + plot from saved records
dj/spend.py     team spending
NOTES.md        shared project context for both members and their coding agents
```
