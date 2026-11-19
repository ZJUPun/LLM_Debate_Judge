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
- [ ] Baselines (N=100)
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
- N=20 is too small: CI width is ~+-20 pp and McNemar p-values are 1.0. Need N=100 before
  any claim about debate vs self-consistency.
- `judgebench` has never been run (commented out in `scripts/run_baseline.sh`) even though
  judging is half the project.
- Duplicate `debate-judge-baseline/` folder (same README as root, empty NOTES template):
  decide which tree is canonical.

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
