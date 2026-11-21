# Debate flips

**Flip** = one agent changes its answer between two consecutive rounds. **W->R** = a wrong answer was corrected (debate fixes); **R->W** = a right answer was abandoned for a wrong one (debate spreads). **W->W / R->R** = sideways moves (answer changed, correctness unchanged). **switch-to-peer** = the new answer was one a peer held in the previous round. Rates are over the answers eligible to change (W->R rate = W->R / wrong answers; R->W rate = R->W / right answers).

## Per method

| Method | n | Round-0 acc | Final acc | Agg. flips (n / W->R / R->W) | Agent W->R (rate) | Agent R->W (rate) | W->R switch | R->W switch | Trajectories (fixed / broken / corrected / corrupted) |
|---|---|---|---|---|---|---|---|---|---|
| debate:n=3,r=2 | 200 | 79.0 | 79.0 | 13 / 5 / 5 | 28 (9.8) | 20 (2.2) | 64.3 | 65.0 | 548 / 123 / 21 / 13 |
| debate:n=3,r=2,peers=0 | 200 | 79.0 | 78.5 | 7 / 2 / 3 | 28 (9.0) | 42 (4.7) | 89.3 | 40.5 | 539 / 137 / 6 / 20 |
| debate:n=3,r=2,style=verify | 200 | 79.0 | 81.0 | 10 / 5 / 1 | 39 (13.6) | 33 (3.6) | 79.5 | 48.5 | 531 / 118 / 20 / 14 |

## Per round (W->R / R->W)

| Method | r0->r1 | r1->r2 |
|---|---|---|
| debate:n=3,r=2 | 17 / 12 | 11 / 8 |
| debate:n=3,r=2,peers=0 | 9 / 27 | 19 / 15 |
| debate:n=3,r=2,style=verify | 21 / 16 | 18 / 17 |

Trajectory legend: **fixed** = never changed answer; **broken** = wrong in every round; **corrected** = wrong at round 0, right at the end; **corrupted** = right at round 0, wrong at the end.
