# Approved Runtime Baseline

`APPROVED_RUNTIME_BASELINE` is the sole recovery reference for MT5 runtime state.

Rules:

- Baseline changes require explicit USER approval.
- The Health Agent may read, hash, compare, and report the baseline.
- It may not rewrite or auto-correct the baseline.
- Unknown values remain `UNKNOWN` or `VERIFY_REQUIRED`.
- Runtime mismatch produces a recovery candidate, not recovery authorization.
- Source deduplication in GitHub never merges EZ Square and Culture Capital runtime environments.

The Culture M30 baseline included in `config/templates/approved_runtime_baseline.example.json`
contains only currently approved chart/indicator counts. Unmeasured MA, Ichimoku, visual, order,
server, and MACD runtime inputs remain `VERIFY_REQUIRED`. The project-approved MACD setting
12/26/9 is not declared runtime-confirmed until a future read-only MT5 adapter measures it.
