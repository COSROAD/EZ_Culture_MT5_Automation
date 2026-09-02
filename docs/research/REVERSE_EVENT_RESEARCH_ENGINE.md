# Reverse Event Research Engine — Phase 1

Task: `TASK-REVERSE-EVENT-RESEARCH-001`

## Research model
Supports both forward research and reverse-event research. A pattern can become an `EARLY_WARNING_CANDIDATE` only after repeated evidence; candidate thresholds are never silently promoted to approved trading thresholds.

## Layers
- L0 Tick anomaly / microstructure
- L1 M1 timing
- L2 M5 setup confirmation
- L3 cross-market / macro regime
- L4 risk / ADD permission
- final output is shadow-only; no live-order path.

## Time and identity
UTC is canonical research time. KST is display time. Broker/server/source identity travels with derived records. Raw broker streams are not silently merged.

## Freshness
Every stream retains one of `FRESH`, `STALE`, `MARKET_CLOSED`, `VERIFY_REQUIRED`, `NOT_AVAILABLE`. Missing macro/web series are never fabricated.

## Threshold governance
Examples, quantiles and test thresholds are research candidates only. Production/trading thresholds require CONTROL review + user approval.

## Raw integrity
Phase 1 reads source data only. Raw CSV, Signal XLSX, Market XLSX and GeneratedTime data are not rewritten. Derived inventory/event/shadow artifacts must use separate research storage.

## First Gold case
`GOLD_CASE_001` is created only if available raw data yields a qualifying reverse-event research candidate. Minute-level macro history not available from the source inventory is marked `VERIFY_REQUIRED`, not reconstructed from guesswork.
