Reference for paired tests: **sc:k=9**  (diff = method - reference, same questions)

**Accuracy (all)** = correct / n, a non-answer counts as wrong (unchanged definition).
**Accuracy (answered)** = correct / questions where the method produced a parsable answer. **No answer %** = share of questions with no parsable answer, split into *wrong*, *no answer* (model answered nothing usable), *truncated* (hit max_tokens) and *error* (technical failure).

| Method | n | Accuracy (all) % | 95% CI | Accuracy (answered) % | No answer % (wrong / no-ans / trunc / error) | Calls/q | Tokens/q (in+out) | Cost/q ($) | Total cost ($) | Diff vs ref (pp) [95% CI] | Wins/Losses | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cot | 200 | 76.5 | [70.2, 81.8] | 95.6 [91.2, 97.9] | 20.0 (7 / 0 / 40 / 0) | 1.0 | 993 | 0.00096 | 0.192 | -5.5 [-9.0, -2.5] | 1/12 | 0.003 |
| sc:k=3 | 200 | 79.0 | [72.8, 84.1] | 91.9 [86.8, 95.1] | 14.0 (14 / 0 / 28 / 0) | 3.0 | 2937 | 0.00279 | 0.557 | -3.0 [-5.5, -1.0] | 0/6 | 0.031 |
| sc:k=6 | 200 | 81.5 | [75.5, 86.3] | 91.6 [86.6, 94.8] | 11.0 (15 / 0 / 22 / 0) | 6.0 | 5863 | 0.00556 | 1.112 | -0.5 [-1.5, 0.0] | 0/1 | 1.000 |
| sc:k=9 | 200 | 82.0 | [76.1, 86.7] | 91.6 [86.6, 94.9] | 10.5 (15 / 0 / 21 / 0) | 9.0 | 8755 | 0.00829 | 1.658 | - | - | - |
| debate:n=3,r=2 | 200 | 79.0 | [72.8, 84.1] | 93.5 [88.7, 96.3] | 15.5 (11 / 0 / 31 / 0) | 9.0 | 10711 | 0.00896 | 1.792 | -3.0 [-6.0, 0.0] | 2/8 | 0.109 |
| debate:n=3,r=2,style=verify | 200 | 81.0 | [75.0, 85.8] | 93.1 [88.3, 96.0] | 13.0 (12 / 0 / 26 / 0) | 9.0 | 11006 | 0.00909 | 1.818 | -1.0 [-3.5, 1.5] | 2/4 | 0.688 |
| debate:n=3,r=2,peers=0 | 200 | 78.5 | [72.3, 83.6] | 92.9 [88.0, 95.9] | 15.5 (12 / 0 / 31 / 0) | 9.0 | 10108 | 0.00934 | 1.868 | -3.5 [-6.5, -1.0] | 1/8 | 0.039 |

- cot: 0 errors, 40 without a parsable answer (counted wrong)
- sc:k=3: 0 errors, 28 without a parsable answer (counted wrong)
- sc:k=6: 0 errors, 22 without a parsable answer (counted wrong)
- sc:k=9: 0 errors, 21 without a parsable answer (counted wrong)
- debate:n=3,r=2: 0 errors, 31 without a parsable answer (counted wrong)
- debate:n=3,r=2,style=verify: 0 errors, 26 without a parsable answer (counted wrong)
- debate:n=3,r=2,peers=0: 0 errors, 31 without a parsable answer (counted wrong)

**Impact of the experiment limit (max_tokens = 2048)**

| Method | Questions with a truncated call | Calls truncated | Truncated calls % |
|---|---|---|---|
| cot | 40/200 (20.0) | 40/200 | 20.0 |
| sc:k=3 | 45/200 (22.5) | 113/600 | 18.8 |
| sc:k=6 | 49/200 (24.5) | 224/1200 | 18.7 |
| sc:k=9 | 51/200 (25.5) | 331/1800 | 18.4 |
| debate:n=3,r=2 | 52/200 (26.0) | 335/1800 | 18.6 |
| debate:n=3,r=2,style=verify | 59/200 (29.5) | 338/1800 | 18.8 |
| debate:n=3,r=2,peers=0 | 69/200 (34.5) | 384/1800 | 21.3 |

A truncated question is one where at least one model call inside the method stopped with `finish_reason == "length"`. Per-call truncation is derived from call usage: records written before truncation tracking existed (metrics_version < 2) have no per-call `finish_reason`, so their counts may be 0/absent.
