# GOLD_CASE_001 Detailed Reverse Reconstruction Method

This module reconstructs the first Gold reverse-event case from actual MarketDataCollector V3 tick data, prioritizing `CultureCapital` and keeping broker streams separate.

It resolves a research candidate pivot from empirical M1 distribution evidence, then evaluates:
- T-60s, T-180s, T-300s, T-10m, T-15m, T-20m, T-30m, T-60m, T-90m
- tick pressure / velocity / acceleration / spread
- M1 failed-low and bullish reversal candidates
- M5 positive confirmation lag
- Silver, NQ, Oil, BTC context when same-time raw data is available
- false-positive failed-low controls
- candidate-only shadow transition timing

Macro minute history (DXY, 2Y, 10Y, 30Y, real yield) remains `VERIFY_REQUIRED` unless an approved historical source is provided.

No production signal, order, EA action, scheduler change, or MT5 mutation is performed.
