# Project notes (shared context)

Both team members AND both members' coding agents read this file first and update it at the
end of every work session. Commit it together with the code and results it describes.
Keep it short and current: delete what is no longer true.

## Team
- Member A: <name> (DJ_USER=<a>)
- Member B: <name> (DJ_USER=<b>)

## Research question and hypothesis
- Question: <which of 1-9, or our own>
- Hypothesis: <the result we expect, and why>

## Current status
- [ ] Offline test passes (`bash scripts/test_offline.sh`)   <- ran manually on Windows,
      see "Log of work sessions"; there is no `bash` in the dev shell, so the steps were
      executed one by one and the structural check ran as `scripts/_check_records.py`
- [ ] Prices and model id checked in `dj/config.py`
- [ ] Pilot run (N=20) - cost per question noted below
- [ ] Baselines (N=100)  (judgebench done for the gpt split; gsm8k/mmlu_pro still N=20)
- [ ] Our method implemented
- [ ] Main experiment
- [ ] Error analysis
- [ ] Report

## Who is doing what (now)
| Task | Owner | Branch / PR | Status |
|---|---|---|---|
| Metrics v2 (accuracy breakdown + max_tokens tracking) | Kat | `Kat` | done, mock-tested |

## Results so far (copy key rows from results/*/table.md)
| Dataset | Method | Acc % [95% CI] | Cost/q | Notes |
|---|---|---|---|---|
| mmlu_pro (N=20) | cot | 65.0 [43.3, 81.9] | 0.00122 | 30% no parsable answer: the call hit max_tokens |
| mmlu_pro (N=20) | sc:k=9 | 70.0 [48.1, 85.5] | 0.00997 | reference method |
| mmlu_pro (N=20) | debate:n=3,r=2 | 65.0 [43.3, 81.9] | 0.01058 | 9 calls, no gain over sc:k=9 |
| gsm8k (N=20) | all | 100.0 [83.9, 100.0] | - | ceiling: the subset is too easy, unusable |
| judgebench gpt (N=100) | judge | 54.0 [44.3, 63.4] | 0.00394 | answered-only 98.2%; 45% of questions truncated |
| judgebench gpt (N=100) | judge:k=3 | 74.0 [64.6, 81.6] | 0.00966 | +20.0 pp vs judge [12.0, 28.0], McNemar p=0.000, 20W/0L |

### JudgeBench finding (N=100, split=gpt, $0.966 spent)
- The judge is **not** bad: accuracy among answered questions is **98.2%** for `judge` and
  94.9% for `judge:k=3`. The old all-questions metric (54.0%) was measuring how often the
  judge fit in max_tokens, not its skill.
- 45% of `judge` questions had a call stop at max_tokens (74/200 calls = 37%).
  With k=3 the share of failed questions drops to 22% simply because 3 samples give more
  chances that at least one of them fits.
- **`deepseek-flash` is deterministic even at temperature 0.0**: two independent samples of
  the same judge prompt returned byte-identical text (320 tokens / 62 tokens with thinking
  disabled). So `judge:k=3` is not 3 independent votes; it behaves like "retry until one
  call fits the limit", at 3x the cost. Compare methods at equal `answered` counts before
  claiming k=3 judges better - at equal coverage it is not better (94.9% vs 98.2%).
- Disabling thinking (`extra_body={"thinking": {"type": "disabled"}}) cut output tokens from
  320 to 62 on the same judge prompt with the same answer. Candidate cheap win, not applied
  yet because it changes the experiment condition.

## Budget
- Limit $30 per team. Spent so far: $0.4534 (real log `logs/calls_sasipol.r.jsonl`, 637 calls;
  run `python -m dj.spend` to refresh)

## Decisions (and why)
- **max_tokens stays 2048 - it is an experiment condition, not a bug to fix.** We do NOT
  raise it. Instead we track `finish_reason == "length"` so the cost of the limit is visible
  per method (see "Metric changes v2" below).
- Accuracy over **all questions** (a non-answer counts as wrong) is kept unchanged, so every
  number already in `results/` stays comparable. The new metrics are ADDED next to it, not
  substituted for it.
- Truncation is counted by observing `dj.llm.chat` from `dj.run`. The methods do
  `from .llm import chat`, so `dj.methods.chat` must be patched too - patching only
  `dj.llm.chat` silently counts nothing. This only observes calls; no algorithm and no
  prompt was changed, so old and new results stay comparable.
- `outcome` label per question: `correct | wrong | no_answer | truncated | technical_error`.
  Old records (metrics_version < 2) have no `outcome` and are re-classified at read time by
  `dj/report.py:outcome_of`; **saved result files are never rewritten**.

## Metric changes v2 (why the table changed)
- `Accuracy (all) %` - unchanged: correct / n, non-answers count as wrong.
- `Accuracy (answered) %` - correct / questions where the method produced a parsable answer,
  with a 95% Wilson CI computed over the answered questions only.
- `No answer % (wrong / no-ans / trunc / error)` - the share of questions outside
  "answered", split by why they are outside. A question is counted only once:
  `truncated` applies only when the method produced no usable answer.
- `Impact of the experiment limit (max_tokens = 2048)` block - per method, how many questions
  had at least one truncated call, and the share of truncated calls out of calls made.

## Open problems / next steps
- Old paid results have no per-call `finish_reason` (written before tracking existed), so
  per-call truncation counts for them are unknown. The `Reply.truncated` fallback
  ("output_tokens >= limit") recovers the question-level fact but not per-call counts.
- N=20 is too small for gsm8k / mmlu_pro: CI width is ~+-20 pp and McNemar p-values are 1.0.
  Need N=100 before any claim about debate vs self-consistency.
- `judgebench` has never been run: **now it has** (N=100, gpt split), but it is still
  commented out in `scripts/run_baseline.sh`. The `claude` split (270 pairs) is untouched.
- The 45% truncation rate on `judge` makes the all-questions number misleading. Either
  report answered-only numbers as the headline, or add a truncation-retry that is applied
  identically to every method (that would change the experiment condition - decide first).
- `deepseek-flash` returns identical samples at temperature 0.0, so self-consistency-style
  voting may be degenerate for this model in general, not only for the judge. Worth checking
  on `sc:k=3/6/9` before interpreting the self-consistency curve.
- Duplicate `debate-judge-baseline/` folder (same README as root, empty NOTES template):
  decide which tree is canonical.
- `requirements.txt` still missing: `datasets` had to be installed by hand, and `h11` had to
  be pinned to `<0.15` for `openai`/`httpx` to work alongside `huggingface-hub`.

## Log of work sessions
- **metrics v2, Kat**: added the accuracy breakdown and max_tokens tracking.
  - `dj/llm.py`: `Reply.finish_reason` + `Reply.truncated`; `_api_call` now reads
    `choices[0].finish_reason`; finish_reason is stored in the cache and the call log;
    `_is_truncated()` falls back to "output_tokens >= limit" for pre-tracking cache entries.
  - `dj/config.py`: `MOCK_TRUNCATION_RATE` (default 0.2) so the mock model can simulate
    hitting max_tokens and returning an empty answer.
  - `dj/run.py`: `TruncationCounter` wraps `dj.llm.chat` **and** `dj.methods.chat` and
    records `truncated_calls` / `calls_made` per question; new record fields `outcome`,
    `truncated_calls`, `calls_made`, `metrics_version`; `run_config.json` now stores
    `max_tokens` and `metrics_version`.
  - `dj/report.py`: `Accuracy (all)` (unchanged), `Accuracy (answered)` + 95% CI,
    `No answer %` split into wrong / no-answer / truncated / error, and an "Impact of the
    experiment limit" table; the plot now has two panels (all vs answered-only).
  - `.gitignore`: `__pycache__`, `.DS_Store`, mock logs/cache (`*.mock`), scratch results
    (`results/_*/`). Existing tracked data was NOT deleted.
  - `scripts/_check_records.py`: fails if a fresh mock record lacks the new fields, or if the
    mock never produced a truncated call (i.e. if truncation tracking silently broke).
  - Testing (mock, $0): all three sample datasets run end-to-end; the structural check is
    green. Verified backwards compatibility: old `results/mmlu_pro` records re-summarise as
    acc 65% / answered 14 of 20 / acc_answered 92.9% / no_answer 30%.
  - Next: run N=100 on `mmlu_pro` with the new metrics; consider running `judgebench`.

- **judgebench N=100, Kat**: first real run of the judge dataset (split=gpt, $0.966).
  - Installed `datasets` 5.2.0 (was missing, so `load_judgebench` could not run at all) and
    pinned `h11<0.15` to satisfy `openai` -> `httpx` -> `httpcore`.
  - Results and the interpretation are in the `judgebench` rows above. Headline: the judge is
    accurate (98.2% among answered) and the low all-questions score is pure truncation.
  - `judge:k=3` looks better (+20 pp) only because it retries; the samples are identical.
  - `.gitignore` now also covers `*.log`, `*.err` and `scripts/_*.py` (one-off helper scripts).
  - Next: decide how truncation should be handled before comparing methods; run the `claude`
    split; write `requirements.txt`.

- **outcome-labeling fix, Sasipol**: `dj.run.classify()` stored `outcome="wrong"` for correct
  answers (it never returned `"correct"`), so the report's outcome breakdown counted correct
  questions under "wrong" (judgebench `judge` showed wrong=55, should be 1).
  - `dj/report.py:outcome_of` now re-derives the label from the authoritative `correct`/`error`/
    `pred`/`truncated_calls` fields instead of trusting the stored `outcome`. Saved records are
    NOT rewritten; the old judgebench table re-summarises correctly (wrong=1 and wrong=4).
  - `dj/run.py:classify` now takes `correct` and returns `"correct"` for correct answers, so new
    records are stored correctly at write time too.
  - `scripts/test_offline.sh` now clears `cache/llm_cache.sqlite.mock` first: a stale mock cache
    (133/134 entries predating truncation tracking) was replaying "stop" replies and hiding
    truncation, failing the structural check. Offline test is green again.

- **flips analysis, Sasipol**: added `dj/flips.py` - read-only debate flip analysis for Q3
  ("does debate correct errors or spread them?"). Counts per-agent answer changes across
  rounds: W->R (corrected), R->W (spread), sideways W->W / R->R, switch-to-peer, plus the
  round-0 vs final majority vote and per-agent trajectories (fixed / broken / corrected /
  corrupted). Writes `flips.md` / `flips.json` / `flips_by_round.png` / `flips_examples.jsonl`
  next to `table.md`. `dj/run.py` auto-runs it after any run that includes a debate method; it
  also runs standalone (`python -m dj.flips results/<folder>`) for free on saved records.
  Verified on mock + mmlu_pro records.

- **peers=0 + style=verify, Sasipol**: added the two Q3 control/innovation variants to
  `dj/methods.py:debate`.
  - `peers=0`: no-peers control - each agent re-checks ONLY its own previous answer (no peer
    solutions shown), separating social influence from re-sampling randomness.
  - `style=verify`: verify-before-switch - an agent may change its answer only after naming a
    specific error in its own previous reasoning (aims to cut R->W flips).
  - Four update prompts now exist (normal/recheck x normal/verify). Round 0 is unchanged and
    still shared with `sc` via the cache, so every debate variant starts from the same agents.
  - `test_offline.sh` now exercises both variants; offline test green.
