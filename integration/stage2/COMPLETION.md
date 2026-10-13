# Integrated Stage 2 completion work

The user authorized taking over both owners' remaining tasks and completing the merged project. Both existing remote owner branches are already ancestors of main. This work preserves the existing Stage 1 release and frozen Stage 2 wire schemas.

| Work | State |
|---|---|
| A/B training and real sandbox tools | Existing verified work retained |
| Real episode pipeline | 80 real train and 20 validation runs collected; reviewed bootstrap labeled |
| S2.07 Critic data/filtering | 320 train / 80 validation examples filtered; feedback-revision coverage missing |
| S2.08 Critic native pilot/train/reload/validation | 20-step pilot and 100-step full training/reload passed; checkpoint validation running |
| A2.08 actual alternative continuations and private Judge labels | Pending Critic freeze |
| A2.09 Judge native training and guarded learned actions | Guards implemented/tested; training pending actual rollouts |
| S2.10 general comparator and opportunity audit | Pending frozen role datasets |
| A2.10 live API and baseline adapters | Live API implemented; CPU semantics passed; research baseline facade pending |
| S2.11 existing UI integration and browser acceptance | Existing UI preserved; live acceptance pending |
| S2.12 final three-seed benchmark and ablations | Pending all release/model/config freezes |
| A2.11/A2.12 system acceptance and release | Pending complete learned release |

Native jobs share the existing per-user compute lease and execute sequentially on this Mac. Live candidate code is executed only in Docker. Reviewed programmatic experiment proposals are labeled reviewed bootstrap, never a trained Critic or fabricated model response. Final assessment remains sealed until every method and adapter freezes. Small genuinely collected datasets will be reported with their actual base counts; variants/repeated states are not independent problems.
