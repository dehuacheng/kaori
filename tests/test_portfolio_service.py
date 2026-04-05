"""Tests for portfolio_service: _extract_json and _compute_account_value."""

import pytest

from kaori.services.portfolio_service import _extract_json, _compute_account_value


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_clean_json(self):
        result = _extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fence(self):
        text = '```json\n{"ticker": "AAPL", "shares": 10}\n```'
        result = _extract_json(text)
        assert result == {"ticker": "AAPL", "shares": 10}

    def test_plain_fence(self):
        text = '```\n{"ticker": "GOOG"}\n```'
        result = _extract_json(text)
        assert result == {"ticker": "GOOG"}

    def test_json_in_prose(self):
        text = 'Here is the extracted data:\n{"positions": [{"ticker": "MSFT"}]}\nDone.'
        result = _extract_json(text)
        assert result["positions"][0]["ticker"] == "MSFT"

    def test_garbage_raises(self):
        with pytest.raises(ValueError, match="Could not extract JSON"):
            _extract_json("no json here at all, just words")

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = _extract_json(text)
        assert result["outer"]["inner"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# _compute_account_value
# ---------------------------------------------------------------------------

class TestComputeAccountValue:
    def test_single_stock(self):
        holdings = [{"ticker": "AAPL", "shares": 10, "cost_basis": 150}]
        prices = {"AAPL": {"price": 200, "previous_close": 195}}
        result = _compute_account_value(holdings, prices)
        assert result["total_value"] == 2000.0
        assert result["day_change"] == 50.0  # 10 * (200 - 195)
        assert result["total_cost"] == 1500.0  # 10 * 150

    def test_cash_holding(self):
        holdings = [{"ticker": "CASH", "shares": 1, "cost_basis": 5000}]
        result = _compute_account_value(holdings, {})
        assert result["total_value"] == 5000.0
        assert result["day_change"] == 0.0

    def test_money_market_treated_as_cash(self):
        holdings = [{"ticker": "MONEY_MARKET", "shares": 1, "cost_basis": 10000}]
        result = _compute_account_value(holdings, {})
        assert result["total_value"] == 10000.0
        assert result["day_change"] == 0.0

    def test_missing_price_skipped(self):
        holdings = [
            {"ticker": "AAPL", "shares": 10, "cost_basis": 150},
            {"ticker": "UNKNOWN", "shares": 5, "cost_basis": 100},
        ]
        prices = {"AAPL": {"price": 200, "previous_close": 195}}
        result = _compute_account_value(holdings, prices)
        # Only AAPL counted
        assert result["total_value"] == 2000.0
        assert len(result["holdings"]) == 1

    def test_multiple_holdings_aggregation(self):
        holdings = [
            {"ticker": "AAPL", "shares": 10, "cost_basis": 150},
            {"ticker": "GOOG", "shares": 5, "cost_basis": 100},
        ]
        prices = {
            "AAPL": {"price": 200, "previous_close": 195},
            "GOOG": {"price": 150, "previous_close": 148},
        }
        result = _compute_account_value(holdings, prices)
        assert result["total_value"] == 2000 + 750  # 10*200 + 5*150
        assert result["total_cost"] == 1500 + 500  # 10*150 + 5*100
        assert result["day_change"] == 50 + 10  # 10*(200-195) + 5*(150-148)

    def test_total_gain(self):
        holdings = [{"ticker": "AAPL", "shares": 10, "cost_basis": 150}]
        prices = {"AAPL": {"price": 200, "previous_close": 195}}
        result = _compute_account_value(holdings, prices)
        assert result["total_gain"] == 500.0  # 2000 - 1500

    def test_day_change_pct(self):
        holdings = [{"ticker": "AAPL", "shares": 10, "cost_basis": 150}]
        prices = {"AAPL": {"price": 200, "previous_close": 195}}
        result = _compute_account_value(holdings, prices)
        # day_change=50, prev_total = 2000 - 50 = 1950, pct = 50/1950*100
        expected_pct = round(50 / 1950 * 100, 2)
        assert result["day_change_pct"] == expected_pct

    def test_no_cost_basis(self):
        holdings = [{"ticker": "AAPL", "shares": 10}]
        prices = {"AAPL": {"price": 200, "previous_close": 195}}
        result = _compute_account_value(holdings, prices)
        assert result["total_gain"] is None
