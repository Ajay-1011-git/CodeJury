# Remaining work

| Work | Evidence / next gate |
|---|---|
| G.01 preserve existing roles and menu | Native baseline inventory and fresh Judge pilot reload verified; controller/menu tests passed |
| G.02 bounded offline provider | SDK, strict schema, secret guard, persisted cap/cache/backoff implemented; live preflight and completion succeeded; tests passed |
| G.03 verified teacher corpus | Completed: 40 proposals, 22 distinct accepted targets over 20 TRAIN bases; no final data opened |
| G.04 candidate quality | Completed native 20-update pilot / 100-update full job; selected step 50, 6/20 solves vs 5/20 current, zero wrong accepts |
| G.05 dependencies | B mining and paired evidence checked; Critic current-distribution gate passed; 536 actual Judge continuations across 96 states completed and scored; new Judge labels/training next |
| G.06 continuation | General selection/parity, merged live API/UI/cancel/restart/download acceptance, clean freeze, final benchmark, portable adapter release |

A2/S2 training interfaces are implemented and actual native A/B/Critic/Judge jobs exist. General's full job has finished, but a completed training process is not quality selection or a completed project. The final benchmark and release are pending. Limited synthetic data and uncertainty remain explicit. No teacher-enhanced adapter is promoted until executable validation improves without increased incorrect acceptance.

The coordinator stopped at a completed phase boundary for transfer to Sarvesh. No
native optimizer job is interrupted. Follow [continuation-handoff.md](continuation-handoff.md)
after pulling main and restoring the separately supplied private snapshot.
