Reference for paired tests: **sc:k=9**  (diff = method - reference, same questions)

**Accuracy (all)** = correct / n, a non-answer counts as wrong (unchanged definition).
**Accuracy (answered)** = correct / questions where the method produced a parsable answer. **No answer %** = share of questions with no parsable answer, split into *wrong*, *no answer* (model answered nothing usable), *truncated* (hit max_tokens) and *error* (technical failure).

| Method | n | Accuracy (all) % | 95% CI | Accuracy (answered) % | No answer % (wrong / no-ans / trunc / error) | Calls/q | Tokens/q (in+out) | Cost/q ($) | Total cost ($) | Diff vs ref (pp) [95% CI] | Wins/Losses | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cot | 200 | 97.0 | [93.6, 98.6] | 98.0 [94.9, 99.2] | 1.0 (4 / 0 / 2 / 0) | 1.0 | 375 | 0.00035 | 0.069 | -0.5 [-1.5, 0.0] | 0/1 | 1.000 |
| sc:k=3 | 200 | 97.0 | [93.6, 98.6] | 97.5 [94.3, 98.9] | 0.5 (5 / 0 / 1 / 0) | 3.0 | 1152 | 0.00107 | 0.214 | -0.5 [-1.5, 0.0] | 0/1 | 1.000 |
| sc:k=6 | 200 | 97.5 | [94.3, 98.9] | 97.5 [94.3, 98.9] | 0.0 (5 / 0 / 0 / 0) | 6.0 | 2293 | 0.00213 | 0.426 | 0.0 [0.0, 0.0] | 0/0 | 1.000 |
| sc:k=9 | 200 | 97.5 | [94.3, 98.9] | 97.5 [94.3, 98.9] | 0.0 (5 / 0 / 0 / 0) | 9.0 | 3440 | 0.00320 | 0.640 | - | - | - |
| debate:n=3,r=2 | 200 | 96.0 | [92.3, 98.0] | 96.5 [92.9, 98.3] | 0.5 (7 / 0 / 1 / 0) | 9.0 | 5266 | 0.00387 | 0.773 | -1.5 [-3.5, 0.0] | 0/3 | 0.250 |
| debate:n=3,r=2,peers=0 | 200 | 95.5 | [91.7, 97.6] | 96.5 [92.9, 98.3] | 1.0 (7 / 0 / 2 / 0) | 9.0 | 4578 | 0.00408 | 0.816 | -2.0 [-4.0, -0.5] | 0/4 | 0.125 |
| debate:n=3,r=2,style=verify | 200 | 96.0 | [92.3, 98.0] | 96.0 [92.3, 98.0] | 0.0 (8 / 0 / 0 / 0) | 9.0 | 5963 | 0.00443 | 0.886 | -1.5 [-3.5, 0.0] | 0/3 | 0.250 |

- cot: 0 errors, 2 without a parsable answer (counted wrong)
- sc:k=3: 0 errors, 1 without a parsable answer (counted wrong)
- debate:n=3,r=2: 0 errors, 1 without a parsable answer (counted wrong)
- debate:n=3,r=2,peers=0: 0 errors, 2 without a parsable answer (counted wrong)

**Impact of the experiment limit (max_tokens = 2048)**

| Method | Questions with a truncated call | Calls truncated | Truncated calls % |
|---|---|---|---|
| cot | 2/200 (1.0) | 2/200 | 1.0 |
| sc:k=3 | 4/200 (2.0) | 7/600 | 1.2 |
| sc:k=6 | 6/200 (3.0) | 13/1200 | 1.1 |
| sc:k=9 | 8/200 (4.0) | 20/1800 | 1.1 |
| debate:n=3,r=2 | 6/200 (3.0) | 21/1800 | 1.2 |
| debate:n=3,r=2,peers=0 | 16/200 (8.0) | 43/1800 | 2.4 |
| debate:n=3,r=2,style=verify | 13/200 (6.5) | 30/1800 | 1.7 |

A truncated question is one where at least one model call inside the method stopped with `finish_reason == "length"`. Per-call truncation is derived from call usage: records written before truncation tracking existed (metrics_version < 2) have no per-call `finish_reason`, so their counts may be 0/absent.
