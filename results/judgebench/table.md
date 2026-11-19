Reference for paired tests: **judge**  (diff = method - reference, same questions)

**Accuracy (all)** = correct / n, a non-answer counts as wrong (unchanged definition).
**Accuracy (answered)** = correct / questions where the method produced a parsable answer. **No answer %** = share of questions with no parsable answer, split into *wrong*, *no answer* (model answered nothing usable), *truncated* (hit max_tokens) and *error* (technical failure).

| Method | n | Accuracy (all) % | 95% CI | Accuracy (answered) % | No answer % (wrong / no-ans / trunc / error) | Calls/q | Tokens/q (in+out) | Cost/q ($) | Total cost ($) | Diff vs ref (pp) [95% CI] | Wins/Losses | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| judge | 100 | 54.0 | [44.3, 63.4] | 98.2 [90.4, 99.7] | 45.0 (55 / 0 / 45 / 0) | 2.0 | 5574 | 0.00394 | 0.394 | - | - | - |
| judge:k=3 | 100 | 74.0 | [64.6, 81.6] | 94.9 [87.5, 98.0] | 22.0 (78 / 0 / 22 / 0) | 6.0 | 16713 | 0.00966 | 0.966 | 20.0 [12.0, 28.0] | 20/0 | 0.000 |

- judge: 0 errors, 45 without a parsable answer (counted wrong)
- judge:k=3: 0 errors, 22 without a parsable answer (counted wrong)

**Impact of the experiment limit (max_tokens = 2048)**

| Method | Questions with a truncated call | Calls truncated | Truncated calls % |
|---|---|---|---|
| judge | 45/100 (45.0) | 74/200 | 37.0 |
| judge:k=3 | 51/100 (51.0) | 211/600 | 35.2 |

A truncated question is one where at least one model call inside the method stopped with `finish_reason == "length"`. Per-call truncation is derived from call usage: records written before truncation tracking existed (metrics_version < 2) have no per-call `finish_reason`, so their counts may be 0/absent.
