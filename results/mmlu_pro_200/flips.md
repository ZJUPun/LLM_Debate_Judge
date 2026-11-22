# Debate flips

**Genuine flip** = one agent changes its (non-empty) answer between two consecutive rounds. **W->R** = a wrong answer was corrected (debate fixes); **R->W** = a right answer was abandoned for a wrong one (debate spreads). **W->W / R->R** = sideways (answer changed, correctness unchanged). **switch-to-peer** = the new answer was one a peer held in the previous round. Rates are over the genuine (non-empty) answers eligible to change.

A transition to/from `none` (no parsable answer) is a **truncation artifact**, not a genuine flip: it is reported separately under "No-answer transitions" and excluded from the W->R / R->W rates.

## Per method

| Method | n | Round-0 acc | Final acc | Agg. flips (n / W->R / R->W) | Genuine W->R (rate) | Genuine R->W (rate) | W->R switch | R->W switch | No-answer trans. | Trajectories (fixed / broken / corrected / corrupted) |
|---|---|---|---|---|---|---|---|---|---|---|
| debate:n=3,r=2 | 200 | 79.0 | 79.0 | 13 / 5 / 5 | 1 (1.7) | 0 (0.0) | 100.0 | 0.0 | 65 | 548 / 23 / 3 / 2 |
| debate:n=3,r=2,peers=0 | 200 | 79.0 | 78.5 | 7 / 2 / 3 | 2 (3.3) | 1 (0.1) | 100.0 | 0.0 | 88 | 539 / 21 / 2 / 2 |
| debate:n=3,r=2,style=verify | 200 | 79.0 | 81.0 | 10 / 5 / 1 | 1 (1.7) | 0 (0.0) | 100.0 | 0.0 | 95 | 531 / 23 / 1 / 2 |

## Genuine flips per round (W->R / R->W)

| Method | r0->r1 | r1->r2 |
|---|---|---|
| debate:n=3,r=2 | 1 / 0 | 0 / 0 |
| debate:n=3,r=2,peers=0 | 2 / 0 | 0 / 1 |
| debate:n=3,r=2,style=verify | 1 / 0 | 0 / 0 |

Trajectory legend (per agent): **fixed** = never changed answer; **broken** = always a genuine wrong answer (never `none`); **corrected** = genuine wrong -> right from round 0 to the end; **corrupted** = genuine right -> wrong.
