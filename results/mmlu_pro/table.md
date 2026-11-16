Reference for paired tests: **sc:k=9**  (diff = method - reference, same questions)

| Method | n | Accuracy % | 95% CI | Calls/q | Tokens/q (in+out) | Cost/q ($) | Total cost ($) | Diff vs ref (pp) [95% CI] | Wins/Losses | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|
| cot | 20 | 65.0 | [43.3, 81.9] | 1.0 | 1185 | 0.00122 | 0.024 | -5.0 [-15.0, 0.0] | 0/1 | 1.000 |
| sc:k=3 | 20 | 65.0 | [43.3, 81.9] | 3.0 | 3409 | 0.00343 | 0.069 | -5.0 [-15.0, 0.0] | 0/1 | 1.000 |
| sc:k=6 | 20 | 70.0 | [48.1, 85.5] | 6.0 | 6671 | 0.00668 | 0.134 | 0.0 [0.0, 0.0] | 0/0 | 1.000 |
| sc:k=9 | 20 | 70.0 | [48.1, 85.5] | 9.0 | 9967 | 0.00997 | 0.199 | - | - | - |
| debate:n=3,r=2 | 20 | 65.0 | [43.3, 81.9] | 9.0 | 11718 | 0.01058 | 0.212 | -5.0 [-15.0, 0.0] | 0/1 | 1.000 |

- cot: 0 errors, 6 without a parsable answer (counted wrong)
- sc:k=3: 0 errors, 4 without a parsable answer (counted wrong)
- sc:k=6: 0 errors, 2 without a parsable answer (counted wrong)
- sc:k=9: 0 errors, 2 without a parsable answer (counted wrong)
- debate:n=3,r=2: 0 errors, 5 without a parsable answer (counted wrong)
