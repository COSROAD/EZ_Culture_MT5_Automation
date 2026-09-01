import unittest

from agent.health.report_delivery import (
    DeliveryStatus,
    FreshnessStatus,
    content_sha256,
    control_current_report,
    evaluate_delivery,
    evaluate_freshness,
    generate_report_id,
)


def report(report_id, body="BODY"):
    return f"REPORT_ID: {report_id}\n{body}\n"


class ReportDeliveryHealthTests(unittest.TestCase):
    def setUp(self):
        self.scheduled = "2026-09-01T12:00:00+09:00"
        self.generated = "2026-09-01T12:02:00+09:00"
        self.verified = "2026-09-01T12:03:00+09:00"
        self.rid = generate_report_id(self.scheduled, "ABC123")
        self.content = report(self.rid)

    def good(self, **overrides):
        args = dict(
            report_id=self.rid,
            scheduled_run_time_kst=self.scheduled,
            generated_time_kst=self.generated,
            drive_saved_time_kst="2026-09-01T12:02:30+09:00",
            history_saved=True,
            history_reopened_content=self.content,
            latest_updated=True,
            latest_reopened_content=self.content,
            expected_content=self.content,
            latest_completed_run_report_id=self.rid,
            control_readable=True,
            report_cycle_matches=True,
            signal_freshness="FRESH",
            market_freshness="FRESH",
            web_market_freshness="FRESH",
            verified_at_kst=self.verified,
            last_valid_report_time="2026-09-01T11:02:00+09:00",
            last_valid_report_id="MARKET5_20260901_1100_KST_OLD001",
        )
        args.update(overrides)
        return evaluate_delivery(**args)

    def test_a_current_report_saved_and_verified_pass(self):
        self.assertEqual(self.good().delivery_status, DeliveryStatus.PASS.value)

    def test_b_latest_previous_hour_is_fail_not_current(self):
        old_id = "MARKET5_20260901_1100_KST_OLD001"
        old_content = report(old_id)
        state = self.good(latest_reopened_content=old_content)
        self.assertNotEqual(state.delivery_status, DeliveryStatus.PASS.value)
        self.assertEqual(control_current_report(state, self.content, old_content)["classification"], "UNAVAILABLE")

    def test_c_history_saved_latest_update_fails(self):
        state = self.good(latest_updated=False)
        self.assertEqual(state.delivery_status, DeliveryStatus.FAIL.value)
        self.assertEqual(state.failure_stage, "LATEST_UPDATE")

    def test_d_latest_reopen_report_id_mismatch_fails(self):
        other = report("MARKET5_20260901_1200_KST_OTHER1")
        state = self.good(latest_reopened_content=other)
        self.assertEqual(state.delivery_status, DeliveryStatus.FAIL.value)

    def test_e_signal_fresh_market_stale_are_separate(self):
        state = self.good(signal_freshness="FRESH", market_freshness="STALE")
        self.assertEqual(state.signal_freshness, "FRESH")
        self.assertEqual(state.market_freshness, "STALE")

    def test_f_no_new_signal_can_be_non_failure(self):
        x = evaluate_freshness(
            check_time=self.verified,
            last_update_time=None,
            expected_max_age=3600,
            market_open_status="OPEN",
            no_new_signal_is_failure=False,
        )
        self.assertEqual(x.freshness_status, FreshnessStatus.FRESH.value)

    def test_g_drive_exists_but_previous_content_is_not_current(self):
        old_id = "MARKET5_20260901_1100_KST_OLD001"
        state = self.good(latest_reopened_content=report(old_id))
        result = control_current_report(state, self.content, report(old_id))
        self.assertIsNone(result["current_report"])
        self.assertEqual(result["last_valid"]["classification"], "REFERENCE_ONLY")

    def test_h_current_timestamp_report_id_mismatch_fails(self):
        other = report("MARKET5_20260901_1200_KST_WRONG1", "CURRENT TIME BODY")
        state = self.good(latest_reopened_content=other)
        self.assertEqual(state.delivery_status, DeliveryStatus.FAIL.value)
        self.assertFalse(state.report_id_match)

    def test_i_previous_valid_retained_reference_only(self):
        state = self.good(latest_updated=False)
        result = control_current_report(state, None, "OLD")
        self.assertEqual(result["last_valid"]["classification"], "REFERENCE_ONLY")

    def test_j_no_false_current_classification_path(self):
        variants = [
            dict(history_saved=False),
            dict(history_reopened_content=None),
            dict(latest_updated=False),
            dict(latest_reopened_content=None),
            dict(control_readable=False),
            dict(report_cycle_matches=False),
        ]
        for override in variants:
            state = self.good(**override)
            result = control_current_report(state, self.content, "OLD")
            self.assertNotEqual(state.delivery_status, DeliveryStatus.PASS.value)
            self.assertNotEqual(result["classification"], "CURRENT")

    def test_report_cycle_stale(self):
        state = self.good(report_cycle_matches=False)
        self.assertEqual(state.delivery_status, DeliveryStatus.STALE.value)
        self.assertEqual(state.failure_stage, "REPORT_FRESHNESS")

    def test_content_hash_mismatch_fails(self):
        changed = report(self.rid, "CHANGED")
        state = self.good(latest_reopened_content=changed)
        self.assertEqual(state.delivery_status, DeliveryStatus.FAIL.value)
        self.assertFalse(state.content_hash_match)

    def test_report_id_format(self):
        self.assertEqual(self.rid, "MARKET5_20260901_1200_KST_ABC123")

    def test_market_stale_by_age(self):
        x = evaluate_freshness(
            check_time="2026-09-01T12:10:00+09:00",
            last_update_time="2026-09-01T12:00:00+09:00",
            expected_max_age=300,
            market_open_status="OPEN",
        )
        self.assertEqual(x.freshness_status, FreshnessStatus.STALE.value)

    def test_market_closed_is_distinct(self):
        x = evaluate_freshness(
            check_time=self.verified,
            last_update_time=None,
            expected_max_age=300,
            market_open_status="MARKET_CLOSED",
        )
        self.assertEqual(x.freshness_status, FreshnessStatus.MARKET_CLOSED.value)

    def test_hash_is_stable(self):
        self.assertEqual(content_sha256(self.content), content_sha256(self.content))


if __name__ == "__main__":
    unittest.main()
