# CI Performance Ratchet

MusicForge release-check budgets are hard gates. CI receives a bounded runner
allowance above local budgets, but an allowance is not permission for unlimited
growth.

v14.1 applies the first post-v14.0.1 ratchet:

| Profile | v14.0.1 CI budget | v14.1 CI budget |
|---|---:|---:|
| security | 1500 s | 1350 s |
| latest | 900 s | 810 s |
| ga | 1200 s | 1080 s |

The limits remain blocking. They may not increase without a tracked performance
report containing at least 20 successful final-SHA samples, the p50 and p95 for
each affected profile, and an expiry for the exception. v14.2 must review the
budgets from that sample set and ratchet them again when p95 permits it.
