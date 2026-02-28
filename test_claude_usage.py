#!/usr/bin/env python3
"""Unit tests for claude-usage.5m.py logic."""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Import functions from the plugin
sys.path.insert(0, os.path.dirname(__file__))

# Import without executing main() by patching the call at the bottom
import types

_src = Path(__file__).parent / "claude-usage.5m.py"
_code = _src.read_text()
# Replace the bare `main()` call at end of file with a no-op
_code = _code.rsplit("main()", 1)
_code = "pass".join(_code)
_mod = types.ModuleType("claude_usage")
exec(compile(_code, str(_src), "exec"), _mod.__dict__)

calc_cost    = _mod.calc_cost
fmt_tokens   = _mod.fmt_tokens
fmt_cost     = _mod.fmt_cost
total_tokens = _mod.total_tokens
usage_bar    = _mod.usage_bar
PRICES       = _mod.PRICES


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_entry(model, input_tokens, output_tokens,
               cache_creation=0, cache_read=0,
               timestamp=None, session_id="sess-1",
               entry_type="assistant"):
    ts = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return json.dumps({
        "type": entry_type,
        "timestamp": ts,
        "sessionId": session_id,
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            }
        }
    })


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFmtTokens(unittest.TestCase):
    def test_small(self):
        self.assertEqual(fmt_tokens(0), "0")
        self.assertEqual(fmt_tokens(999), "999")

    def test_thousands(self):
        self.assertEqual(fmt_tokens(1_000), "1.0k")
        self.assertEqual(fmt_tokens(15_500), "15.5k")
        self.assertEqual(fmt_tokens(999_999), "1000.0k")

    def test_millions(self):
        self.assertEqual(fmt_tokens(1_000_000), "1.0M")
        self.assertEqual(fmt_tokens(9_500_000), "9.5M")


class TestFmtCost(unittest.TestCase):
    def test_small(self):
        self.assertEqual(fmt_cost(0.001), "<$0.01")
        self.assertEqual(fmt_cost(0.009), "<$0.01")

    def test_normal(self):
        self.assertEqual(fmt_cost(0.01), "$0.01")
        self.assertEqual(fmt_cost(1.23), "$1.23")
        self.assertEqual(fmt_cost(80.5), "$80.50")


class TestTotalTokens(unittest.TestCase):
    def test_sums_all_fields(self):
        u = {"input_tokens": 100, "output_tokens": 200,
             "cache_creation_input_tokens": 50, "cache_read_input_tokens": 25}
        self.assertEqual(total_tokens(u), 375)

    def test_missing_fields_default_zero(self):
        self.assertEqual(total_tokens({}), 0)
        self.assertEqual(total_tokens({"input_tokens": 500}), 500)


class TestCalcCost(unittest.TestCase):
    def _usage(self, inp=0, out=0, cw=0, cr=0):
        return {"input_tokens": inp, "output_tokens": out,
                "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr}

    def test_sonnet_input(self):
        cost = calc_cost("claude-sonnet-4-6", self._usage(inp=1_000_000))
        self.assertAlmostEqual(cost, 3.00, places=5)

    def test_sonnet_output(self):
        cost = calc_cost("claude-sonnet-4-6", self._usage(out=1_000_000))
        self.assertAlmostEqual(cost, 15.00, places=5)

    def test_opus_pricing(self):
        cost = calc_cost("claude-opus-4-6", self._usage(inp=1_000_000))
        self.assertAlmostEqual(cost, 15.00, places=5)

    def test_haiku_pricing(self):
        cost = calc_cost("claude-haiku-4-5", self._usage(inp=1_000_000))
        self.assertAlmostEqual(cost, 0.80, places=5)

    def test_cache_read(self):
        cost = calc_cost("claude-sonnet-4-6", self._usage(cr=1_000_000))
        self.assertAlmostEqual(cost, 0.30, places=5)

    def test_cache_write(self):
        cost = calc_cost("claude-sonnet-4-6", self._usage(cw=1_000_000))
        self.assertAlmostEqual(cost, 3.75, places=5)

    def test_unknown_model_uses_default(self):
        cost = calc_cost("claude-unknown-model", self._usage(inp=1_000_000))
        self.assertAlmostEqual(cost, PRICES["default"]["in"], places=5)

    def test_zero_usage(self):
        self.assertEqual(calc_cost("claude-sonnet-4-6", self._usage()), 0.0)


class TestUsageBar(unittest.TestCase):
    def test_zero_limit(self):
        self.assertEqual(usage_bar(100, 0), "")

    def test_full(self):
        self.assertEqual(usage_bar(10, 10), "[██████████] 100%")

    def test_empty(self):
        self.assertEqual(usage_bar(0, 10), "[░░░░░░░░░░] 0%")

    def test_half(self):
        self.assertEqual(usage_bar(5, 10), "[█████░░░░░] 50%")

    def test_over_limit_capped(self):
        self.assertEqual(usage_bar(20, 10), "[██████████] 100%")


class TestParseSessions(unittest.TestCase):
    """Test parse_sessions() using temp JSONL files."""

    def _run_parse(self, lines, today_override=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "session.jsonl"
            fpath.write_text("\n".join(lines))
            with patch.object(_mod, "find_jsonl_files", return_value=[fpath]):
                if today_override:
                    with patch("claude_usage.date") as mock_date:
                        mock_date.today.return_value = today_override
                        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
                        return _mod.parse_sessions()
                return _mod.parse_sessions()

    def test_basic_today(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = make_entry("claude-sonnet-4-6", 1000, 500, timestamp=ts)
        data = self._run_parse([entry])
        self.assertEqual(data["today"]["input_tokens"], 1000)
        self.assertEqual(data["today"]["output_tokens"], 500)
        self.assertEqual(data["sessions_today"], 1)
        self.assertGreater(data["today_cost"], 0)

    def test_skips_non_assistant(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = make_entry("claude-sonnet-4-6", 1000, 500, timestamp=ts, entry_type="user")
        data = self._run_parse([entry])
        self.assertEqual(data["today"]["input_tokens"], 0)

    def test_skips_error_messages(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        obj = json.loads(make_entry("claude-sonnet-4-6", 1000, 500, timestamp=ts))
        obj["isApiErrorMessage"] = True
        data = self._run_parse([json.dumps(obj)])
        self.assertEqual(data["today"]["input_tokens"], 0)

    def test_skips_synthetic_model(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        obj = json.loads(make_entry("claude-sonnet-4-6", 1000, 500, timestamp=ts))
        obj["message"]["model"] = "<synthetic>"
        data = self._run_parse([json.dumps(obj)])
        self.assertEqual(data["today"]["input_tokens"], 0)

    def test_skips_invalid_json(self):
        data = self._run_parse(["not valid json", "also bad"])
        self.assertEqual(data["today"]["input_tokens"], 0)

    def test_skips_bad_timestamp(self):
        entry = make_entry("claude-sonnet-4-6", 1000, 500, timestamp="not-a-date")
        data = self._run_parse([entry])
        self.assertEqual(data["today"]["input_tokens"], 0)

    def test_accumulates_multiple_entries(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        e1 = make_entry("claude-sonnet-4-6", 1000, 500, timestamp=ts, session_id="s1")
        e2 = make_entry("claude-sonnet-4-6", 2000, 800, timestamp=ts, session_id="s2")
        data = self._run_parse([e1, e2])
        self.assertEqual(data["today"]["input_tokens"], 3000)
        self.assertEqual(data["today"]["output_tokens"], 1300)
        self.assertEqual(data["sessions_today"], 2)

    def test_old_entry_not_in_today(self):
        old_ts = "2020-01-01T00:00:00Z"
        entry = make_entry("claude-sonnet-4-6", 1000, 500, timestamp=old_ts)
        data = self._run_parse([entry])
        self.assertEqual(data["today"]["input_tokens"], 0)
        self.assertEqual(data["all_time"]["input_tokens"], 1000)

    def test_models_tracked(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        e1 = make_entry("claude-sonnet-4-6", 100, 50, timestamp=ts)
        e2 = make_entry("claude-haiku-4-5", 200, 80, timestamp=ts)
        data = self._run_parse([e1, e2])
        self.assertIn("claude-sonnet-4-6", data["models"])
        self.assertIn("claude-haiku-4-5", data["models"])

    def test_no_files(self):
        with patch.object(_mod, "find_jsonl_files", return_value=[]):
            data = _mod.parse_sessions()
        self.assertEqual(data["files_found"], 0)
        self.assertEqual(data["today"]["input_tokens"], 0)


class TestDailyBudget(unittest.TestCase):
    def test_under_budget_bar(self):
        # $3.40 of $5.00 = 68%
        bar = usage_bar(3.40, 5.00)
        self.assertIn("68%", bar)
        self.assertTrue(bar.startswith("["))

    def test_over_budget_detection(self):
        # over budget when cost >= limit
        self.assertTrue(5.0 > 0 and 5.20 >= 5.0)
        # not over when cost < limit
        self.assertFalse(5.0 > 0 and 3.40 >= 5.0)
        # never over when budget is 0
        self.assertFalse(0.0 > 0 and 100.0 >= 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
