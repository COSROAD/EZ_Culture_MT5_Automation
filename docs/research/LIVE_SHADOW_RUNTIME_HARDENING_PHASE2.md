# Shadow Runtime Hardening Phase-2

Implements runner-level single-instance ownership, duplicate process denial, stale/orphaned-lock recovery, atomic current-state update, restart reference-only semantics, stable decision/event identities, duplicate ledgers, heartbeat/decision separation, and visible runtime health.

This remains task-branch-only. It does not create or modify a scheduler, does not alter MT5, and contains no live-order path.

`SHADOW_HEALTH.json` is designed to expose runtime status, process id, start/heartbeat/decision times, lock state, tick/M1/M5/signal freshness, macro status, broker status, last error and recovery state.

Previous decisions are always `REFERENCE_ONLY` until fresh recomputation after restart.
