| Run | Criteria | Screenshot losses | DOM losses | Screenshot misses | DOM misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| run_1 | 619 | 51 | 16 | 56 | 69 |
| run_2 | 619 | 62 | 15 | 50 | 57 |
| run_3 | 619 | 70 | 8 | 58 | 64 |
| Mean | 619 | 61.00 (9.85%) | 13.00 (2.10%) | 54.67 | 63.33 |

| Measure | Estimate | 95% interval |
| --- | ---: | ---: |
| Screenshot loss rate | 9.85% | 6.59% to 13.48% |
| DOM loss rate | 2.10% | 0.88% to 3.62% |
| Screenshot minus DOM rate | 7.75 pp | 4.07 to 11.71 pp |
| Relative reduction | 78.69% | 57.25% to 91.62% |

The matched comparison uses 97 of 100 catalog tasks in every run.
Intervals resample tasks, then recorded runs within each task, keeping both representations together.

Recordings without captured states remain recorded execution errors, not zero-loss audits.
Tasks outside the common panel: task_80, task_83, task_94.

| Run | Available audited tasks | Available criteria | Screenshot losses | DOM losses |
| --- | ---: | ---: | ---: | ---: |
| run_1 | 100 | 640 | 51 | 16 |
| run_2 | 99 | 633 | 62 | 15 |
| run_3 | 97 | 619 | 70 | 8 |
