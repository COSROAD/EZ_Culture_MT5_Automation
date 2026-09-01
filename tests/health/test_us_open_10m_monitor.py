import unittest
from datetime import date, datetime, timedelta

from agent.health.us_open_10m import (
    KST, IntensiveSnapshot, MacroState, MarketState,
    cadence_slot, corporate_credit_status, evaluate_alert,
    hourly_collision_context, intensive_window_kst,
    is_inside_first_3h, is_ten_minute_boundary,
    scheduler_plan, storage_design, us_cash_open_kst,
)

def markets(
    nq=("LONG","NORMAL","N/A"),
    gold=("LONG","NORMAL","ADD"),
    silver=("LONG","NORMAL","ADD"),
    oil=("LONG","NORMAL","N/A"),
    btc=("LONG","NORMAL","N/A"),
):
    return {
        "NQ": MarketState(*nq),
        "GOLD": MarketState(*gold),
        "SILVER": MarketState(*silver),
        "OIL": MarketState(*oil),
        "BTC": MarketState(*btc),
    }

def snap(check_id, when, m=None, **kw):
    return IntensiveSnapshot(
        check_id=check_id,
        check_time_kst=when.isoformat(),
        markets=m or markets(),
        macro=kw.pop("macro", MacroState()),
        web_market_freshness=kw.pop("web_market_freshness","FRESH"),
        signal_data_freshness=kw.pop("signal_data_freshness","FRESH"),
        market_data_freshness=kw.pop("market_data_freshness","FRESH"),
        delivery_status=kw.pop("delivery_status","PASS"),
        **kw
    )

class USOpen10MinuteTests(unittest.TestCase):
    def test_dst_open_window(self):
        self.assertEqual(us_cash_open_kst(date(2026,9,1)).strftime("%H:%M"), "22:30")

    def test_standard_time_open_window(self):
        self.assertEqual(us_cash_open_kst(date(2026,12,1)).strftime("%H:%M"), "23:30")

    def test_inside_first_3h_window(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        self.assertTrue(is_inside_first_3h(start + timedelta(hours=2, minutes=59)))

    def test_outside_first_3h_window(self):
        _,end = intensive_window_kst(date(2026,9,1))
        self.assertFalse(is_inside_first_3h(end))

    def test_10minute_cadence(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        self.assertEqual(cadence_slot(start + timedelta(minutes=40)), 4)
        self.assertTrue(is_ten_minute_boundary(start + timedelta(minutes=40)))

    def test_hourly_collision_context(self):
        self.assertTrue(hourly_collision_context(datetime(2026,9,1,23,0,tzinfo=KST)))

    def test_hourly_latest_overwrite_blocked(self):
        s = storage_design()
        self.assertEqual(s["hourly_authority"], "MARKET5_LATEST_REPORT")
        self.assertFalse(s["may_overwrite_hourly_latest"])
        self.assertEqual(s["authority"], "EARLY_WARNING_ONLY")

    def test_direction_change_alert(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start, markets(nq=("LONG","NORMAL","N/A")))
        cur = snap("B", start+timedelta(minutes=10), markets(nq=("SHORT","NORMAL","N/A")))
        result = evaluate_alert(prev,cur)
        self.assertTrue(result.alert_required)
        self.assertIn("NQ:DIRECTION_CHANGE", result.triggers)
        self.assertEqual(result.action,"SHORT_BIAS")

    def test_risk_escalation_alert(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), markets(nq=("LONG","HIGH_RISK","N/A")))
        self.assertIn("NQ:RISK_LEVEL_CHANGE", evaluate_alert(prev,cur).triggers)

    def test_add_to_no_add_alert(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), markets(gold=("LONG","NORMAL","NO_ADD")))
        result = evaluate_alert(prev,cur)
        self.assertIn("GOLD:ADD_PERMISSION_CHANGE", result.triggers)
        self.assertEqual(result.action,"NO_ADD")

    def test_silver_relative_weakness_alert(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), silver_relative_weakness=True)
        result = evaluate_alert(prev,cur)
        self.assertIn("SILVER:SILVER_RELATIVE_WEAKNESS", result.triggers)
        self.assertNotEqual(result.action,"LONG_BIAS")

    def test_oil_short_block_alert(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), oil_geopolitical_shock=True)
        self.assertEqual(evaluate_alert(prev,cur).action,"SHORT_BLOCK")

    def test_nq_yield_shock_alert(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), nq_yield_shock=True)
        self.assertIn("NQ:YIELD_SHOCK", evaluate_alert(prev,cur).triggers)

    def test_btc_risk_alert(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), btc_risk_shock=True)
        self.assertIn("BTC:RISK_SHOCK", evaluate_alert(prev,cur).triggers)

    def test_no_material_change_suppression(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10))
        result = evaluate_alert(prev,cur)
        self.assertFalse(result.alert_required)
        self.assertEqual(result.status,"NO_MATERIAL_CHANGE")

    def test_stale_data_warning_is_separate(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), market_data_freshness="STALE")
        result = evaluate_alert(prev,cur)
        self.assertEqual(result.data_freshness["MARKET_DATA_FRESHNESS"],"STALE")
        self.assertEqual(result.data_freshness["WEB_MARKET_FRESHNESS"],"FRESH")

    def test_no_false_current_alert_when_delivery_not_pass(self):
        start,_ = intensive_window_kst(date(2026,9,1))
        prev = snap("A", start)
        cur = snap("B", start+timedelta(minutes=10), delivery_status="STALE", nq_yield_shock=True)
        result = evaluate_alert(prev,cur)
        self.assertFalse(result.current_alert)
        self.assertFalse(result.alert_required)
        self.assertEqual(result.status,"VERIFY_REQUIRED")

    def test_corporate_credit_unavailable_verify_required(self):
        self.assertEqual(corporate_credit_status(None,None,None,None,None),"VERIFY_REQUIRED")

    def test_scheduler_rollback_and_not_live(self):
        p = scheduler_plan()
        self.assertEqual(p["architecture"],"B")
        self.assertFalse(p["live_activation"])
        self.assertEqual(p["rollback"],"DISABLE_DEDICATED_TASK_ONLY")
        self.assertTrue(p["hourly_report_preserved"])

if __name__ == "__main__":
    unittest.main()
