# Protection Rules

CHECKPOINT 12A: CLOSED / PROTECTED.

Protected systems and semantics:

- Legacy V2.2 MQ5.
- Legacy 15-column Signal CSV.
- Legacy TIME semantics = BAR OPEN TIME.
- GeneratedTime parallel structure.
- SIGNAL_GENERATED_TIME_UTC semantics.
- Signal V4 merge.
- Existing EX5.
- Signal logic: MACD, MA30/MA60, Ichimoku, ATR, SCORE, WATCH, CONFIRMED, STRONG, Arrow, Strong Star.
- MarketDataCollector.
- Market Raw schema.
- 5-minute aggregation.
- Google Drive linkage.
- EZ Square / Culture Capital broker separation.
- Existing Scheduler.
- EA order logic.
- Position logic.
- Lot / Risk logic.

Any change requires an explicit CONTROL-approved TASK.

## GeneratedTime current status

DEPLOYMENT: COMPLETE

RUNTIME NATURAL SIGNAL VALIDATION: PENDING

OBSERVATION: READ-ONLY ACTIVE

Existing chart principle:

- Use existing operating charts.
- Switching timeframe on the same chart keeps the indicator.
- Do not attach duplicate GeneratedTime instances per timeframe.
- New chart creation requires explicit approval.
- Validate using natural signals only.
- Forced signals prohibited.
- Historical rewrite prohibited.