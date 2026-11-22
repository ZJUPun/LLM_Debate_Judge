# Debate flips

**Genuine flip** = one agent changes its (non-empty) answer between two consecutive rounds. **W->R** = a wrong answer was corrected (debate fixes); **R->W** = a right answer was abandoned for a wrong one (debate spreads). **W->W / R->R** = sideways (answer changed, correctness unchanged). **switch-to-peer** = the new answer was one a peer held in the previous round. Rates are over the genuine (non-empty) answers eligible to change.

A transition to/from `none` (no parsable answer) is a **truncation artifact**, not a genuine flip: it is reported separately under "No-answer transitions" and excluded from the W->R / R->W rates.

## Per method

| Method | n | Round-0 acc | Final acc | Agg. flips (n / W->R / R->W) | Genuine W->R (rate) | Genuine R->W (rate) | W->R switch | R->W switch | No-answer trans. | Trajectories (fixed / broken / corrected / corrupted) |
|---|---|---|---|---|---|---|---|---|---|---|
| debate:n=3,r=2 | 200 | 97.0 | 96.0 | 3 / 0 / 2 | 0 (0.0) | 7 (0.6) | 0.0 | 42.9 | 16 | 583 / 13 / 0 / 6 |
| debate:n=3,r=2,peers=0 | 200 | 97.0 | 95.5 | 3 / 0 / 3 | 3 (8.8) | 7 (0.6) | 33.3 | 0.0 | 37 | 570 / 12 / 0 / 5 |
| debate:n=3,r=2,style=verify | 200 | 97.0 | 96.0 | 3 / 0 / 2 | 0 (0.0) | 6 (0.5) | 0.0 | 33.3 | 28 | 568 / 13 / 0 / 6 |

## Genuine flips per round (W->R / R->W)

| Method | r0->r1 | r1->r2 |
|---|---|---|
| debate:n=3,r=2 | 0 / 3 | 0 / 4 |
| debate:n=3,r=2,peers=0 | 0 / 7 | 3 / 0 |
| debate:n=3,r=2,style=verify | 0 / 4 | 0 / 2 |

Trajectory legend (per agent): **fixed** = never changed answer; **broken** = always a genuine wrong answer (never `none`); **corrected** = genuine wrong -> right from round 0 to the end; **corrupted** = genuine right -> wrong.
