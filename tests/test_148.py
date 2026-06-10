import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib
import json
from datetime import date

m148 = importlib.import_module("148")
run_liquidity_stress_test = m148.run_liquidity_stress_test
write_report = m148.write_report


def test_liquidity_stress_test_and_report(tmp_path):
    assets = [
        {"name": "checking", "amount": 2500},
        {"name": "savings", "amount": 4500.50},
        {"name": "cash", "amount": 999.50},
    ]

    report = run_liquidity_stress_test(
        assets=assets,
        monthly_expenses=4000,
        monthly_income=1000,
    )

    assert report.liquid_assets == 8000.0
    assert report.monthly_burn_rate == 3000.0
    assert report.runway_days == 80.0
    assert report.auto_liquidation is False

    output_path = write_report(report, reports_dir=str(tmp_path), as_of=date(2026, 6, 10))

    with open(output_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    assert payload["liquid_assets"] == 8000.0
    assert payload["monthly_burn_rate"] == 3000.0
    assert payload["runway_days"] == 80.0
    assert payload["auto_liquidation"] is False
    assert output_path.endswith("df-148-2026-06-10.json")


def test_zero_burn_rate_means_infinite_runway():
    report = run_liquidity_stress_test(
        assets=[{"name": "reserve", "amount": 1200}],
        monthly_expenses=900,
        monthly_income=900,
    )

    assert report.monthly_burn_rate == 0.0
    assert report.runway_days == float("inf")
