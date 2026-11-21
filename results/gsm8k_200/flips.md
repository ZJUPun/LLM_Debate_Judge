# Debate flips

**Flip** = one agent changes its answer between two consecutive rounds. **W->R** = a wrong answer was corrected (debate fixes); **R->W** = a right answer was abandoned for a wrong one (debate spreads). **W->W / R->R** = sideways moves (answer changed, correctness unchanged). **switch-to-peer** = the new answer was one a peer held in the previous round. Rates are over the answers eligible to change (W->R rate = W->R / wrong answers; R->W rate = R->W / right answers).

## Per method

| Method | n | Round-0 acc | Final acc | Agg. flips (n / W->R / R->W) | Agent W->R (rate) | Agent R->W (rate) | W->R switch | R->W switch | Trajectories (fixed / broken / corrected / corrupted) |
|---|---|---|---|---|---|---|---|---|---|
| debate:n=3,r=2 | 200 | 97.0 | 96.0 | 3 / 0 / 2 | 6 (13.3) | 13 (1.1) | 100.0 | 53.8 | 583 / 18 / 0 / 7 |
| debate:n=3,r=2,peers=0 | 200 | 97.0 | 95.5 | 3 / 0 / 3 | 14 (23.3) | 26 (2.3) | 85.7 | 26.9 | 570 / 19 / 0 / 12 |
| debate:n=3,r=2,style=verify | 200 | 97.0 | 96.0 | 3 / 0 / 2 | 6 (12.2) | 23 (2.0) | 66.7 | 34.8 | 568 / 18 / 2 / 19 |

## Per round (W->R / R->W)

| Method | r0->r1 | r1->r2 |
|---|---|---|
| debate:n=3,r=2 | 2 / 7 | 4 / 6 |
| debate:n=3,r=2,peers=0 | 1 / 21 | 13 / 5 |
| debate:n=3,r=2,style=verify | 1 / 10 | 5 / 13 |

Trajectory legend: **fixed** = never changed answer; **broken** = wrong in every round; **corrected** = wrong at round 0, right at the end; **corrupted** = right at round 0, wrong at the end.
